"""
Render a top-down greyscale height map from a foreground PLY file.
Dark grey = lowest points, light grey = highest points.

Usage:
    python heatmap_foreground.py                    # auto-picks latest *_foreground.ply
    python heatmap_foreground.py capture_XXX_foreground.ply
    python heatmap_foreground.py --res 1            # 1 mm/pixel (default: 0.5)
"""

import sys
import os
import glob
import argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _load_ply(path):
    with open(path, "rb") as f:
        n, props = None, []
        while True:
            line = f.readline().decode("ascii").strip()
            if line.startswith("element vertex"):
                n = int(line.split()[-1])
            if line.startswith("property"):
                props.append(line.split()[-1])
            if line == "end_header":
                break
        dtype = np.dtype([("x","<f4"),("y","<f4"),("z","<f4"),
                          ("r","u1"),("g","u1"),("b","u1")])
        data = np.frombuffer(f.read(n * dtype.itemsize), dtype=dtype)
    return np.stack([data["x"], data["y"], data["z"]], axis=-1)


def render_heightmap(ply_path, resolution_mm=2, output_path=None):
    import cv2
    from scipy.interpolate import griddata

    print(f"Loading {ply_path} ...")
    points = _load_ply(ply_path)
    print(f"  {len(points):,} points")

    # Top-down: u = camera X, v = camera Z (depth), height = viewer Z = -camera Y
    u = points[:, 0]
    v = points[:, 2]
    h = -points[:, 1]   # positive = up

    res = resolution_mm / 1000.0

    u_min, u_max = u.min(), u.max()
    v_min, v_max = v.min(), v.max()
    W = max(4, int(np.ceil((u_max - u_min) / res)) + 2)
    H = max(4, int(np.ceil((v_max - v_min) / res)) + 2)
    print(f"  Grid: {W} x {H} px  ({W*res*100:.1f} x {H*res*100:.1f} cm)  at {resolution_mm} mm/px")

    px_u = np.clip(((u - u_min) / res).astype(int), 0, W - 1)
    px_v = np.clip(((v - v_min) / res).astype(int), 0, H - 1)
    px_v_flip = H - 1 - px_v   # near depth = bottom of image

    # Per-pixel maximum height (topmost surface wins)
    sort_idx    = np.argsort(h)
    flat_idx    = px_v_flip[sort_idx] * W + px_u[sort_idx]
    height_flat = np.full(H * W, np.nan, dtype=np.float32)
    height_flat[flat_idx] = h[sort_idx].astype(np.float32)
    height_grid = height_flat.reshape(H, W)

    valid = ~np.isnan(height_grid)
    print(f"  Valid cells: {valid.sum():,} / {H*W:,} ({100*valid.mean():.1f} %)")

    ys, xs = np.where(valid)
    zs = height_grid[valid]

    h_min = float(zs.min())
    h_max = float(zs.max())
    print(f"  Height range: {h_min*100:.2f} cm (dark) → {h_max*100:.2f} cm (light)")

    # Interpolate gaps — linear keeps surface detail, nearest fills edges
    grid_ys, grid_xs = np.mgrid[0:H, 0:W]
    filled = griddata((ys, xs), zs, (grid_ys, grid_xs), method="linear")
    nan_mask = np.isnan(filled)
    if nan_mask.any():
        filled_nn = griddata((ys, xs), zs, (grid_ys, grid_xs), method="nearest")
        filled[nan_mask] = filled_nn[nan_mask]

    # Normalise to 0-255 — no smoothing so ridges stay sharp
    if h_max == h_min:
        grey = np.full((H, W), 128, dtype=np.uint8)
    else:
        grey = ((filled - h_min) / (h_max - h_min) * 255).astype(np.uint8)

    # CLAHE: enhances local contrast so surface ridges are clearly visible
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    grey = clahe.apply(grey)

    # Scale up with smooth interpolation — at least 800 px on longest side
    long_side = max(H, W)
    scale = max(1, 800 // long_side)
    if scale > 1:
        grey = cv2.resize(grey, (W * scale, H * scale),
                          interpolation=cv2.INTER_LINEAR)

    if output_path is None:
        output_path = os.path.splitext(ply_path)[0] + "_heightmap.png"

    cv2.imwrite(output_path, grey)
    print(f"  Saved -> {output_path}")
    return output_path


def find_latest_foreground():
    files = glob.glob(os.path.join(ROOT, "point clouds", "*_foreground.ply"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def main():
    parser = argparse.ArgumentParser(
        description="Render greyscale height map PNG from foreground PLY")
    parser.add_argument("ply", nargs="?", default=None,
                        help="Path to *_foreground.ply (auto-picks latest if omitted)")
    parser.add_argument("--res", type=float, default=0.5, metavar="MM",
                        help="Grid resolution in mm/pixel (default: 0.5)")
    args = parser.parse_args()

    ply_path = args.ply
    if ply_path is None:
        ply_path = find_latest_foreground()
        if ply_path is None:
            print("No *_foreground.ply found in", os.path.join(ROOT, "output"))
            sys.exit(1)
        print(f"Auto-selected: {os.path.basename(ply_path)}")

    if not os.path.exists(ply_path):
        print(f"File not found: {ply_path}")
        sys.exit(1)

    render_heightmap(ply_path, resolution_mm=args.res)


if __name__ == "__main__":
    main()
