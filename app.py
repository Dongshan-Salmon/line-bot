# 匯入必要的模組
from flask import Flask, request, abort
from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
import os
import requests
import threading
import datetime # 導入 datetime 模組

app = Flask(__name__)

# --- 新增部分：記錄程式啟動時間 ---
# 這行程式碼只會在 Gunicorn 工作進程 (worker process) 啟動時執行一次
APP_START_TIME = datetime.datetime.utcnow()
# 設定一個閾值(秒)，用來判斷是否為剛喚醒
# 如果程式啟動時間在5秒以內，我們就視為「剛喚醒」
WAKE_UP_THRESHOLD_SECONDS = 5 
# ------------------------------------

# 從環境變數讀取 LINE 的金鑰
line_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.environ.get('LINE_CHANNEL_SECRET')

# 從環境變數讀取 Dify 的金鑰
dify_api_key = os.environ.get('DIFY_API_KEY')
dify_api_url = 'https://api.dify.ai/v1/chat-messages'

configuration = Configuration(access_token=line_access_token)
handler = WebhookHandler(line_channel_secret)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

def process_message_in_background(event):
    user_id = event.source.user_id
    user_message = event.message.text
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # --- 修改部分：根據運行時間判斷是否發送啟動訊息 ---
        time_since_startup = (datetime.datetime.utcnow() - APP_START_TIME).total_seconds()
        
        # 如果程式啟動至今的時間小於我們設定的閾值，才發送啟動訊息
        if time_since_startup < WAKE_UP_THRESHOLD_SECONDS:
            app.logger.info(f"Service waking up. Time since startup: {time_since_startup:.2f}s. Sending wake-up message.")
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text='🤖 機器人啟動中，請稍候...')]
                )
            )
        # ----------------------------------------------------

        # 準備並呼叫 Dify API (這部分邏輯不變)
        headers = {
            'Authorization': f'Bearer {dify_api_key}',
            'Content-Type': 'application/json',
        }
        data = {
            'inputs': {},
            'query': user_message,
            'user': user_id,
            'response_mode': 'blocking',
        }

        try:
            response = requests.post(dify_api_url, headers=headers, json=data)
            response.raise_for_status()
            dify_response_data = response.json()
            reply_text = dify_response_data.get('answer', '抱歉，我現在無法回答。')

        except requests.exceptions.RequestException as e:
            app.logger.error(f"Dify API request failed: {e}")
            reply_text = "系統忙碌中，請稍後再試。"

        # 將 Dify 的最終答案「推送」給使用者 (這部分邏輯不變)
        line_bot_api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=reply_text)]
            )
        )

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    thread = threading.Thread(target=process_message_in_background, args=(event,))
    thread.start()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
