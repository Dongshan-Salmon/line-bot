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
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
import os
import requests # 導入 requests 函式庫

app = Flask(__name__)

# 從環境變數讀取 LINE 的金鑰
line_access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = os.environ.get('LINE_CHANNEL_SECRET')

# 從環境變數讀取 Dify 的金鑰
dify_api_key = os.environ.get('DIFY_API_KEY')
dify_api_url = 'https://api.dify.ai/v1/chat-messages' # 這是 Dify 的對話 API URL

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

# --- 這是修改的核心 ---
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # 1. 準備呼叫 Dify API 所需的資料
    headers = {
        'Authorization': f'Bearer {dify_api_key}',
        'Content-Type': 'application/json',
    }
    data = {
        'inputs': {},
        'query': event.message.text, # 使用者傳來的訊息
        'user': event.source.user_id, # 使用者的 LINE User ID
        'response_mode': 'blocking',
    }

    # 2. 呼叫 Dify API
    try:
        response = requests.post(dify_api_url, headers=headers, json=data)
        response.raise_for_status() # 如果 API 回應錯誤 (非 2xx)，會拋出異常
        
        # 3. 取得 Dify 回傳的答案
        dify_response_data = response.json()
        reply_text = dify_response_data.get('answer', '抱歉，我現在無法回答。')

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Dify API request failed: {e}")
        reply_text = "系統忙碌中，請稍後再試。"

    # 4. 將 Dify 的答案回覆給使用者
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

# --- 啟動伺服器 (維持不變) ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
