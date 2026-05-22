"""
Live capture + background removal by depth and height.
No colour filtering — removes background beyond depth cutoff and points
below the viewer Z threshold, keeps everything else.

Usage:
    python capture_grey_block.py
    python capture_grey_block.py --z-min -0.05     # lower floor cut
    python capture_grey_block.py --depth-max 130   # manual depth cutoff at 130 cm
"""

import sys
import os
import argparse
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import capture_pointcloud as cap
import detect_grey_block  as det


def _load_roi_config():
    """Load bounding box from roi_config.txt saved by live_roi.py, if present."""
    path = os.path.join(HERE, "roi_config.txt")
    if not os.path.exists(path):
        return {}
    cfg = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = float(v.strip())
    print(f"Loaded ROI config from {path}")
    return cfg


def main():
    roi = _load_roi_config()

    parser = argparse.ArgumentParser(
        description="Capture Orbbec point cloud and remove background by depth + height")

    # Capture
    parser.add_argument("-n", "--frames",    type=int,   default=15)
    parser.add_argument("--no-denoise",      action="store_true", default=True)
    parser.add_argument("--denoise-k",       type=int,   default=20)
    parser.add_argument("--denoise-std",     type=float, default=6.0)

    # Background removal — defaults come from roi_config.txt if available
    parser.add_argument("--depth-min", type=float, default=roi.get("depth_min", None), metavar="CM")
    parser.add_argument("--depth-max", type=float, default=roi.get("depth_max", 67.0), metavar="CM")
    parser.add_argument("--x-min",  type=float, default=roi.get("x_min", -12.0), metavar="CM")
    parser.add_argument("--x-max",  type=float, default=roi.get("x_max",  12.0), metavar="CM")
    parser.add_argument("--z-min",  type=float, default=roi.get("z_min", -10.0), metavar="CM")
    parser.add_argument("--z-max",  type=float, default=roi.get("z_max",  10.0), metavar="CM")

    parser.add_argument("--no-view", action="store_true")
    args = parser.parse_args()

    # ── Step 1: capture ───────────────────────────────────────────────────────
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_ply = os.path.join(HERE, f"capture_{ts}.ply")

    print("=" * 60)
    print("STEP 1 — Live Orbbec capture")
    print("=" * 60)
    saved = cap.capture_orbbec(
        output_path = out_ply,
        num_frames  = args.frames,
        denoise     = not args.no_denoise,
        denoise_k   = args.denoise_k,
        denoise_std = args.denoise_std,
        classify    = False,
    )

    # ── Step 2: remove background ─────────────────────────────────────────────
    print()
    print("=" * 60)
    print("STEP 2 — Background removal")
    print("=" * 60)
    det.process(
        saved,
        open_viewer = not args.no_view,
        depth_min_m = args.depth_min / 100.0 if args.depth_min is not None else None,
        depth_max_m = args.depth_max / 100.0 if args.depth_max is not None else None,
        x_min_m     = args.x_min / 100.0,
        x_max_m     = args.x_max / 100.0,
        z_min_m     = args.z_min / 100.0,
        z_max_m     = args.z_max / 100.0,
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
