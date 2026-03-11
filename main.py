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
    """精準抓取 HiStock 資訊：市價與報酬率"""
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
                code_match = re.search(r'(\d{4,})', cells[1].get_text())
                if code_match:
                    code = code_match.group(1)
                    # 索引：[5]是收盤價, [9]是報酬率
                    market_price_str = cells[5].get_text(strip=True).replace(',', '')
                    yield_str = cells[9].get_text(strip=True).replace('%', '')
                    prices[code] = {
                        'market_price': float(market_price_str) if market_price_str and market_price_str != '--' else 0,
                        'yield': yield_str
                    }
    except Exception as e:
        print(f"HiStock 輔助抓取失敗: {e}")
    return prices

def get_today_tw():
    """取得今天民國年日期 (補零格式)，例如 115/03/11"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    return f"{now.year - 1911}/{now.strftime('%m/%d')}"

def run_crawler():
    conf = Configuration(access_token=LINE_ACCESS_TOKEN)
    with ApiClient(conf) as api_client:
        line_bot_api = MessagingApi(api_client)
        try:
            print("正在連線證交所 API...")
            res = requests.get(API_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            twse_data = res.json().get('data', [])
            if not twse_data: 
                print("今日證交所無資料。")
                return

            histock_info = get_histock_prices()
            today_tw = get_today_tw()
            messages_to_send = []
            trigger_flex = False

            # 讀取上次代號
            last_code = ""
            if os.path.exists(LAST_ID_FILE):
                with open(LAST_ID_FILE, "r") as f: last_code = f.read().strip()

            # 證交所 API 資料由新到舊排列
            for idx, item in enumerate(twse_data):
                # 修正後的正確索引：
                # [2]名稱, [3]代號, [6]截止日, [11]股數, [12]承銷價
                name = item[2].strip()
                code = str(item[3]).strip()
                end_date = item[6].strip()
                
                try:
                    shares = int(item[11].replace(',', ''))
                    sub_price = float(item[12].replace(',', ''))
                except ValueError:
                    continue # 若數值解析失敗則跳過該筆

                h_data = histock_info.get(code, {'market_price': 0, 'yield': 'N/A'})
                
                # 計算：(市價 - 申購價) * 股數
                total_sub_price = int(sub_price * shares)
                diff_per_share = (h_data['market_price'] - sub_price) if h_data['market_price'] > 0 else 0
                total_diff = int(diff_per_share * shares)
                
                # 判定邏輯：最新一筆新案公告 OR 截止日是今天
                is_new = (idx == 0 and code != last_code)
                is_deadline = (end_date == today_tw)

                if is_new or is_deadline:
                    msg = (
                        f"📢 抽籤通知\n"
                        f"{name}({code})\n"
                        f"　價差：{total_diff:,}元（~{h_data['yield']}%）\n"
                        f"　申購價：{total_sub_price:,}元\n"
                        f"　截止日期：{end_date}"
                    )
                    messages_to_send.append(TextMessage(text=msg))
                    trigger_flex = True
                    
                    if is_new:
                        with open(LAST_ID_FILE, "w") as f: f.write(code)

            if trigger_flex:
                flex = FlexMessage(alt_text="🎁 領取您的 Percento 專屬折扣", contents=get_percento_flex())
                messages_to_send.append(flex)
            
            if messages_to_send:
                # LINE SDK v3 限制一次最多 5 則訊息
                line_bot_api.push_message(PushMessageRequest(to=GROUP_ID, messages=messages_to_send[:5]))
                print(f"✅ 成功發送 {len(messages_to_send)} 則通知。")
            else:
                print(f"今日 ({today_tw}) 無符合條件之案件。")

        except Exception as e:
            print(f"❌ 執行失敗：{e}")

if __name__ == "__main__":
    run_crawler()
