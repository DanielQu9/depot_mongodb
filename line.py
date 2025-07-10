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


app = Flask(__name__)

env = dotenv_values()
line_bot_api = LineBotApi(env["LINE_CHANNEL_ACCESS_TOKEN"])
handler = WebhookHandler(env["LINE_CHANNEL_SECRET"])


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
    msg = event.message.text.strip()

    if msg.startswith("!"):  # 指令區域，未處理這邊可擴充
        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text="指令功能尚未實作")
        )
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
                    action=MessageAction(
                        label="檢視倉庫狀態", text="!check"
                    ),  # 佔位功能
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


if __name__ == "__main__":
    app.run(port=8000)
