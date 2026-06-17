"""
Orbbec Astra camera viewer — color + depth streams.
Requires: Orbbec SDK (OpenNI2 runtime) installed + openni + opencv-python
"""

import sys
import numpy as np
import cv2

try:
    from openni import openni2
    from openni import _openni2 as c_api
except ImportError:
    print("ERROR: 'openni' package not found. Run: python -m pip install openni")
    sys.exit(1)

import os
OPENNI2_RUNTIME = os.environ.get("ASTRA_SDK_BIN") or None

def main():
    try:
        if OPENNI2_RUNTIME:
            openni2.initialize(OPENNI2_RUNTIME)
        else:
            openni2.initialize()
    except Exception as e:
        print(f"ERROR: Could not initialize OpenNI2: {e}")
        print("Make sure the Orbbec SDK (OpenNI2 runtime) is installed.")
        print("Download from: https://www.orbbec.com/developers/")
        sys.exit(1)

    device = openni2.Device.open_any()
    print(f"Connected: {device.get_device_info()}")

    # Color stream
    color_stream = device.create_color_stream()
    color_stream.set_video_mode(c_api.OniVideoMode(
        pixelFormat=c_api.OniPixelFormat.ONI_PIXEL_FORMAT_RGB888,
        resolutionX=640, resolutionY=480, fps=30
    ))
    color_stream.start()

    # Depth stream
    depth_stream = device.create_depth_stream()
    depth_stream.set_video_mode(c_api.OniVideoMode(
        pixelFormat=c_api.OniPixelFormat.ONI_PIXEL_FORMAT_DEPTH_1_MM,
        resolutionX=640, resolutionY=480, fps=30
    ))
    depth_stream.start()

    print("Streaming — press 'q' to quit, 's' to save a snapshot.")

    while True:
        color_frame = color_stream.read_frame()
        depth_frame = depth_stream.read_frame()

        # Color image (RGB -> BGR for OpenCV)
        color_data = np.frombuffer(color_frame.get_buffer_as_uint8(), dtype=np.uint8)
        color_img = color_data.reshape((480, 640, 3))
        color_bgr = cv2.cvtColor(color_img, cv2.COLOR_RGB2BGR)

        # Depth image (normalised to 0-255 for display)
        depth_data = np.frombuffer(depth_frame.get_buffer_as_uint16(), dtype=np.uint16)
        depth_img = depth_data.reshape((480, 640))
        depth_display = cv2.normalize(depth_img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        depth_colormap = cv2.applyColorMap(depth_display, cv2.COLORMAP_JET)

        cv2.imshow("Orbbec Astra — Color", color_bgr)
        cv2.imshow("Orbbec Astra — Depth", depth_colormap)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            cv2.imwrite("snapshot_color.png", color_bgr)
            cv2.imwrite("snapshot_depth.png", depth_colormap)
            print("Saved snapshot_color.png and snapshot_depth.png")

    color_stream.stop()
    depth_stream.stop()
    device.close()
    openni2.unload()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
