"""
Live Orbbec RGB + depth feed.
Draw a rectangle over the target object to auto-compute 3D bounding box parameters.

Controls:
    Click + drag   — draw ROI rectangle
    S              — sample depth in ROI and print bounding box parameters
    R              — reset ROI
    Q / Esc        — quit
"""

import sys
import os
import math
import ctypes
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))

W, H = 640, 480

# ── Mouse state ───────────────────────────────────────────────────────────────
_roi_start = None
_roi_end   = None
_drawing   = False
_confirmed = False

def _square_end(start, x, y):
    """Constrain end point so the ROI is a square."""
    dx = x - start[0]
    dy = y - start[1]
    side = max(abs(dx), abs(dy))
    return (start[0] + int(np.sign(dx) * side),
            start[1] + int(np.sign(dy) * side))


def _mouse(event, x, y, flags, param):
    global _roi_start, _roi_end, _drawing, _confirmed
    if event == cv2.EVENT_LBUTTONDOWN:
        _roi_start = (x, y)
        _roi_end   = (x, y)
        _drawing   = True
        _confirmed = False
    elif event == cv2.EVENT_MOUSEMOVE and _drawing:
        _roi_end = _square_end(_roi_start, x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        _roi_end  = _square_end(_roi_start, x, y)
        _drawing  = False


def _init_orbbec():
    from openni import openni2
    from openni import _openni2 as c_api

    search = [
        r"C:\Users\Bhavana\Downloads\AstraSDK-v2.1.3-94bca0f52e-20210608T034051Z-vs2015-win64\AstraSDK-v2.1.3-94bca0f52e-20210608T034051Z-vs2015-win64\bin",
        r"C:\Program Files\Orbbec\Astra SDK\lib",
        r"C:\Program Files (x86)\Orbbec\Astra SDK\lib",
        r"C:\Program Files\OpenNI2\Redist",
        r"C:\Program Files (x86)\OpenNI2\Redist",
    ]
    for path in search + [None]:
        try:
            openni2.initialize(path) if path else openni2.initialize()
            break
        except Exception:
            continue
    else:
        print("Failed to initialise OpenNI2.")
        sys.exit(1)

    import time
    device = None
    for attempt in range(5):
        try:
            device = openni2.Device.open_any()
            break
        except Exception:
            print(f"  Device not ready, retrying ({attempt+1}/5)...")
            time.sleep(2.0)
    if device is None:
        print("Could not open Orbbec device.")
        openni2.unload()
        sys.exit(1)

    depth_stream = device.create_depth_stream()
    color_stream = None
    try:
        color_stream = device.create_color_stream()
        color_stream.set_video_mode(c_api.OniVideoMode(
            pixelFormat=c_api.OniPixelFormat.ONI_PIXEL_FORMAT_RGB888,
            resolutionX=W, resolutionY=H, fps=30,
        ))
    except Exception as e:
        print(f"  Color stream error: {e}")

    try:
        if device.is_image_registration_mode_supported(1):
            device.set_image_registration_mode(1)
            print("  Depth-to-color registration: enabled")
    except Exception:
        pass

    depth_stream.start()
    if color_stream:
        color_stream.start()

    # Read intrinsics
    fx = fy = cx = cy = None
    try:
        cal = device.get_property(14, ctypes.c_float * 9)
        fx, fy, cx, cy = float(cal[0]), float(cal[1]), float(cal[2]), float(cal[3])
    except Exception:
        fov_h = depth_stream.get_horizontal_fov()
        fov_v = depth_stream.get_vertical_fov()
        fx = (W / 2) / math.tan(fov_h / 2)
        fy = (H / 2) / math.tan(fov_v / 2)
        cx, cy = W / 2.0, H / 2.0
    print(f"  Intrinsics: fx={fx:.1f}  fy={fy:.1f}  cx={cx:.1f}  cy={cy:.1f}")

    return openni2, device, depth_stream, color_stream, fx, fy, cx, cy


def _read_frames(depth_stream, color_stream):
    d_frame = depth_stream.read_frame()
    depth = np.frombuffer(d_frame.get_buffer_as_uint16(),
                          dtype=np.uint16).reshape((H, W)).astype(np.float32)
    color = None
    if color_stream:
        c_frame = color_stream.read_frame()
        raw = np.frombuffer(c_frame.get_buffer_as_uint8(), dtype=np.uint8)
        color = raw.reshape((H, W, 3)).copy()
    return depth, color


def _compute_bbox(depth_mm, fx, fy, cx, cy, u0, v0, u1, v1):
    """Project pixels in the ROI through depth to 3D and return bounding box in cm."""
    depth_scale = 0.001  # mm -> m
    u0, u1 = min(u0, u1), max(u0, u1)
    v0, v1 = min(v0, v1), max(v0, v1)

    roi_depth = depth_mm[v0:v1, u0:u1]
    uu, vv = np.meshgrid(np.arange(u0, u1), np.arange(v0, v1))

    z = roi_depth * depth_scale
    valid = z > 0.1

    if valid.sum() < 10:
        print("  Not enough valid depth pixels in ROI — point the camera closer.")
        return None

    z_v   = z[valid]
    uu_v  = uu[valid].astype(np.float32)
    vv_v  = vv[valid].astype(np.float32)

    cam_x = (uu_v - cx) * z_v / fx
    cam_y = (vv_v - cy) * z_v / fy
    cam_z = z_v

    # Convert to viewer coords (same as detect_grey_block)
    viewer_x =  cam_x         # camera X
    viewer_y = -cam_y         # viewer Z (up)
    depth    =  cam_z         # depth

    # Use 5th/95th percentile to ignore outliers
    def p(arr, lo, hi):
        return float(np.percentile(arr, lo)), float(np.percentile(arr, hi))

    x_min, x_max   = p(viewer_x, 5, 95)
    z_min, z_max   = p(viewer_y, 5, 95)
    d_min, d_max   = p(depth,    5, 95)

    # Add a small margin
    margin = 0.02  # 2 cm
    x_min -= margin;  x_max += margin
    z_min -= margin;  z_max += margin
    d_max += margin

    return dict(
        x_min=x_min, x_max=x_max,
        z_min=z_min, z_max=z_max,
        depth_min=d_min, depth_max=d_max,
    )


def _save_config(bbox):
    path = os.path.join(HERE, "roi_config.txt")
    with open(path, "w") as f:
        f.write(f"x_min={bbox['x_min']*100:.2f}\n")
        f.write(f"x_max={bbox['x_max']*100:.2f}\n")
        f.write(f"z_min={bbox['z_min']*100:.2f}\n")
        f.write(f"z_max={bbox['z_max']*100:.2f}\n")
        f.write(f"depth_min={bbox['depth_min']*100:.2f}\n")
        f.write(f"depth_max={bbox['depth_max']*100:.2f}\n")
    print(f"  Config saved -> {path}")


def main():
    global _roi_start, _roi_end, _drawing, _confirmed

    print("Initialising Orbbec...")
    openni2, device, depth_stream, color_stream, fx, fy, cx, cy = _init_orbbec()

    print("Warming up (30 frames)...")
    for _ in range(30):
        depth_stream.read_frame()
        if color_stream:
            color_stream.read_frame()

    cv2.namedWindow("Live ROI", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Live ROI", W * 2, H * 2)
    cv2.setMouseCallback("Live ROI", _mouse)

    print("\nDraw a rectangle over the target object.")
    print("  S = sample depth & compute bounding box")
    print("  R = reset ROI   |   Q / Esc = quit\n")

    depth_frame = None
    color_frame = None
    key = 0xFF

    try:
        while True:
            depth_raw, color_raw = _read_frames(depth_stream, color_stream)
            depth_frame = depth_raw

            if color_raw is not None:
                display = cv2.cvtColor(color_raw, cv2.COLOR_RGB2BGR)
            else:
                display = np.zeros((H, W, 3), dtype=np.uint8)

            # Draw current ROI
            if _roi_start and _roi_end:
                cv2.rectangle(display, _roi_start, _roi_end, (0, 255, 0), 2)
                # Physical size using centre depth
                rw_px = abs(_roi_end[0] - _roi_start[0])
                rh_px = abs(_roi_end[1] - _roi_start[1])
                label = f"{rw_px}x{rh_px}px"
                if depth_frame is not None and rw_px > 0 and rh_px > 0:
                    cu = (min(_roi_start[0], _roi_end[0]) + rw_px // 2)
                    cv_ = (min(_roi_start[1], _roi_end[1]) + rh_px // 2)
                    cz = depth_frame[cv_, cu] * 0.001  # mm -> m
                    if cz > 0.05:
                        phys_w = (rw_px / fx) * cz * 1000  # mm
                        phys_h = (rh_px / fy) * cz * 1000
                        label = f"{phys_w:.0f} x {phys_h:.0f} mm"
                cv2.putText(display, label,
                            (min(_roi_start[0], _roi_end[0]),
                             min(_roi_start[1], _roi_end[1]) - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            cv2.putText(display, "Draw ROI then press S to sample  |  R=reset  Q=quit",
                        (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
            if key not in (0xFF, 255):
                cv2.putText(display, f"key={key}", (6, H - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 255, 100), 1)

            cv2.imshow("Live ROI", display)
            key = cv2.waitKey(30) & 0xFF

            if key in (ord('q'), ord('Q'), 27):
                break

            elif key in (ord('r'), ord('R')):
                _roi_start = _roi_end = None
                print("ROI reset.")

            elif key in (ord('s'), ord('S')):
                if _roi_start is None or _roi_end is None:
                    print("Draw a ROI first.")
                    continue
                u0 = max(0, min(_roi_start[0], _roi_end[0]))
                v0 = max(0, min(_roi_start[1], _roi_end[1]))
                u1 = min(W, max(_roi_start[0], _roi_end[0]))
                v1 = min(H, max(_roi_start[1], _roi_end[1]))
                if (u1 - u0) < 4 or (v1 - v0) < 4:
                    print("ROI too small — draw a larger box.")
                    continue

                print(f"\nSampling ROI: ({u0},{v0}) → ({u1},{v1})")
                bbox = _compute_bbox(depth_frame, fx, fy, cx, cy, u0, v0, u1, v1)
                if bbox is None:
                    continue

                print(f"\n  Bounding box result:")
                print(f"    x_min    = {bbox['x_min']*100:+.1f} cm")
                print(f"    x_max    = {bbox['x_max']*100:+.1f} cm")
                print(f"    z_min    = {bbox['z_min']*100:+.1f} cm  (viewer up/down)")
                print(f"    z_max    = {bbox['z_max']*100:+.1f} cm")
                print(f"    depth_min= {bbox['depth_min']*100:.1f} cm")
                print(f"    depth_max= {bbox['depth_max']*100:.1f} cm")
                print(f"\n  Run command:")
                print(f'    capture_grey_block.bat '
                      f'--x-min {bbox["x_min"]*100:.1f} --x-max {bbox["x_max"]*100:.1f} '
                      f'--z-min {bbox["z_min"]*100:.1f} --z-max {bbox["z_max"]*100:.1f} '
                      f'--depth-max {bbox["depth_max"]*100:.1f}')

                _save_config(bbox)

    finally:
        depth_stream.stop()
        if color_stream:
            color_stream.stop()
        device.close()
        openni2.unload()
        cv2.destroyAllWindows()
        print("\nDone.")


if __name__ == "__main__":
    main()
