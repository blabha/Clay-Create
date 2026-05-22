import asyncio
import base64
import io
import traceback
from typing import Optional

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image
from pydantic import BaseModel

from pipeline.exporter import export_obj, export_png
from pipeline.midas_processor import MiDaSProcessor
from pipeline.sd_generator import SDGenerator
from pipeline.tile_manager import TileManager

app = FastAPI(title="Clay Relief Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── global session state (single user, in-memory) ─────────────────────
tile_manager = TileManager()
sd_gen = SDGenerator()
midas = MiDaSProcessor()


# ── helpers ───────────────────────────────────────────────────────────

def arr_to_b64(arr: Optional[np.ndarray], rgb: bool = False) -> Optional[str]:
    if arr is None:
        return None
    if rgb:
        img = Image.fromarray(arr.astype(np.uint8), mode="RGB")
    else:
        img = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def state_response():
    return tile_manager.to_state_dict(arr_to_b64)


def enhance_heightmap(image: Image.Image, midas_depth: np.ndarray,
                      texture_weight: float = 0.72) -> np.ndarray:
    """
    Blend SD image luminance with MiDaS depth, smooth for clay-like shallow relief.
    Gentle CLAHE preserves pattern without creating jagged spikes.
    """
    img_rgb = np.array(image.convert("RGB"))
    img_lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
    luminance = img_lab[:, :, 0].astype(np.float32) / 255.0

    h, w = midas_depth.shape
    if luminance.shape != (h, w):
        pil = Image.fromarray((luminance * 255).astype(np.uint8))
        luminance = np.array(pil.resize((w, h), Image.LANCZOS), dtype=np.float32) / 255.0

    # Gentle CLAHE — enough to reveal pattern, not so much that it spikes
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lum_clahe = clahe.apply((luminance * 255).astype(np.uint8)).astype(np.float32) / 255.0

    # Blend texture detail with coarse MiDaS depth
    blended = texture_weight * lum_clahe + (1.0 - texture_weight) * midas_depth

    # Gaussian smooth → gradual clay-like transitions, no jagged edges
    smoothed = gaussian_filter(blended, sigma=1.8)

    # Single gentle CLAHE pass to recover contrast lost in smoothing
    enhanced = clahe.apply((smoothed * 255).astype(np.uint8)).astype(np.float32) / 255.0

    lo, hi = enhanced.min(), enhanced.max()
    return (enhanced - lo) / (hi - lo + 1e-6)


# ── request models ────────────────────────────────────────────────────

class PromptRequest(BaseModel):
    prompt: str
    steps: int = 25


class DrawRequest(BaseModel):
    image_data: str   # base64 data URL


# ── endpoints ─────────────────────────────────────────────────────────

@app.get("/api/state")
async def get_state():
    return state_response()


@app.post("/api/generate")
async def generate(req: PromptRequest):
    """
    Run the full SD→MiDaS→tile pipeline.
    Heavy blocking work is offloaded to a thread so the event loop stays free.
    """
    def _pipeline():
        image = sd_gen.generate(req.prompt, steps=req.steps)
        midas_depth = midas.process(image)
        heightmap = enhance_heightmap(image, midas_depth)
        tile_manager.initialize(heightmap)

    try:
        await asyncio.to_thread(_pipeline)
        return state_response()
    except FileNotFoundError as e:
        traceback.print_exc()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)                                    # full trace in backend terminal
        raise HTTPException(status_code=500, detail=tb)   # full trace to frontend


@app.post("/api/tile/{idx}/upload-scan")
async def upload_scan(idx: int, file: UploadFile = File(...)):
    _check_ready(idx)
    data = await file.read()
    img = Image.open(io.BytesIO(data)).convert("L")
    scanned = np.array(img, dtype=np.float32) / 255.0
    await asyncio.to_thread(tile_manager.process_tile, idx, scanned)
    return state_response()


@app.post("/api/tile/{idx}/draw")
async def draw_scan(idx: int, req: DrawRequest):
    _check_ready(idx)
    raw = req.image_data
    if "," in raw:
        raw = raw.split(",", 1)[1]
    img_data = base64.b64decode(raw)
    img = Image.open(io.BytesIO(img_data)).convert("L")
    scanned = np.array(img, dtype=np.float32) / 255.0
    await asyncio.to_thread(tile_manager.process_tile, idx, scanned)
    return state_response()


@app.get("/api/tile/{idx}/surface3d")
async def surface3d(idx: int, res: int = 64):
    if not tile_manager.initialized:
        raise HTTPException(status_code=400, detail="Not initialized")
    if not (0 <= idx <= 8):
        raise HTTPException(status_code=400, detail="Index 0-8 only")
    return tile_manager.get_surface3d(idx, res)


@app.get("/api/export/png/{idx}")
async def export_tile_png(idx: int):
    tile = _get_tile(idx)
    buf = export_png(tile)
    return StreamingResponse(
        buf, media_type="image/png",
        headers={"Content-Disposition": f"attachment; filename=tile_{idx:02d}.png"},
    )


@app.get("/api/export/obj/{idx}")
async def export_tile_obj(idx: int):
    tile = _get_tile(idx)
    buf = export_obj(tile)
    return StreamingResponse(
        buf, media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=tile_{idx:02d}.obj"},
    )


@app.post("/api/reset")
async def reset():
    tile_manager.reset()
    return state_response()


# ── private helpers ───────────────────────────────────────────────────

def _check_ready(idx: int):
    if not tile_manager.initialized:
        raise HTTPException(status_code=400, detail="Not initialized — generate first")
    if not (0 <= idx <= 8):
        raise HTTPException(status_code=400, detail="Tile index must be 0–8")


def _get_tile(idx: int) -> np.ndarray:
    _check_ready(idx)
    tile = tile_manager.intended[idx]
    if tile is None:
        raise HTTPException(status_code=404, detail="Tile not found")
    return tile
