"""
Live viewer for Orbbec Astra — shows depth stream in real time.
Press 'q' to quit.
"""

import numpy as np
import cv2
from openni import openni2

import os
SDK = os.environ.get("ASTRA_SDK_BIN") or None

openni2.initialize(SDK) if SDK else openni2.initialize()
device = openni2.Device.open_any()
print(f"Connected: {device.get_device_info()}")

depth_stream = device.create_depth_stream()
depth_stream.start()

print("Showing depth stream — press 'q' to quit.")

while True:
    frame = depth_stream.read_frame()
    depth = np.frombuffer(frame.get_buffer_as_uint16(), dtype=np.uint16).reshape((480, 640))

    # Normalise to 8-bit for display
    display = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    coloured = cv2.applyColorMap(display, cv2.COLORMAP_JET)

    cv2.imshow("Orbbec Depth (press q to quit)", coloured)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

depth_stream.stop()
device.close()
openni2.unload()
cv2.destroyAllWindows()
