@echo off
echo -------------------------------------------------
echo  STEP 1 - Draw ROI   (press S to sample, Q to quit)
echo -------------------------------------------------
"C:\Users\Bhavana\AppData\Local\Python\pythoncore-3.14-64\python.exe" "c:\Users\Bhavana\Documents\Hardware 3\04_Point cloud\python\live_roi.py" %*

echo.
echo -------------------------------------------------
echo  STEP 2 - Capture and save foreground point cloud
echo -------------------------------------------------
"C:\Users\Bhavana\AppData\Local\Python\pythoncore-3.14-64\python.exe" "c:\Users\Bhavana\Documents\Hardware 3\04_Point cloud\python\capture_grey_block.py" %*

echo.
echo -------------------------------------------------
echo  STEP 3 - Starting hand detection monitor
echo -------------------------------------------------
start "Clay Create - Hand Monitor" "C:\Users\Bhavana\AppData\Local\Python\pythoncore-3.11-64\python.exe" "c:\Users\Bhavana\Documents\Hardware 3\03_Hands recognition\ipad_stream.py"

pause
