# 倉庫管理系統
## 說明
基於 python 以及 mondgdb 寫出來的倉庫管理工具  
版本使用 python@3.12 測試  
依賴項目請使用 <code>"pip install -r requirements.txt"</code>   
  
## 啟用
庫管理系統後台 使用 <code>python app.py</code> 執行   
~~倉庫管理 使用 <code>python gui.py</code> 執行~~ (停止維護)  
配置env及隧道 使用 <code>python start_dns.py</code> 執行   
LineBot開機 使用 <code>python line.py</code> 執行  
>Windows 系統可以直接使用 start_total 一次打開
## 配置  
到 ./config 進行相關配置  
server_config: 伺服器端配置  
item_id: 配置esp32物品 

## .env 配置範例:  
```
LINE_CHANNEL_SECRET=""
LINE_CHANNEL_ACCESS_TOKEN=""
LINE_DNS_TOKEN=""
WEB_DNS_TOKEN=""
```
<br >
剩下我懶得寫，幫我提交3Q~  
<br><br>

#### 補充當前物品可掛載tag: <br>
"no_auto_remove" [bool]: 是否關閉自動移除(默認false)  
"unit_weight" [int]: 單位重量<br>
"min_weight_warning" [int]: 補貨重量警告線<br>
