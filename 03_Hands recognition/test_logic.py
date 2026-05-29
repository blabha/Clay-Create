"""
Offline test for ipad_stream.py logic.
Uses a laptop webcam instead of the iPad — no Record3D needed.

Checks:
  1. MediaPipe hand detection on live webcam frames
  2. ROI crop and point-cloud filter geometry
  3. 5-second hands-absent timer and archive/scan trigger
  4. _hands_detection_active gate (nothing fires until S is pressed)

Press:
  S  — activate hand detection (simulates "first point cloud saved")
  O  — draw ROI on the current frame
  Q  — quit
"""

import cv2
import numpy as np
import mediapipe as mp
import time
import os
import shutil
import subprocess
from datetime import datetime

SCAN_SCRIPT = r"C:\Users\Bhavana\Documents\Hardware 3\04_Point cloud\python\capture_grey_block.py"
PYTHON_EXE  = r"C:\Users\Bhavana\AppData\Local\Python\pythoncore-3.11-64\python.exe"
HANDS_TIMEOUT = 5.0

# ── State ─────────────────────────────────────────────────────────────────────
roi                    = None   # (x, y, w, h)
roi_frame_size         = None   # (H, W) when ROI was drawn
hands_detection_active = False
last_hand_time         = time.time()
archived               = False

_mp = mp.solutions.hands
hands_detector = _mp.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)
mp_draw = mp.solutions.drawing_utils

# ── ROI helpers ───────────────────────────────────────────────────────────────
def set_roi(frame):
    global roi, roi_frame_size
    roi_frame_size = frame.shape[:2]
    title = "Set ROI -- ENTER/SPACE confirm, C cancel"
    r = cv2.selectROI(title, frame, fromCenter=False, showCrosshair=True)
    cv2.destroyWindow(title)
    if r[2] > 0 and r[3] > 0:
        roi = r
        print(f"[ROI] Set: {roi}")
    else:
        print("[ROI] Cancelled")

def crop_to_roi(frame):
    if roi is None:
        return frame
    x, y, w, h = roi
    return frame[y:y+h, x:x+w]

# ── Archive / scan (writes to temp files so nothing real is overwritten) ──────
TMP_HEATMAP = r"C:\Users\Bhavana\AppData\Local\Temp\test_current_heatmap.png"
TMP_PCD     = r"C:\Users\Bhavana\AppData\Local\Temp\test_current_pointcloud_placeholder.txt"

def archive_and_scan(frame):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Save ROI-cropped image to temp location
    capture = crop_to_roi(frame)
    cv2.imwrite(TMP_HEATMAP, capture)
    print(f"[TEST] Heatmap capture saved -> {TMP_HEATMAP}  size={capture.shape}")

    # Verify scan script exists before triggering
    if os.path.exists(SCAN_SCRIPT):
        print(f"[TEST] Scan script found  -> would trigger: {PYTHON_EXE} {SCAN_SCRIPT} --no-view")
        # Uncomment to actually fire:
        # subprocess.Popen([PYTHON_EXE, SCAN_SCRIPT, "--no-view"],
        #                  creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        print(f"[TEST] Scan script NOT found at {SCAN_SCRIPT}")

# ── Main loop ─────────────────────────────────────────────────────────────────
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("No webcam found — cannot run test.")
    exit(1)

print("\n=== Test running ===")
print("  S = activate hand detection (simulates first S-key capture)")
print("  O = draw ROI")
print("  Q = quit\n")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    display = frame.copy()

    # Hand detection
    result = hands_detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    hands_present = bool(result.multi_hand_landmarks)

    if result.multi_hand_landmarks:
        for lm in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(display, lm, _mp.HAND_CONNECTIONS)

    # Draw ROI overlay
    if roi is not None:
        x, y, w, h = roi
        cv2.rectangle(display, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.putText(display, "ROI", (x, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    # Timer / trigger logic
    if hands_detection_active:
        if hands_present:
            last_hand_time = time.time()
            archived = False
        elif not archived:
            elapsed = time.time() - last_hand_time
            remaining = HANDS_TIMEOUT - elapsed
            cv2.putText(display, f"No hands: {elapsed:.1f}s / {HANDS_TIMEOUT}s",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 80, 255), 2)
            if elapsed >= HANDS_TIMEOUT:
                print(f"\n[TRIGGER] {HANDS_TIMEOUT}s elapsed — archiving + scan")
                archive_and_scan(frame)
                archived = True

    # Status overlay
    status = "ACTIVE" if hands_detection_active else "INACTIVE (press S)"
    colour = (0, 200, 0) if hands_detection_active else (0, 0, 200)
    cv2.putText(display, f"Hand detection: {status}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
    hands_txt = "HANDS DETECTED" if hands_present else "no hands"
    cv2.putText(display, hands_txt, (10, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0) if hands_present else (100, 100, 100), 2)

    cv2.imshow("ipad_stream logic test", display)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break
    elif key == ord('s'):
        hands_detection_active = True
        last_hand_time = time.time()
        print("[TEST] Hand detection activated (first capture simulated)")
    elif key == ord('o'):
        set_roi(frame)

cap.release()
cv2.destroyAllWindows()
print("\nTest complete.")
