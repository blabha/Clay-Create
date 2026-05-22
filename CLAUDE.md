# Clay Create — AI Generation Pipeline

## Project context
MRAC01 Hardware III workshop at IAAC Barcelona. A co-creative fabrication system where a robot carves clay blocks forming a large wall relief. The human scans each carved block; the system adapts the remaining block designs to maintain continuity with what was actually carved.

## Key constraints
- Clay block: **15 cm × 15 cm × 3 cm** (depth range = 30 mm)
- Wall grid: user-defined, calculated as `floor(wall_dim_cm / 15)` — round down only
- Units: centimetres throughout
- MiDaS output is relative depth (not absolute mm); it maps to the full 3 cm carving range
- The SD model (`v1-5-pruned-emaonly.safetensors`) is gitignored — users place it manually

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
2. **Harmonic interpolation** regenerates all uncarved neighbours:
   - Collects actual scanned edge pixels from every completed neighbour
   - Gaussian-spreads those boundary values inward (σ = 0.35 × TILE_SIZE)
   - Distance-weighted blend: boundary-driven near edges, original design at centre
   - 50/50 final blend with original depth map
3. Master heightmap updated: completed tiles show **actual scanned result**, pending tiles show updated intended design

### Key files
| File | Role |
|---|---|
| `backend/main.py` | FastAPI endpoints, `enhance_heightmap`, `crop_to_grid` |
| `backend/pipeline/tile_manager.py` | Tile state, harmonic interpolation, deviation propagation |
| `backend/pipeline/midas_processor.py` | MiDaS depth estimation (accepts target output size) |
| `frontend/src/App.jsx` | Two-step flow: WallSetup → ImageUpload → tile workflow |
| `frontend/src/components/WallSetup.jsx` | Wall dimensions input, live grid preview |
| `frontend/src/components/ImageUpload.jsx` | Drag-and-drop image upload |
| `frontend/src/components/MasterView.jsx` | Dynamic grid overlay on master heightmap |

## Starting the servers
Port 8000 is blocked on this machine — backend always runs on **8001**.
```
# Always use the venv
cd AI-generation/backend && venv\Scripts\python -m uvicorn main:app --port 8001

# Frontend (proxies /api/* to :8001 via vite.config.js)
cd AI-generation/frontend && npm run dev
```
`start.bat` handles both but uses `cmd /k` — prefer launching via Bash if start.bat doesn't open.

## Design decisions
- **No Stable Diffusion** in current pipeline — removed to eliminate the 4 GB model dependency. Depth comes from MiDaS + image luminance detail.
- **Harmonic interpolation** (not additive edge correction) for neighbour adaptation — additive corrections created visible stripe artifacts.
- **50/50 blend** (original design : harmonically interpolated surface) — keeps aesthetic continuity with the reference image while guaranteeing seam-free boundaries.
- `imageRendering: pixelated` on all heightmap `<img>` tags — prevents browser anti-aliasing from softening the depth data.