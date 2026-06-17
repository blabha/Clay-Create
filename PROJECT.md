# Clay Create — Hardware 3
**MRAC01 Hardware III Workshop · IAAC Barcelona**

A co-creative fabrication system where participants sculpt individual clay blocks that form a large wall relief. A depth camera scans each block; AI adapts the remaining designs to maintain continuity with what was actually carved.

---

## System Overview

```
iPad / Orbbec camera
        │
        ▼
03_Hands recognition / ipad_stream.py
  MediaPipe hand detection (background)
  ROI-gated capture trigger (5s absence)
        │
        ├──► z_Current Heatmap_PNG / current_heatmap.png
        │
        └──► scan.bat ──► capture_grey_block.py
                               │
                               ▼
                    z_Current Point cloud / current_pointcloud.ply
                               │
                               ▼
                    z_Target heat_PNG_Outpumap_Colourt / target_heatmap.png
                    z_Target heatmap_Colour_PNG_Output / progress_heatmap.png
                               │
        ┌──────────────────────┘
        ▼
01_Rashi_Interface  (AI depth pipeline)        http://localhost:5173
02_Xio-User-interface  (projection server)     http://localhost:5000/projection
```

---

## Modules

### 01_Rashi_Interface — AI Design Pipeline
FastAPI backend + Vite/React frontend.

| Component | Description |
|---|---|
| `AI-generation/backend/main.py` | FastAPI server on **port 8001** |
| `AI-generation/backend/pipeline/midas_processor.py` | MiDaS_small depth estimation (80% weight) |
| `AI-generation/backend/pipeline/tile_manager.py` | Tile state, harmonic interpolation, seam correction |
| `AI-generation/backend/pipeline/exporter.py` | PNG + OBJ export (150×150×30 mm) |
| `AI-generation/frontend/` | Vite/React UI on **port 5173** |
| `AI-generation/start.bat` | Launches both backend and frontend |

**Pipeline:**
1. User uploads reference image + wall dimensions (cols × rows)
2. Image centre-cropped, MiDaS estimates depth (80%) + luminance detail (20%)
3. CLAHE + Gaussian blur + gamma correction → final heightmap
4. Split into `cols × rows` tiles of 256×256 px

**Scan → adapt loop (per block):**
- Deviation = scanned − intended
- Harmonic interpolation regenerates all uncarved neighbours automatically
- Master heightmap updated after every scan

**Start:**
```
cd 01_Rashi_Interface/AI-generation/backend
venv\Scripts\python -m uvicorn main:app --port 8001

cd 01_Rashi_Interface/AI-generation/frontend
npm run dev
```

---

### 02_Xio-User-interface — Projection Interface
Flask + SocketIO server serving the projector HTML.

| File | Description |
|---|---|
| `app.py` | Flask server on **port 5000** |
| `ui/templates/projection.html` | Projector display |
| `ui/templates/pointcloud_viewer.html` | Live point cloud viewer |

**Key routes:**
| Route | Serves |
|---|---|
| `/projection` | Main projector view |
| `/api/target-heatmap` | `z_Target heat_PNG_Outpumap_Colourt\target_heatmap.png` |
| `/api/progress-heatmap` | `z_Target heatmap_Colour_PNG_Output\progress_heatmap.png` |
| `/api/current-pointcloud` | `z_Current Point cloud\current_pointcloud.ply` |
| `/pointcloud-viewer` | Three.js point cloud viewer |

**Auto-update:** `trigger_watcher` polls both heatmap files every 1 second — any file change fires a WebSocket `image_update` to refresh the projection instantly.

**Start:**
```
cd 02_Xio-User-interface
python app.py
```

**UDP communication:**
- Receives from Grasshopper on **port 6005**
- Sends to Grasshopper on **port 6006** (also writes `gh_state.json` polled every 200ms)

---

### 03_Hands recognition — Background Monitor
Orbbec camera feed with MediaPipe hand detection. Launched automatically by `scan.bat` after initial capture.

| File | Description |
|---|---|
| `ipad_stream.py` | Main background monitor |
| `test_logic.py` | Offline webcam test (no Orbbec needed) |

**Flow:**
1. Loads ROI from `04_Point cloud/roi_config.txt` (set during `scan.bat` Step 1)
2. Hand detection **active immediately** on startup
3. Hands absent ≥ 5 seconds → archives heatmap + triggers new scan
4. Timer resets when hands return — repeats indefinitely

**On trigger:**
- `z_Current Heatmap_PNG/current_heatmap.png` → archived to `z_History Heatmap_PNG/heatmap_YYYYMMDD_HHMMSS.png`
- Fresh ROI-cropped + left-right-flipped RGB saved as new `current_heatmap.png`
- Orbbec camera released → `capture_grey_block.py --no-view` runs → camera reclaimed

**Run with Python 3.11:**
```
py -3.11 "03_Hands recognition/ipad_stream.py"
```

---

### 04_Point cloud — Orbbec Capture Pipeline

| File | Description |
|---|---|
| `batch files/scan.bat` | Full scan workflow (3 steps) |
| `python/live_roi.py` | Interactive ROI selection → saves `roi_config.txt` |
| `python/capture_grey_block.py` | Capture + background removal |
| `python/capture_pointcloud.py` | Raw Orbbec frame capture |
| `processing/detect_grey_block.py` | Foreground isolation, floor removal, save pipeline |

**scan.bat steps:**
```
Step 1 — live_roi.py          Draw ROI → saves roi_config.txt
Step 2 — capture_grey_block.py  Capture + process foreground point cloud
Step 3 — ipad_stream.py        Launch hand detection monitor (background)
```

**Point cloud saved to:** `z_Current Point cloud/current_pointcloud.ply`
- Y axis flipped (camera Y down → world Y up)
- Rotated 90° clockwise around Z axis
- Previous file archived to `z_History Point Cloud/pointcloud_YYYYMMDD.ply`

**Requires Python 3.14 + Orbbec Astra SDK.**
Set the `ASTRA_SDK_BIN` environment variable to the SDK `bin/` directory, or let OpenNI2 auto-detect it.

---

### 05_PointCloud to Mesh
Poisson surface reconstruction via Open3D.

```
python mesh.py --input <file.ply> --output <file.obj>
```

Output: `z_Current Point Cloud_Mesh/current_mesh.obj` (150×150×30 mm)

---

## File Storage

| Folder | Contents |
|---|---|
| `z_Current Point cloud/` | `current_pointcloud.ply` — latest scan |
| `z_History Point Cloud/` | `pointcloud_YYYYMMDD_HHMMSS.ply` — per-session archive |
| `z_Current Heatmap_PNG/` | `current_heatmap.png` — latest RGB capture (ROI-cropped, flipped) |
| `z_History Heatmap_PNG/` | `heatmap_YYYYMMDD_HHMMSS.png` — per-session archive |
| `z_Current Point Cloud_Mesh/` | `current_mesh.obj` — latest mesh |
| `z_Target heat_PNG_Outpumap_Colourt/` | `target_heatmap.png` — target design (projected) |
| `z_Target heatmap_Colour_PNG_Output/` | `progress_heatmap.png` — carving progress heatmap |
| `z_CurrentTargetDesign/` | `current_target.jpg` — active tile's intended design |
| `z_Completed Target Design/` | `target_YYYYMMDD.jpg` — archived completed targets |

---

## Quick Start

```
# 1. Run scan.bat to capture first point cloud + launch monitor
04_Point cloud\batch files\scan.bat

# 2. Start Rashi AI backend
cd 01_Rashi_Interface\AI-generation\backend
venv\Scripts\python -m uvicorn main:app --port 8001

# 3. Start Rashi frontend
cd 01_Rashi_Interface\AI-generation\frontend
npm run dev

# 4. Start Xio projection server
cd 02_Xio-User-interface
python app.py

# 5. Open projection in browser
http://localhost:5000/projection

# 6. Open point cloud viewer
http://localhost:5000/pointcloud-viewer
# or open pointcloud_viewer.html directly in a browser
```

---

## Python Environments

| Environment | Used by |
|---|---|
| Python 3.14 (system default) | `scan.bat`, `capture_grey_block.py`, Orbbec capture |
| Python 3.11 (`pythoncore-3.11-64`) | `ipad_stream.py` (MediaPipe, Open3D, OpenNI2) |
| Rashi venv (`01_Rashi_Interface/AI-generation/backend/venv`) | FastAPI + MiDaS backend |

**Install 3.11 dependencies:**
```
py -3.11 -m pip install -r "03_Hands recognition\requirements.txt"
```

---

## Key Parameters

| Parameter | Value | Location |
|---|---|---|
| Hand absence timeout | 5 seconds | `03_Hands recognition/ipad_stream.py` |
| Clay block size | 15 cm × 15 cm × 3 cm | CLAUDE.md |
| Tile size | 256 × 256 px | `tile_manager.py` |
| MiDaS weight | 80% depth + 20% luminance | `main.py` |
| OBJ export | 150×150×30 mm, 128² vertices | `exporter.py` |
| Orbbec resolution | 640×480 @ 30fps | `ipad_stream.py` |

---

## GitHub
Repository: [https://github.com/blabha/Clay-Create](https://github.com/blabha/Clay-Create)
Branch: `Bhavana_Main`
