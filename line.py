from flask import Flask, request, abort
from dotenv import dotenv_values
from linebot.v3 import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.messaging.models import FlexMessage
import json


app = Flask(__name__)

# read env
env = dotenv_values()
channel_secret = env["LINE_CHANNEL_SECRET"]
channel_access_token = env["LINE_CHANNEL_ACCESS_TOKEN"]

# 設定 handler 與 API
handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print(f"Error: {e}")
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    msg = event.message.text.strip()
    reply_token = event.reply_token

    if msg == "help":
        try:
            with open("./templates/bothelp.txt", "r", encoding="utf-8") as f:
                help_text = f.read()
        except FileNotFoundError:
            help_text = "找不到說明文件 🤔"
        reply = TextMessage(text=help_text, quickReply=None, quoteToken=None)

    elif msg == "web":
        reply = TextMessage(
            text="🌐 前往網站：https://example.com", quickReply=None, quoteToken=None
        )

    elif msg == "test":
        bubble_json = {  # 上面那段 JSON 貼到這裡
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "Hello, Bubble!",
                        "weight": "bold",
                        "size": "xl",
                        "align": "center",
                    },
                    {
                        "type": "text",
                        "text": "這是一個簡易的測試訊息。",
                        "size": "md",
                        "wrap": True,
                        "margin": "md",
                    },
                ],
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "action": {
                            "type": "message",
                            "label": "點我回覆",
                            "text": "我按了按鈕👍",
                        },
                    }
                ],
            },
        }

        reply = FlexMessage(
            altText="Bubble 測試", contents=bubble_json, quickReply=None
        )

    else:
        reply = TextMessage(
            text=f"輸入 help 以查閱指令表", quickReply=None, quoteToken=None
        )

    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message(
            ReplyMessageRequest(
                replyToken=reply_token, messages=[reply], notificationDisabled=True
            )
        )


if __name__ == "__main__":
    app.run(port=8000)
