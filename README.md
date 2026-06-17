# Clay Create — Hardware 3

**MRAC01 Hardware III Workshop · IAAC Barcelona**

A co-creative fabrication system where workshop participants each sculpt one clay block that together form a large wall relief. A depth camera scans each block after carving; AI adapts all remaining tile designs automatically to keep the full wall visually continuous.

---

## Requirements

### Hardware

| Hardware | Purpose |
|---|---|
| **Orbbec Astra depth camera** | Captures point clouds and RGB frames during scanning and hand monitoring |
| **Orbbec AstraSDK v2.1.3** | Driver/runtime required to communicate with the camera — download from the Orbbec website |
| **Projector** | Pointed at table workspace — displays the target carving design and progress heatmap during each participant's turn |
| **Windows PC** | All scripts are Windows-native (batch files, Python on Windows paths) |

### Materials

| Material | Purpose |
|---|---|
| **Clay** | One block per participant (15 × 15 × 3 cm), assembled together to form the full wall relief |
| **Water** | For keeping clay workable and preventing cracking during carving |
| **Clay carving tools** | Loops, wire tools, and sculpting knives for removing material and refining the surface |

Set the SDK path once so all scripts can find it:

```bat
set ASTRA_SDK_BIN=<path-to-AstraSDK>\bin
```

---

## How the System Works

The wall is divided into a **grid of tiles** (e.g. 3 × 2 = 6 blocks). Each participant is assigned one block to carve in clay. The AI generates a unique heightmap target for each block based on a reference image, ensuring the carvings will connect visually across the full wall when assembled.

**One participant's turn looks like this:**
1. Their target design is projected onto the wall by the projector
2. They begin carving the clay block by hand
3. Every time they step back for 5 seconds, the camera scans the current state
4. A progress heatmap is projected showing how close the current carve is to the target
5. When finished, the scan is logged and the next participant begins

The AI continuously updates the remaining uncarved tiles based on what was actually carved — so each block adapts to the real outcomes of the ones before it.

---

## System Architecture

```
► START HERE: 04_Point cloud/batch files/scan.bat
        │
        │  Step 1 — live_roi.py
        │    Draw a rectangle around the clay block area
        │    → saves roi_config.txt (bounding box for all future scans)
        │
        │  Step 2 — capture_grey_block.py
        │    Captures the first point cloud + RGB image
        │    → z_Current Point cloud/current_pointcloud.ply
        │    → z_Current Heatmap_PNG/current_heatmap.png
        │
        │  Step 3 — launches ipad_stream.py in background
        │    Hand detection now runs continuously
        │    Hands absent 5s → auto-scan → repeat until session ends
        │
        ▼
01_Innitialization_Backend_UI   ← AI pipeline (FastAPI + React, port 8001/5173)
  Upload reference image + set grid (cols × rows)
  MiDaS generates per-tile depth heightmaps
  After each scan: adapts uncarved neighbours automatically
        │
        ▼ writes heatmap PNGs
        │
02_Projected_UI                 ← projection server (Flask, port 5000)
  Serves target + progress heatmaps to the projector
  Auto-refreshes via WebSocket when files change
  Receives grid/geometry updates from Grasshopper over UDP
```

---

## Modules

### 01_Innitialization_Backend_UI — AI Design Pipeline
FastAPI backend + Vite/React frontend. This is where you set up the session before carving begins.

- Upload a reference image and set the wall grid dimensions (cols × rows)
- MiDaS depth model (80% weight) + luminance detail (20%) → per-tile heightmaps
- Each tile gets a unique 256 × 256 px target depth map
- After every scan: harmonic interpolation automatically updates all uncarved neighbours to maintain visual continuity

**Ports:** Backend `8001` · Frontend `5173`

### 02_Projected_UI — Projection Server
Flask + SocketIO server that drives the projector display during the workshop.

- `/projection` — the main display, shown on the projector pointed at the wall
- `/pointcloud-viewer` — live Three.js viewer for the latest scan
- `/api/target-heatmap`, `/api/progress-heatmap` — image endpoints polled every 1 second
- WebSocket push refreshes the projection instantly when either heatmap file changes

**Port:** `5000`

### 03_Hands Recognition — Background Scan Monitor
Orbbec colour stream + MediaPipe hand detection. Launched automatically by `scan.bat` — you do not start this manually.

- Watches for hands leaving the ROI area
- Hand absent ≥ 5 seconds → archives current heatmap → triggers new scan → repeats
- Releases the Orbbec camera before the scan subprocess runs, reclaims it after
- Loops indefinitely until the session ends (Ctrl+C to stop)

**Requires Python 3.11** (MediaPipe is not compatible with Python 3.14)

### 04_Point Cloud — Orbbec Capture Pipeline
**Entry point for every session.** Run `scan.bat` to begin.

1. `live_roi.py` — draw a bounding box around the block area; saves `roi_config.txt`
2. `capture_grey_block.py` — capture foreground point cloud + RGB within the ROI
3. Launches `ipad_stream.py` (hand monitor) in a background window

Point cloud output: Y-flipped + rotated 90° CW to convert from camera space to world space.

### 05_PointCloud to Mesh
Optional. Converts a point cloud to a surface mesh via Open3D Poisson reconstruction.

```bat
python mesh.py --input <file.ply> --output <file.obj>
```

---

## Required Data Folders

These folders are **not included in the repository** (gitignored — they hold large scan data). Create them once after cloning:

```bat
mkdir "z_Current Point cloud"
mkdir "z_History Point Cloud"
mkdir "z_Current Heatmap_PNG"
mkdir "z_History Heatmap_PNG"
mkdir "z_Current Point Cloud_Mesh"
mkdir "z_History Point Cloud_Mesh"
mkdir "z_Target heat_PNG_Outpumap_Colourt"
mkdir "z_Target heatmap_Colour_PNG_Output"
mkdir "z_CurrentTargetDesign"
mkdir "z_Completed Target Design"
```

---

## Installation

### Python environments

This project requires **two separate Python versions** — do not mix them:

| Environment | Version | Used by |
|---|---|---|
| System Python | **3.14** | `scan.bat`, all `04_Point cloud` capture scripts |
| Secondary Python | **3.11** | `ipad_stream.py` — MediaPipe does not support 3.14 |
| Rashi venv | **3.x** (inside venv) | `01_Innitialization_Backend_UI` AI backend |

### 1. Point cloud capture (Python 3.14)

```bat
cd "04_Point cloud"
pip install -r requirements.txt
```

### 2. Hand detection monitor (Python 3.11 — must be installed separately)

```bat
py -3.11 -m pip install -r "03_Hands recognition\requirements.txt"
```

> `mediapipe==0.10.9` is version-pinned — newer versions removed the `solutions` API that this project uses.

### 3. AI backend (dedicated venv)

```bat
cd 01_Innitialization_Backend_UI\AI-generation\backend
python -m venv venv

rem PyTorch — install FIRST, before requirements.txt
rem CPU only:
venv\Scripts\pip install torch torchvision
rem CUDA 12.4:
venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

venv\Scripts\pip install -r requirements.txt
```

### 4. Projection server (Python 3.14 or any env with Flask)

```bat
cd 02_Projected_UI
pip install -r requirements.txt
```

### 5. AI frontend (Node.js)

```bat
cd 01_Innitialization_Backend_UI\AI-generation\frontend
npm install
```

---

## Quick Start

Run these in order at the start of each workshop session:

```bat
rem ── Terminal 1: run the scan + launch hand monitor ──
"04_Point cloud\batch files\scan.bat"

rem ── Terminal 2: AI backend ──
cd 01_Innitialization_Backend_UI\AI-generation\backend
venv\Scripts\python -m uvicorn main:app --port 8001

rem ── Terminal 3: AI frontend ──
cd 01_Innitialization_Backend_UI\AI-generation\frontend
npm run dev

rem ── Terminal 4: projection server ──
cd 02_Projected_UI
python app.py
```

Then open in browser:
- **AI design interface** → `http://localhost:5173` — upload image, set grid, assign blocks
- **Projector display** → `http://localhost:5000/projection` — open this on the projector screen
- **Point cloud viewer** → `http://localhost:5000/pointcloud-viewer`

---

## File Storage

| Folder | File | Written by |
|---|---|---|
| `z_Current Point cloud/` | `current_pointcloud.ply` | `detect_grey_block.py` |
| `z_History Point Cloud/` | `pointcloud_YYYYMMDD_HHMMSS.ply` | `detect_grey_block.py` |
| `z_Current Heatmap_PNG/` | `current_heatmap.png` | `ipad_stream.py` + `detect_grey_block.py` |
| `z_History Heatmap_PNG/` | `heatmap_YYYYMMDD_HHMMSS.png` | `ipad_stream.py` |
| `z_Current Point Cloud_Mesh/` | `current_mesh.obj` | `mesh.py` |
| `z_Target heat_PNG_Outpumap_Colourt/` | `target_heatmap.png` | `01_Innitialization_Backend_UI` backend |
| `z_Target heatmap_Colour_PNG_Output/` | `progress_heatmap.png` | `detect_grey_block.py` |
| `z_CurrentTargetDesign/` | `current_target.jpg` | `02_Projected_UI/app.py` |
| `z_Completed Target Design/` | `target_YYYYMMDD.jpg` | `02_Projected_UI/app.py` |

---

## Grasshopper Integration

Grasshopper is a visual programming plugin for **Rhino 3D**, used here to generate and receive carving geometry. The `.gh` files are in `01_Innitialization_Backend_UI/` and `04_Point cloud/Clay-Create/`. Open them in Rhino → Grasshopper.

The system connects to Grasshopper via two heatmap files and a UDP socket.

### Part 1 — Target Heatmap (AI-generated design)

Before carving begins, the AI pipeline converts the reference image into a colour-mapped depth PNG per tile. Grasshopper reads this to define the intended carving depth for every zone of the block.

**File:**
```
z_Target heat_PNG_Outpumap_Colourt\target_heatmap.png
```
Live endpoint: `http://localhost:5000/api/target-heatmap`

### Part 2 — Progress Heatmap (scan feedback)

After every triggered scan, the point cloud is converted into a colour heatmap showing how the current carved surface compares to the target. Grasshopper reads this to provide real-time depth guidance during carving.

**File:**
```
z_Target heatmap_Colour_PNG_Output\progress_heatmap.png
```
Live endpoint: `http://localhost:5000/api/progress-heatmap`

### UDP Communication

| Direction | Port | Purpose |
|---|---|---|
| Grasshopper → `02_Projected_UI` | `6005` | Projection geometry (elements, curves, block index) |
| `02_Projected_UI` → Grasshopper | `6006` | Session state updates |

`gh_state.json` (in `02_Projected_UI/`) is also written after every update and can be polled by Grasshopper every 200 ms as an alternative to UDP.

---

## Key Parameters

| Parameter | Value | Where to change |
|---|---|---|
| Hand absence timeout | 5 seconds | `03_Hands recognition/ipad_stream.py` → `HANDS_TIMEOUT` |
| Clay block size | 15 × 15 × 3 cm | `01_Innitialization_Backend_UI/AI-generation/backend/pipeline/exporter.py` |
| Tile size | 256 × 256 px | `tile_manager.py` |
| MiDaS depth weight | 80% depth + 20% luminance | `main.py` → `enhance_heightmap` |
| Orbbec resolution | 640 × 480 @ 30 fps | `ipad_stream.py` → stream setup |
| Point cloud orientation | Y-flip + 90° CW | `detect_grey_block.py` → `process()` |

---

## Repository

```
https://github.com/blabha/Clay-Create
Branch: Bhavana_Main
```
