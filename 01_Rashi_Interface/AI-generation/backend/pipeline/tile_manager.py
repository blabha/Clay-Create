import numpy as np
from PIL import Image
from typing import Optional, Callable
from scipy.ndimage import distance_transform_edt, gaussian_filter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TILE_SIZE = 256


class TileManager:
    def __init__(self):
        self.initialized = False
        self.cols = 3
        self.rows = 3
        self.n_tiles = 9
        self.master: Optional[np.ndarray] = None
        self.intended: list[Optional[np.ndarray]] = []
        self.original_intended: list[Optional[np.ndarray]] = []
        self.scanned: list[Optional[np.ndarray]] = []
        self.deviations: list[Optional[np.ndarray]] = []
        self.deviation_colors: list[Optional[np.ndarray]] = []
        self.regen_diffs: list[Optional[np.ndarray]] = []
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
        self.original_intended = [t.copy() for t in self.intended]
        self.scanned = [None] * self.n_tiles
        self.deviations = [None] * self.n_tiles
        self.deviation_colors = [None] * self.n_tiles
        self.regen_diffs = [None] * self.n_tiles
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
        self._regen_neighbors(idx)
        self._rebuild_master()

        for i in range(self.n_tiles):
            if i not in self.completed:
                self.current_tile = i
                break
        else:
            self.current_tile = -1

    def regenerate_tile(self, idx: int):
        """Seam-correct an uncarved tile for line continuity."""
        if idx in self.completed:
            return
        self.intended[idx] = self._seam_corrected_tile(idx)
        self.regen_diffs[idx] = self._regen_diff(idx)
        self._rebuild_master()

    def regenerate_all(self):
        """Seam-correct every uncarved tile for line continuity."""
        for idx in range(self.n_tiles):
            if idx not in self.completed:
                self.intended[idx] = self._seam_corrected_tile(idx)
                self.regen_diffs[idx] = self._regen_diff(idx)
        self._rebuild_master()

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
                    "original_intended": arr_to_b64(self.original_intended[i]),
                    "scanned": arr_to_b64(self.scanned[i]),
                    "deviation": arr_to_b64(self.deviations[i]),
                    "deviation_color": arr_to_b64(self.deviation_colors[i], rgb=True),
                    "regen_diff": arr_to_b64(self.regen_diffs[i], rgb=True),
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
    # Neighbour regeneration — harmonic interpolation

    def _regen_neighbors(self, idx: int):
        """After carving idx, regenerate the intended design for all uncarved neighbours."""
        row, col = self._tile_pos(idx)
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = row + dr, col + dc
                if not (0 <= nr < self.rows and 0 <= nc < self.cols):
                    continue
                n_idx = nr * self.cols + nc
                if n_idx in self.completed:
                    continue
                self.intended[n_idx] = self._harmonic_tile(n_idx)
                self.regen_diffs[n_idx] = self._regen_diff(n_idx)

    def _seam_corrected_tile(self, idx: int) -> np.ndarray:
        """
        Seam-only correction for line continuity across carved boundaries.

        For each shared edge with a completed neighbour, compute the difference
        between what was actually scanned and what the original design expected
        at that edge (scanned_edge - original_edge).  Spread that additive
        correction a short distance inward (~30 px) with exponential decay, then
        add it to the original design.  The tile interior is left untouched.
        """
        original = self.original_intended[idx].copy()
        row, col = self._tile_pos(idx)

        correction = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)
        mask = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)

        if row > 0:
            n = (row - 1) * self.cols + col
            if n in self.completed and self.scanned[n] is not None:
                correction[0, :] = self.scanned[n][-1, :] - original[0, :]
                mask[0, :] = 1.0

        if row < self.rows - 1:
            n = (row + 1) * self.cols + col
            if n in self.completed and self.scanned[n] is not None:
                correction[-1, :] = self.scanned[n][0, :] - original[-1, :]
                mask[-1, :] = 1.0

        if col > 0:
            n = row * self.cols + (col - 1)
            if n in self.completed and self.scanned[n] is not None:
                correction[:, 0] = self.scanned[n][:, -1] - original[:, 0]
                mask[:, 0] = 1.0

        if col < self.cols - 1:
            n = row * self.cols + (col + 1)
            if n in self.completed and self.scanned[n] is not None:
                correction[:, -1] = self.scanned[n][:, 0] - original[:, -1]
                mask[:, -1] = 1.0

        if not mask.any():
            return original

        # Smooth the correction along the seam (handles noisy scanned edges)
        sigma = TILE_SIZE * 0.12          # ~30 px smoothing along boundary
        decay = TILE_SIZE * 0.10          # ~26 px inward reach

        num = gaussian_filter(correction * mask, sigma=sigma)
        den = gaussian_filter(mask, sigma=sigma)
        correction_field = np.where(den > 0.001, num / den, 0.0)

        dist = distance_transform_edt(1.0 - mask).astype(np.float32)
        fade = np.exp(-dist / decay)

        return np.clip(original + fade * correction_field, 0, 1)

    def _harmonic_tile(self, idx: int) -> np.ndarray:
        """
        Regenerate the intended design for an uncarved tile by interpolating
        from actual scanned edges of completed neighbours toward the original design.

        Boundary pixels are set from the scanned edge of each completed neighbour.
        A Gaussian spread + distance-based weight creates a smooth transition
        from those fixed boundaries into the tile interior, which falls back to
        the original depth map. Final result is blended 50/50 with the original
        so the reference image's aesthetic is preserved.
        """
        original = self.intended[idx].copy()
        row, col = self._tile_pos(idx)

        boundary_mask = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)
        boundary_vals = np.zeros((TILE_SIZE, TILE_SIZE), dtype=np.float32)

        # Top neighbour → constrain top edge of this tile
        if row > 0:
            n = (row - 1) * self.cols + col
            if n in self.completed and self.scanned[n] is not None:
                boundary_mask[0, :] = 1.0
                boundary_vals[0, :] = self.scanned[n][-1, :]

        # Bottom neighbour → constrain bottom edge
        if row < self.rows - 1:
            n = (row + 1) * self.cols + col
            if n in self.completed and self.scanned[n] is not None:
                boundary_mask[-1, :] = 1.0
                boundary_vals[-1, :] = self.scanned[n][0, :]

        # Left neighbour → constrain left edge
        if col > 0:
            n = row * self.cols + (col - 1)
            if n in self.completed and self.scanned[n] is not None:
                boundary_mask[:, 0] = 1.0
                boundary_vals[:, 0] = self.scanned[n][:, -1]

        # Right neighbour → constrain right edge
        if col < self.cols - 1:
            n = row * self.cols + (col + 1)
            if n in self.completed and self.scanned[n] is not None:
                boundary_mask[:, -1] = 1.0
                boundary_vals[:, -1] = self.scanned[n][:, 0]

        if not boundary_mask.any():
            return original

        # Spread boundary values inward with a large Gaussian
        sigma = TILE_SIZE * 0.35
        num = gaussian_filter(boundary_vals * boundary_mask, sigma=sigma)
        den = gaussian_filter(boundary_mask, sigma=sigma)
        spread = np.where(den > 0.001, num / den, original)

        # Weight: 1.0 at boundary pixels, decays exponentially toward centre
        dist = distance_transform_edt(1.0 - boundary_mask).astype(np.float32)
        w = np.exp(-dist / (TILE_SIZE * 0.45))

        # Blend: boundary-driven near edges, original design toward centre
        harmonic = w * spread + (1.0 - w) * original

        # 50/50 with original to preserve the reference image's aesthetic
        return np.clip(0.5 * harmonic + 0.5 * original, 0, 1)

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
            # Completed tiles: show what was actually carved
            data = self.scanned[i] if (i in self.completed and self.scanned[i] is not None) else self.intended[i]
            self.master[r0:r0 + TILE_SIZE, c0:c0 + TILE_SIZE] = np.clip(data, 0, 1)

    def _regen_diff(self, idx: int) -> np.ndarray:
        """Colorized diff between current intended and original intended for tile idx."""
        return self._colorize(self.intended[idx] - self.original_intended[idx])

    def _colorize(self, deviation: np.ndarray) -> np.ndarray:
        max_abs = max(float(np.abs(deviation).max()), 1e-6)
        norm = deviation / max_abs
        cmap = plt.get_cmap("RdBu_r")
        rgba = cmap((norm + 1) / 2)
        return (rgba[:, :, :3] * 255).astype(np.uint8)