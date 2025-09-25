@echo off
echo Starting Python applications...

chcp 65001

cd /d "%~dp0"
echo Current directory: %cd%


start "Python App 1" cmd /k "cd /d "%~dp0" && python app.py"


start "Python App 2" cmd /k "cd /d "%~dp0" && python line.py"


start "Python App 3" cmd /k "cd /d "%~dp0" && python start_dns.py"

echo All Python applications started.