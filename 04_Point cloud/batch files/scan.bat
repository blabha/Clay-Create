@echo off
echo -------------------------------------------------
echo  STEP 1 - Draw ROI   (press S to sample, Q to quit)
echo -------------------------------------------------
py -3.14 "%~dp0..\python\live_roi.py" %*

echo.
echo -------------------------------------------------
echo  STEP 2 - Capture and save foreground point cloud
echo -------------------------------------------------
py -3.14 "%~dp0..\python\capture_grey_block.py" %*

echo.
echo -------------------------------------------------
echo  STEP 3 - Starting hand detection monitor
echo -------------------------------------------------
start "Clay Create - Hand Monitor" py -3.11 "%~dp0..\..\03_Hands recognition\ipad_stream.py"

pause
