import numpy as np
from PIL import Image
from typing import Optional, Callable
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TILE_SIZE = 256
MASTER_SIZE = 768   # 3 × TILE_SIZE
BLEND_SIZE = 80


def _tile_pos(idx: int):
    return idx // 3, idx % 3


class TileManager:
    def __init__(self):
        self.initialized = False
        self.master: Optional[np.ndarray] = None          # (768,768) float32
        self.intended: list[Optional[np.ndarray]] = [None] * 9
        self.scanned: list[Optional[np.ndarray]] = [None] * 9
        self.deviations: list[Optional[np.ndarray]] = [None] * 9
        self.deviation_colors: list[Optional[np.ndarray]] = [None] * 9
        self.completed: set[int] = set()
        self.current_tile: int = 0

    # ------------------------------------------------------------------
    # Initialise

    def initialize(self, heightmap: np.ndarray):
        img = Image.fromarray((heightmap * 255).astype(np.uint8))
        img = img.resize((MASTER_SIZE, MASTER_SIZE), Image.LANCZOS)
        self.master = np.array(img, dtype=np.float32) / 255.0
        self.intended = [self._extract_tile(i) for i in range(9)]
        self.scanned = [None] * 9
        self.deviations = [None] * 9
        self.deviation_colors = [None] * 9
        self.completed = set()
        self.current_tile = 0
        self.initialized = True

    def reset(self):
        self.__init__()

    # ------------------------------------------------------------------
    # Per-tile processing

    def process_tile(self, idx: int, scanned: np.ndarray):
        """Accept a scanned heightmap for tile idx, compute deviation, propagate."""
        intended = self.intended[idx]

        # Resize to TILE_SIZE if needed
        if scanned.shape != (TILE_SIZE, TILE_SIZE):
            pil = Image.fromarray((np.clip(scanned, 0, 1) * 255).astype(np.uint8))
            pil = pil.resize((TILE_SIZE, TILE_SIZE), Image.LANCZOS)
            scanned = np.array(pil, dtype=np.float32) / 255.0

        self.scanned[idx] = scanned.copy()
        deviation = scanned - intended            # roughly [-1, 1]
        self.deviations[idx] = deviation
        self.deviation_colors[idx] = self._colorize(deviation)

        self.completed.add(idx)
        self._propagate(idx, deviation)
        self._rebuild_master()

        # Advance current_tile
        for i in range(9):
            if i not in self.completed:
                self.current_tile = i
                break
        else:
            self.current_tile = -1

    # ------------------------------------------------------------------
    # 3D surface data (downsampled)

    def get_surface3d(self, idx: int, res: int = 64) -> dict:
        tile = self.intended[idx]
        if tile is None:
            return {"z": [], "x": [], "y": []}
        pil = Image.fromarray((tile * 255).astype(np.uint8))
        pil = pil.resize((res, res), Image.LANCZOS)
        z = np.array(pil, dtype=np.float32) / 255.0
        return {"z": z.tolist(), "x": list(range(res)), "y": list(range(res))}

    # ------------------------------------------------------------------
    # Serialisation helper

    def to_state_dict(self, arr_to_b64: Callable) -> dict:
        tiles = []
        for i in range(9):
            tiles.append({
                "idx": i,
                "intended": arr_to_b64(self.intended[i]),
                "scanned": arr_to_b64(self.scanned[i]),
                "deviation": arr_to_b64(self.deviations[i]),
                "deviation_color": arr_to_b64(self.deviation_colors[i], rgb=True),
            })
        return {
            "initialized": self.initialized,
            "current_tile": self.current_tile,
            "completed": list(self.completed),
            "master": arr_to_b64(self.master) if self.initialized else None,
            "tiles": tiles if self.initialized else [],
        }

    # ------------------------------------------------------------------
    # Internals

    def _extract_tile(self, idx: int) -> np.ndarray:
        r, c = _tile_pos(idx)
        r0, c0 = r * TILE_SIZE, c * TILE_SIZE
        return self.master[r0:r0 + TILE_SIZE, c0:c0 + TILE_SIZE].copy()

    def _rebuild_master(self):
        for i in range(9):
            r, c = _tile_pos(i)
            r0, c0 = r * TILE_SIZE, c * TILE_SIZE
            self.master[r0:r0 + TILE_SIZE, c0:c0 + TILE_SIZE] = np.clip(self.intended[i], 0, 1)

    def _colorize(self, deviation: np.ndarray) -> np.ndarray:
        """Diverging RdBu colormap → uint8 RGB."""
        max_abs = max(float(np.abs(deviation).max()), 1e-6)
        norm = deviation / max_abs           # [-1, 1]
        cmap = plt.get_cmap("RdBu_r")
        rgba = cmap((norm + 1) / 2)         # map [-1,1] → [0,1]
        return (rgba[:, :, :3] * 255).astype(np.uint8)

    def _propagate(self, idx: int, dev: np.ndarray):
        """Propagate edge deviation into all 8 uncarved neighbours."""
        row, col = _tile_pos(idx)
        fade = np.linspace(1.0, 0.0, BLEND_SIZE, dtype=np.float32)

        neighbour_ops = [
            # (dr, dc, correction_builder)
            (-1,  0, lambda: self._corr_top(dev, fade)),
            ( 1,  0, lambda: self._corr_bottom(dev, fade)),
            ( 0, -1, lambda: self._corr_left(dev, fade)),
            ( 0,  1, lambda: self._corr_right(dev, fade)),
            (-1, -1, lambda: self._corr_corner(dev[ 0,  0], fade, 'tl')),
            (-1,  1, lambda: self._corr_corner(dev[ 0, -1], fade, 'tr')),
            ( 1, -1, lambda: self._corr_corner(dev[-1,  0], fade, 'bl')),
            ( 1,  1, lambda: self._corr_corner(dev[-1, -1], fade, 'br')),
        ]

        for dr, dc, build_corr in neighbour_ops:
            nr, nc = row + dr, col + dc
            if not (0 <= nr < 3 and 0 <= nc < 3):
                continue
            n_idx = nr * 3 + nc
            if n_idx in self.completed:
                continue
            correction = build_corr()
            self.intended[n_idx] = np.clip(self.intended[n_idx] + correction, 0, 1)

    # -- correction builders (each returns (TILE_SIZE, TILE_SIZE) float32)

    def _corr_right(self, dev, fade):
        c = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)
        c[:, :BLEND_SIZE] = dev[:, -1:] * fade[np.newaxis, :]
        return c

    def _corr_left(self, dev, fade):
        c = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)
        c[:, TILE_SIZE - BLEND_SIZE:] = dev[:, :1] * fade[::-1][np.newaxis, :]
        return c

    def _corr_bottom(self, dev, fade):
        c = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)
        c[:BLEND_SIZE, :] = dev[-1:, :] * fade[:, np.newaxis]
        return c

    def _corr_top(self, dev, fade):
        c = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)
        c[TILE_SIZE - BLEND_SIZE:, :] = dev[:1, :] * fade[::-1][:, np.newaxis]
        return c

    def _corr_corner(self, val: float, fade, corner: str):
        c = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)
        fade2d = np.outer(fade, fade)
        bs = BLEND_SIZE
        if corner == 'br':
            c[:bs, :bs] = val * fade2d
        elif corner == 'bl':
            c[:bs, TILE_SIZE - bs:] = val * fade2d[:, ::-1]
        elif corner == 'tr':
            c[TILE_SIZE - bs:, :bs] = val * fade2d[::-1, :]
        elif corner == 'tl':
            c[TILE_SIZE - bs:, TILE_SIZE - bs:] = val * fade2d[::-1, ::-1]
        return c
