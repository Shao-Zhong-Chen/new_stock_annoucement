# flex_manager.py
from linebot.v3.messaging import FlexContainer

def get_percento_flex():
    """管理 Percento 折扣的 Flex Message 模板"""
    content = {
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
                  { "type": "text", "text": "🎁 特別優惠", "color": "#FED7AA", "size": "sm", "weight": "bold", "flex": 1 },
                  { "type": "text", "text": "900A9848712A", "color": "#FFFFFF", "size": "xs", "align": "end", "weight": "bold", "flex": 2 }
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
              { "type": "text", "text": "若尚未安裝 App，請先下載 Percento。", "color": "#ABB2BF", "size": "sm", "wrap": True },
              {
                "type": "button",
                "action": {
                  "type": "uri",
                  "label": "下載 Percento",
                  "uri": "https://apps.apple.com/app/apple-store/id1494319934?pt=2271561&mt=8&ct=discount_link_goose-ig"
                },
                "style": "primary", "color": "#F97316", "height": "md"
              }
            ]
          }
        ]
      },
      "footer": {
        "type": "box", "layout": "vertical", "spacing": "xs", "paddingBottom": "20px",
        "contents": [
          { "type": "text", "text": "截止至 2026/05/12 02:42:49 UTC", "size": "xxs", "color": "#6B7280", "align": "center" },
          { "type": "text", "text": "適用於 Percento 5.0.7 以上版本", "size": "xxs", "color": "#6B7280", "align": "center" }
        ]
      },
      "styles": { "body": { "backgroundColor": "#0B0F19" }, "footer": { "backgroundColor": "#0B0F19" } }
    }
    return FlexContainer.from_dict(content)