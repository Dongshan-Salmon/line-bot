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
    # 移除 ReplyMessageRequest，因為我們不再使用 Reply API
    PushMessageRequest, # 改為匯入 PushMessageRequest
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
import os
import requests
import threading # 導入 threading 模組

app = Flask(__name__)

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
    return 'OK' # 無論如何都先回傳 'OK'

# --- 這是修改的核心 ---

def process_message_in_background(event):
    """
    這個函式會在背景執行緒中處理所有耗時的任務
    """
    user_id = event.source.user_id
    user_message = event.message.text
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # 1. (可選) 告知使用者系統已啟動，正在處理中
        # 如果不希望傳送這則訊息，可以將以下區塊註解掉
        line_bot_api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text='🤖 機器人啟動中，請稍候...')]
            )
        )

        # 2. 準備並呼叫 Dify API
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

        # 3. 將 Dify 的最終答案「推送」給使用者
        line_bot_api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=reply_text)]
            )
        )

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # 建立一個背景執行緒來處理訊息，主執行緒可以立刻返回
    thread = threading.Thread(target=process_message_in_background, args=(event,))
    thread.start()


# --- 啟動伺服器 (維持不變) ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
