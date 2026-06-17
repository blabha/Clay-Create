# -*- coding: utf-8 -*-
"""
Orbbec depth camera — background hand detection monitor.
Launched automatically by scan.bat after the initial capture.
Triggers capture_grey_block.py whenever hands are absent for HANDS_TIMEOUT seconds.
Stop with Ctrl+C.
"""

import sys
import os
import math
import ctypes
from pathlib import Path
import numpy as np
import cv2
import mediapipe as mp
import time
import shutil
import subprocess
from datetime import datetime

try:
    from openni import openni2
    from openni import _openni2 as c_api
except ImportError:
    print("ERROR: 'openni' package not found.  Run: py -3.11 -m pip install openni")
    sys.exit(1)

# ── Paths (all relative to this file's location) ──────────────────────────────
_HERE = Path(__file__).parent          # 03_Hands recognition/
_ROOT = _HERE.parent                   # project root (Hardware 3/)

# Astra SDK bin directory — override with ASTRA_SDK_BIN env var if needed
OPENNI2_RUNTIME = os.environ.get("ASTRA_SDK_BIN") or None
SCAN_SCRIPT     = str(_ROOT / "04_Point cloud" / "python" / "capture_grey_block.py")
PYTHON_EXE      = sys.executable       # whichever python launched this script
ROI_CONFIG      = str(_ROOT / "04_Point cloud" / "roi_config.txt")
CURRENT_HEATMAP = str(_ROOT / "z_Current Heatmap_PNG" / "current_heatmap.png")
HISTORY_HEATMAP = str(_ROOT / "z_History Heatmap_PNG")
HANDS_TIMEOUT   = 5.0   # seconds of absent hands before triggering scan

W, H = 640, 480


# ── Orbbec helpers ────────────────────────────────────────────────────────────
def _init_orbbec():
    for path in [OPENNI2_RUNTIME, None]:
        try:
            openni2.initialize(path) if path else openni2.initialize()
            break
        except Exception:
            continue
    else:
        print("ERROR: Could not initialise OpenNI2 — is the Astra SDK installed?")
        sys.exit(1)

    device = None
    for attempt in range(5):
        try:
            device = openni2.Device.open_any()
            break
        except Exception:
            print(f"  Device not ready, retrying ({attempt+1}/5)...")
            time.sleep(2.0)
    if device is None:
        print("ERROR: Could not open Orbbec device.")
        openni2.unload()
        sys.exit(1)

    color_stream = device.create_color_stream()
    color_stream.set_video_mode(c_api.OniVideoMode(
        pixelFormat=c_api.OniPixelFormat.ONI_PIXEL_FORMAT_RGB888,
        resolutionX=W, resolutionY=H, fps=30,
    ))

    depth_stream = device.create_depth_stream()
    depth_stream.set_video_mode(c_api.OniVideoMode(
        pixelFormat=c_api.OniPixelFormat.ONI_PIXEL_FORMAT_DEPTH_1_MM,
        resolutionX=W, resolutionY=H, fps=30,
    ))

    try:
        if device.is_image_registration_mode_supported(1):
            device.set_image_registration_mode(1)
    except Exception:
        pass

    color_stream.start()
    depth_stream.start()

    # Camera intrinsics
    try:
        cal = device.get_property(14, ctypes.c_float * 9)
        fx, fy, cx, cy = float(cal[0]), float(cal[1]), float(cal[2]), float(cal[3])
    except Exception:
        fov_h = depth_stream.get_horizontal_fov()
        fov_v = depth_stream.get_vertical_fov()
        fx = (W / 2) / math.tan(fov_h / 2)
        fy = (H / 2) / math.tan(fov_v / 2)
        cx, cy = W / 2.0, H / 2.0

    print(f"Orbbec connected — intrinsics: fx={fx:.1f} fy={fy:.1f} cx={cx:.1f} cy={cy:.1f}")
    return device, color_stream, depth_stream, fx, fy, cx, cy


def _read_frames(color_stream, depth_stream):
    c_frame = color_stream.read_frame()
    color   = np.frombuffer(c_frame.get_buffer_as_uint8(), dtype=np.uint8).reshape((H, W, 3)).copy()
    d_frame = depth_stream.read_frame()
    depth   = np.frombuffer(d_frame.get_buffer_as_uint16(), dtype=np.uint16).reshape((H, W)).astype(np.float32)
    return color, depth   # color is RGB; depth is mm


# ── ROI helpers ───────────────────────────────────────────────────────────────
def _compute_bbox(depth_mm, fx, fy, cx, cy, x, y, w, h):
    u0, v0, u1, v1 = x, y, x + w, y + h
    roi_depth = depth_mm[v0:v1, u0:u1]
    uu, vv    = np.meshgrid(np.arange(u0, u1), np.arange(v0, v1))
    z         = roi_depth * 0.001           # mm -> m
    valid     = z > 0.1
    if valid.sum() < 10:
        return None
    z_v  = z[valid];  uu_v = uu[valid].astype(np.float32);  vv_v = vv[valid].astype(np.float32)
    cam_x =  (uu_v - cx) * z_v / fx
    cam_y = -(vv_v - cy) * z_v / fy   # flip Y to viewer up
    cam_z =   z_v

    def pct(arr, lo, hi):
        return float(np.percentile(arr, lo)), float(np.percentile(arr, hi))

    x_min, x_max = pct(cam_x, 5, 95)
    z_min, z_max = pct(cam_y, 5, 95)
    d_min, d_max = pct(cam_z, 5, 95)
    m = 0.02
    return dict(x_min=x_min-m, x_max=x_max+m,
                z_min=z_min-m, z_max=z_max+m,
                depth_min=d_min, depth_max=d_max+m)


def _save_roi_config(bbox, roi):
    x, y, w, h = roi
    os.makedirs(os.path.dirname(ROI_CONFIG), exist_ok=True)
    with open(ROI_CONFIG, "w") as f:
        f.write(f"x_min={bbox['x_min']*100:.2f}\n")
        f.write(f"x_max={bbox['x_max']*100:.2f}\n")
        f.write(f"z_min={bbox['z_min']*100:.2f}\n")
        f.write(f"z_max={bbox['z_max']*100:.2f}\n")
        f.write(f"depth_min={bbox['depth_min']*100:.2f}\n")
        f.write(f"depth_max={bbox['depth_max']*100:.2f}\n")
        f.write(f"roi_u0={x}\nroi_v0={y}\nroi_u1={x+w}\nroi_v1={y+h}\n")
    print(f"[ROI] Config saved -> {ROI_CONFIG}")


# ── Heatmap archive ───────────────────────────────────────────────────────────
def _archive_heatmap(roi, color_bgr, timestamp):
    # Archive existing file if present (skip silently if not — still write new one)
    if os.path.exists(CURRENT_HEATMAP):
        os.makedirs(HISTORY_HEATMAP, exist_ok=True)
        dest = os.path.join(HISTORY_HEATMAP, f"heatmap_{timestamp}.png")
        shutil.move(CURRENT_HEATMAP, dest)
        print(f"[Heatmap] Archived -> {dest}")
    # Always write fresh capture so the next cycle has a file to archive
    capture = color_bgr[roi[1]:roi[1]+roi[3], roi[0]:roi[0]+roi[2]] if roi is not None else color_bgr
    capture = cv2.flip(capture, 1)  # flip along vertical axis (left-right mirror)
    os.makedirs(os.path.dirname(CURRENT_HEATMAP), exist_ok=True)
    cv2.imwrite(CURRENT_HEATMAP, capture)
    print(f"[Heatmap] Captured -> {CURRENT_HEATMAP}")


# ── Scan trigger ──────────────────────────────────────────────────────────────
def _trigger_scan(color_stream, depth_stream):
    """Release the Orbbec camera, run the scan, then reclaim it."""
    print("[Scan] Releasing camera for capture_grey_block.py ...")
    color_stream.stop()
    depth_stream.stop()
    print("[Scan] Running capture_grey_block.py ...")
    subprocess.run([PYTHON_EXE, SCAN_SCRIPT, "--no-view"])
    print("[Scan] Capture complete — resuming monitoring.")
    color_stream.start()
    depth_stream.start()


# ── ROI config loader ─────────────────────────────────────────────────────────
def _load_roi_from_config():
    """Read pixel ROI saved by live_roi.py into (x, y, w, h)."""
    if not os.path.exists(ROI_CONFIG):
        return None
    cfg = {}
    with open(ROI_CONFIG) as f:
        for line in f:
            if '=' in line:
                k, v = line.strip().split('=', 1)
                cfg[k.strip()] = float(v.strip())
    if all(k in cfg for k in ('roi_u0', 'roi_v0', 'roi_u1', 'roi_v1')):
        x0, y0 = int(cfg['roi_u0']), int(cfg['roi_v0'])
        x1, y1 = int(cfg['roi_u1']), int(cfg['roi_v1'])
        roi = (x0, y0, x1 - x0, y1 - y0)
        print(f"[ROI] Loaded from config: {roi}")
        return roi
    return None


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    device, color_stream, depth_stream, fx, fy, cx, cy = _init_orbbec()

    _mp            = mp.solutions.hands
    hands_detector = _mp.Hands(static_image_mode=False, max_num_hands=2,
                                min_detection_confidence=0.5, min_tracking_confidence=0.5)

    roi              = _load_roi_from_config()
    last_hand_time   = time.time()
    heatmap_archived = False
    prev_hands       = False
    last_tick        = -1   # last whole-second countdown printed

    print("\n[Monitor] Running in background — Ctrl+C to stop.")
    print(f"[Monitor] ROI: {roi}")
    print(f"[Monitor] Timeout: {HANDS_TIMEOUT}s\n")

    try:
        while True:
            color_rgb, _ = _read_frames(color_stream, depth_stream)

            result        = hands_detector.process(color_rgb)
            hands_present = bool(result.multi_hand_landmarks)

            if hands_present:
                if not prev_hands:
                    print("[Monitor] Hand detected — timer reset.")
                last_hand_time   = time.time()
                heatmap_archived = False
                last_tick        = -1
            else:
                if prev_hands:
                    print("[Monitor] Hand removed — countdown started.")
                if not heatmap_archived:
                    elapsed      = time.time() - last_hand_time
                    whole_second = int(elapsed)
                    if whole_second != last_tick:
                        remaining = max(0, HANDS_TIMEOUT - elapsed)
                        print(f"[Monitor] No hands: {elapsed:.0f}s  ({remaining:.0f}s until capture)")
                        last_tick = whole_second
                    if elapsed >= HANDS_TIMEOUT:
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        print(f"[Monitor] Triggering capture ({ts}) ...")
                        _archive_heatmap(roi, cv2.cvtColor(color_rgb, cv2.COLOR_RGB2BGR), ts)
                        _trigger_scan(color_stream, depth_stream)
                        heatmap_archived = True
                        last_tick        = -1
                        print("[Monitor] Capture done — waiting for next hand removal.\n")

            prev_hands = hands_present

    except KeyboardInterrupt:
        print("\n[Monitor] Stopped.")
    finally:
        hands_detector.close()
        color_stream.stop()
        depth_stream.stop()
        device.close()
        openni2.unload()


if __name__ == "__main__":
    main()
