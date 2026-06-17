# Clay Create — Hardware 3

**MRAC01 Hardware III Workshop · IAAC Barcelona**

A co-creative fabrication system where participants sculpt clay blocks that together form a large wall relief. An Orbbec depth camera scans each block; AI adapts the remaining tile designs to keep the full wall visually continuous with what was actually carved.

---

## System Architecture

```
Orbbec Astra Camera
        │
        ▼
03_Hands recognition / ipad_stream.py   ← background process (Python 3.11)
  MediaPipe hand detection
  5-second absence → archive heatmap + trigger scan
        │
        ▼
04_Point cloud / scan.bat               ← main scan workflow (Python 3.14)
  Step 1 · live_roi.py        → draw ROI, save roi_config.txt
  Step 2 · capture_grey_block.py → capture point cloud + RGB
  Step 3 · launch ipad_stream.py in background
        │
        ├──► z_Current Point cloud / current_pointcloud.ply
        └──► z_Current Heatmap_PNG / current_heatmap.png
                       │
                       ▼
01_Rashi_Interface                       ← AI depth pipeline (FastAPI + React)
  MiDaS depth estimation
  Tile adaptation via harmonic interpolation
  → z_Target heat_PNG_Outpumap_Colourt / target_heatmap.png
  → z_Target heatmap_Colour_PNG_Output / progress_heatmap.png
                       │
                       ▼
02_Xio-User-interface                    ← projection server (Flask + SocketIO)
  Live projection at http://localhost:5000/projection
  Auto-refresh via WebSocket on file change
```

---

## Modules

### 01 · Rashi Interface — AI Design Pipeline
FastAPI backend + Vite/React frontend.

- Uploads a reference image + wall dimensions
- MiDaS depth (80%) + luminance detail (20%) → per-tile heightmaps
- After each scan: harmonic interpolation adapts uncarved neighbours automatically

**Ports:** Backend `8001` · Frontend `5173`

### 02 · Xio User Interface — Projection Server
Flask + SocketIO server driving the projector display.

- `/projection` — main projector view
- `/pointcloud-viewer` — live Three.js point cloud viewer
- `/api/target-heatmap`, `/api/progress-heatmap` — file-based image endpoints
- Polls heatmap files every 1 second; WebSocket push on change

**Port:** `5000`

### 03 · Hands Recognition — Background Monitor
Orbbec colour stream + MediaPipe. Launched by `scan.bat` after initial capture.

- Loads ROI from `04_Point cloud/roi_config.txt` on startup
- Hand absent ≥ 5 seconds → archives current heatmap + fires new scan
- Releases Orbbec before scan subprocess runs, reclaims after

**Requires Python 3.11**

### 04 · Point Cloud — Orbbec Capture Pipeline
`scan.bat` runs three steps in sequence:
1. `live_roi.py` — draw bounding box → `roi_config.txt`
2. `capture_grey_block.py` — capture foreground point cloud + RGB
3. Launch `ipad_stream.py` in background window

Point cloud output: Y-flipped + rotated 90° CW (camera space → world space)

### 05 · PointCloud to Mesh
Open3D Poisson reconstruction.

```
python mesh.py --input <file.ply> --output <file.obj>
```

---

## File Storage

| Folder | File | Written by |
|---|---|---|
| `z_Current Point cloud/` | `current_pointcloud.ply` | `detect_grey_block.py` |
| `z_History Point Cloud/` | `pointcloud_YYYYMMDD_HHMMSS.ply` | `detect_grey_block.py` |
| `z_Current Heatmap_PNG/` | `current_heatmap.png` | `ipad_stream.py` / `detect_grey_block.py` |
| `z_History Heatmap_PNG/` | `heatmap_YYYYMMDD_HHMMSS.png` | `ipad_stream.py` |
| `z_Current Point Cloud_Mesh/` | `current_mesh.obj` | `mesh.py` |
| `z_Target heat_PNG_Outpumap_Colourt/` | `target_heatmap.png` | Rashi backend |
| `z_Target heatmap_Colour_PNG_Output/` | `progress_heatmap.png` | Rashi backend |
| `z_CurrentTargetDesign/` | `current_target.jpg` | `app.py` (on block assign) |
| `z_Completed Target Design/` | `target_YYYYMMDD.jpg` | `app.py` (on block assign) |

---

## Quick Start

### Full session (run in order)

```bat
# 1. Scan first block + launch hand monitor
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
```

### Hand monitor only (without scan.bat)

```bat
py -3.11 "03_Hands recognition\ipad_stream.py"
```

---

## Installation

### Python environments

| Environment | Scripts |
|---|---|
| **Python 3.14** (system default) | `scan.bat`, all `04_Point cloud` scripts |
| **Python 3.11** (`pythoncore-3.11-64`) | `ipad_stream.py` (MediaPipe + OpenNI2) |
| **Rashi venv** (`01_Rashi_Interface/AI-generation/backend/venv`) | FastAPI + MiDaS |

### Install Python 3.11 dependencies (hands monitor)

```bat
py -3.11 -m pip install -r "03_Hands recognition\requirements.txt"
```

### Install Rashi backend dependencies

```bat
cd 01_Rashi_Interface\AI-generation\backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt

# PyTorch (CPU):
venv\Scripts\pip install torch torchvision

# PyTorch (CUDA 12.4):
venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

### Install Xio server dependencies

```bat
cd 02_Xio-User-interface
pip install -r requirements.txt
```

### Install Point cloud capture dependencies

```bat
cd "04_Point cloud"
pip install -r requirements.txt
```

### Orbbec Astra SDK

Install `AstraSDK-v2.1.3` and either add the `bin/` folder to `PATH`, or set the environment variable:

```bat
set ASTRA_SDK_BIN=<path-to-AstraSDK>\bin
```

`ipad_stream.py` reads `ASTRA_SDK_BIN` automatically; if unset, OpenNI2 auto-detects the SDK.

### Rashi frontend

```bat
cd 01_Rashi_Interface\AI-generation\frontend
npm install
```

---

## Key Parameters

| Parameter | Value | Where to change |
|---|---|---|
| Hand absence timeout | 5 seconds | `03_Hands recognition/ipad_stream.py` → `HANDS_TIMEOUT` |
| Clay block size | 15 × 15 × 3 cm | `01_Rashi_Interface/AI-generation/backend` — exporter |
| Tile size | 256 × 256 px | `tile_manager.py` |
| MiDaS weight | 80% depth + 20% luminance | `main.py` → `enhance_heightmap` |
| Orbbec resolution | 640 × 480 @ 30 fps | `ipad_stream.py` → stream setup |
| Point cloud orientation | Y-flip + 90° CW rotation | `detect_grey_block.py` → `process()` |

---

## Repository

```
https://github.com/blabha/Clay-Create
Branch: Bhavana_Main
```
