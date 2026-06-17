"""
Detect and segment an object from the Orbbec Astra feed,
then extract and visualise only that object's point cloud.

Usage:
    python segment_pointcloud.py                     # detect all, pick interactively
    python segment_pointcloud.py --class person
    python segment_pointcloud.py --class chair --conf 0.5
    python segment_pointcloud.py --all               # extract every detected object
"""

import numpy as np
import cv2
import sys
import math
import time
import os
import webbrowser
from datetime import datetime


def remove_outliers(points, colors, k=20, std_ratio=2.0):
    from scipy.spatial import KDTree
    if len(points) < k + 1:
        return points, colors
    print(f"  Outlier removal (k={k}, std={std_ratio}) on {len(points):,} points...")
    tree = KDTree(points)
    dists, _ = tree.query(points, k=k + 1)
    mean_d = dists[:, 1:].mean(axis=1)
    threshold = mean_d.mean() + std_ratio * mean_d.std()
    keep = mean_d < threshold
    print(f"  Kept {keep.sum():,} / {len(points):,} points ({100*keep.sum()/len(points):.1f} %)")
    return points[keep], colors[keep]

OPENNI2_PATH = os.environ.get("ASTRA_SDK_BIN") or None
W, H = 640, 480


# ── Helpers ───────────────────────────────────────────────────────────────────

def save_ply(path, points, colors):
    n = len(points)
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {n}\n"
        "property float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\n"
        "end_header\n"
    )
    data = np.zeros(n, dtype=[("x","<f4"),("y","<f4"),("z","<f4"),
                               ("r","u1"),("g","u1"),("b","u1")])
    data["x"],data["y"],data["z"] = points[:,0],points[:,1],points[:,2]
    data["r"],data["g"],data["b"] = colors[:,0],colors[:,1],colors[:,2]
    with open(path, "wb") as f:
        f.write(header.encode())
        f.write(data.tobytes())
    print(f"  Saved {n:,} points -> {path}")


def project_masked(depth_mm, color_rgb, mask, fx, fy, cx, cy, depth_scale=0.001):
    """Back-project only pixels where mask=True into a coloured 3D point cloud."""
    uu, vv = np.meshgrid(np.arange(W), np.arange(H))
    z = depth_mm * depth_scale
    valid = (z > 0) & mask
    x = (uu[valid] - cx) * z[valid] / fx
    y = (vv[valid] - cy) * z[valid] / fy
    points = np.stack([x, y, z[valid]], axis=-1)
    colors = color_rgb[valid]
    return points, colors


def visualize(points, colors, title="Segmented point cloud"):
    import plotly.graph_objects as go
    depth_mm  = points[:, 2] * 1000
    color_val = depth_mm % 200.0

    fig = go.Figure(data=[go.Scatter3d(
        x=-points[:, 0], y=points[:, 2], z=-points[:, 1],
        mode="markers",
        marker=dict(size=1, color=color_val, colorscale="HSV",
                    cmin=0, cmax=200, opacity=1.0,
                    colorbar=dict(title="Depth mod 200 mm")),
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
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_title = title.replace(" ", "_").replace("/", "-")[:40]
    html_path = os.path.abspath(f"segmented_{safe_title}_{ts}_viewer.html")
    fig.write_html(html_path, auto_open=False)
    print(f"  Viewer -> {html_path}")
    webbrowser.open("file:///" + html_path.replace(os.sep, "/").replace(" ", "%20"))


# ── Step 1: capture colour frame ──────────────────────────────────────────────

def capture_color():
    print("Capturing colour frame...")
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
    for _ in range(10):
        cap.read()
    ret, bgr = cap.read()
    cap.release()
    if not ret:
        print("ERROR: could not read colour frame.")
        sys.exit(1)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    print(f"  Colour frame: {rgb.shape}")
    return rgb, bgr


# ── Step 2: YOLO segmentation ─────────────────────────────────────────────────

def run_segmentation(bgr, target_class=None, min_conf=0.4):
    from ultralytics import YOLO
    print("Running YOLO segmentation (downloading model on first run)...")
    model = YOLO("yolov8n-seg.pt")
    results = model(bgr, verbose=False)[0]

    detections = []
    if results.masks is None:
        print("  No objects detected.")
        return detections

    names = model.names
    for i, (box, mask_data) in enumerate(zip(results.boxes, results.masks.data)):
        cls_id   = int(box.cls[0])
        cls_name = names[cls_id]
        conf     = float(box.conf[0])
        if conf < min_conf:
            continue
        if target_class and cls_name.lower() != target_class.lower():
            continue
        # Resize mask to frame size (YOLO may output at different resolution)
        mask_np = mask_data.cpu().numpy()
        mask_resized = cv2.resize(mask_np, (W, H), interpolation=cv2.INTER_NEAREST)
        mask_bool = mask_resized > 0.5
        detections.append({
            "index":    i,
            "class":    cls_name,
            "conf":     conf,
            "mask":     mask_bool,
            "bbox":     box.xyxy[0].cpu().numpy().astype(int),
        })

    return detections


def pick_detection(detections):
    """Print detections and let the user pick one interactively."""
    print(f"\n  {len(detections)} object(s) detected:")
    for i, d in enumerate(detections):
        print(f"    [{i}] {d['class']}  conf={d['conf']:.2f}")
    if len(detections) == 1:
        print("  Only one object — selecting it automatically.")
        return [detections[0]]
    try:
        choice = input("\n  Enter index (or 'a' for all): ").strip()
    except (EOFError, KeyboardInterrupt):
        choice = "0"
    if choice.lower() == "a":
        return detections
    try:
        return [detections[int(choice)]]
    except (ValueError, IndexError):
        print("  Invalid choice, using first detection.")
        return [detections[0]]


# ── Step 3: capture depth frames ──────────────────────────────────────────────

def capture_depth(num_frames=10):
    from openni import openni2
    print("Capturing depth frames via OpenNI2...")
    time.sleep(1.0)
    openni2.initialize(OPENNI2_PATH)
    device = None
    for attempt in range(5):
        try:
            device = openni2.Device.open_any()
            break
        except Exception:
            print(f"  Retrying ({attempt+1}/5)...")
            time.sleep(2.0)
    if device is None:
        print("ERROR: Could not open Orbbec. Unplug and replug the camera.")
        openni2.unload()
        sys.exit(1)

    d = device.create_depth_stream()
    d.start()
    fov_h = d.get_horizontal_fov()
    fov_v = d.get_vertical_fov()
    fx = (W / 2) / math.tan(fov_h / 2)
    fy = (H / 2) / math.tan(fov_v / 2)
    cx, cy = W / 2.0, H / 2.0

    print("  Warming up (30 frames)...")
    for _ in range(30):
        d.read_frame()

    print(f"  Capturing {num_frames} frame(s)...")
    stack = []
    for i in range(num_frames):
        frame = d.read_frame()
        raw = np.frombuffer(frame.get_buffer_as_uint16(),
                            dtype=np.uint16).reshape((H, W)).astype(np.float32)
        stack.append(raw)
        print(f"    Frame {i+1}/{num_frames}")

    avg = np.mean(stack, axis=0)
    print(f"  Non-zero depth pixels: {np.count_nonzero(avg):,} / {W*H:,}")

    d.stop()
    device.close()
    openni2.unload()
    return avg, fx, fy, cx, cy


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Segment object -> point cloud")
    parser.add_argument("--class",    dest="cls", default=None,
                        help="Only extract this YOLO class (e.g. person, chair)")
    parser.add_argument("--conf",     type=float, default=0.4,
                        help="Minimum detection confidence (default: 0.4)")
    parser.add_argument("--all",      action="store_true",
                        help="Extract all detected objects (one file each)")
    parser.add_argument("--frames",   type=int, default=10,
                        help="Depth frames to average (default: 10)")
    args = parser.parse_args()

    # 1. Colour
    rgb, bgr = capture_color()

    # 2. Segment
    detections = run_segmentation(bgr, target_class=args.cls, min_conf=args.conf)
    if not detections:
        print("No matching objects detected. Try a different --class or lower --conf.")
        sys.exit(0)

    # Save annotated preview image
    preview = bgr.copy()
    for d in detections:
        x1,y1,x2,y2 = d["bbox"]
        cv2.rectangle(preview, (x1,y1), (x2,y2), (0,255,0), 2)
        cv2.putText(preview, f"{d['class']} {d['conf']:.2f}",
                    (x1, max(y1-8, 12)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
    preview_path = "detection_preview.png"
    cv2.imwrite(preview_path, preview)
    print(f"  Detection preview saved -> {preview_path}")

    # 3. Pick object(s)
    if args.all:
        chosen = detections
    else:
        chosen = pick_detection(detections)

    # 4. Depth
    depth_mm, fx, fy, cx, cy = capture_depth(num_frames=args.frames)

    # 5. For each chosen object: mask depth -> project -> save -> visualise
    for det in chosen:
        label = f"{det['class']}_conf{det['conf']:.2f}"
        print(f"\nExtracting point cloud for: {label}")
        points, colors = project_masked(depth_mm, rgb, det["mask"],
                                        fx, fy, cx, cy)
        if len(points) == 0:
            print("  No depth data under this mask — object may be out of range.")
            continue
        points, colors = remove_outliers(points, colors)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ply_path = f"segmented_{det['class']}_{ts}.ply"
        save_ply(ply_path, points, colors)
        visualize(points, colors, title=label)


if __name__ == "__main__":
    main()
