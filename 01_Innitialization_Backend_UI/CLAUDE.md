# Clay Create — AI Generation Pipeline

## Project context
MRAC01 Hardware III workshop at IAAC Barcelona. A co-creative fabrication system where a robot carves clay blocks forming a large wall relief. The human scans each carved block; the system adapts the remaining block designs to maintain continuity with what was actually carved.

## Key constraints
- Clay block: **15 cm × 15 cm × 3 cm** (depth range = 30 mm)
- Wall grid: user-defined, calculated as `floor(wall_dim_cm / 15)` — round down only
- Units: centimetres throughout
- MiDaS output is relative depth (not absolute mm); it maps to the full 3 cm carving range
- No SD model — removed entirely. Depth comes from MiDaS + luminance detail only.

## Architecture
```
frontend (Vite/React :5173)  →  Vite proxy  →  backend (FastAPI :8001)
```

### Backend pipeline (`AI-generation/backend/`)
1. User uploads reference image + wall dimensions (cols × rows)
2. Image is **center-cropped** to `cols:rows` aspect ratio, resized to `cols×256 × rows×256` px
3. **MiDaS_small** estimates depth → 80% weight in final heightmap
4. Image **high-frequency luminance detail** (original minus blurred) → 20% weight
5. CLAHE (clipLimit=6) + Gaussian blur (σ=0.3) + gamma=0.8 → contrast-enhanced heightmap
6. Split into `cols × rows` tiles of 256×256 px each

### Scan → adaptation loop
After each tile is carved and scanned:
1. Deviation = scanned − intended
2. **Harmonic interpolation** (`_harmonic_tile`) regenerates all uncarved neighbours automatically:
   - Collects actual scanned edge pixels from every completed neighbour
   - Gaussian-spreads those boundary values inward (σ = 0.35 × TILE_SIZE)
   - Distance-weighted blend: boundary-driven near edges, original design at centre
   - 50/50 final blend with original depth map
3. Master heightmap updated: completed tiles show **actual scanned result**, pending tiles show updated intended design

### Regenerate Design (manual)
`_seam_corrected_tile` — used by `POST /api/regenerate-all`:
- Computes `scanned_edge − original_edge` at every shared boundary with a completed neighbour
- Spreads that additive correction ~26 px inward with exponential decay (`exp(-dist / 0.10×TILE_SIZE)`)
- Adds the faded correction to the original design — interior is untouched, only seam region adjusts
- Purpose: ensure contour lines are continuous across tile boundaries without changing the interior design

### Regenerate Design vs harmonic interpolation
| | `_harmonic_tile` | `_seam_corrected_tile` |
|---|---|---|
| Trigger | Automatic after each scan | Manual "Regenerate Design" button |
| Effect | Smooth boundary continuation | Seam-only additive correction |
| Interior | Blended with original | Untouched |

### OBJ export dimensions
150 mm × 150 mm × 30 mm, triangulated, 128² vertices.

### Key files
| File | Role |
|---|---|
| `backend/main.py` | FastAPI endpoints, `enhance_heightmap`, `crop_to_grid` |
| `backend/pipeline/tile_manager.py` | Tile state, harmonic interpolation, seam correction, deviation tracking, `original_intended` snapshot, `regen_diffs` |
| `backend/pipeline/midas_processor.py` | MiDaS depth estimation (accepts target output size) |
| `backend/pipeline/exporter.py` | PNG + OBJ export (150×150×30 mm) |
| `frontend/src/App.jsx` | Three-step flow: WallSetup → ImageUpload → tile workflow; carver name state |
| `frontend/src/components/CarverModal.jsx` | Modal asking for carver name when an uncarved tile is selected |
| `frontend/src/components/WallSetup.jsx` | Wall dimensions input, live grid preview |
| `frontend/src/components/ImageUpload.jsx` | Drag-and-drop image upload |
| `frontend/src/components/MasterView.jsx` | Dynamic grid overlay; carver names shown on carved tiles |
| `frontend/src/components/TileWorkflow.jsx` | Scan upload, deviation view, design adaptation diff, Regenerate Design button, 3D surface |
| `frontend/src/components/DeviationView.jsx` | Intended / Scanned / Deviation comparison for carved tiles |

## Starting the servers
Port 8000 is blocked on this machine — backend always runs on **8001**.
```
# Always use the venv
cd AI-generation/backend && venv\Scripts\python -m uvicorn main:app --port 8001

# Frontend (proxies /api/* to :8001 via vite.config.js)
cd AI-generation/frontend && npm run dev
```
`start.bat` handles both but uses `cmd /k` — prefer launching via Bash if start.bat doesn't open.

## UI design
- Color palette: warm clay tones — background `#FAF8F5`, accent terracotta `#B87050`, sage green `#6B9E70`
- Font: DM Sans (Google Fonts, loaded in `index.html`)
- No yellow anywhere — `--accent` is terracotta, `--green` is sage

## Carver name feature
- Clicking an uncarved tile triggers `CarverModal` (if no name assigned yet)
- Name stored in `carverNames` state in `App.jsx` — `{ tileIdx: string }`
- Name overlaid as a small badge on the tile in `MasterView` SVG (only for carved tiles)
- `carverNames` is cleared on Reset

## Design decisions
- **No Stable Diffusion** — removed to eliminate the 4 GB model dependency. `diffusers`, `transformers`, `tokenizers`, `accelerate` removed from `requirements.txt`.
- **Harmonic interpolation** (not additive edge correction) for automatic neighbour adaptation — additive corrections created visible stripe artifacts.
- **Seam correction** (not full-tile deviation propagation) for manual regeneration — deviation propagation changed too much of the interior design.
- **50/50 blend** in `_harmonic_tile` — keeps aesthetic continuity with the reference image while guaranteeing seam-free boundaries.
- `imageRendering: pixelated` on all heightmap `<img>` tags — prevents browser anti-aliasing from softening the depth data.
- Paint Deviations (DrawingCanvas) removed — upload-only scan workflow.