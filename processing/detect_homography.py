"""
Load a foreground PLY, fit a plane to the surface, rotate points so the
block lies flat (homography / planar rectification), then generate a
heightmap and open the viewer.

Uses roi_config.txt (written by live_roi.py) for bounding box — if absent,
falls back to detect_grey_block defaults.

Usage:
    python detect_homography.py                  # auto-picks latest *_foreground.ply
    python detect_homography.py capture_XXX_foreground.ply
    python detect_homography.py --no-view
"""

import sys
import os
import glob
import argparse
import numpy as np
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


# ── PLY I/O ───────────────────────────────────────────────────────────────────

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
    points = np.stack([data["x"], data["y"], data["z"]], axis=-1)
    colors = np.stack([data["r"], data["g"], data["b"]], axis=-1)
    return points, colors


def _save_ply(path, points, colors):
    n = len(points)
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {n}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    )
    dtype = np.dtype([("x","<f4"),("y","<f4"),("z","<f4"),
                      ("r","u1"),("g","u1"),("b","u1")])
    data = np.zeros(n, dtype=dtype)
    data["x"], data["y"], data["z"] = points[:,0], points[:,1], points[:,2]
    data["r"], data["g"], data["b"] = colors[:,0], colors[:,1], colors[:,2]
    with open(path, "wb") as f:
        f.write(header.encode("ascii"))
        f.write(data.tobytes())
    print(f"  Saved {n:,} points -> {path}")


# ── ROI config ────────────────────────────────────────────────────────────────

def _load_roi_config():
    path = os.path.join(ROOT, "roi_config.txt")
    cfg = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = float(v.strip())
        print(f"Loaded ROI config: {cfg}")
    return cfg


# ── Bounding box filter ───────────────────────────────────────────────────────

def _apply_bbox(points, colors, x_min, x_max, z_min, z_max, depth_min, depth_max):
    mask = (
        (points[:, 0] >= x_min)      & (points[:, 0] <= x_max)   &  # camera X
        (points[:, 2] >= depth_min)  & (points[:, 2] <= depth_max) & # depth
        (points[:, 1] >= -z_max)     & (points[:, 1] <= -z_min)     # viewer Z -> camera Y
    )
    print(f"  Bounding box: {mask.sum():,} / {len(points):,} points kept")
    return points[mask], colors[mask]


# ── Plane fit + rectification ─────────────────────────────────────────────────

def fit_plane(points):
    """Least-squares plane fit. Returns normal vector (unit) and centroid."""
    centroid = points.mean(axis=0)
    centred  = points - centroid
    _, _, Vt = np.linalg.svd(centred, full_matrices=False)
    normal = Vt[-1]                  # smallest singular value = plane normal
    if normal[1] > 0:                # ensure normal points upward in viewer
        normal = -normal
    return normal, centroid


def rotation_to_align(normal, target=None):
    """
    Return a 3x3 rotation matrix R such that R @ normal ≈ target.
    Default target = (0, -1, 0)  (camera -Y = viewer up).
    """
    if target is None:
        target = np.array([0.0, -1.0, 0.0])
    normal = normal / np.linalg.norm(normal)
    target = target / np.linalg.norm(target)

    v = np.cross(normal, target)
    s = np.linalg.norm(v)
    c = np.dot(normal, target)

    if s < 1e-10:           # already aligned
        return np.eye(3)

    vx = np.array([
        [ 0,    -v[2],  v[1]],
        [ v[2],  0,    -v[0]],
        [-v[1],  v[0],  0   ],
    ])
    R = np.eye(3) + vx + vx @ vx * ((1 - c) / (s * s))
    return R


def rectify(points, colors):
    """Fit plane, rotate so it's horizontal, centre the cloud."""
    print("\nPlane fitting...")
    normal, centroid = fit_plane(points)
    angle_deg = float(np.degrees(np.arccos(np.clip(abs(normal[1]), 0, 1))))
    print(f"  Surface normal: [{normal[0]:.3f}, {normal[1]:.3f}, {normal[2]:.3f}]")
    print(f"  Tilt from vertical camera axis: {angle_deg:.2f} deg")

    R = rotation_to_align(normal)
    pts_r = (R @ (points - centroid).T).T

    # Translate so the plane sits at viewer Z = 0
    pts_r[:, 1] -= pts_r[:, 1].mean()
    print(f"  Rotation applied — surface now horizontal.")
    return pts_r, colors, R, centroid


# ── Heightmap ─────────────────────────────────────────────────────────────────

def render_heightmap(points, colors, output_path, resolution_mm=1.0):
    import cv2
    from scipy.interpolate import griddata

    u = points[:, 0]
    v = points[:, 2]
    h = -points[:, 1]

    res = resolution_mm / 1000.0
    u_min, u_max = u.min(), u.max()
    v_min, v_max = v.min(), v.max()
    W = max(4, int(np.ceil((u_max - u_min) / res)) + 2)
    H = max(4, int(np.ceil((v_max - v_min) / res)) + 2)
    print(f"\nHeightmap: {W}x{H} px at {resolution_mm} mm/px  "
          f"({W*res*100:.1f} x {H*res*100:.1f} cm)")

    px_u = np.clip(((u - u_min) / res).astype(int), 0, W - 1)
    px_v = np.clip(((v - v_min) / res).astype(int), 0, H - 1)
    px_v = H - 1 - px_v

    sort_idx    = np.argsort(h)
    flat_idx    = px_v[sort_idx] * W + px_u[sort_idx]
    height_flat = np.full(H * W, np.nan, dtype=np.float32)
    height_flat[flat_idx] = h[sort_idx].astype(np.float32)
    height_grid = height_flat.reshape(H, W)

    ys, xs = np.where(~np.isnan(height_grid))
    zs = height_grid[ys, xs]
    grid_ys, grid_xs = np.mgrid[0:H, 0:W]
    filled = griddata((ys, xs), zs, (grid_ys, grid_xs), method="linear")
    nan_mask = np.isnan(filled)
    if nan_mask.any():
        filled[nan_mask] = griddata((ys, xs), zs,
                                    (grid_ys[nan_mask], grid_xs[nan_mask]),
                                    method="nearest")

    h_min, h_max = float(filled.min()), float(filled.max())
    print(f"  Height range: {h_min*1000:.1f} mm (dark) → {h_max*1000:.1f} mm (light)")

    grey = ((filled - h_min) / max(h_max - h_min, 1e-6) * 255).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    grey  = clahe.apply(grey)

    scale = max(1, 800 // max(H, W))
    if scale > 1:
        grey = cv2.resize(grey, (W * scale, H * scale), interpolation=cv2.INTER_LINEAR)

    cv2.imwrite(output_path, grey)
    print(f"  Heightmap -> {output_path}")


# ── Viewer ────────────────────────────────────────────────────────────────────

def _visualize(points, colors, html_path, title, color_png=None, heightmap_png=None):
    import plotly.graph_objects as go
    import base64

    packed = ((colors[:,0].astype(np.uint32) << 16)
            | (colors[:,1].astype(np.uint32) << 8)
            |  colors[:,2].astype(np.uint32))
    hex_colors = ["#{:06x}".format(int(p)) for p in packed]

    fig = go.Figure(data=[go.Scatter3d(
        x=-points[:,0], y=points[:,2], z=-points[:,1],
        mode="markers",
        marker=dict(size=2, color=hex_colors, opacity=1.0),
    )])
    fig.update_layout(
        title=title,
        scene=dict(
            xaxis_title="X (m)", yaxis_title="Depth (m)", zaxis_title="Up (m)",
            aspectmode="data",
            camera=dict(up=dict(x=0,y=0,z=1), eye=dict(x=0,y=-2,z=0.4),
                        projection=dict(type="orthographic")),
        ),
        margin=dict(l=0, r=0, b=0, t=40),
    )
    fig.write_html(html_path, auto_open=False)

    def _b64(path, label, right_px):
        if not (path and os.path.exists(path)):
            return ""
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = os.path.splitext(path)[1].lstrip(".")
        return (
            f'<div style="position:fixed;top:10px;right:{right_px}px;width:220px;'
            'text-align:center;background:rgba(0,0,0,0.55);color:#fff;'
            f'font:11px sans-serif;padding:2px;z-index:10000;border-radius:4px 4px 0 0;">{label}</div>'
            f'<img src="data:image/{ext};base64,{b64}" '
            f'style="position:fixed;top:28px;right:{right_px}px;width:220px;'
            'border:2px solid #555;border-radius:0 0 4px 4px;z-index:9999;">'
        )

    inject = _b64(color_png, "RGB input", 10) + _b64(heightmap_png, "Heightmap", 240)
    if inject:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html.replace("</body>", inject + "</body>"))

    print(f"  Viewer -> {html_path}")
    webbrowser.open("file:///" + html_path.replace(os.sep, "/").replace(" ", "%20"))


# ── Main ──────────────────────────────────────────────────────────────────────

def process(ply_path, open_viewer=True, resolution_mm=1.0,
            x_min=None, x_max=None, z_min=None, z_max=None,
            depth_min=None, depth_max=None):

    print(f"\nLoading {ply_path} ...")
    points, colors = _load_ply(ply_path)
    print(f"  {len(points):,} points")

    # Apply bounding box
    print("\nBounding box filter")
    points, colors = _apply_bbox(
        points, colors,
        x_min    / 100.0,
        x_max    / 100.0,
        z_min    / 100.0,
        z_max    / 100.0,
        depth_min / 100.0,
        depth_max / 100.0,
    )
    if len(points) == 0:
        print("No points remain after bounding box filter.")
        return

    # Planar rectification
    points, colors, R, centroid = rectify(points, colors)

    base         = os.path.splitext(ply_path)[0].replace("_foreground", "")
    out_ply      = base + "_rectified.ply"
    out_html     = base + "_rectified_viewer.html"
    out_hmap     = base + "_rectified_heightmap.png"
    color_png    = base + "_color.png"

    print()
    _save_ply(out_ply, points, colors)
    render_heightmap(points, colors, out_hmap, resolution_mm=resolution_mm)

    if open_viewer:
        _visualize(points, colors, out_html,
                   title=f"Rectified — {len(points):,} pts",
                   color_png=color_png if os.path.exists(color_png) else None,
                   heightmap_png=out_hmap)


def find_latest_foreground():
    files = glob.glob(os.path.join(ROOT, "point clouds", "*_foreground.ply"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Planar rectification + heightmap from foreground PLY")
    parser.add_argument("ply", nargs="?", default=None,
                        help="*_foreground.ply (auto-picks latest if omitted)")
    parser.add_argument("--no-view",  action="store_true")
    parser.add_argument("--res", type=float, default=1.0, metavar="MM",
                        help="Heightmap resolution in mm/pixel (default: 1)")
    args = parser.parse_args()

    ply_path = args.ply
    if ply_path is None:
        ply_path = find_latest_foreground()
        if ply_path is None:
            print("No *_foreground.ply found.")
            sys.exit(1)
        print(f"Auto-selected: {os.path.basename(ply_path)}")

    roi = _load_roi_config()
    process(
        ply_path,
        open_viewer  = not args.no_view,
        resolution_mm= args.res,
        x_min        = roi.get("x_min",    -12.0),
        x_max        = roi.get("x_max",     12.0),
        z_min        = roi.get("z_min",    -10.0),
        z_max        = roi.get("z_max",     10.0),
        depth_min    = roi.get("depth_min",  0.0),
        depth_max    = roi.get("depth_max", 67.0),
    )
