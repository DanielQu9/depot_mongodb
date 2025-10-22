from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from depot import AsyncDepot, DepotItem, DepotError
import markdown
import asyncio
import httpx
import json
import time


# ---- 應用生命週期管理 ----
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 應用啟動時的初始化操作
    await depot.tool.clear_inventory(double_check=True)  # 初始化清空倉庫
    yield
    # 應用關閉時的清理操作（如果需要）


# ---- 初始化配置 ----
CONFIG = json.load(open("./config/server_config.json", "r", encoding="utf-8"))
ITEM_ID = json.load(open("./config/item_id.json", "r", encoding="utf-8"))
app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None, lifespan=lifespan)
# app.mount("/static", StaticFiles(directory="static"), name="static")  # 掛載靜態資源
templates = Jinja2Templates(
    directory=("templates" if not CONFIG.get("new_ui", False) else "new_templates")
)  # 模板目錄
app.add_middleware(  # 允許跨網域讀資源
    CORSMiddleware,
    allow_origins=[CONFIG["url"]["line"], CONFIG["url"]["line_local"]],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 全域物件初始化 ----
depot = AsyncDepot()
status_cache: list | None = None  # status狀態快取
status_cache_lock = asyncio.Lock()
status_last_time = time.time()  # status頁狀態-最後刷新時間
esp_do_depot_last = {}  # 暫存上次紀錄


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


def readme_to_html() -> str:
    """將readme轉成html"""
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            readme_md = f.read()
        return markdown.markdown(readme_md)
    except Exception as err:
        return "<h3>無法讀取 README.md</h3><p>目前無說明文件。</p>"


manager = ConnectionManager()
readme_html = readme_to_html()


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
    return templates.TemplateResponse(
        "home.html", {"request": request, "readme_html": readme_html}
    )


@app.get("/esp", response_class=HTMLResponse, name="esp_live")
async def esp_live(request: Request):
    """即時顯示秤重重量"""
    return templates.TemplateResponse("live.html", {"request": request})


@app.get("/inventory", response_class=HTMLResponse)
async def inventory(request: Request):
    """倉庫庫存"""
    inv = await depot.get_inventory()
    return templates.TemplateResponse(
        "inventory.html", {"request": request, "items": inv}
    )


@app.get("/records", response_class=HTMLResponse)
async def records(request: Request):
    """進出貨紀錄 - 輸出框架網頁"""
    table_list = sorted(await depot.date_collections, reverse=True)
    return templates.TemplateResponse(
        "records.html", {"request": request, "tables": table_list}
    )


@app.get("/records/data", response_class=HTMLResponse)
async def records_data(request: Request, date: str):
    """進出貨紀錄 - 輸出紀錄"""
    data = await depot.find_records(date)
    return templates.TemplateResponse(
        "records_data.html", {"request": request, "data": data, "date": date}
    )


@app.get("/status", response_class=HTMLResponse)
async def status_page(request: Request):
    """回傳狀態頁"""
    results = [{"name": "連線中", "url": "------連線中------"}]
    return templates.TemplateResponse(
        "status.html", {"request": request, "results": results, "framework": "FastAPI"}
    )


@app.get("/status/data")
async def status_data(request: Request):
    """檢查各服務是否上線"""
    global status_last_time, status_cache
    services = [
        {"name": "LineBot", "url": f"{CONFIG["url"]["line"]}/status"},
        {"name": "WEB 服務", "url": f"{CONFIG["url"]["web"]}/home"},
        {"name": "ESP32", "url": "WebSocket"},  # 請確保ESP32的index在2, 不然下面自己改
    ]
    results = []
    current_time = time.time()

    # 如果快取存在且未過期，直接返回快取結果
    if (status_cache is not None) and (status_last_time + 10 > current_time):
        return JSONResponse(content={"results": status_cache})

    async with status_cache_lock:
        # 雙重檢查，等鎖時防重複發送
        if (status_cache is not None) and (status_last_time + 10 > current_time):
            return JSONResponse(content={"results": status_cache})

        async with httpx.AsyncClient(timeout=3.0) as client:
            for svc in services:
                try:
                    resp = await client.get(svc["url"])
                    online = resp.status_code < 400
                except:
                    online = False
                results.append(
                    {"name": svc["name"], "url": svc["url"], "online": online}
                )

            # 檢查ESP32是否上線:
            if manager.esp_connected:
                results[2]["online"] = True

            status_last_time = current_time
            status_cache = results

            return JSONResponse(content={"results": results})


@app.get("/stock/input", response_class=HTMLResponse)
async def stock_input(request: Request):
    """貨物進出 - 框架網頁"""
    inv: dict = await depot.get_inventory()
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
            await depot.write(
                DepotItem(stock["type"], stock["item"], stock["amount"]), source="app"
            )
        except DepotError as err:
            fail_data.append(str(err))
        except Exception as err:
            fail_data.append(str(err))
    if not fail_data:
        return {"status": "success", "message": f"共{len(stock_data)}筆資料已成功處理"}
    return {
        "status": "error",
        "message": f"共{len(fail_data)}筆資料均已忽略，原因:\n{''.join(fail_data)}",
    }


@app.post("/menu_post")
async def menu_post(menu_data: dict):
    try:
        await menu_do_depot(menu_data)
        return {"status": "success", "message": "資料已成功寫入"}
    except Exception as err:
        return {"status": "error", "message": str(err)}


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
            await esp_do_depot(data)
    except WebSocketDisconnect:
        manager.esp_connected = False
        # ESP32 斷線時，通知所有瀏覽器客戶端
        await manager.broadcast_json({"type": "status", "esp": False})


# ---- 功能方法 ----
async def esp_do_depot(data: dict):
    """處理 ESP32 傳來的出貨資料，並寫入 Depot"""
    if (not data) or (not data.get("final", False)):
        return

    global esp_do_depot_last
    try:
        if data != esp_do_depot_last:
            item_dict: dict = {i["esp"]: i["name"] for i in ITEM_ID}
            for i in data:
                if i in item_dict:
                    await depot.write(
                        DepotItem(
                            "auto",
                            item_dict[i],
                            data[i] - esp_do_depot_last.get(i, 0),
                        ),
                        source="esp",
                    )
            esp_do_depot_last = data
    except DepotError as err:
        print(f"[Depot]-error: {err}")


async def menu_do_depot(data: dict):
    """處理 Menu 傳來的出貨資料，並寫入 Depot"""
    for i in data["items"]:
        try:
            await depot.write(DepotItem("out", i["material"], i["quantity"]), "menu")
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

    uvicorn.run("app:app", host="127.0.0.1", port=5000, reload=True)
