# 倉庫管理系統
基於 python 以及 mondgdb 寫出來的倉庫管理工具 <br>
版本使用 python@3.12 測試 <br>
依賴項目請使用 <code>"pip install -r requirements.txt"</code> <br>
<br>
倉庫管理 使用 <code>python gui.py</code> 執行<br>
網頁秤重 使用 <code>python app.py</code> 執行<br>
LineBot開機 使用 <code>python line.py</code> 執行<br>
開啟cloudflared隧道 使用 <code>python start_dns.py</code> 執行<br>
<br>
.env 配置範例:<br>
<code>
LINE_CHANNEL_SECRET=""
LINE_CHANNEL_ACCESS_TOKEN=""
LINE_DNS_TOKEN=""
WEB_DNS_TOKEN=""
</code>
<br><br>
剩下我懶得寫，幫我提交3Q~<br>
<br><br>
### 補充當前物品可掛載tag:<br>
"no_auto_remove" [bool]: 是否關閉自動移除(默認false)<br>
"unit_weight" [int]: 單位重量<br>
"min_weight_warning" [int]: 補貨重量警告線<br>
