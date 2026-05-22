import numpy as np
from PIL import Image
from typing import Optional, Callable
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TILE_SIZE = 256
BLEND_SIZE = 80


class TileManager:
    def __init__(self):
        self.initialized = False
        self.cols = 3
        self.rows = 3
        self.n_tiles = 9
        self.master: Optional[np.ndarray] = None
        self.intended: list[Optional[np.ndarray]] = []
        self.scanned: list[Optional[np.ndarray]] = []
        self.deviations: list[Optional[np.ndarray]] = []
        self.deviation_colors: list[Optional[np.ndarray]] = []
        self.completed: set[int] = set()
        self.current_tile: int = 0

    # ------------------------------------------------------------------
    # Initialise

    def initialize(self, heightmap: np.ndarray, cols: int = 3, rows: int = 3):
        self.cols = cols
        self.rows = rows
        self.n_tiles = cols * rows

        target_w = cols * TILE_SIZE
        target_h = rows * TILE_SIZE
        img = Image.fromarray((heightmap * 255).astype(np.uint8))
        img = img.resize((target_w, target_h), Image.LANCZOS)
        self.master = np.array(img, dtype=np.float32) / 255.0

        self.intended = [self._extract_tile(i) for i in range(self.n_tiles)]
        self.scanned = [None] * self.n_tiles
        self.deviations = [None] * self.n_tiles
        self.deviation_colors = [None] * self.n_tiles
        self.completed = set()
        self.current_tile = 0
        self.initialized = True

    def reset(self):
        self.__init__()

    # ------------------------------------------------------------------
    # Per-tile processing

    def process_tile(self, idx: int, scanned: np.ndarray):
        intended = self.intended[idx]

        if scanned.shape != (TILE_SIZE, TILE_SIZE):
            pil = Image.fromarray((np.clip(scanned, 0, 1) * 255).astype(np.uint8))
            pil = pil.resize((TILE_SIZE, TILE_SIZE), Image.LANCZOS)
            scanned = np.array(pil, dtype=np.float32) / 255.0

        self.scanned[idx] = scanned.copy()
        deviation = scanned - intended
        self.deviations[idx] = deviation
        self.deviation_colors[idx] = self._colorize(deviation)

        self.completed.add(idx)
        self._propagate(idx, deviation)
        self._rebuild_master()

        for i in range(self.n_tiles):
            if i not in self.completed:
                self.current_tile = i
                break
        else:
            self.current_tile = -1

    # ------------------------------------------------------------------
    # 3D surface data

    def get_surface3d(self, idx: int, res: int = 64) -> dict:
        tile = self.intended[idx]
        if tile is None:
            return {"z": [], "x": [], "y": []}
        pil = Image.fromarray((tile * 255).astype(np.uint8))
        pil = pil.resize((res, res), Image.LANCZOS)
        z = np.array(pil, dtype=np.float32) / 255.0
        return {"z": z.tolist(), "x": list(range(res)), "y": list(range(res))}

    # ------------------------------------------------------------------
    # Serialisation

    def to_state_dict(self, arr_to_b64: Callable) -> dict:
        tiles = []
        if self.initialized:
            for i in range(self.n_tiles):
                tiles.append({
                    "idx": i,
                    "intended": arr_to_b64(self.intended[i]),
                    "scanned": arr_to_b64(self.scanned[i]),
                    "deviation": arr_to_b64(self.deviations[i]),
                    "deviation_color": arr_to_b64(self.deviation_colors[i], rgb=True),
                })
        return {
            "initialized": self.initialized,
            "cols": self.cols,
            "rows": self.rows,
            "current_tile": self.current_tile,
            "completed": list(self.completed),
            "master": arr_to_b64(self.master) if self.initialized else None,
            "tiles": tiles,
        }

    # ------------------------------------------------------------------
    # Internals

    def _tile_pos(self, idx: int):
        return idx // self.cols, idx % self.cols

    def _extract_tile(self, idx: int) -> np.ndarray:
        r, c = self._tile_pos(idx)
        r0, c0 = r * TILE_SIZE, c * TILE_SIZE
        return self.master[r0:r0 + TILE_SIZE, c0:c0 + TILE_SIZE].copy()

    def _rebuild_master(self):
        for i in range(self.n_tiles):
            r, c = self._tile_pos(i)
            r0, c0 = r * TILE_SIZE, c * TILE_SIZE
            self.master[r0:r0 + TILE_SIZE, c0:c0 + TILE_SIZE] = np.clip(self.intended[i], 0, 1)

    def _colorize(self, deviation: np.ndarray) -> np.ndarray:
        max_abs = max(float(np.abs(deviation).max()), 1e-6)
        norm = deviation / max_abs
        cmap = plt.get_cmap("RdBu_r")
        rgba = cmap((norm + 1) / 2)
        return (rgba[:, :, :3] * 255).astype(np.uint8)

    def _propagate(self, idx: int, dev: np.ndarray):
        row, col = self._tile_pos(idx)
        fade = np.linspace(1.0, 0.0, BLEND_SIZE, dtype=np.float32)

        neighbour_ops = [
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
            if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                continue
            n_idx = nr * self.cols + nc
            if n_idx in self.completed:
                continue
            correction = build_corr()
            self.intended[n_idx] = np.clip(self.intended[n_idx] + correction, 0, 1)

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