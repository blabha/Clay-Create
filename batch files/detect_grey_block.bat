@echo off
if "%~1"=="" (
    echo Usage: detect_grey_block.bat [file.ply]
    echo        detect_grey_block.bat --capture
    pause
    exit /b 1
)
"C:\Users\Bhavana\AppData\Local\Python\pythoncore-3.14-64\python.exe" "c:\Users\Bhavana\Documents\Hardware 3\Point cloud\processing\detect_grey_block.py" %*
pause
