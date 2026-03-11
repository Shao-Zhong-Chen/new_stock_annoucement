import os
import sys
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    FlexMessage,
    FlexContainer
)

# 1. 取得環境變數 (與您的股票爬蟲一致)
LINE_ACCESS_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID')

# 安全檢查：確保金鑰都有抓到
if not LINE_ACCESS_TOKEN or not GROUP_ID:
    print("❌ 錯誤：找不到環境變數 LINE_ACCESS_TOKEN 或 GROUP_ID。")
    print("請檢查 GitHub Secrets 設定。")
    sys.exit(1)

def send_percento_flex():
    # 初始化 API 配置
    configuration = Configuration(access_token=LINE_ACCESS_TOKEN)
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # 2. 您提供的 Flex Message JSON 內容
        flex_contents = {
          "type": "bubble",
          "size": "giga",
          "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "25px",
            "contents": [
              {
                "type": "image",
                "url": "https://is1-ssl.mzstatic.com/image/thumb/PurpleSource221/v4/c7/b6/49/c7b64979-20b2-aea9-df0b-6571f99f7467/Placeholder.mill/200x200bb-75.webp",
                "size": "70px",
                "aspectMode": "cover",
                "align": "start",
                "cornerRadius": "14px"
              },
              {
                "type": "text",
                "text": "兌換 Percento 折扣",
                "weight": "bold",
                "size": "xl",
                "color": "#FFFFFF",
                "margin": "lg"
              },
              {
                "type": "box",
                "layout": "vertical",
                "margin": "xl",
                "backgroundColor": "#1A1F2B",
                "cornerRadius": "md",
                "paddingAll": "12px",
                "contents": [
                  {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                      {
                        "type": "text",
                        "text": "🎁 特別優惠",
                        "color": "#FED7AA",
                        "size": "sm",
                        "weight": "bold",
                        "flex": 1
                      },
                      {
                        "type": "text",
                        "text": "900A9848712A",
                        "color": "#FFFFFF",
                        "size": "xs",
                        "align": "end",
                        "weight": "bold",
                        "flex": 2
                      }
                    ]
                  }
                ]
              },
              {
                "type": "box",
                "layout": "vertical",
                "margin": "xxl",
                "spacing": "md",
                "contents": [
                  {
                    "type": "text",
                    "text": "若尚未安裝 App，請先下載 Percento。",
                    "color": "#ABB2BF",
                    "size": "sm",
                    "wrap": true
                  },
                  {
                    "type": "button",
                    "action": {
                      "type": "uri",
                      "label": "下載 Percento",
                      "uri": "https://apps.apple.com/app/apple-store/id1494319934?pt=2271561&mt=8&ct=discount_link_goose-ig"
                    },
                    "style": "primary",
                    "color": "#F97316",
                    "height": "md"
                  }
                ]
              }
            ]
          },
          "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "xs",
            "contents": [
              {
                "type": "text",
                "text": "截止至 2026/05/12 02:42:49 UTC",
                "size": "xxs",
                "color": "#6B7280",
                "align": "center"
              },
              {
                "type": "text",
                "text": "適用於 Percento 5.0.7 以上版本",
                "size": "xxs",
                "color": "#6B7280",
                "align": "center"
              }
            ],
            "paddingBottom": "20px"
          },
          "styles": {
            "body": {
              "backgroundColor": "#0B0F19"
            },
            "footer": {
              "backgroundColor": "#0B0F19"
            }
          }
        }

        # 3. 封裝 Flex 訊息物件
        # v3 必須使用 FlexContainer.from_dict 轉換 JSON
        flex_message = FlexMessage(
            alt_text="🎁 領取您的 Percento 專屬折扣",
            contents=FlexContainer.from_dict(flex_contents)
        )

        # 4. 建立發送請求
        push_message_request = PushMessageRequest(
            to=GROUP_ID,
            messages=[flex_message]
        )

        try:
            line_bot_api.push_message(push_message_request)
            print("✅ Flex Message 發送成功！")
        except Exception as e:
            print(f"❌ 發送失敗。錯誤詳情：\n{e}")
            sys.exit(1)

if __name__ == "__main__":
    send_percento_flex()
