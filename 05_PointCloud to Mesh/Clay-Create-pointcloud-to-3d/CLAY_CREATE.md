# CLAY CREATE
**A co-creative fabrication system using depth sensing, projection feedback, and AI-generated target geometry**

---

## Overview

Clay Create is a human-in-the-loop sculpting system that bridges physical craft with computational guidance. A depth camera captures the live surface of a clay block; that scan is processed into a voxel map; and a projector casts a red-to-green contour overlay directly onto the clay, telling the sculptor exactly how much material to remove — and where. The target geometry is AI-generated and evolves tile by tile, so each completed frame seeds the next.

---

## Research Questions

- How can projection function as a **live fabrication interface** rather than a representational overlay?
- What changes when AI proposes geometry but the **human remains the fabricator**?
- How can **continuity emerge** across multiple handmade modules through computational mediation?
- Can a material process become adaptive, sequential, and collaborative **without becoming fully automated**?

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE                           │
│          (tile grid selection · pattern prompt · sequence)      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AI GEOMETRY ENGINE                          │
│   Generates grayscale heightfield for current tile              │
│   Uses shared boundary conditions from previous tile            │
│   Outputs: target heightfield (PNG / NumPy array)               │
└───────────────────────────┬─────────────────────────────────────┘
                            │  target heightfield
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  DEPTH CAPTURE — Record 3D (iPhone)             │
│   Captures live point cloud of clay surface via LiDAR           │
│   Exports: .r3d stream → reconstructed point cloud              │
└───────────────────────────┬─────────────────────────────────────┘
                            │  point cloud (.xyz / .ply)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               MESH RECONSTRUCTION — Grasshopper + Rhino         │
│   Point cloud → surface mesh (Delaunay / MeshFromPoints)        │
│   Mesh cleaned and aligned to frame coordinate system           │
└───────────────────────────┬─────────────────────────────────────┘
                            │  mesh geometry
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              ANEMONE LOOP — Grasshopper                         │
│   Iterative loop continuously re-ingests updated mesh           │
│   Each loop iteration:                                          │
│     1. Sample mesh Z-values onto a regular grid                 │
│     2. Compare sampled heights to target heightfield            │
│     3. Compute per-cell depth delta (Δh)                        │
│     4. Classify cells → ABOVE / AT TARGET / BELOW / OVERCUT     │
│     5. Map classification to colour (red → green → grey/purple) │
│     6. Output voxel colour map for projection                   │
└───────────────────────────┬─────────────────────────────────────┘
                            │  voxel colour map (image / data)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│           PROJECTOR CALIBRATION & MAPPING                       │
│   Projector-camera homography computed at setup                 │
│   Colour map warped to match physical frame footprint           │
│   Projected overhead onto clay surface                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │  projected light onto clay
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   HUMAN FABRICATOR                              │
│   Reads projected colour feedback                               │
│   Carves clay with hand tools                                   │
│   Loop repeats until frame reaches target surface               │
└───────────────────────────┬─────────────────────────────────────┘
                            │  completed tile scan
                            ▼
              Next tile boundary conditions →  AI Geometry Engine
```

---

## Hardware

| Component | Role |
|---|---|
| iPhone (LiDAR) + Record 3D | Live point cloud capture of clay surface |
| Overhead digital projector | Projects voxel colour map onto clay frame |
| Stable table + fixed mount | Maintains projector/camera alignment across sessions |
| 9 modular frames (15×15×4 cm) | Physical tile system; defines working boundary |
| Clay block + sculpting tools | Raw material; subtractive making |

---

## Software Stack

| Tool | Role |
|---|---|
| **Record 3D** (iOS) | LiDAR depth capture → point cloud export |
| **Rhino + Grasshopper** | Core geometry environment |
| **Anemone** (GH plugin) | Iterative loop driving real-time mesh → voxel pipeline |
| **Python + NumPy** | Heightfield comparison, delta computation, colour mapping |
| **OpenCV** (optional) | Projector-camera calibration, homography |
| **AI model** (generative) | Target heightfield synthesis with edge continuity |

---

## Data Flow Detail

### 1 · Point Cloud Capture (Record 3D)
- iPhone LiDAR scans the clay surface at ~30 fps
- Record 3D exports a live `.r3d` file stream or static `.ply` / `.xyz` point cloud
- Point cloud is cropped to the active frame bounding box
- Coordinate system aligned to frame origin (bottom-left corner, Z = 0 at frame base)

### 2 · Mesh Reconstruction (Grasshopper)
- Points fed into `Delaunay Mesh` or `MeshFromPoints` component
- Mesh smoothed with a low-pass filter to suppress noise
- Mesh re-sampled onto a regular **N×N grid** matching the voxel resolution (e.g. 30×30 cells for a 15 cm frame at 5 mm resolution)

### 3 · Anemone Loop
The Anemone loop runs continuously while carving is in progress:

```
Loop Start
  │
  ├─ Ingest latest mesh from Record 3D
  ├─ Sample mesh Z at each grid cell → current_height[i,j]
  ├─ Load target_height[i,j] from AI heightfield
  ├─ Δh[i,j] = current_height[i,j] - target_height[i,j]
  │
  ├─ Classify each cell:
  │     Δh > 0 (clay above target) →  BLUE gradient (shade encodes remaining depth)
  │                                    deep blue = lot to carve, light blue = nearly there
  │     Δh within ±tolerance       →  GREEN  (at target depth)
  │     Δh < -tolerance (overcut)  →  GREY   (carved too deep, error state)
  │     Clay absent                →  NO PROJECTION
  │
  ├─ Build colour map image
  ├─ Send to projector
  │
  └─ Check stop condition: all cells GREEN → COMPLETE
Loop End
```

**Capture interval:** a still image of the clay surface is captured every **2 minutes**. No continuous streaming — the loop idles between captures and reprojects the last known colour map.

**Capture trigger:** at the 2-minute mark, the system captures a fresh image, recomputes the depth delta, and updates the projection.

### 4 · Projection Mapping
- At setup: projector-camera homography computed from a calibration grid placed on the frame
- Colour map image warped by homography so projected zones align precisely with physical clay
- Projection resolution matched to frame size: each projected cell = 5 mm × 5 mm of clay surface

---

## Finite State Machine

### Interface FSM

| # | Condition | Action | State |
|---|---|---|---|
| 1 | Grid selected | Display tile grid | IDLE |
| 2 | Pattern prompted | Generate AI target heightfield → 3D mesh | IDLE |
| 3 | User selects tile | Create voxel projection for that tile | IDLE |

### Carving FSM

| # | Condition | Action | State |
|---|---|---|---|
| 1 | No clay block detected | No projection | IDLE |
| 2 | Clay block placed | Begin projection of last known voxel map | STARTED |
| 3 | Carving in progress | Hold current projection; countdown to next capture | CARVING |
| 4 | 2-minute timer elapses | Capture still image; extract point cloud | CAPTURE |
| 5 | Current state ≠ previous state | Recalculate Δh; update colour map; reproject | CHECKING |
| 6 | All cells within tolerance (GREEN) | Stop projection | COMPLETE |
| 7 | Projection stopped | Export scan → seed next tile | REPEAT |

### Projection Colour FSM

| # | Condition | Projection | State |
|---|---|---|---|
| 1 | Δh large (far from target) | Deep blue | CHECKING |
| 2 | Δh moderate (partially carved) | Mid blue | CHECKING |
| 3 | Δh small (nearly at target) | Light / pale blue | CHECKING |
| 4 | Δh within ±tolerance | Green (cell complete) | CHECKING |
| 5 | Δh < −tolerance (overcut) | Grey (error) | CHECKING |

**Colour mapping — Δh = current height − target height:**

| Colour | Meaning | Δh value |
|---|---|---|
| 🔵 **Deep blue** | Much clay still to remove | Large positive Δh |
| 🩵 **Light blue** | Close to target depth | Small positive Δh |
| 🟢 **Green** | At target depth (within tolerance) | Δh ≈ 0 |
| ⬜ **Grey** | Overcut — carved too deep | Negative Δh |

The blue gradient is a **linear or perceptual ramp** mapped directly to the magnitude of Δh, giving the sculptor an intuitive read of how much material remains at any point on the surface.

---

## AI Geometry Strategy

- Target surface generated as a **grayscale heightfield** (0 = frame base, 255 = max height)
- Brighter pixels = higher surface elevation
- Heightfield converted into contour bands for projection via threshold stepping
- **Tile continuity:** each new tile's heightfield is generated with the shared edge profile of the completed adjacent tile as a hard boundary condition
- This preserves visual continuity across the panel while allowing new formal variation interior to each tile
- AI output can be seeded by: text prompt, image reference, or pure procedural noise

---

## Frame Logic

Only **one frame is active at a time**. The sculptor completes a frame fully before moving to the next. Each completed frame is scanned, and that scan seeds the AI heightfield for the following frame.

```
Frame 1 (AI seed)
  └─ sculpt → complete → scan → export boundary
       └─ Frame 2 (boundary-conditioned AI generation)
            └─ sculpt → complete → scan → export boundary
                 └─ Frame 3 ...
                      └─ ... Frame 9
```

- Each frame: 15 × 15 × 4 cm
- One frame sculpted, completed, and scanned before the next begins
- Completed scan feeds boundary conditions to the next frame's AI heightfield
- Global pattern emerges from sequential local decisions
- No single fixed global model; the artefact is discovered through making

---

## Prototype Development Phases

| Phase | Task |
|---|---|
| 1 | Single-frame prototype with static target geometry |
| 2 | Red-to-green contour feedback from depth comparison |
| 3 | Projector + Record 3D camera calibration and alignment |
| 4 | Anemone loop integration for continuous capture/project cycle |
| 5 | Tile-to-tile boundary continuity logic |
| 6 | AI-generated target heightfields |
| 7 | Interaction refinement, legibility testing, sculpting workflow |

---

## Research Position

Clay Create does not automate craft. It explores fabrication as a **conversation** between:
- Sensing (depth camera, point cloud)
- Computation (mesh reconstruction, voxel comparison, Anemone loop)
- Proposal (AI-generated geometry)
- Interpretation (human judgment, material negotiation)
- Making (hands, tools, clay)

AI is positioned as a **speculative design partner**, not an autonomous author. The human remains central — the one who interprets, negotiates, and physically realizes the evolving form.

---

## Expected Outcomes

- A functioning human-in-the-loop sculpting prototype
- A real-time projected guidance system for clay shaping
- A sequence of 9 connected clay tiles generated through continuity constraints
- A research framework for co-creative making between AI, human action, and material resistance
