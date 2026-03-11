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
            # 🆕 動態抓取欄位名稱，避免 HiStock 改版導致抓錯
            th_elements = table.find_all('th')
            headers_text = [th.get_text(strip=True) for th in th_elements]
            
            # 尋找「市價」與「報酬率(%)」的正確位置
            idx_market_price = next((i for i, h in enumerate(headers_text) if '市價' in h), 5)
            idx_yield = next((i for i, h in enumerate(headers_text) if '報酬率' in h), 9)

            rows = table.find_all('tr')[1:]
            for row in rows:
                cells = row.find_all('td')
                if len(cells) <= max(idx_market_price, idx_yield): continue
                
                # 取得代號
                code_match = re.search(r'(\d{4,})', cells[1].get_text())
                if code_match:
                    code = code_match.group(1)
                    # 取得市價與報酬率
                    m_price = cells[idx_market_price].get_text(strip=True).replace(',', '')
                    yield_val = cells[idx_yield].get_text(strip=True).replace('%', '')
                    
                    try:
                        prices[code] = {
                            'market_price': float(m_price) if m_price and m_price != '--' else 0,
                            'yield': yield_val
                        }
                    except ValueError:
                        prices[code] = {'market_price': 0, 'yield': 'N/A'}
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
            fields = data.get('fields', []) # 🆕 取得 API 的欄位名稱對照表
            
            if not twse_data:
                print("今日證交所無公開申購資料。")
                return

            # 留下 Log 以利未來如果有其他欄位異動時可以對照
            print(f"📊 API 欄位對照: {fields}")

            # 🎯 終極解法：動態尋找欄位 Index (容忍證交所隨意調動欄位)
            # 先給定舊的欄位位置當作備用預設值
            idx_name = 2
            idx_code = 3
            idx_start = 5
            idx_end = 6
            idx_shares = 11
            idx_price = 12
            
            # 如果證交所有提供欄位名稱，就動態找出來
            if fields:
                idx_name = next((i for i, f in enumerate(fields) if '名稱' in f), idx_name)
                idx_code = next((i for i, f in enumerate(fields) if '代號' in f), idx_code)
                idx_start = next((i for i, f in enumerate(fields) if '開始日' in f), idx_start)
                idx_end = next((i for i, f in enumerate(fields) if '截止日' in f), idx_end)
                
                # 價格優先找「實際承銷價」，沒有再找「承銷價」
                idx_price = next((i for i, f in enumerate(fields) if '實際承銷價' in f), -1)
                if idx_price == -1:
                    idx_price = next((i for i, f in enumerate(fields) if '承銷價' in f), 12)
                    
                # 股數找「申購股數」或「承銷股數」
                idx_shares = next((i for i, f in enumerate(fields) if '申購股數' in f), -1)
                if idx_shares == -1:
                    idx_shares = next((i for i, f in enumerate(fields) if '股數' in f), 11)

            histock_info = get_histock_prices()
            today_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()
            
            stock_text_blocks = []
            last_code = ""
            if os.path.exists(LAST_ID_FILE):
                with open(LAST_ID_FILE, "r") as f:
                    last_code = f.read().strip()

            for idx, item in enumerate(twse_data):
                # 🆕 全面改用動態 Index
                name = str(item[idx_name]).strip()
                code = str(item[idx_code]).strip()
                
                try:
                    start_date_obj = parse_twse_date(str(item[idx_start]).strip())
                    end_date_obj = parse_twse_date(str(item[idx_end]).strip())
                except Exception as e:
                    print(f"日期解析失敗 ({code}): {e}")
                    continue
                
                if start_date_obj <= today_date <= end_date_obj:
                    try:
                        # 🆕 全面改用動態 Index
                        shares_str = str(item[idx_shares]).replace(',', '').strip()
                        price_str = str(item[idx_price]).replace(',', '').strip()
                        
                        if not shares_str or shares_str == '--': shares_str = '1000'
                        if not price_str or price_str == '--': price_str = '0'

                        shares = int(float(shares_str))
                        sub_price_per_share = float(price_str)
                        
                    except Exception as e:
                        print(f"⚠️ 略過 {name}({code})，數值解析失敗。")
                        print(f"   欄位 [{idx_shares}]股數: '{item[idx_shares]}' / [{idx_price}]承銷價: '{item[idx_price]}'")
                        print(f"   錯誤原因: {e}")
                        continue 

                    h_data = histock_info.get(code, {'market_price': 0, 'yield': 'N/A'})
                    
                    total_sub_price = int(sub_price_per_share * shares)
                    total_diff = 0
                    if h_data['market_price'] > 0:
                        total_diff = int((h_data['market_price'] - sub_price_per_share) * shares)

                    # 組合單筆股票的文字 (修正排版與換行)
                    msg = (
                        f"📢抽籤通知\n"
                        f"{name} ({code})\n"
                        f"　價差：{total_diff:,}元（~{h_data['yield']}%）\n"
                        f"　申購價：{total_sub_price:,}元\n"
                        f"　截止日期：{str(item[idx_end]).strip()}"
                    )
                    stock_text_blocks.append(msg)

                    if idx == 0 and code != last_code:
                        with open(LAST_ID_FILE, "w") as f:
                            f.write(code)

            # --- 執行發送 ---
            if stock_text_blocks:
                messages_to_send = []
                
                # 將所有股票文字區塊用兩個換行符號合併成一則長訊息
                combined_text = "\n\n".join(stock_text_blocks)
                messages_to_send.append(TextMessage(text=combined_text))
                
                flex_msg = FlexMessage(
                    alt_text="🎁 領取您的 Percento 專屬折扣",
                    contents=get_percento_flex()
                )
                messages_to_send.append(flex_msg)
                
                line_bot_api.push_message(PushMessageRequest(
                    to=GROUP_ID, 
                    messages=messages_to_send
                ))
                print(f"✅ 成功發送 {len(stock_text_blocks)} 檔股票資訊 (合併為 1 則訊息) 與折扣推播。")
            else:
                print(f"今日 ({today_date}) 無符合申購期間之案件。")

        except Exception as e:
            print(f"❌ 執行失敗：{e}")

if __name__ == "__main__":
    run_crawler()
