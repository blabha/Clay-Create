# Point Cloud Capture & Processing

Capture coloured 3-D point clouds from an Orbbec Astra depth camera, isolate a target object using a depth/height bounding box, and generate interactive HTML viewers, orthographic projections, and heightmaps.

---

## Folder layout

```
Point cloud/
├── python/               Entry-point scripts (run these)
│   ├── capture_grey_block.py   Capture + background removal in one step
│   ├── live_roi.py             Live camera feed — draw ROI to measure bounding box
│   ├── live_view.py            Quick depth-stream viewer
│   ├── orbbec_camera.py        Colour + depth stream viewer with snapshot
│   ├── segment_pointcloud.py   YOLO-based object segmentation → point cloud
│   └── ipad_stream.py          iPad LiDAR streaming via Record3D
├── capture/
│   └── capture_pointcloud.py   Low-level capture library (Orbbec / RealSense / ZED)
├── processing/
│   ├── detect_grey_block.py    Background removal by depth + height bounding box
│   ├── detect_homography.py    Plane fitting, rectification, and heightmap
│   ├── heatmap_foreground.py   Greyscale top-down heightmap from foreground PLY
│   └── live_roi.py             (processing copy — use python/live_roi.py instead)
├── batch files/              Windows batch launchers for each script
├── point clouds/             Output PLY files, colour PNGs, and HTML viewers
├── roi_config.txt            Bounding box saved by live_roi.py, read by capture_grey_block.py
└── requirements.txt
```

---

## Quick start

### 1. Measure the bounding box (once per setup)

Run `live_roi.bat` or:

```
python python\live_roi.py
```

- A live colour + depth window opens.
- Click and drag a rectangle around the target object.
- Press **S** to sample depth and compute the bounding box.
- The result is saved to `roi_config.txt` automatically.

Controls: `S` sample · `R` reset ROI · `Q` / `Esc` quit

---

### 2. Capture and remove background

Run `capture_grey_block.bat` or:

```
python python\capture_grey_block.py
```

Reads `roi_config.txt` for bounding box defaults. Override any parameter on the command line:

```
python python\capture_grey_block.py --depth-max 80 --x-min -10 --x-max 10 --z-min -5 --z-max 20
```

Output goes to `point clouds\capture_<timestamp>.ply` and `…_foreground.ply`.

| Flag | Default | Description |
|---|---|---|
| `-n` / `--frames` | 15 | Depth frames to average |
| `--depth-max CM` | 67 | Far background cutoff (cm) |
| `--depth-min CM` | — | Near noise cutoff (cm) |
| `--x-min / --x-max CM` | ±12 | Horizontal crop (cm) |
| `--z-min / --z-max CM` | ±10 | Vertical crop — viewer up/down (cm) |
| `--no-view` | — | Skip opening the HTML viewer |

---

### 3. Post-processing (optional)

**Plane rectification + heightmap**

```
detect_homography.bat                        # auto-picks latest *_foreground.ply
detect_homography.bat capture_XXX_foreground.ply
```

**Greyscale heightmap only**

```
heatmap_foreground.bat
heatmap_foreground.bat capture_XXX_foreground.ply
heatmap_foreground.bat capture_XXX_foreground.ply --res 1   # 1 mm/pixel
```

**Raw capture (no background removal)**

```
capture.bat                                  # saves to the current directory
```

---

## Installation

### Requirements

- Python 3.12 or 3.14
- Orbbec Astra SDK (OpenNI2 runtime) — install from the Orbbec website; the SDK path is auto-detected from common locations.

### Python packages

```
pip install -r requirements.txt
pip install openni plotly scipy scikit-learn
```

For YOLO segmentation (`segment_pointcloud.py`):

```
pip install ultralytics
```

For iPad streaming (`ipad_stream.py`):

```
pip install record3d open3d
```

---

## Workflow diagram

```
live_roi.py  ──►  roi_config.txt
                       │
                       ▼
         capture_grey_block.py
                │
        ┌───────┴────────┐
        ▼                ▼
  capture_*.ply    *_foreground.ply
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
    detect_homography  heatmap   HTML viewer
    (rectified.ply +  (_heightmap  (opens in
     heightmap)        .png)        browser)
```

---

## Grasshopper Integration

The point cloud pipeline feeds two heatmap images that Grasshopper reads to guide and monitor the carving process.

### Part 1 — Target Heatmap (AI-generated design)

Before carving begins, the Rashi AI pipeline converts a reference image into a depth-based heightmap and colour-maps it as a PNG. Grasshopper reads this file to define the intended carving geometry — it sets the target depth for every zone of the block.

**File path:**
```
z_Target heat_PNG_Outpumap_Colourt\target_heatmap.png
```

This file is written by the Rashi backend when a tile is assigned and is also served live at:
```
http://localhost:5000/api/target-heatmap
```

### Part 2 — Progress Heatmap (point cloud scan feedback)

While carving is in progress, every time hands leave the block for 5 seconds the Orbbec camera captures a new point cloud. That scan is converted into a colour heatmap showing the current clay surface depth. Grasshopper reads this file to compare the actual carved state against the target and provide real-time guidance during the session.

**File path:**
```
z_Target heatmap_Colour_PNG_Output\progress_heatmap.png
```

This file is updated after every triggered scan and is also served live at:
```
http://localhost:5000/api/progress-heatmap
```

### UDP Communication

Grasshopper can send and receive session state over UDP alongside the file-based workflow:

| Direction | Port | Purpose |
|---|---|---|
| Grasshopper → Xio | `6005` | Projection geometry (elements, curves, block index) |
| Xio → Grasshopper | `6006` | Session state updates |

Xio also writes `gh_state.json` after every update, which Grasshopper can poll every 200 ms as an alternative to the UDP socket.

---

## Output files

| Suffix | Description |
|---|---|
| `capture_<ts>.ply` | Full raw point cloud |
| `capture_<ts>_color.png` | Companion RGB frame |
| `capture_<ts>_foreground.ply` | Background-removed point cloud |
| `capture_<ts>_foreground_viewer.html` | Interactive 3-D viewer |
| `capture_<ts>_ortho_front.png` | Orthographic front-view image |
| `capture_<ts>_rectified.ply` | Plane-rectified point cloud |
| `capture_<ts>_rectified_heightmap.png` | Top-down greyscale heightmap |
