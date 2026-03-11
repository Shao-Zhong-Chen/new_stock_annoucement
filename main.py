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
                # 取得代號
                code_match = re.search(r'(\d{4,})', cells[1].get_text())
                if code_match:
                    code = code_match.group(1)
                    # 索引：[5] 收盤價, [9] 報酬率(%)
                    m_price = cells[5].get_text(strip=True).replace(',', '')
                    yield_val = cells[9].get_text(strip=True).replace('%', '')
                    prices[code] = {
                        'market_price': float(m_price) if m_price and m_price != '--' else 0,
                        'yield': yield_val
                    }
    except Exception as e:
        print(f"⚠️ HiStock 資料抓取失敗: {e}")
    return prices

def get_today_tw():
    """獲取台灣目前的日期 (民國年且補零)，例如 115/03/11"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    return f"{now.year - 1911}/{now.strftime('%m/%d')}"

def run_crawler():
    # 初始化 API 客戶端
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
            today_tw = get_today_tw()
            messages_to_send = []
            
            # 讀取上次代號紀錄 [cite: 2]
            last_code = ""
            if os.path.exists(LAST_ID_FILE):
                with open(LAST_ID_FILE, "r") as f:
                    last_code = f.read().strip()

            for idx, item in enumerate(twse_data):
                # 正確欄位索引：
                # [2]名稱, [3]代號, [5]開始日, [6]截止日, [11]股數, [12]承銷單價
                name = item[2].strip()
                code = str(item[3]).strip()
                start_date = item[5].strip()
                end_date = item[6].strip()
                
                # 判定邏輯：只要今天在申購期間內（含開始與結束當日）
                if start_date <= today_tw <= end_date:
                    try:
                        shares = int(item[11].replace(',', ''))
                        sub_price_per_share = float(item[12].replace(',', ''))
                    except (ValueError, IndexError):
                        continue

                    h_data = histock_info.get(code, {'market_price': 0, 'yield': 'N/A'})
                    
                    # 計算總金額
                    # 申購價 = 承銷價 * 股數
                    total_sub_price = int(sub_price_per_share * shares)
                    # 價差 = (現價 - 承銷價) * 股數
                    total_diff = 0
                    if h_data['market_price'] > 0:
                        total_diff = int((h_data['market_price'] - sub_price_per_share) * shares)

                    # 依照預期格式組合訊息
                    msg = (
                        f"📢 抽籤通知\n"
                        f"{name}({code})\n"
                        f"　價差：{total_diff:,}元（~{h_data['yield']}%）\n"
                        f"　申購價：{total_sub_price:,}元\n"
                        f"　截止日期：{end_date}"
                    )
                    messages_to_send.append(TextMessage(text=msg))

                    # 紀錄最新一筆股票代號
                    if idx == 0 and code != last_code:
                        with open(LAST_ID_FILE, "w") as f:
                            f.write(code)

            # --- 執行發送 ---
            if messages_to_send:
                # 只要有股票資訊，就附加 Percento Flex Message
                flex_msg = FlexMessage(
                    alt_text="🎁 領取您的 Percento 專屬折扣",
                    contents=get_percento_flex()
                )
                messages_to_send.append(flex_msg)
                
                # LINE 一次 Push 最多 5 則訊息
                line_bot_api.push_message(PushMessageRequest(
                    to=GROUP_ID, 
                    messages=messages_to_send[:5]
                ))
                print(f"✅ 成功發送 {len(messages_to_send)} 則訊息。")
            else:
                print(f"今日 ({today_tw}) 無符合申購期間之案件。")

        except Exception as e:
            print(f"❌ 執行失敗：{e}")

if __name__ == "__main__":
    run_crawler()
