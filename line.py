from flask import Flask, request, abort
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


app = Flask(__name__)

env = dotenv_values()
line_bot_api = LineBotApi(env["LINE_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(env["LINE_CHANNEL_SECRET"])
depot = Depot()


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


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
                    style="link",
                    action=URIAction(label="前往網站", uri="http://depot-web.dx-q.net"),
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
    app.run(port=8000)
