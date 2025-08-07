from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from depot import Depot, DepotItem, DepotError, DepotMongo
import json
import httpx


# ---- 初始化配置 ----
app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory="static"), name="static")  # 掛載靜態資源
templates = Jinja2Templates(directory="templates")  # 模板目錄

# ---- 全域物件初始化 ----
depot = Depot()
mg = DepotMongo()


class ConnectionManager:
    """連線管理器, 維護瀏覽器客戶端連線與 ESP32 狀態"""

    def __init__(self):
        self.clients: list[WebSocket] = []
        self.esp_connected: bool = False

    async def connect_client(self, websocket: WebSocket):
        await websocket.accept()
        self.clients.append(websocket)

    def disconnect_client(self, websocket: WebSocket):
        if websocket in self.clients:
            self.clients.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.clients:
            try:
                await connection.send_text(message)
            except:
                pass

    async def broadcast_json(self, message: dict):
        for connection in self.clients:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


# ---- 路由定義 ----
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    side_items = [
        {"name": "首頁", "endpoint": "home"},
        {"name": "ESP32即時顯示", "endpoint": "esp_live"},
        {"name": "倉庫", "endpoint": "inventory"},
        {"name": "出/入貨物", "endpoint": "stock_input"},
        {"name": "貨物紀錄", "endpoint": "records"},
        {"name": "狀態", "endpoint": "status_page"},
    ]
    return templates.TemplateResponse(
        "base.html", {"request": request, "side_items": side_items}
    )


@app.get("/home", response_class=HTMLResponse)
async def home(request: Request):
    """首頁"""
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/esp", response_class=HTMLResponse, name="esp_live")
async def esp_live(request: Request):
    """即時顯示秤重重量"""
    return templates.TemplateResponse("live.html", {"request": request})


@app.get("/inventory", response_class=HTMLResponse)
async def inventory(request: Request):
    """倉庫庫存"""
    inv = depot.get_inventory()
    return templates.TemplateResponse(
        "inventory.html", {"request": request, "items": inv}
    )


@app.get("/records", response_class=HTMLResponse)
async def records(request: Request):
    """進出貨紀錄 - 輸出框架網頁"""
    mg.__init__()  # 初始化mg
    table_list = sorted(mg.date_collections, reverse=True)
    return templates.TemplateResponse(
        "records.html", {"request": request, "tables": table_list}
    )


@app.get("/records/data", response_class=HTMLResponse)
async def records_data(request: Request, date: str):
    """進出貨紀錄 - 輸出紀錄"""
    data = mg.find_records(date)
    return templates.TemplateResponse(
        "records_data.html", {"request": request, "data": data, "date": date}
    )


@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """回傳狀態頁"""
    return templates.TemplateResponse(
        "status.html", {"request": request, "framework": "FastAPI"}
    )


@app.get("/status/data", response_class=HTMLResponse)
async def status_data(request: Request):
    """檢查各服務是否上線"""
    services = [
        {"name": "LineBot", "url": "https://depot-line.dx-q.net/status"},
        {"name": "WEB 服務", "url": "https://depot-web.dx-q.net/home"},
        {"name": "ESP32", "url": "WebSocket"},  # 請確保ESP32的index在2, 不然下面自己改
    ]
    results = []

    async with httpx.AsyncClient(timeout=3.0) as client:
        for svc in services:
            try:
                resp = await client.get(svc["url"])
                online = resp.status_code < 400
            except:
                online = False
            results.append({"name": svc["name"], "url": svc["url"], "online": online})

        # 檢查ESP32是否上線:
        if manager.esp_connected:
            results[2]["online"] = True

    return JSONResponse(content={"results": results})


@app.get("/stock/input", response_class=HTMLResponse)
async def stock_input(request: Request):
    """貨物進出 - 框架網頁"""
    inv = depot.get_inventory()
    existing_items = list(inv.keys()) if inv else None
    return templates.TemplateResponse(
        "stock_input.html", {"request": request, "items": existing_items}
    )


@app.post("/stock/submit")
async def stock_submit(stock_data: list[dict]):
    """貨物進出 - 資料處理"""
    fail_data = []
    for stock in stock_data:
        try:
            depot.write(
                DepotItem(stock["type"], stock["item"], stock["amount"]), source="app"
            )
        except DepotError as err:
            fail_data.append(str(err))
        except Exception as err:
            fail_data.append(str(err))
    if not fail_data:
        return {"status": "success", "count": len(stock_data)}
    return {
        "status": "failure",
        "msg": f"共{len(fail_data)}筆資料均已忽略，原因:\n{''.join(fail_data)}",
    }


# ---- WebSocket: 瀏覽器客戶端 ----
@app.websocket("/ws/client")
async def ws_client(websocket: WebSocket):
    """WebSocket協議 - 瀏覽器端"""
    await manager.connect_client(websocket)
    # 初次連線時發送當前 ESP32 連線狀態
    await websocket.send_json({"type": "status", "esp": manager.esp_connected})
    try:
        while True:
            await websocket.receive_text()  # 保持連線，只處理斷線情況
    except WebSocketDisconnect:
        manager.disconnect_client(websocket)


# ---- WebSocket: ESP32 ----
@app.websocket("/ws/esp32")
async def ws_esp32(websocket: WebSocket):
    """WebSocket協議 - esp32端"""
    await websocket.accept()
    manager.esp_connected = True
    # ESP32 連線時，通知所有瀏覽器客戶端
    await manager.broadcast_json({"type": "status", "esp": True})
    try:
        while True:
            raw = await websocket.receive_text()
            # 廣播接收到的原始資料給瀏覽器客戶端
            await manager.broadcast(raw)
            # 處理並寫入出貨資料
            data = json.loads(raw)
            do_depot(data)
    except WebSocketDisconnect:
        manager.esp_connected = False
        # ESP32 斷線時，通知所有瀏覽器客戶端
        await manager.broadcast_json({"type": "status", "esp": False})


def do_depot(data: dict):
    """處理 ESP32 傳來的出貨資料，並寫入 Depot"""
    if not data or data.get("final", False):
        return
    try:
        small = DepotItem("out", "small", data.get("small", 0))
        big = DepotItem("out", "big", data.get("big", 0))
        tube = DepotItem("out", "tube", data.get("tube", 0))
        depot.write(small, source="esp")
        depot.write(big, source="esp")
        depot.write(tube, source="esp")
        # print("[Depot]-info: write_down")
    except DepotError as err:
        print(f"[Depot]-error: {err}")


# ---- 自訂 404 錯誤處理 ----
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """自訂 404 頁面"""
    if exc.status_code == 404:
        return templates.TemplateResponse(
            "404.html", {"request": request}, status_code=404
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app_Fast:app", host="127.0.0.1", port=5000, reload=True)
