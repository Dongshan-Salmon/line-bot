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

app = Flask(__name__)

# --- 這一段是修正的關鍵 ---
# 從 Render 的環境變數中讀取您的金鑰
# os.environ.get('KEY_NAME') 會去尋找您在 Render 環境變數中設定的 KEY_NAME
access_token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
channel_secret = os.environ.get('LINE_CHANNEL_SECRET')

# 使用從環境變數讀取到的值來設定
configuration = Configuration(access_token=access_token)
handler = WebhookHandler(channel_secret)
# --- 修正結束 ---


# 這個是 Webhook 的路徑，LINE Platform 會把使用者的訊息傳送到這裡
@app.route("/callback", methods=['POST'])
def callback():
    # 取得 X-Line-Signature 標頭值
    signature = request.headers['X-Line-Signature']

    # 取得請求主體
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # 處理 Webhook 主體
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

# 處理文字訊息事件
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        # 將收到的訊息原封不動地回傳
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=event.message.text)]
            )
        )

# 讓 Flask 應用程式可以被外部訪問
if __name__ == "__main__":
    # 取得 hosting 服務設定的 PORT，如果在本機測試，預設為 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
