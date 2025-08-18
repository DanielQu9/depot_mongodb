#!/bin/zsh
echo "Starting Python applications..."

# 設定工作目錄為腳本所在目錄
cd "$(dirname "$0")"
echo "Current directory: $(pwd)"

# 取得當前目錄路徑
CURRENT_DIR=$(pwd)

# 在新Terminal視窗中執行第一個Python檔案
osascript -e "tell application \"Terminal\" to do script \"cd '$CURRENT_DIR' && source .venv/bin/activate && python app.py\""

# 在新Terminal視窗中執行第二個Python檔案
osascript -e "tell application \"Terminal\" to do script \"cd '$CURRENT_DIR' && source .venv/bin/activate && python line.py\""

# 在新Terminal視窗中執行第三個Python檔案
osascript -e "tell application \"Terminal\" to do script \"cd '$CURRENT_DIR' && source .venv/bin/activate && python start_dns.py\""

echo "All Python applications started."