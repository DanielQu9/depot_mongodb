from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sock import Sock
from depot import Depot, DepotItem, DepotError, DepotMongo
import threading
import requests
import json


# ==== 初始化設定 ====
app = Flask(__name__)
sock = Sock(app)
depot = Depot()
mg = DepotMongo()
clients = set()  # websocket-瀏覽器 列隊
clients_lock = threading.Lock()  # websocket-瀏覽器 鎖
esp_connected = False  # websocket-esp 列隊
esp_lock = threading.Lock()  # websocket-esp 鎖


@app.route("/")
def index():
    # side_items：可動態新增選單
    side_items = [
        {"name": "首頁", "endpoint": "home"},
        {"name": "ESP32即時顯示", "endpoint": "esp_live"},
        {"name": "倉庫", "endpoint": "inventory"},
        {"name": "出/入貨物", "endpoint": "stock_input"},
        {"name": "貨物紀錄", "endpoint": "records"},
        {"name": "狀態", "endpoint": "status"},
        # 日後再加頁面，就在這邊添加
    ]
    return render_template("base.html", side_items=side_items)


@app.route("/home")
def home():
    """首頁"""
    return render_template("home.html")


@app.route("/inventory")
def inventory():
    """倉庫庫存"""
    inv = depot.get_inventory()
    return render_template("inventory.html", items=inv)


@app.route("/records")
def records():
    """進出貨紀錄-輸出列表"""
    table_list = sorted(mg.date_collections, reverse=True)  # 獲取所有資料表
    return render_template("records.html", tables=table_list)


@app.route("/records/data")
def records_data():
    """進出貨紀錄-輸出紀錄"""
    table_name = request.args.get("date")
    data = mg.find_records(str(table_name))
    return render_template("records_data.html", data=data, date=table_name)


@app.route("/status")
def status():
    services = [
        {"name": "LineBot", "url": "https://depot.dx-q.net/status"},
        {"name": "WEB 服務", "url": "https://depot-web.dx-q.net/home"},
        {"name": "ESP32", "url": "WebSocket"},  # 請確保ESP32的index在2, 不然下面自己改
    ]
    results = []

    # 檢查網站是否存活
    for svc in services:
        try:
            # 使用 HEAD 請求檢查，超時設為 3 秒
            resp = requests.head(svc["url"], timeout=3)
            online = resp.status_code < 400
        except:
            online = False
        results.append({"name": svc["name"], "url": svc["url"], "online": online})

    # 檢查ESP32是否上線:
    if esp_connected:
        results.append(
            {"name": services[2]["name"], "url": services[2]["url"], "online": True}
        )

    return render_template("status.html", results=results, framework="Flask")


@app.route("/stock/input")
def stock_input():
    """進出貨-功能選單"""
    inv = depot.get_inventory()
    existing_items = list(inv.keys()) if inv else None
    return render_template("stock_input.html", items=existing_items)


@app.route("/stock/submit", methods=["POST"])
def stock_submit():
    """進出貨-提交選單"""
    fail_data = []
    data = request.get_json()
    for stock in data:
        try:
            depot.write(
                DepotItem(stock["type"], stock["item"], stock["amount"]), source="app"
            )
        except DepotError as err:
            fail_data.append(err.message)
        except Exception as err:
            fail_data.append(err)

    if fail_data == []:
        return {"status": "success", "count": len(data)}
    else:
        return {
            "status": "failure",
            "msg": f"共{len(fail_data)}均已忽略, 原因:\n {''.join(f'{i}\n' for i in fail_data)}",
        }


@app.route("/esp")
def esp_live():
    """即時顯示秤重重量"""
    return render_template("live.html")


@sock.route("/ws/client")
def ws_client(ws):
    """WebSocket協議, 瀏覽器端"""
    # 新連線加入 clients
    with clients_lock:
        clients.add(ws)
    # 初次建立時先告知當前 ESP32 狀態
    with esp_lock:
        ws.send(json.dumps({"type": "status", "esp": esp_connected}))
    try:
        # 只要連線沒斷，就保持 open（也可接收來自前端的訊息）
        while True:
            msg = ws.receive()
            if msg is None:
                break
    finally:
        with clients_lock:
            clients.discard(ws)


@sock.route("/ws/esp32")
def ws_esp32(ws):
    """WebSocket協議, esp32端"""
    # ESP32 一旦連上，更新狀態並廣播，再持續接收它送來的 JSON 資料
    global esp_connected
    with esp_lock:
        esp_connected = True
    # 廣播給所有瀏覽器：ESP32 已連線
    with clients_lock, esp_lock:
        for c in list(clients):
            try:
                c.send(json.dumps({"type": "status", "esp": True}))
            except:
                pass

    while True:
        raw = ws.receive()
        if raw is None:
            break

        # 將接收到的內容轉傳給所有瀏覽器 clients
        with clients_lock:
            for client in list(clients):
                try:
                    client.send(raw)
                except:
                    # 跳過已斷線的 client
                    pass

        # 處理資料
        do_depot(json.loads(raw))

    # ESP32 斷線時，更新狀態並廣播
    with esp_lock:
        esp_connected = False
    with clients_lock, esp_lock:
        for c in list(clients):
            try:
                c.send(json.dumps({"type": "status", "esp": False}))
            except:
                pass


def do_depot(jsonfile):
    """寫入esp32出貨資料"""
    data = jsonfile
    final = data.get("final", False)
    if (not data) or (final):
        return

    # 處理資料
    try:
        small = DepotItem("out", "small", data["small"])
        big = DepotItem("out", "big", data["big"])
        tube = DepotItem("out", "tube", data["tube"])

        depot.write(small, "esp")
        depot.write(big, "esp")
        depot.write(tube, "esp")
        print(f"[Depot]-info: write_down")
    except DepotError as err:
        print(f"[Depot]-error: {err}")
        return jsonify({"status": "error", "message": f"deta_bad: {err}"})

    return jsonify({"status": "success", "message": "deta_ok"})


@app.route("/api/data")
def index_page_api_data():
    """暫時用不到\n回傳: item, count, unit_weight, min_weight_warning"""
    return redirect(url_for("home"))
    item = request.args.get("item")
    if not item:
        return jsonify({})
    inventory = depot.get_inventory()
    # 明確指定要查 tag 的 item
    tag = depot.get_tag_json(item)
    count = inventory.get(item, 0) if inventory else 0
    unit_w = tag.get("unit_weight", 0) if tag else None
    min_w = tag.get("min_weight_warning", 0) if tag else None
    return jsonify(
        {"item": item, "count": count, "unit_weight": unit_w, "min_weight": min_w}
    )


@app.errorhandler(404)
def page_not_found(e):
    """自訂 404 頁面"""
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True)
