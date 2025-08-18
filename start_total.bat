@echo off
echo Starting Python applications...

REM 設定工作目錄為批次檔所在目錄
cd /d "%~dp0"
echo Current directory: %cd%

REM 在新視窗中執行第一個Python檔案
start "Python App 1" cmd /k "cd /d "%~dp0" && python app.py"

REM 在新視窗中執行第二個Python檔案
start "Python App 2" cmd /k "cd /d "%~dp0" && python line.py"

REM 在新視窗中執行第三個Python檔案
start "Python App 3" cmd /k "cd /d "%~dp0" && python start_dns.py"

echo All Python applications started.