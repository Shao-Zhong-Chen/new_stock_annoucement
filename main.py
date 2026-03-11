import os
import time
import requests
import datetime
import re
from bs4 import BeautifulSoup
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage, FlexMessage
)
from flex_manager import get_percento_flex

LINE_ACCESS_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID')
API_URL = f"https://www.twse.com.tw/rwd/zh/announcement/publicForm?response=json&_={int(time.time() * 1000)}"
LAST_ID_FILE = "last_stock_id.txt"

def get_histock_prices():
    """精準抓取 HiStock 資訊：收盤價"""
    prices = {}
    try:
        url = "https://histock.tw/stock/public.aspx"
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        table = soup.find('table', {'class': 'gvTB'})
        if table:
            rows = table.find_all('tr')[1:]
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 10: continue
                # 索引校正：[1]名稱代號, [5]收盤價, [9]報酬率
                code_match = re.search(r'(\d{4,})', cells[1].get_text())
                if code_match:
                    code = code_match.group(1)
                    # 抓取收盤價 (處理逗號)
                    market_price_str = cells[5].get_text(strip=True).replace(',', '')
                    yield_str = cells[9].get_text(strip=True).replace('%', '')
                    prices[code] = {
                        'market_price': float(market_price_str) if market_price_str else 0,
                        'yield': yield_str
                    }
    except Exception as e:
        print(f"HiStock 輔助抓取失敗: {e}")
    return prices

def get_today_tw():
    """取得今天民國年日期 格式: 115/03/11"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    return f"{now.year - 1911}/{now.strftime('%m/%d')}"

def run_crawler():
    conf = Configuration(access_token=LINE_ACCESS_TOKEN)
    with ApiClient(conf) as api_client:
        line_bot_api = MessagingApi(api_client)
        try:
            res = requests.get(API_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            twse_data = res.json().get('data', [])
            if not twse_data: return

            histock_info = get_histock_prices()
            today_tw = get_today_tw()
            messages_to_send = []
            trigger_flex = False

            # 讀取上次代號
            last_code = ""
            if os.path.exists(LAST_ID_FILE):
                with open(LAST_ID_FILE, "r") as f: last_code = f.read().strip()

            for item in twse_data:
                # 證交所 API 欄位：[2]名稱, [3]代號, [4]股數, [6]截止日, [11]承銷價
                name = item[2].strip()
                code = str(item[3]).strip()
                shares = int(item[4].replace(',', ''))
                end_date = item[6].strip()
                sub_price = float(item[11].replace(',', ''))
                
                # 計算邏輯
                h_data = histock_info.get(code, {'market_price': 0, 'yield': 'N/A'})
                total_sub_price = int(sub_price * shares)
                # 價差 = (現價 - 申購價) * 股數
                total_diff = int((h_data['market_price'] - sub_price) * shares) if h_data['market_price'] > 0 else 0
                
                is_new = (code != last_code and item == twse_data[0])
                is_deadline = (end_date == today_tw)

                if is_new or is_deadline:
                    # 統一訊息格式為 📢 抽籤通知
                    msg = (
                        f"📢 抽籤通知\n"
                        f"{name}({code})\n"
                        f"　價差：{total_diff:,}元（~{h_data['yield']}%）\n"
                        f"　申購價：{total_sub_price:,}元\n"
                        f"　截止日期：{end_date}"
                    )
                    messages_to_send.append(TextMessage(text=msg))
                    trigger_flex = True
                    
                    if is_new: # 更新紀錄
                        with open(LAST_ID_FILE, "w") as f: f.write(code)

            if trigger_flex:
                flex = FlexMessage(alt_text="🎁 領取您的 Percento 專屬折扣", contents=get_percento_flex())
                messages_to_send.append(flex)
            
            if messages_to_send:
                # 避免訊息過多，只取前 5 則
                line_bot_api.push_message(PushMessageRequest(to=GROUP_ID, messages=messages_to_send[:5]))
                print("✅ 訊息發送成功")

        except Exception as e:
            print(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    run_crawler()