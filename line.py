from flask import (
    Flask,
    request,
    abort,
    Response,
    render_template,
    jsonify,
    redirect,
    url_for,
)
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    FlexSendMessage,
    URIAction,
    MessageAction,
    BubbleContainer,
    BoxComponent,
    TextComponent,
    ButtonComponent,
)
from dotenv import dotenv_values
from depot import Depot
import requests
import json


app = Flask(__name__)

CONFIG = json.load(open("./config/server_config.json", "r", encoding="utf-8"))
env = dotenv_values()
line_bot_api = LineBotApi(env["LINE_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(env["LINE_CHANNEL_SECRET"])
depot = Depot()


@app.route("/")
def index():
    return redirect(url_for("line_web_menu", new=1))


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@app.route("/status")
def status():
    return Response(status=204)


@app.route("/line_web_menu")
def line_web_menu():
    if request.args.get("new") == "1":
        return render_template("new_line_menu.html")
    return render_template("line_web_menu.html")


@app.route("/sc", methods=["POST"])
def sc_do():
    try:
        # 接收來自前端的資料
        data = request.get_json()

        # 轉發到 sc
        response = requests.post(CONFIG["url"]["sc"], json=data, timeout=30)

        # 回傳結果給前端
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "SC request forwarded successfully",
                    "response_status": response.status_code,
                }
            ),
            response.status_code,
        )

    except requests.exceptions.RequestException as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Failed to forward SC request: {str(e)}",
                }
            ),
            500,
        )
    except Exception as e:
        return jsonify({"status": "error", "message": f"Internal error: {str(e)}"}), 500


@app.route("/xc", methods=["POST"])
def xc_do():
    try:
        # 接收來自前端的資料
        data = request.get_json()

        # 轉發到 xc
        response = requests.post(CONFIG["url"]["xc"], json=data, timeout=30)

        # 回傳結果給前端
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "XC request forwarded successfully",
                    "response_status": response.status_code,
                }
            ),
            response.status_code,
        )

    except requests.exceptions.RequestException as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"Failed to forward XC request: {str(e)}",
                }
            ),
            500,
        )
    except Exception as e:
        return jsonify({"status": "error", "message": f"Internal error: {str(e)}"}), 500


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg: str = event.message.text.strip()

    if msg.startswith("!"):  # 指令區域，未處理這邊可擴充
        reply_cmd: str = "unknow command."
        match msg[1:]:
            case "check":
                reply_cmd = get_depot_inventory()

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_cmd))
        return

    # 非指令 → 顯示功能選單 Bubble
    bubble = BubbleContainer(
        body=BoxComponent(
            layout="vertical",
            contents=[
                TextComponent(
                    text="📋 功能選單", weight="bold", size="xl", align="center"
                ),
            ],
        ),
        footer=BoxComponent(
            layout="vertical",
            contents=[
                ButtonComponent(
                    style="primary",
                    action=MessageAction(label="檢視倉庫狀態", text="!check"),
                ),
                ButtonComponent(
                    style="secondary",
                    action=URIAction(label="後台網站", uri=CONFIG["url"]["web"]),
                ),
                ButtonComponent(
                    style="primary",
                    action=URIAction(
                        label="前台網站",
                        uri=f"{CONFIG["url"]["line"]}/line_web_menu",
                    ),
                ),
                ButtonComponent(
                    style="secondary",
                    action=URIAction(
                        label="[TEST]新版前台網站",
                        uri=f"{CONFIG["url"]["line"]}/line_web_menu?new=1",
                    ),
                ),
                # ButtonComponent(
                #     style="secondary",
                #     action=MessageAction(label="（佔位按鈕）", text="!todo"),
                # ),
            ],
            spacing="md",
        ),
    )

    flex = FlexSendMessage(alt_text="功能選單", contents=bubble)
    line_bot_api.reply_message(event.reply_token, flex)


def get_depot_inventory():
    inventory = depot.get_inventory()
    reply = "當前倉庫剩餘:\n"
    if inventory is None:
        reply += "  無物品"
    else:
        for name, amount in inventory.items():
            reply += f"  {name}: {amount}\n"
    return reply


if __name__ == "__main__":
    app.run(port=8000, debug=True)
