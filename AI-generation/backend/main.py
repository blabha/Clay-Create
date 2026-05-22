import asyncio
import base64
import io
import traceback
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from PIL import Image
from pydantic import BaseModel

from pipeline.exporter import export_obj, export_png
from pipeline.midas_processor import MiDaSProcessor
from pipeline.tile_manager import TILE_SIZE, TileManager

app = FastAPI(title="Clay Relief Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── global session state (single user, in-memory) ─────────────────────
tile_manager = TileManager()
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


def crop_to_grid(image: Image.Image, cols: int, rows: int) -> Image.Image:
    """Center-crop image to cols:rows aspect ratio, then resize to exact grid pixels."""
    target_aspect = cols / rows
    w, h = image.size
    img_aspect = w / h

    if img_aspect > target_aspect:
        new_w = int(h * target_aspect)
        left = (w - new_w) // 2
        image = image.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_aspect)
        top = (h - new_h) // 2
        image = image.crop((0, top, w, top + new_h))

    return image.resize((cols * TILE_SIZE, rows * TILE_SIZE), Image.LANCZOS)


def enhance_heightmap(image: Image.Image, midas_depth: np.ndarray) -> np.ndarray:
    """
    True depth map: MiDaS provides the coarse 3D structure; image high-frequency
    detail sharpens it without overriding depth ordering.
    """
    img_rgb = np.array(image.convert("RGB"))
    img_lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
    luminance = img_lab[:, :, 0].astype(np.float32) / 255.0

    h, w = midas_depth.shape
    if luminance.shape != (h, w):
        pil = Image.fromarray((luminance * 255).astype(np.uint8))
        luminance = np.array(pil.resize((w, h), Image.LANCZOS), dtype=np.float32) / 255.0

    # Normalise MiDaS depth
    d_lo, d_hi = midas_depth.min(), midas_depth.max()
    depth_norm = (midas_depth - d_lo) / (d_hi - d_lo + 1e-6)

    # Extract only high-frequency surface detail from the image
    # (subtract a mildly blurred version to isolate fine texture)
    lum_blur = cv2.GaussianBlur(luminance, (0, 0), sigmaX=8)
    hf_detail = luminance - lum_blur          # fine bumps / ridges, mean ≈ 0

    # Add fine detail on top of real depth — 80% MiDaS, 20% surface texture
    combined = 0.80 * depth_norm + 0.20 * (hf_detail + 0.5)

    # Strong CLAHE for punchy local contrast
    clahe = cv2.createCLAHE(clipLimit=6.0, tileGridSize=(8, 8))
    enhanced = clahe.apply((np.clip(combined, 0, 1) * 255).astype(np.uint8)).astype(np.float32) / 255.0

    # Gentle blur to soften fine texture lines while preserving large-scale depth
    enhanced = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=0.3)

    # Stretch full dynamic range to [0, 1]
    lo, hi = enhanced.min(), enhanced.max()
    enhanced = (enhanced - lo) / (hi - lo + 1e-6)

    # Gamma < 1 lifts midtones; increases perceived contrast in the depth map
    return np.power(enhanced, 0.8)


# ── request models ────────────────────────────────────────────────────

class DrawRequest(BaseModel):
    image_data: str   # base64 data URL


# ── endpoints ─────────────────────────────────────────────────────────

@app.get("/api/state")
async def get_state():
    return state_response()


@app.post("/api/generate")
async def generate(
    file: UploadFile = File(...),
    cols: int = Form(...),
    rows: int = Form(...),
):
    """
    Upload an image → center-crop to wall grid → MiDaS depth + luminance blend → tiles.
    """
    data = await file.read()

    def _pipeline():
        image = Image.open(io.BytesIO(data)).convert("RGB")
        image = crop_to_grid(image, cols, rows)

        midas_depth = midas.process(image, out_h=rows * TILE_SIZE, out_w=cols * TILE_SIZE)
        heightmap = enhance_heightmap(image, midas_depth)
        tile_manager.initialize(heightmap, cols, rows)

    try:
        await asyncio.to_thread(_pipeline)
        return state_response()
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)
        raise HTTPException(status_code=500, detail=tb)


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
    if not (0 <= idx < tile_manager.n_tiles):
        raise HTTPException(status_code=400, detail=f"Index 0–{tile_manager.n_tiles - 1} only")
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


@app.post("/api/tile/{idx}/regenerate")
async def regenerate_tile(idx: int):
    _check_ready(idx)
    if idx in tile_manager.completed:
        raise HTTPException(status_code=400, detail="Tile already carved — cannot regenerate")
    await asyncio.to_thread(tile_manager.regenerate_tile, idx)
    return state_response()


@app.post("/api/regenerate-all")
async def regenerate_all():
    if not tile_manager.initialized:
        raise HTTPException(status_code=400, detail="Not initialized — generate first")
    await asyncio.to_thread(tile_manager.regenerate_all)
    return state_response()


@app.post("/api/reset")
async def reset():
    tile_manager.reset()
    return state_response()


# ── private helpers ───────────────────────────────────────────────────

def _check_ready(idx: int):
    if not tile_manager.initialized:
        raise HTTPException(status_code=400, detail="Not initialized — generate first")
    if not (0 <= idx < tile_manager.n_tiles):
        raise HTTPException(status_code=400, detail=f"Tile index must be 0–{tile_manager.n_tiles - 1}")


def _get_tile(idx: int) -> np.ndarray:
    _check_ready(idx)
    tile = tile_manager.intended[idx]
    if tile is None:
        raise HTTPException(status_code=404, detail="Tile not found")
    return tile