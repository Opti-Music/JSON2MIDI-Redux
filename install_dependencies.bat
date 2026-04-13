@echo off
echo.

if not exist "venv\Scripts\activate.bat" (
    echo Create a virtual environment...
    python -m venv venv
    echo Done creating virtual environment!
    echo.
)

echo Activate virtual environment..
call venv\Scripts\activate.bat

echo.
echo Install dependencies...
pip install -r requirements.txt

echo.
echo The process has done!
pause
exit /b