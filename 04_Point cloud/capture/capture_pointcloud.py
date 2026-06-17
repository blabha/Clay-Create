"""
Capture a point cloud from a depth camera and save as .ply file.
Supports Intel RealSense (--camera realsense) and Orbbec (--camera orbbec).

Requirements:
    pip install pyrealsense2 numpy plotly openni opencv-python
"""

import numpy as np
from datetime import datetime
import sys
import math
import os


# ── PLY I/O ──────────────────────────────────────────────────────────────────

def save_ply(path: str, points: np.ndarray, colors: np.ndarray,
             normals: np.ndarray = None, labels: np.ndarray = None):
    assert len(points) == len(colors)
    n = len(points)
    extra_props = ""
    if normals is not None:
        extra_props += "property float nx\nproperty float ny\nproperty float nz\n"
    if labels is not None:
        extra_props += "property uchar label\n"
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {n}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property uchar red\n"
        "property uchar green\n"
        "property uchar blue\n"
        + extra_props +
        "end_header\n"
    )
    dtype = [("x","<f4"),("y","<f4"),("z","<f4"),
             ("r","u1"),("g","u1"),("b","u1")]
    if normals is not None:
        dtype += [("nx","<f4"),("ny","<f4"),("nz","<f4")]
    if labels is not None:
        dtype += [("label","u1")]
    data = np.zeros(n, dtype=dtype)
    data["x"] = points[:, 0].astype(np.float32)
    data["y"] = points[:, 1].astype(np.float32)
    data["z"] = points[:, 2].astype(np.float32)
    data["r"] = colors[:, 0].astype(np.uint8)
    data["g"] = colors[:, 1].astype(np.uint8)
    data["b"] = colors[:, 2].astype(np.uint8)
    if normals is not None:
        data["nx"] = normals[:, 0].astype(np.float32)
        data["ny"] = normals[:, 1].astype(np.float32)
        data["nz"] = normals[:, 2].astype(np.float32)
    if labels is not None:
        data["label"] = labels.astype(np.uint8)
    with open(path, "wb") as f:
        f.write(header.encode("ascii"))
        f.write(data.tobytes())
    print(f"Saved {n:,} points -> {path}")


def load_ply(path: str):
    with open(path, "rb") as f:
        n = None
        props = []
        while True:
            line = f.readline().decode("ascii").strip()
            if line.startswith("element vertex"):
                n = int(line.split()[-1])
            if line.startswith("property"):
                props.append(line.split()[-1])
            if line == "end_header":
                break
        has_normals = "nx" in props
        has_labels  = "label" in props
        dtype_fields = [("x","<f4"),("y","<f4"),("z","<f4"),
                        ("r","u1"),("g","u1"),("b","u1")]
        if has_normals:
            dtype_fields += [("nx","<f4"),("ny","<f4"),("nz","<f4")]
        if has_labels:
            dtype_fields += [("label","u1")]
        dtype = np.dtype(dtype_fields)
        data = np.frombuffer(f.read(n * dtype.itemsize), dtype=dtype)
    points  = np.stack([data["x"], data["y"], data["z"]], axis=-1)
    colors  = np.stack([data["r"], data["g"], data["b"]], axis=-1)
    normals = np.stack([data["nx"], data["ny"], data["nz"]], axis=-1) if has_normals else None
    labels  = data["label"].copy() if has_labels else None
    return points, colors, normals, labels


# ── Visualisation ─────────────────────────────────────────────────────────────

def visualize(path: str, min_depth_m: float = 0.6, max_depth_m: float = 8.0,
              show_rgb: bool = False):
    import plotly.graph_objects as go
    import webbrowser
    import os

    print(f"Loading {path} for visualisation...")
    points, colors, normals, labels = load_ply(path)
    print(f"  Raw points: {len(points):,}")

    # Clamp depth range
    mask   = (points[:, 2] >= min_depth_m) & (points[:, 2] <= max_depth_m)
    points = points[mask]
    colors = colors[mask]
    nrm    = normals[mask] if normals is not None else None
    lbl    = labels[mask]  if labels  is not None else None
    print(f"  After depth clamp ({min_depth_m*100:.0f}–{max_depth_m*100:.0f} cm): {len(points):,}")

    traces = []

    if lbl is not None:
        # One trace per color class so the legend shows class names
        for label_id, label_name in COLOR_LABELS.items():
            sel = lbl == label_id
            if not sel.any():
                continue
            p   = points[sel]
            rgb = COLOR_DISPLAY[label_id]
            hex_color = "#{:02x}{:02x}{:02x}".format(
                int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
            traces.append(go.Scatter3d(
                x=-p[:, 0], y=p[:, 2], z=-p[:, 1],
                mode="markers",
                marker=dict(size=1, color=hex_color, opacity=1.0),
                name=label_name,
            ))
        print(f"  Viewer: color-class mode ({len(traces)} classes)")
    elif show_rgb:
        # Encode each point's RGB as a hex string for Plotly
        packed = ((colors[:, 0].astype(np.uint32) << 16)
                | (colors[:, 1].astype(np.uint32) << 8)
                |  colors[:, 2].astype(np.uint32))
        hex_colors = ["#{:06x}".format(int(p)) for p in packed]
        traces.append(go.Scatter3d(
            x=-points[:, 0], y=points[:, 2], z=-points[:, 1],
            mode="markers",
            marker=dict(size=1, color=hex_colors, opacity=1.0),
            name="points",
        ))
        print(f"  Viewer: RGB camera colour mode")
    else:
        depth_mm  = points[:, 2] * 1000
        cycle_mm  = 200.0
        color_val = depth_mm % cycle_mm
        traces.append(go.Scatter3d(
            x=-points[:, 0], y=points[:, 2], z=-points[:, 1],
            mode="markers",
            marker=dict(size=1, color=color_val, colorscale="HSV",
                        cmin=0, cmax=cycle_mm, opacity=1.0,
                        colorbar=dict(title="Depth mod 200 mm")),
            name="points",
        ))

    if nrm is not None:
        # Show every 50th normal as a short line segment (avoids overloading renderer)
        step = max(1, len(points) // 2000)
        p  = points[::step]
        n  = nrm[::step]
        scale = 0.02
        # Build paired start/end/None arrays for line segments
        px = np.repeat(-p[:, 0], 3)
        py = np.repeat( p[:, 2], 3)
        pz = np.repeat(-p[:, 1], 3)
        ex = np.repeat(-(p[:, 0] + n[:, 0] * scale), 3)
        ey = np.repeat(  p[:, 2] + n[:, 2] * scale,  3)
        ez = np.repeat(-(p[:, 1] + n[:, 1] * scale), 3)
        xs = np.where(np.arange(len(px)) % 3 == 2, np.nan,
                      np.where(np.arange(len(px)) % 3 == 0, px, ex))
        ys = np.where(np.arange(len(py)) % 3 == 2, np.nan,
                      np.where(np.arange(len(py)) % 3 == 0, py, ey))
        zs = np.where(np.arange(len(pz)) % 3 == 2, np.nan,
                      np.where(np.arange(len(pz)) % 3 == 0, pz, ez))
        traces.append(go.Scatter3d(
            x=xs, y=ys, z=zs,
            mode="lines",
            line=dict(color="white", width=1),
            name="normals",
        ))
        print(f"  Showing {len(p):,} normal vectors (every {step}th point)")

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=path,
        scene=dict(
            xaxis_title="X (m)", yaxis_title="Depth (m)", zaxis_title="Up (m)",
            aspectmode="data",
            camera=dict(up=dict(x=0, y=0, z=1), eye=dict(x=0, y=-2, z=0.4),
                        projection=dict(type="orthographic")),
        ),
        margin=dict(l=0, r=0, b=0, t=40),
    )

    html_path = os.path.abspath(os.path.splitext(path)[0] + "_viewer.html")
    fig.write_html(html_path, auto_open=False)

    # Overlay the companion RGB image (saved alongside the PLY during capture)
    base = os.path.splitext(path)[0]
    color_img_path = base + "_color.png"
    # If viewing a filtered file (e.g. _white.ply), look for the parent's color image
    if not os.path.exists(color_img_path):
        for suffix in COLOR_LABELS.values():
            if base.endswith(f"_{suffix}"):
                color_img_path = base[: -len(suffix) - 1] + "_color.png"
                break
    if os.path.exists(color_img_path):
        import base64
        with open(color_img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        img_style = (
            "position:fixed;top:10px;right:10px;width:320px;"
            "border:2px solid #444;border-radius:4px;z-index:9999;"
            "box-shadow:0 2px 8px rgba(0,0,0,0.6);"
        )
        label_style = (
            "position:fixed;top:10px;right:10px;width:320px;text-align:center;"
            "color:#ccc;font-family:sans-serif;font-size:11px;"
            "z-index:10000;pointer-events:none;"
        )
        inject = (
            f'<div style="{label_style}">RGB input</div>'
            f'<img src="data:image/png;base64,{img_b64}" style="{img_style}" title="RGB input">'
        )
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("</body>", inject + "</body>")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  RGB image overlaid from {os.path.basename(color_img_path)}")

    print(f"Viewer saved -> {html_path}")
    url = "file:///" + html_path.replace(os.sep, "/").replace(" ", "%20")
    webbrowser.open(url)
    print("Opened in browser. If it didn't appear, open the file manually.")


# ── Shared projection helper ──────────────────────────────────────────────────

def _project(avg_depth: np.ndarray, color_image: np.ndarray,
             depth_scale: float, fx: float, fy: float,
             cx: float, cy: float):
    """Back-project a depth map to a coloured 3-D point cloud."""
    h, w = avg_depth.shape
    uu, vv = np.meshgrid(np.arange(w), np.arange(h))
    z = avg_depth * depth_scale
    valid = z > 0
    x = (uu[valid] - cx) * z[valid] / fx
    y = (vv[valid] - cy) * z[valid] / fy
    points = np.stack([x, y, z[valid]], axis=-1)
    colors = color_image[valid]
    return points, colors


# ── Depth hole filling ───────────────────────────────────────────────────────

def fill_depth_holes(depth_mm: np.ndarray, inpaint_radius: int = 6) -> np.ndarray:
    """Fill zero-depth pixels by inpainting from surrounding valid pixels."""
    import cv2
    d16 = np.clip(depth_mm, 0, 65535).astype(np.uint16)
    missing = (d16 == 0).astype(np.uint8)
    n_missing = int(missing.sum())
    if n_missing == 0:
        return depth_mm
    filled = cv2.inpaint(d16, missing, inpaintRadius=inpaint_radius, flags=cv2.INPAINT_NS)
    result = depth_mm.copy()
    result[missing.astype(bool)] = filled[missing.astype(bool)]
    n_filled = int((result > 0).sum()) - int((depth_mm > 0).sum())
    print(f"  Depth hole fill: recovered {n_filled:,} / {n_missing:,} missing pixels")
    return result


# ── Statistical Outlier Removal ───────────────────────────────────────────────

def remove_outliers(points: np.ndarray, colors: np.ndarray,
                    k: int = 20, std_ratio: float = 2.0):
    """Remove flying pixels: drop points whose mean kNN distance exceeds mean + std_ratio*std."""
    from scipy.spatial import KDTree
    if len(points) < k + 1:
        return points, colors
    print(f"  Outlier removal (k={k}, std={std_ratio}) on {len(points):,} points...")
    tree = KDTree(points)
    dists, _ = tree.query(points, k=k + 1)   # first hit is self (dist=0)
    mean_d = dists[:, 1:].mean(axis=1)
    threshold = mean_d.mean() + std_ratio * mean_d.std()
    keep = mean_d < threshold
    print(f"  Kept {keep.sum():,} / {len(points):,} points "
          f"({100*keep.sum()/len(points):.1f} %)")
    return points[keep], colors[keep]


# ── Polygon crop ─────────────────────────────────────────────────────────────

def crop_to_polygon(points: np.ndarray, colors: np.ndarray,
                    corners, normals: np.ndarray = None):
    """Keep only points whose (plotly_x, depth) = (-px, pz) falls inside the polygon.

    corners: sequence of (plotly_x, depth_m) pairs matching the viewer tooltip values.
    """
    import matplotlib.path as mpath
    verts = list(corners) + [corners[0]]
    codes = ([mpath.Path.MOVETO]
             + [mpath.Path.LINETO] * (len(corners) - 1)
             + [mpath.Path.CLOSEPOLY])
    poly = mpath.Path(verts, codes)
    plotly_xy = np.stack([-points[:, 0], points[:, 2]], axis=1)
    mask = poly.contains_points(plotly_xy)
    print(f"  Crop: kept {mask.sum():,} / {len(points):,} points inside polygon")
    nrm = normals[mask] if normals is not None else None
    return points[mask], colors[mask], nrm


# ── Color classification ──────────────────────────────────────────────────────

COLOR_LABELS = {
    0:  "unknown",
    1:  "red",
    2:  "orange",
    3:  "yellow",
    4:  "green",
    5:  "cyan",
    6:  "blue",
    7:  "purple",
    8:  "magenta",
    9:  "white",
    10: "grey",
    11: "black",
}

# Display color for each label in the viewer (RGB 0-1)
COLOR_DISPLAY = {
    0:  (0.5, 0.5, 0.5),
    1:  (1.0, 0.1, 0.1),
    2:  (1.0, 0.5, 0.0),
    3:  (1.0, 1.0, 0.0),
    4:  (0.0, 0.8, 0.0),
    5:  (0.0, 0.9, 0.9),
    6:  (0.1, 0.1, 1.0),
    7:  (0.6, 0.0, 0.8),
    8:  (1.0, 0.0, 0.8),
    9:  (1.0, 1.0, 1.0),
    10: (0.5, 0.5, 0.5),
    11: (0.1, 0.1, 0.1),
}


def classify_by_color(colors: np.ndarray) -> np.ndarray:
    """Assign each point a color label (0-11) based on its RGB value via HSV thresholds."""
    rgb = colors.astype(np.float32) / 255.0
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]

    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    # Value and saturation
    v = cmax
    s = np.where(cmax > 0, delta / cmax, 0.0)

    # Hue (0-360)
    h = np.zeros(len(r), dtype=np.float32)
    m = delta > 0
    mr = m & (cmax == r)
    mg = m & (cmax == g)
    mb = m & (cmax == b)
    h[mr] = (60 * ((g[mr] - b[mr]) / delta[mr])) % 360
    h[mg] = (60 * ((b[mg] - r[mg]) / delta[mg]) + 120)
    h[mb] = (60 * ((r[mb] - g[mb]) / delta[mb]) + 240)

    labels = np.zeros(len(r), dtype=np.uint8)

    # Achromatic: white / grey / black
    # Grey catches all low-saturation pixels first, then white overrides the bright end.
    achromatic = s < 0.15
    labels[achromatic & (v >= 0.20)] = 10  # grey (default for low-saturation bright pixels)
    labels[achromatic & (v < 0.20)]  = 11  # black
    # White: must be very bright (V >= 0.90) AND nearly colourless (S < 0.08)
    labels[(s < 0.08) & (v >= 0.90)] = 9   # white (strict)

    # Chromatic by hue
    chrom = ~achromatic
    labels[chrom & ((h < 15)  | (h >= 345))] = 1   # red
    labels[chrom & (h >= 15)  & (h < 45)]   = 2    # orange
    labels[chrom & (h >= 45)  & (h < 75)]   = 3    # yellow
    labels[chrom & (h >= 75)  & (h < 165)]  = 4    # green
    labels[chrom & (h >= 165) & (h < 195)]  = 5    # cyan
    labels[chrom & (h >= 195) & (h < 255)]  = 6    # blue
    labels[chrom & (h >= 255) & (h < 285)]  = 7    # purple
    labels[chrom & (h >= 285) & (h < 345)]  = 8    # magenta

    counts = {COLOR_LABELS[i]: int((labels == i).sum())
              for i in range(12) if (labels == i).sum() > 0}
    print(f"  Color classes: { {k: f'{v:,}' for k, v in counts.items()} }")
    return labels


# ── Color filter ─────────────────────────────────────────────────────────────

def filter_by_color(points: np.ndarray, colors: np.ndarray,
                    color_name: str, normals: np.ndarray = None,
                    labels: np.ndarray = None):
    """Keep only points whose color class matches color_name (e.g. 'white')."""
    label_id = next((k for k, v in COLOR_LABELS.items() if v == color_name.lower()), None)
    if label_id is None:
        valid = ", ".join(v for v in COLOR_LABELS.values() if v != "unknown")
        print(f"  Unknown color '{color_name}'. Valid options: {valid}")
        return points, colors, normals, labels
    if labels is None:
        labels = classify_by_color(colors)
    mask = labels == label_id
    print(f"  Filter '{color_name}': kept {mask.sum():,} / {len(points):,} points")
    nrm = normals[mask] if normals is not None else None
    return points[mask], colors[mask], nrm, labels[mask]


# ── DBSCAN spatial clustering ─────────────────────────────────────────────────

def find_largest_cluster(points: np.ndarray, colors: np.ndarray,
                         normals: np.ndarray = None, labels: np.ndarray = None,
                         eps_cm: float = 3.0, min_samples: int = 10):
    """Return only the largest spatial cluster in points using DBSCAN.

    eps_cm: max neighbour distance in cm (3 cm works well for desktop objects).
    Points labelled -1 by DBSCAN (noise) are discarded.
    """
    try:
        from sklearn.cluster import DBSCAN
    except ImportError:
        print("  scikit-learn not found — skipping DBSCAN (pip install scikit-learn)")
        return points, colors, normals, labels

    eps_m = eps_cm / 100.0
    print(f"  DBSCAN clustering (eps={eps_cm:.1f} cm, min_samples={min_samples}) "
          f"on {len(points):,} points...")
    db = DBSCAN(eps=eps_m, min_samples=min_samples, n_jobs=-1).fit(points)
    ids = db.labels_

    unique, counts = np.unique(ids[ids >= 0], return_counts=True)
    if len(unique) == 0:
        print("  No clusters found — returning all points unchanged.")
        return points, colors, normals, labels

    largest_id = unique[np.argmax(counts)]
    mask = ids == largest_id
    centroid = points[mask].mean(axis=0)
    radius = float(np.percentile(np.linalg.norm(points[mask] - centroid, axis=1), 85))
    print(f"  {len(unique)} cluster(s) found — largest: {mask.sum():,} points, "
          f"radius (85th pct) = {radius*100:.2f} cm")

    nrm = normals[mask] if normals is not None else None
    lbl = labels[mask]  if labels  is not None else None
    return points[mask], colors[mask], nrm, lbl


# ── Normal estimation ─────────────────────────────────────────────────────────

def compute_normals(points: np.ndarray, k: int = 30) -> np.ndarray:
    """PCA-based normal estimation; normals are oriented toward the camera origin."""
    from scipy.spatial import KDTree
    print(f"  Computing normals (k={k}) for {len(points):,} points...")
    tree = KDTree(points)
    _, idxs = tree.query(points, k=k)          # (N, k)
    neighbors = points[idxs]                   # (N, k, 3)
    centroid  = neighbors.mean(axis=1, keepdims=True)
    centered  = neighbors - centroid           # (N, k, 3)
    cov = np.einsum("nki,nkj->nij", centered, centered) / max(k - 1, 1)
    _, eigvecs = np.linalg.eigh(cov)           # ascending eigenvalues; [:,*,0] = smallest
    normals = eigvecs[:, :, 0].copy()          # (N, 3)
    # Orient toward camera (at origin): flip if pointing away
    flip = (normals * (-points)).sum(axis=1) < 0
    normals[flip] *= -1
    print(f"  Normals done.")
    return normals


# ── RealSense capture ─────────────────────────────────────────────────────────

def capture_realsense(output_path: str, num_frames: int,
                      denoise: bool = True, denoise_k: int = 20, denoise_std: float = 2.0,
                      crop_corners=None, with_normals: bool = False,
                      normals_k: int = 30, classify: bool = False) -> str:
    import pyrealsense2 as rs

    pipeline = rs.pipeline()
    config   = rs.config()
    config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16,  30)
    config.enable_stream(rs.stream.color, 640, 480, rs.format.rgb8, 30)

    print("Starting RealSense pipeline...")
    try:
        profile = pipeline.start(config)
    except RuntimeError as e:
        print(f"Failed to start RealSense: {e}")
        sys.exit(1)

    depth_scale = profile.get_device().first_depth_sensor().get_depth_scale()
    print(f"Depth scale: {depth_scale*1000:.4f} mm/unit")

    align    = rs.align(rs.stream.color)
    spatial  = rs.spatial_filter()
    temporal = rs.temporal_filter()
    holes    = rs.hole_filling_filter()

    try:
        print("Warming up (30 frames)...")
        for _ in range(30):
            pipeline.wait_for_frames()

        print(f"Capturing {num_frames} frame(s)...")
        depth_stack, color_image = [], None
        for _ in range(num_frames):
            frames  = pipeline.wait_for_frames()
            aligned = align.process(frames)
            d = aligned.get_depth_frame()
            c = aligned.get_color_frame()
            if not d or not c:
                continue
            d = spatial.process(d)
            d = temporal.process(d)
            d = holes.process(d)
            depth_stack.append(np.asanyarray(d.get_data()).astype(np.float32))
            if color_image is None:
                color_image = np.asanyarray(c.get_data())

        if not depth_stack or color_image is None:
            print("No valid frames captured.")
            sys.exit(1)

        intr = (profile.get_stream(rs.stream.color)
                       .as_video_stream_profile().get_intrinsics())
        points, colors = _project(
            np.mean(depth_stack, axis=0), color_image, depth_scale,
            intr.fx, intr.fy, intr.ppx, intr.ppy,
        )
        if denoise:
            points, colors = remove_outliers(points, colors, k=denoise_k, std_ratio=denoise_std)
        normals = None
        if crop_corners:
            points, colors, normals = crop_to_polygon(points, colors, crop_corners, normals)
        if with_normals:
            normals = compute_normals(points, k=normals_k)
        labels = classify_by_color(colors) if classify else None
        save_ply(output_path, points, colors, normals, labels)
        return output_path
    finally:
        pipeline.stop()
        print("RealSense stopped.")


# ── Orbbec capture ────────────────────────────────────────────────────────────

def capture_orbbec(output_path: str, num_frames: int, openni2_path: str = None,
                   color_cam_index: int = None,
                   denoise: bool = True, denoise_k: int = 20, denoise_std: float = 2.0,
                   crop_corners=None, with_normals: bool = False,
                   normals_k: int = 30, classify: bool = False,
                   pixel_roi=None) -> str:
    from openni import openni2
    import time

    import os
    default_search = [s for s in [os.environ.get("ASTRA_SDK_BIN")] if s] + [
        r"C:\Program Files\Orbbec\Astra SDK\lib",
        r"C:\Program Files (x86)\Orbbec\Astra SDK\lib",
        r"C:\Program Files\OpenNI2\Redist",
        r"C:\Program Files (x86)\OpenNI2\Redist",
    ]

    W, H = 640, 480

    # ── Initialise OpenNI2 ────────────────────────────────────────────────────
    print("Initialising OpenNI2 / Orbbec...")
    candidates = [openni2_path] + default_search if openni2_path else default_search + [None]
    initialized = False
    for candidate in candidates:
        try:
            if candidate:
                openni2.initialize(candidate)
            else:
                openni2.initialize()
            initialized = True
            if candidate:
                print(f"OpenNI2 loaded from: {candidate}")
            break
        except Exception:
            continue

    if not initialized:
        print("Failed to initialise OpenNI2.")
        print('  --openni2-path "C:\\path\\to\\OpenNI2\\lib"')
        sys.exit(1)

    device = None
    for attempt in range(5):
        try:
            device = openni2.Device.open_any()
            break
        except Exception:
            print(f"  Device not ready, retrying ({attempt+1}/5)...")
            time.sleep(2.0)
    if device is None:
        print("Could not open Orbbec device. Try unplugging and replugging the camera.")
        openni2.unload()
        sys.exit(1)
    print(f"Connected: {device.get_device_info()}")

    # ── Create both streams (registration must be set after both are created) ──
    depth_stream = device.create_depth_stream()

    color_stream = None
    try:
        from openni import _openni2 as c_api
        color_stream = device.create_color_stream()
        color_stream.set_video_mode(c_api.OniVideoMode(
            pixelFormat=c_api.OniPixelFormat.ONI_PIXEL_FORMAT_RGB888,
            resolutionX=W, resolutionY=H, fps=30,
        ))
    except Exception as e:
        print(f"  OpenNI2 color stream unavailable ({e}), falling back to OpenCV")
        color_stream = None

    # ── Enable depth-to-color registration (requires both streams created) ───
    registration_ok = False
    try:
        # Try integer value 1 directly — avoids enum import issues
        if device.is_image_registration_mode_supported(1):
            device.set_image_registration_mode(1)
            registration_ok = True
            print("  Depth-to-color registration: enabled")
        else:
            print("  Depth-to-color registration: not supported by device")
    except Exception as e:
        print(f"  Depth-to-color registration unavailable: {e}")

    # Start both streams after registration is configured
    depth_stream.start()
    if color_stream is not None:
        color_stream.start()
        print("  Color stream: OpenNI2")
    time.sleep(0.1)   # give hardware time to start streaming before first read

    # ── Read actual intrinsics from device property 14 ───────────────────────
    # Property 14 returns [color_fx, color_fy, color_cx, color_cy,
    #                       ir_fx,    ir_fy,    ir_cx,    ir_cy,   ...]
    # With depth-to-color registration on, use the colour-camera values (first 4).
    fx = fy = cx = cy = None
    try:
        import ctypes
        cal = device.get_property(14, ctypes.c_float * 9)
        if registration_ok:
            fx, fy, cx, cy = float(cal[0]), float(cal[1]), float(cal[2]), float(cal[3])
        else:
            fx, fy, cx, cy = float(cal[4]), float(cal[5]), float(cal[6]), float(cal[7])
        print(f"  Intrinsics from device (prop 14): fx={fx:.3f} fy={fy:.3f} "
              f"cx={cx:.3f} cy={cy:.3f}")
    except Exception as e:
        print(f"  Device intrinsics unavailable ({e}), falling back to FOV approx")

    if fx is None:
        ref = color_stream if (registration_ok and color_stream is not None) else depth_stream
        fov_h = ref.get_horizontal_fov()
        fov_v = ref.get_vertical_fov()
        fx = (W / 2) / math.tan(fov_h / 2)
        fy = (H / 2) / math.tan(fov_v / 2)
        cx, cy = W / 2.0, H / 2.0
        print(f"  Intrinsics (FOV approx): fx={fx:.3f} fy={fy:.3f} cx={cx:.3f} cy={cy:.3f}")

    depth_scale = 0.001

    try:
        print("Warming up (10 frames)...")
        warmed = 0
        for _ in range(30):
            try:
                depth_stream.read_frame()
                if color_stream is not None:
                    color_stream.read_frame()
                warmed += 1
                if warmed >= 10:
                    break
            except Exception:
                time.sleep(0.05)
        print(f"  Warm-up done ({warmed} frames).")

        print(f"Capturing {num_frames} frame(s)...")
        depth_stack = []
        color_image = None
        for i in range(num_frames):
            d_frame = depth_stream.read_frame()
            raw = np.frombuffer(
                d_frame.get_buffer_as_uint16(), dtype=np.uint16
            ).reshape((H, W)).astype(np.float32)
            depth_stack.append(raw)

            if color_stream is not None and color_image is None:
                c_frame = color_stream.read_frame()
                color_data = np.frombuffer(
                    c_frame.get_buffer_as_uint8(), dtype=np.uint8
                )
                color_image = color_data.reshape((H, W, 3)).copy()  # already RGB
                print(f"  Color frame captured from Orbbec: {color_image.shape}")

            print(f"  Depth frame {i+1}/{num_frames} captured.")

        # Fallback: OpenCV if OpenNI2 color failed
        if color_image is None:
            import cv2
            cam_idx = color_cam_index if color_cam_index is not None else 0
            print(f"  Capturing color via OpenCV index {cam_idx}...")
            cap = cv2.VideoCapture(cam_idx)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
            for _ in range(10):
                cap.read()
            ret, bgr = cap.read()
            cap.release()
            if ret:
                color_image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                print(f"  Color frame (OpenCV fallback): {color_image.shape}")
            else:
                print("  WARNING: no color frame — point cloud will be grey.")
                color_image = np.full((H, W, 3), 180, dtype=np.uint8)

        avg_depth = np.median(np.stack(depth_stack, axis=0), axis=0)
        print(f"  Valid depth pixels (before fill): {np.count_nonzero(avg_depth):,} / {W*H:,}")
        avg_depth = fill_depth_holes(avg_depth)
        print(f"  Valid depth pixels (after fill):  {np.count_nonzero(avg_depth):,} / {W*H:,}")

        _roi_crop = None
        if pixel_roi is not None:
            ru0 = max(0, pixel_roi[0]); rv0 = max(0, pixel_roi[1])
            ru1 = min(W, pixel_roi[2]); rv1 = min(H, pixel_roi[3])
            mask2d = np.zeros((H, W), dtype=bool)
            mask2d[rv0:rv1, ru0:ru1] = True
            avg_depth[~mask2d] = 0
            _roi_crop = (rv0, rv1, ru0, ru1)
            print(f"  Pixel ROI applied: only ({ru0},{rv0})→({ru1},{rv1}) projected to 3D")

        points, colors = _project(avg_depth, color_image, depth_scale, fx, fy, cx, cy)
        if denoise:
            points, colors = remove_outliers(points, colors, k=denoise_k, std_ratio=denoise_std)
        normals = None
        if crop_corners:
            points, colors, normals = crop_to_polygon(points, colors, crop_corners, normals)
        if with_normals:
            normals = compute_normals(points, k=normals_k)
        labels = classify_by_color(colors) if classify else None

        import cv2 as _cv2
        color_png = os.path.splitext(output_path)[0] + "_color.png"
        save_color = (color_image[_roi_crop[0]:_roi_crop[1], _roi_crop[2]:_roi_crop[3]]
                      if _roi_crop else color_image)
        _cv2.imwrite(color_png, _cv2.cvtColor(save_color, _cv2.COLOR_RGB2BGR))
        print(f"  Color image saved -> {color_png}")

        save_ply(output_path, points, colors, normals, labels)
        return output_path

    finally:
        depth_stream.stop()
        if color_stream is not None:
            color_stream.stop()
        device.close()
        openni2.unload()
        print("Orbbec stopped.")


# ── ZED capture ──────────────────────────────────────────────────────────────

def capture_zed(output_path: str, num_frames: int, serial_number: int = None,
                resolution: str = "HD720", depth_mode: str = "ULTRA",
                denoise: bool = True, denoise_k: int = 20, denoise_std: float = 2.0,
                crop_corners=None, with_normals: bool = False,
                normals_k: int = 30, classify: bool = False) -> str:
    try:
        import pyzed.sl as sl
    except ImportError:
        print("pyzed not installed.")
        print("1. Install the ZED SDK from https://www.stereolabs.com/developers/release")
        print("2. Then: pip install pyzed  (or run get_python_api.py from the SDK)")
        sys.exit(1)
    import cv2

    cam = sl.Camera()
    init = sl.InitParameters()

    res_map = {
        "WVGA":  sl.RESOLUTION.WVGA,
        "HD720": sl.RESOLUTION.HD720,
        "HD1080": sl.RESOLUTION.HD1080,
        "HD2K":  sl.RESOLUTION.HD2K,
    }
    mode_map = {
        "PERFORMANCE": sl.DEPTH_MODE.PERFORMANCE,
        "QUALITY":     sl.DEPTH_MODE.QUALITY,
        "ULTRA":       sl.DEPTH_MODE.ULTRA,
        "NEURAL":      sl.DEPTH_MODE.NEURAL,
    }
    init.camera_resolution     = res_map.get(resolution.upper(), sl.RESOLUTION.HD720)
    init.depth_mode            = mode_map.get(depth_mode.upper(), sl.DEPTH_MODE.ULTRA)
    init.coordinate_units      = sl.UNIT.METER
    init.depth_minimum_distance = 0.1
    init.depth_maximum_distance = 20.0
    if serial_number:
        init.set_from_serial_number(serial_number)

    label = f"ZED SN:{serial_number}" if serial_number else "ZED"
    print(f"Opening {label} ({resolution}, depth={depth_mode})...")
    status = cam.open(init)
    if status != sl.ERROR_CODE.SUCCESS:
        print(f"Failed to open ZED: {status}")
        sys.exit(1)

    info   = cam.get_camera_information()
    calib  = info.camera_configuration.calibration_parameters.left_cam
    fx, fy, cx, cy = calib.fx, calib.fy, calib.cx, calib.cy
    W = info.camera_configuration.resolution.width
    H = info.camera_configuration.resolution.height
    print(f"  Model: {info.camera_model}  SN: {info.serial_number}")
    print(f"  {W}x{H}  fx={fx:.1f}  fy={fy:.1f}  cx={cx:.1f}  cy={cy:.1f}")

    runtime = sl.RuntimeParameters()
    img_mat   = sl.Mat()
    depth_mat = sl.Mat()

    try:
        print("Warming up (30 frames)...")
        for _ in range(30):
            cam.grab(runtime)

        print(f"Capturing {num_frames} frame(s)...")
        depth_stack, color_image = [], None
        for i in range(num_frames):
            if cam.grab(runtime) == sl.ERROR_CODE.SUCCESS:
                if color_image is None:
                    cam.retrieve_image(img_mat, sl.VIEW.LEFT)
                    bgra = img_mat.get_data()
                    color_image = cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGB)
                cam.retrieve_measure(depth_mat, sl.MEASURE.DEPTH)
                d = depth_mat.get_data().copy().astype(np.float32)
                d = np.nan_to_num(d, nan=0.0, posinf=0.0, neginf=0.0)
                depth_stack.append(d)
                print(f"  Frame {i+1}/{num_frames}  non-zero: {np.count_nonzero(d):,}")

        if not depth_stack or color_image is None:
            print("No valid frames captured.")
            sys.exit(1)

        avg_depth = np.mean(depth_stack, axis=0)
        print(f"  Averaged depth  non-zero: {np.count_nonzero(avg_depth):,} / {W*H:,}")

        # ZED depth is already in metres — depth_scale = 1.0
        points, colors = _project(avg_depth, color_image, 1.0, fx, fy, cx, cy)

        if denoise:
            points, colors = remove_outliers(points, colors, k=denoise_k, std_ratio=denoise_std)
        normals = None
        if crop_corners:
            points, colors, normals = crop_to_polygon(points, colors, crop_corners, normals)
        if with_normals:
            normals = compute_normals(points, k=normals_k)
        labels = classify_by_color(colors) if classify else None
        save_ply(output_path, points, colors, normals, labels)
        return output_path

    finally:
        cam.close()
        print("ZED closed.")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Capture depth-camera point cloud")
    parser.add_argument("--camera", choices=["realsense", "orbbec", "zed"], default="orbbec",
                        help="Camera backend (default: orbbec)")
    parser.add_argument("-o", "--output", default=None, help="Output .ply file path")
    parser.add_argument("-n", "--frames", type=int, default=20,
                        help="Depth frames to average (default: 20, more = fewer holes)")
    parser.add_argument("--view", action="store_true", default=True,
                        help="Open interactive 3D viewer after saving (default: on)")
    parser.add_argument("--view-only", metavar="FILE",
                        help="Skip capture — just visualise an existing .ply file")
    parser.add_argument("--process", metavar="FILE",
                        help="Crop / add normals to an existing .ply file without recapturing")
    parser.add_argument("--openni2-path", default=None, metavar="DIR",
                        help="Path to folder containing OpenNI2.dll (Orbbec only)")
    parser.add_argument("--color-cam", type=int, default=None, metavar="N",
                        help="Force OpenCV camera index for Orbbec color stream (overrides auto-detect)")
    parser.add_argument("--serial", type=int, default=16603007, metavar="SN",
                        help="ZED camera serial number (default: 16603007)")
    parser.add_argument("--zed-resolution", default="HD720",
                        choices=["WVGA", "HD720", "HD1080", "HD2K"],
                        help="ZED capture resolution (default: HD720)")
    parser.add_argument("--zed-depth-mode", default="ULTRA",
                        choices=["PERFORMANCE", "QUALITY", "ULTRA", "NEURAL"],
                        help="ZED depth quality mode (default: ULTRA)")
    parser.add_argument("--min-depth", type=float, default=60.0, metavar="CM",
                        help="Minimum depth in cm (default: 60, Astra minimum range)")
    parser.add_argument("--max-depth", type=float, default=800.0, metavar="CM",
                        help="Maximum depth in cm (default: 800, Astra maximum range)")
    parser.add_argument("--no-denoise", action="store_true",
                        help="Skip statistical outlier removal (keep all noisy points)")
    parser.add_argument("--denoise-k", type=int, default=20, metavar="K",
                        help="kNN neighbours for outlier removal (default: 20, lower = keep more points)")
    parser.add_argument("--denoise-std", type=float, default=3.0, metavar="S",
                        help="Std-ratio threshold for outlier removal (default: 3.0, lower = stricter)")
    parser.add_argument("--crop", nargs=4, metavar="X,Y",
                        help='Crop to polygon: 4 "plotly_x,depth_m" corners from the viewer tooltip '
                             '(e.g. --crop "-0.038,1.093" "0.080,1.098" "0.874,1.096" "-0.059,1.096")')
    parser.add_argument("--normals", action="store_true",
                        help="Compute and save surface normals (nx ny nz) for each point")
    parser.add_argument("--normals-k", type=int, default=30, metavar="K",
                        help="kNN neighbourhood size for normal estimation (default: 30)")
    parser.add_argument("--classify", action="store_true",
                        help="Classify each point by colour (red/green/blue/etc.) and save label")
    parser.add_argument("--filter-color", default=None, metavar="COLOR",
                        help="Keep only points of this colour class (e.g. white, red, green). "
                             "Implies --classify. Valid: red orange yellow green cyan blue purple magenta white grey black")
    parser.add_argument("--rgb", action="store_true",
                        help="Colour the viewer with actual camera RGB instead of depth rainbow")
    args = parser.parse_args()

    # Parse --crop corners  "x,y" -> list of (float, float)
    crop_corners = None
    if args.crop:
        try:
            crop_corners = [tuple(float(v) for v in s.split(",")) for s in args.crop]
        except ValueError:
            print("ERROR: --crop values must be in 'x,y' format, e.g. -0.038,1.093")
            sys.exit(1)

    if args.view_only:
        visualize(args.view_only, min_depth_m=args.min_depth/100, max_depth_m=args.max_depth/100, show_rgb=args.rgb)
        sys.exit(0)

    if args.process:
        print(f"Processing {args.process} ...")
        points, colors, normals, labels = load_ply(args.process)
        print(f"  Loaded {len(points):,} points")
        if crop_corners:
            points, colors, normals = crop_to_polygon(points, colors, crop_corners, normals)
        if args.normals:
            normals = compute_normals(points, k=args.normals_k)
        if args.classify or args.filter_color:
            labels = classify_by_color(colors)
        if args.filter_color:
            points, colors, normals, labels = filter_by_color(
                points, colors, args.filter_color, normals, labels)
        out = args.output or (
            os.path.splitext(args.process)[0]
            + ("_cropped"              if crop_corners     else "")
            + ("_normals"              if args.normals      else "")
            + ("_classified"           if args.classify     else "")
            + (f"_{args.filter_color}" if args.filter_color else "")
            + ".ply"
        )
        save_ply(out, points, colors, normals, labels)
        if args.view:
            visualize(out, min_depth_m=args.min_depth/100, max_depth_m=args.max_depth/100, show_rgb=args.rgb)
        sys.exit(0)

    if args.output is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = f"pointcloud_{args.camera}_{ts}.ply"

    capture_kwargs = dict(
        denoise=not args.no_denoise,
        denoise_k=args.denoise_k,
        denoise_std=args.denoise_std,
        crop_corners=crop_corners,
        with_normals=args.normals,
        normals_k=args.normals_k,
        classify=args.classify or bool(args.filter_color),
    )

    if args.camera == "zed":
        saved = capture_zed(output_path=args.output, num_frames=args.frames,
                            serial_number=args.serial,
                            resolution=args.zed_resolution,
                            depth_mode=args.zed_depth_mode,
                            **capture_kwargs)
    elif args.camera == "orbbec":
        saved = capture_orbbec(output_path=args.output, num_frames=args.frames,
                               openni2_path=args.openni2_path,
                               color_cam_index=args.color_cam,
                               **capture_kwargs)
    else:
        saved = capture_realsense(output_path=args.output, num_frames=args.frames,
                                  **capture_kwargs)

    if args.filter_color:
        print(f"\nPost-processing {saved}...")
        points, colors, normals, labels = load_ply(saved)

        if labels is None:
            labels = classify_by_color(colors)

        points, colors, normals, labels = filter_by_color(
            points, colors, args.filter_color, normals, labels)
        base = os.path.splitext(saved)[0]
        for name in COLOR_LABELS.values():
            if base.endswith(f"_{name}"):
                base = base[: -len(name) - 1]
                break
        filtered_path = f"{base}_{args.filter_color}.ply"
        save_ply(filtered_path, points, colors, normals, labels)
        saved = filtered_path

    if args.view:
        visualize(saved, min_depth_m=args.min_depth/100, max_depth_m=args.max_depth/100, show_rgb=args.rgb)
    else:
        print("Done. Run with --view to open the interactive viewer.")
