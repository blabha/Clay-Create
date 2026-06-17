# Clay Create

Co-creative clay relief fabrication system developed at IAAC Barcelona — MRAC01 Hardware III.
A robot carves clay blocks forming a large wall relief. After each block is carved, a depth scan is uploaded; the system adapts all remaining block designs to maintain visual continuity with what was actually carved.

---

## Architecture

```
frontend (Vite / React — port 5173)
        ↕  /api/* proxy
backend  (FastAPI — port 8001)
```

**No Stable Diffusion model required.** Depth comes entirely from MiDaS + image luminance detail.

---

## Setup

### Backend

```bash
cd AI-generation/backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
python -m uvicorn main:app --port 8001
```

MiDaS weights (~100 MB) are downloaded automatically from `torch.hub` on first run.

### Frontend

```bash
cd AI-generation/frontend
npm install
npm run dev
```

Open **http://localhost:5173**

### Quick start (Windows)

Run `start.bat` — opens backend and frontend in separate terminals.

---

## Pipeline

1. **Wall setup** — enter wall dimensions in cm; the system calculates the grid as `floor(dim / 15)` blocks per axis
2. **Upload reference image** — center-cropped to the grid aspect ratio
3. **Depth estimation** — MiDaS_small (80 % weight) + high-frequency luminance detail (20 %)
4. **CLAHE + gamma** — contrast enhancement for sharp, deep relief
5. **Tile split** — `cols × rows` tiles of 256 × 256 px each

### Carving workflow

For each tile:
- Click the tile → enter the **carver's name** → the tile is locked to that person
- Upload a grayscale depth scan (PNG) from the depth camera
- Deviation = `scanned − intended` is computed and displayed
- All uncarved neighbour tiles are updated via **harmonic interpolation** for automatic seam continuity
- Click **Regenerate Design** to manually re-run seam correction across all remaining tiles

Carver names are overlaid on completed tiles in the master heightmap view.

### Seam correction (Regenerate Design)

Computes `scanned_edge − original_edge` at every shared boundary with a completed neighbour, spreads that additive correction ~26 px inward with exponential decay, and adds it to the original design. Interior of the tile is untouched — only the seam region is adjusted so contour lines remain continuous.

---

## Clay block specifications

| Property | Value |
|---|---|
| Block size | 15 × 15 × 3 cm |
| Carving depth range | 30 mm |
| Tile resolution | 256 × 256 px |

---

## Export (per tile)

| Format | Dimensions | Details |
|---|---|---|
| PNG | 256 × 256 px | Grayscale heightmap |
| OBJ | 150 × 150 × 30 mm | Triangulated mesh, 128² vertices |

---

## Key files

| File | Role |
|---|---|
| `backend/main.py` | FastAPI endpoints, `enhance_heightmap`, `crop_to_grid` |
| `backend/pipeline/tile_manager.py` | Tile state, harmonic interpolation, seam correction, deviation tracking |
| `backend/pipeline/midas_processor.py` | MiDaS depth estimation |
| `backend/pipeline/exporter.py` | PNG and OBJ export |
| `frontend/src/App.jsx` | Main app state, carver name modal, routing |
| `frontend/src/components/CarverModal.jsx` | Name entry popup |
| `frontend/src/components/MasterView.jsx` | Dynamic grid overlay with carver names |
| `frontend/src/components/TileWorkflow.jsx` | Per-tile scan upload, deviation view, 3D surface |
| `frontend/src/components/WallSetup.jsx` | Wall dimensions input and grid preview |