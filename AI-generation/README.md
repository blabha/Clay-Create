# Clay Relief Pipeline

9-tile clay carving simulation: Stable Diffusion → MiDaS heightmap → tile workflow → OBJ export.

## Setup

### 1. Place the SD model

Copy `v1-5-pruned-emaonly.safetensors` into:
```
CLAY-CREATE/models/v1-5-pruned-emaonly.safetensors
```

### 2. Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

MiDaS weights are downloaded automatically from torch.hub on first run (~100 MB).

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

### Quick start (Windows)

Double-click `start.bat` — it opens both servers in separate terminals.

---

## Tile order

```
1 2 3
4 5 6
7 8 9
```

Work through tiles in sequence. For each tile:
- **Paint deviations** — use the brush to simulate depth-camera error (white = raised, black = lowered)
- **Upload scan** — or drop a grayscale PNG (e.g. from an actual depth camera)

After processing, edge corrections propagate into all uncarved neighbours with an 80 px linear fade.

## Export

- **PNG** — 256 × 256 grayscale heightmap
- **OBJ** — 200 mm × 200 mm × 40 mm triangulated mesh (128² vertices)
