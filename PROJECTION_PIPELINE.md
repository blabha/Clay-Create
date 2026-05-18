# Projection Update Pipeline
**Branch: Bhavana_Gestures**

Every 2 minutes the system captures the current clay surface, computes the difference from the AI-generated target, and reprojects a new heat map onto the workspace. This document describes each stage of that cycle.

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      2-MINUTE TIMER FIRES                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1 · CAPTURE                                              │
│  iPhone LiDAR (Record 3D) takes a still snapshot of clay        │
│  Exports: point cloud (.ply / .xyz)                             │
│  Cropped to active frame bounding box                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │  point cloud
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2 · MESH RECONSTRUCTION                                  │
│  Grasshopper ingests point cloud                                │
│  Delaunay mesh → smoothed → re-sampled onto N×N grid            │
│  Output: current_height[i,j] per cell                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │  current heightfield grid
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3 · DELTA COMPUTATION                                    │
│  Load target_height[i,j] from AI-generated heightfield          │
│  Δh[i,j] = current_height[i,j] − target_height[i,j]            │
│  Output: per-cell depth difference map                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │  Δh map
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 4 · CLASSIFICATION & COLOUR MAPPING                      │
│  Each cell assigned a colour based on Δh magnitude:             │
│    Δh large positive  →  deep blue   (much clay to remove)      │
│    Δh small positive  →  light blue  (nearly at target)         │
│    Δh ≈ 0 (±tolerance)→  green       (at target depth)          │
│    Δh negative        →  grey        (overcut — error)          │
│  Output: colour map image (N×N pixels)                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │  colour map
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 5 · PROJECTION MAPPING                                   │
│  Colour map warped by projector-camera homography               │
│  Aligned to physical frame footprint (5 mm/cell resolution)     │
│  Cast overhead onto clay surface                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │  projected heat map on clay
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 6 · IDLE / HOLD                                          │
│  System holds last projected image                              │
│  No streaming between captures                                  │
│  Sculptor carves using the static overlay as a guide            │
│  Next capture triggered at 2-minute mark                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
              ┌─────────────┴──────────────┐
              │                            │
              ▼                            ▼
   All cells GREEN?                  Cells still blue/grey?
   → COMPLETE                        → Return to CAPTURE
     Stop projection                   (next 2-min cycle)
     Export scan as boundary seed
     for next tile's AI heightfield
```

---

## Stage Details

### Stage 1 · Capture
- **Trigger:** 2-minute hardware/software timer
- **Device:** iPhone Pro or iPad Pro running Record 3D (LiDAR)
- **Output:** static `.ply` or `.xyz` point cloud, cropped to the active 15×15 cm frame bounding box
- **No continuous streaming** — one still per cycle keeps compute load low and gives the sculptor a stable overlay between updates

### Stage 2 · Mesh Reconstruction
- Point cloud fed into Grasshopper via file watch or live pipe
- `Delaunay Mesh` or `MeshFromPoints` component builds a surface
- Low-pass smoothing applied to suppress LiDAR noise
- Mesh re-sampled onto a regular grid matching voxel resolution (e.g. 30×30 cells → 5 mm per cell for a 15 cm frame)
- Result: `current_height[i,j]` — one Z value per grid cell

### Stage 3 · Delta Computation
- `target_height[i,j]` loaded from the AI-generated grayscale heightfield for the current tile (PNG or NumPy array)
- Per-cell subtraction: `Δh[i,j] = current_height[i,j] − target_height[i,j]`
- Positive Δh → clay is above target → sculptor must remove material
- Negative Δh → clay is below target → overcut, cannot be recovered
- Δh ≈ 0 → cell is complete

### Stage 4 · Classification & Colour Mapping
| Δh value | Colour | Meaning |
|---|---|---|
| Large positive | Deep blue | Much clay still to remove |
| Small positive | Light blue | Close to target depth |
| Within ±tolerance | Green | At target — cell complete |
| Negative | Grey | Overcut — carved too deep |

- Blue gradient is a linear or perceptual ramp over the Δh range, giving the sculptor an intuitive read of remaining material at a glance
- Tolerance band (±Δh threshold) is configurable per session

### Stage 5 · Projection Mapping
- Projector-camera homography computed once at session setup using a calibration grid placed on the frame
- Colour map image warped by the homography matrix so each projected cell aligns to its physical 5×5 mm patch of clay
- Projected overhead, perpendicular to the work surface

### Stage 6 · Idle / Hold
- Between captures the system reprojects the last computed colour map unchanged
- Sculptor works freely; the overlay remains a stable spatial reference
- On the next 2-minute trigger the cycle restarts from Stage 1

---

## Completion & Tile Handoff

When all cells are classified GREEN (within tolerance):
1. Projection stops
2. Final scan is captured and exported
3. The completed tile's edge profiles are extracted
4. These boundary conditions seed the AI heightfield generation for the next tile
5. System resets and the sculptor moves to the next frame

```
Tile N complete
  └─ export boundary edges
       └─ AI generates Tile N+1 heightfield using shared edge as constraint
            └─ new target_height loaded → projection cycle begins on Tile N+1
```

---

## Key Parameters

| Parameter | Value | Notes |
|---|---|---|
| Capture interval | 2 minutes | Fixed timer per cycle |
| Frame size | 15 × 15 × 4 cm | Physical clay frame |
| Grid resolution | 30 × 30 cells | 5 mm per cell |
| Depth tolerance | ±Δh (configurable) | Threshold for GREEN classification |
| Projection resolution | 5 mm × 5 mm per cell | Matched to grid |
| Tiles in sequence | 9 | Each seeds the next |

---

## Data Flow Summary

```
Record 3D (LiDAR)
    │  .ply point cloud
    ▼
Grasshopper (Delaunay mesh → N×N grid)
    │  current_height[i,j]
    ▼
Python / NumPy (Δh = current − target)
    │  Δh map
    ▼
Colour classifier (blue → green → grey)
    │  colour map image
    ▼
OpenCV homography warp
    │  warped projection image
    ▼
Projector → clay surface
```
