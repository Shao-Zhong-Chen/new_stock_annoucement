import os
import time
import requests
import datetime
import re
from bs4 import BeautifulSoup
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage, FlexMessage
)
# 引用您獨立出來的 Flex 管理器
from flex_manager import get_percento_flex

# 1. 環境變數設定
LINE_ACCESS_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID')
# 加入動態 timestamp 避免 API 快取問題
API_URL = f"https://www.twse.com.tw/rwd/zh/announcement/publicForm?response=json&_={int(time.time() * 1000)}"
LAST_ID_FILE = "last_stock_id.txt"

def get_histock_prices():
    """從 HiStock 獲取即時市價與報酬率"""
    prices = {}
    try:
        url = "https://histock.tw/stock/public.aspx"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        res = requests.get(url, headers=headers, timeout=15)
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
                    m_price = cells[5].get_text(strip=True).replace(',', '')
                    yield_val = cells[9].get_text(strip=True).replace('%', '')
                    prices[code] = {
                        'market_price': float(m_price) if m_price and m_price != '--' else 0,
                        'yield': yield_val
                    }
    except Exception as e:
        print(f"⚠️ HiStock 資料抓取失敗: {e}")
    return prices

# 🆕 新增：將 TWSE 民國日期轉為西元 datetime.date 物件
def parse_twse_date(date_str):
    parts = date_str.split('/')
    return datetime.date(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))

def run_crawler():
    conf = Configuration(access_token=LINE_ACCESS_TOKEN)
    with ApiClient(conf) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        try:
            print("正在連線證交所 API...")
            res = requests.get(API_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            data = res.json()
            twse_data = data.get('data', [])
            
            if not twse_data:
                print("今日證交所無公開申購資料。")
                return

            histock_info = get_histock_prices()
            
            # 🆕 修正：獲取「今日」的 datetime.date 物件
            today_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
            messages_to_send = []
            
            last_code = ""
            if os.path.exists(LAST_ID_FILE):
                with open(LAST_ID_FILE, "r") as f:
                    last_code = f.read().strip()

            for idx, item in enumerate(twse_data):
                name = item[2].strip()
                code = str(item[3]).strip()
                
                # 🆕 修正：將 API 日期轉為真正的日期物件
                try:
                    start_date_obj = parse_twse_date(item[5].strip())
                    end_date_obj = parse_twse_date(item[6].strip())
                except Exception as e:
                    print(f"日期解析失敗 ({code}): {e}")
                    continue
                
                # 🎯 修正核心：用日期物件進行比對，不管跨月、補零都不會錯！
                if start_date_obj <= today_date <= end_date_obj:
                    try:
                        shares = int(item[11].replace(',', ''))
                        sub_price_per_share = float(item[12].replace(',', ''))
                    except (ValueError, IndexError):
                        continue

                    h_data = histock_info.get(code, {'market_price': 0, 'yield': 'N/A'})
                    
                    total_sub_price = int(sub_price_per_share * shares)
                    total_diff = 0
                    if h_data['market_price'] > 0:
                        total_diff = int((h_data['market_price'] - sub_price_per_share) * shares)

                    msg = (
                        f"📢 抽籤通知\n"
                        f"{name}({code})\n"
                        f"　價差：{total_diff:,}元（~{h_data['yield']}%）\n"
                        f"　申購價：{total_sub_price:,}元\n"
                        f"　截止日期：{item[6].strip()}"
                    )
                    messages_to_send.append(TextMessage(text=msg))

                    if idx == 0 and code != last_code:
                        with open(LAST_ID_FILE, "w") as f:
                            f.write(code)

            # --- 執行發送 ---
            if messages_to_send:
                # 🆕 修正：確保股票訊息最多 4 則，保留第 5 則的位置給 Flex Message
                final_messages = messages_to_send[:4]
                
                flex_msg = FlexMessage(
                    alt_text="🎁 領取您的 Percento 專屬折扣",
                    contents=get_percento_flex()
                )
                final_messages.append(flex_msg)
                
                line_bot_api.push_message(PushMessageRequest(
                    to=GROUP_ID, 
                    messages=final_messages
                ))
                print(f"✅ 成功發送 {len(final_messages)} 則訊息 (含折扣推播)。")
            else:
                print(f"今日 ({today_date}) 無符合申購期間之案件。")

        except Exception as e:
            print(f"❌ 執行失敗：{e}")

if __name__ == "__main__":
    run_crawler()
