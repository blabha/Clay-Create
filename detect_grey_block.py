"""
Isolate foreground objects by removing the floor (and far background) from a point cloud.
No colour filtering — works purely on depth and height.

Usage:
    python detect_grey_block.py <file.ply>
    python detect_grey_block.py --capture
    python detect_grey_block.py <file.ply> --floor-margin 3   # cm above auto-detected floor

Pipeline:
    1. Auto depth cutoff  — removes far background wall/floor beyond the object
    2. Auto floor cut     — finds the floor plane from the Y histogram and removes it
    3. Viewer opens with only the foreground object(s) remaining
"""

import sys
import os
import numpy as np
import webbrowser
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))


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
        has_normals = "nx" in props
        fields = [("x","<f4"),("y","<f4"),("z","<f4"),
                  ("r","u1"),("g","u1"),("b","u1")]
        if has_normals:
            fields += [("nx","<f4"),("ny","<f4"),("nz","<f4")]
        dtype = np.dtype(fields)
        data  = np.frombuffer(f.read(n * dtype.itemsize), dtype=dtype)
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
    print(f"Saved {n:,} points -> {path}")


# ── Auto depth cutoff ─────────────────────────────────────────────────────────

def auto_depth_max(points, margin_m=0.20):
    """
    Find the gap between the nearest object and the background in the Z histogram.
    Returns the gap depth + margin, so the background wall/floor is excluded.
    """
    z = points[:, 2]
    z = z[(z > 0.3) & (z < 5.0)]
    if len(z) < 100:
        print("  Auto depth cutoff: too few points, skipping")
        return None

    edges  = np.arange(0.3, 5.02, 0.02)
    counts, _ = np.histogram(z, bins=edges)
    smooth = np.convolve(counts, np.ones(3) / 3.0, mode="same")

    half      = len(smooth) // 2
    peak_idx  = int(np.argmax(smooth[:half]))
    threshold = smooth[peak_idx] * 0.15

    cut_idx = None
    for i in range(peak_idx, len(smooth)):
        if smooth[i] < threshold:
            cut_idx = i
            break

    if cut_idx is None:
        cut = float(np.percentile(z, 30)) + margin_m
        print(f"  Auto depth cutoff: no clear gap, using 30th-pct + {margin_m*100:.0f} cm = {cut*100:.0f} cm")
    else:
        cut = float(edges[cut_idx]) + margin_m
        print(f"  Auto depth cutoff: peak={edges[peak_idx]*100:.0f} cm  "
              f"gap={edges[cut_idx]*100:.0f} cm  cutoff={cut*100:.0f} cm")
    return cut


# ── Filters ───────────────────────────────────────────────────────────────────

def apply_depth_max(points, colors, depth_max_m):
    mask = points[:, 2] <= depth_max_m
    print(f"  Depth filter (Z <= {depth_max_m*100:.0f} cm): "
          f"{mask.sum():,} / {len(points):,} kept")
    return points[mask], colors[mask]


def apply_depth_min(points, colors, depth_min_m):
    mask = points[:, 2] >= depth_min_m
    print(f"  Depth filter (Z >= {depth_min_m*100:.1f} cm): "
          f"{mask.sum():,} / {len(points):,} kept")
    return points[mask], colors[mask]


# ── Bounding box ──────────────────────────────────────────────────────────────

def print_bbox(points):
    if len(points) == 0:
        return
    lo, hi = points.min(axis=0), points.max(axis=0)
    size = (hi - lo) * 100
    cx   = ((lo + hi) / 2) * 100
    # viewer Z = -camera_y  (positive = up, negative = down)
    viewer_z_top    = -lo[1] * 100   # highest point  (most positive viewer Z)
    viewer_z_bottom = -hi[1] * 100   # lowest point   (most negative viewer Z)
    print(f"  Size         W={size[0]:.1f} cm  H={size[1]:.1f} cm  D={size[2]:.1f} cm")
    print(f"  Depth range  {lo[2]*100:.1f} cm  ->  {hi[2]*100:.1f} cm")
    print(f"  Highest point (viewer Z): {viewer_z_top:.2f} cm")
    print(f"  Lowest point  (viewer Z): {viewer_z_bottom:.2f} cm  <-- use this for floor cut")


# ── Orthographic projection ───────────────────────────────────────────────────

def render_ortho(points, colors, view="top", resolution_cm=0.5):
    """
    Render a 2D orthographic image of the point cloud.

    view="top"   — bird's-eye view:  horizontal=X, vertical=Z (depth), no Y
    view="front" — frontal view:     horizontal=X, vertical=-Y (up),   no Z

    Each output pixel = resolution_cm × resolution_cm in world space.
    Points are averaged per pixel cell so the image is smooth.
    Returns a (H, W, 3) uint8 BGR image ready for cv2.imwrite.
    """
    import cv2

    res = resolution_cm / 100.0  # metres per pixel

    if view == "top":
        u =  points[:, 0]       # X  → image columns
        v =  points[:, 2]       # Z  → image rows (near = top)
    else:
        u =  points[:, 0]       # X  → image columns
        v = -points[:, 1]       # -Y → image rows (up = top)

    u_min, v_min = u.min(), v.min()
    W = max(1, int(np.ceil((u.max() - u_min) / res)) + 2)
    H = max(1, int(np.ceil((v.max() - v_min) / res)) + 2)

    # Accumulate colour sums and counts per pixel cell
    col_sum = np.zeros((H, W, 3), dtype=np.float32)
    col_cnt = np.zeros((H, W),    dtype=np.float32)

    px_u = np.clip(((u - u_min) / res).astype(int), 0, W - 1)
    px_v = np.clip(((v - v_min) / res).astype(int), 0, H - 1)
    px_v_flip = H - 1 - px_v  # flip so larger v = higher in image

    np.add.at(col_sum, (px_v_flip, px_u), colors.astype(np.float32))
    np.add.at(col_cnt, (px_v_flip, px_u), 1)

    valid = col_cnt > 0
    img = np.full((H, W, 3), 30, dtype=np.uint8)   # dark background
    img[valid] = (col_sum[valid] / col_cnt[valid, None]).astype(np.uint8)

    # BGR for cv2 (colors are RGB)
    img = img[:, :, ::-1]

    # Scale up for readability (min 400 px on shortest axis)
    scale = max(1, 400 // min(H, W))
    if scale > 1:
        img = cv2.resize(img, (W * scale, H * scale),
                         interpolation=cv2.INTER_NEAREST)

    # Label axes
    font, fs, thick = cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1
    axes_label = "X  |  Z(depth)" if view == "top" else "X  |  Y(up)"
    cv2.putText(img, axes_label, (6, 16), font, fs, (200, 200, 200), thick)
    cv2.putText(img, view.upper(), (6, img.shape[0] - 6), font, fs, (180, 180, 180), thick)

    return img


def save_ortho_views(points, colors, base_path, resolution_cm=0.5):
    """Render front orthographic view and save as PNG. Returns (None, front_path)."""
    import cv2
    front_path = base_path + "_ortho_front.png"
    cv2.imwrite(front_path, render_ortho(points, colors, "front", resolution_cm))
    print(f"  Ortho front -> {os.path.basename(front_path)}")
    return None, front_path


# ── Viewer ────────────────────────────────────────────────────────────────────

def _visualize(points, colors, title, html_path, color_png=None,
               ortho_top=None, ortho_front=None):
    import plotly.graph_objects as go

    packed = ((colors[:,0].astype(np.uint32) << 16)
            | (colors[:,1].astype(np.uint32) << 8)
            |  colors[:,2].astype(np.uint32))
    hex_colors = ["#{:06x}".format(int(p)) for p in packed]

    fig = go.Figure(data=[go.Scatter3d(
        x=-points[:,0], y=points[:,2], z=-points[:,1],
        mode="markers",
        marker=dict(size=2, color=hex_colors, opacity=1.0),
        name="foreground",
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

    import base64

    def _b64_img(path, label, right_offset):
        """Return fixed-position label+image HTML snippet for injection."""
        if not (path and os.path.exists(path)):
            return ""
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext  = os.path.splitext(path)[1].lstrip(".")
        mime = "png" if ext in ("png", "jpg", "jpeg") else ext
        return (
            f'<div style="position:fixed;top:10px;right:{right_offset}px;width:220px;'
            'text-align:center;background:rgba(0,0,0,0.55);color:#fff;'
            'font:11px sans-serif;padding:2px 0;z-index:10000;'
            f'border-radius:4px 4px 0 0;">{label}</div>'
            f'<img src="data:image/{mime};base64,{b64}" '
            f'style="position:fixed;top:28px;right:{right_offset}px;width:220px;'
            'border:2px solid #555;border-radius:0 0 4px 4px;z-index:9999;'
            'box-shadow:0 2px 8px rgba(0,0,0,0.6);">'
        )

    inject = (
        _b64_img(color_png,    "RGB input",       10)
        + _b64_img(ortho_front, "Ortho — front",  240)
    )

    if inject:
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html.replace("</body>", inject + "</body>"))
        print(f"  Overlays injected (RGB + ortho views)")

    print(f"  Viewer -> {html_path}")
    webbrowser.open("file:///" + html_path.replace(os.sep, "/").replace(" ", "%20"))


# ── Main pipeline ─────────────────────────────────────────────────────────────

def process(ply_path, open_viewer=True,
            depth_min_m=None, depth_max_m=0.67,
            x_min_m=-0.12, x_max_m=0.12,
            z_min_m=-0.1,  z_max_m=0.1):
    """
    depth_min_m / depth_max_m — depth (camera Z) range in metres
    x_min_m / x_max_m         — X bounding box in metres (default -8 cm to +12 cm)
    z_min_m / z_max_m         — viewer Z (up) bounding box in metres (default -0.1 to +0.1)
                                 viewer Z = -camera_y, so z_min=-0.1 keeps points up to
                                 10 cm below camera, z_max=+0.1 up to 10 cm above.
    """
    print(f"\nLoading {ply_path} ...")
    points, colors = _load_ply(ply_path)
    print(f"  Total points: {len(points):,}")

    # Depth filter — remove far background and optionally near noise
    print("\nDepth filter")
    if depth_max_m is None:
        depth_max_m = auto_depth_max(points)
    if depth_min_m is not None:
        points, colors = apply_depth_min(points, colors, depth_min_m)
        if len(points) == 0:
            print("  No points remain after min-depth filter.")
            return
    if depth_max_m is not None:
        points, colors = apply_depth_max(points, colors, depth_max_m)
        if len(points) == 0:
            print("  No points remain after max-depth filter.")
            return

    # X bounding box  (camera_x = -viewer_x, but symmetric range so same)
    print("\nX bounding box")
    x_mask = (points[:, 0] >= x_min_m) & (points[:, 0] <= x_max_m)
    print(f"  X in [{x_min_m*100:.0f}, {x_max_m*100:.0f}] cm: "
          f"{x_mask.sum():,} / {len(points):,} kept")
    points, colors = points[x_mask], colors[x_mask]
    if len(points) == 0:
        print("  No points remain in X range.")
        return

    # Up (viewer Z) bounding box — viewer_z = -camera_y
    # z_min_m=-0.1, z_max_m=0.1  keeps viewer Z in [-0.1, +0.1] m
    print("\nUp (Z) bounding box")
    camera_y_min = -z_max_m   # viewer_z = -camera_y → camera_y = -viewer_z
    camera_y_max = -z_min_m
    z_mask = (points[:, 1] >= camera_y_min) & (points[:, 1] <= camera_y_max)
    print(f"  Viewer Z in [{z_min_m*100:.0f}, {z_max_m*100:.0f}] cm: "
          f"{z_mask.sum():,} / {len(points):,} kept")
    points, colors = points[z_mask], colors[z_mask]
    if len(points) == 0:
        print("  No points remain in Z range.")
        return

    print(f"\n  Remaining: {len(points):,} points")
    print("\nBounding box:")
    print_bbox(points)

    base      = os.path.splitext(ply_path)[0]
    out_ply   = base + "_foreground.ply"
    out_html  = base + "_foreground_viewer.html"
    color_png = base + "_color.png"

    print()
    _save_ply(out_ply, points, colors)

    print("\nStep 3 — orthographic projections")
    ortho_top, ortho_front = save_ortho_views(points, colors, base)

    if open_viewer:
        _visualize(points, colors,
                   title=f"Foreground — {len(points):,} pts",
                   html_path=out_html,
                   color_png=color_png    if os.path.exists(color_png)    else None,
                   ortho_top=None,
                   ortho_front=ortho_front if os.path.exists(ortho_front) else None)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Remove floor and background from a point cloud by depth + height")
    parser.add_argument("ply", nargs="?", default=None)
    parser.add_argument("--capture", action="store_true",
                        help="Capture live from Orbbec first")
    parser.add_argument("--no-view", action="store_true")
    parser.add_argument("--depth-min", type=float, default=None, metavar="CM",
                        help="Minimum depth in cm — removes points closer than this")
    parser.add_argument("--depth-max", type=float, default=67.0, metavar="CM",
                        help="Maximum depth in cm (default: 67)")
    parser.add_argument("--x-min",  type=float, default=-12.0, metavar="CM",
                        help="X bounding box min in cm (default: -12)")
    parser.add_argument("--x-max",  type=float, default=12.0,  metavar="CM",
                        help="X bounding box max in cm (default: +12)")
    parser.add_argument("--z-min",  type=float, default=-10.0, metavar="CM",
                        help="Viewer Z (up) bounding box min in cm (default: -10)")
    parser.add_argument("--z-max",  type=float, default=10.0,  metavar="CM",
                        help="Viewer Z (up) bounding box max in cm (default: +10)")
    args = parser.parse_args()

    if args.capture:
        import subprocess
        py  = r"C:\Users\Bhavana\AppData\Local\Python\pythoncore-3.14-64\python.exe"
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        ply = os.path.join(HERE, f"capture_{ts}.ply")
        r   = subprocess.run([py, os.path.join(HERE, "capture_pointcloud.py"),
                              "--camera", "orbbec", "--rgb", "-o", ply])
        if r.returncode != 0 or not os.path.exists(ply):
            print("Capture failed.")
            sys.exit(1)
    elif args.ply:
        ply = args.ply
    else:
        parser.print_help()
        sys.exit(1)

    process(
        ply,
        open_viewer = not args.no_view,
        depth_min_m = args.depth_min / 100.0 if args.depth_min is not None else None,
        depth_max_m = args.depth_max / 100.0 if args.depth_max is not None else None,
        x_min_m     = args.x_min / 100.0,
        x_max_m     = args.x_max / 100.0,
        z_min_m     = args.z_min / 100.0,
        z_max_m     = args.z_max / 100.0,
    )
