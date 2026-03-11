import requests
from bs4 import BeautifulSoup
import os
import sys
import datetime
import re
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage
)

# 1. 環境變數
LINE_ACCESS_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID')

def get_taiwan_info():
    """獲取台灣目前的日期物件"""
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    return now.date()

def get_twse_date_map():
    """從證交所 API 取得精準截止日 (含民國年)"""
    twse_map = {}
    url = "https://www.twse.com.tw/rwd/zh/announcement/publicForm?response=json"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        data = res.json()
        if 'data' in data:
            for item in data['data']:
                code = str(item[3]).strip()
                twse_map[code] = str(item[6]).strip() # 申購結束日
    except: pass
    return twse_map

def send_line_notification(message):
    if not LINE_ACCESS_TOKEN or not GROUP_ID: return
    conf = Configuration(access_token=LINE_ACCESS_TOKEN)
    with ApiClient(conf) as api_client:
        line_bot_api = MessagingApi(api_client)
        try:
            line_bot_api.push_message(PushMessageRequest(
                to=GROUP_ID, messages=[TextMessage(text=message)]
            ))
            print("✅ 估計版預警發送成功！")
        except Exception as e:
            print(f"❌ LINE 發送失敗: {e}")

def scrape_high_yield():
    date_map = get_twse_date_map()
    today = get_taiwan_info()
    url = "https://histock.tw/stock/public.aspx"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://histock.tw/'
    }

    try:
        print("正在擷取最新資料並計算整數報酬率...")
        res = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(res.text, 'html.parser')
        table = soup.find('table', {'class': 'gvTB'})
        
        if not table: return

        headers_text = [th.get_text(strip=True) for th in table.find_all('th')]
        idx_name_code = 1
        idx_yield = headers_text.index('報酬率(%)')

        high_yield_list = []
        rows = table.find_all('tr')[1:]

        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 10: continue

            # 1. 提取代號與名稱
            name_code_text = cells[idx_name_code].get_text(strip=True)
            code_match = re.search(r'(\d{4,})', name_code_text)
            if not code_match: continue
            stock_code = code_match.group(1)
            stock_name = name_code_text.replace(stock_code, '').strip()

            # 2. 擷取報酬率並轉為整數
            raw_yield_str = cells[idx_yield].get_text(strip=True)
            try:
                # 使用 int(float()) 將 34.7 轉為 34
                num_yield = int(float(raw_yield_str.replace('%', '')))
            except:
                num_yield = 0

            # 3. 日期過濾 (比對證交所 API)
            is_active = False
            full_end_date = "資料暫缺"
            if stock_code in date_map:
                full_end_date = date_map[stock_code]
                parts = full_end_date.split('/')
                # 民國轉西元進行比較
                end_date_obj = datetime.date(int(parts[0])+1911, int(parts[1]), int(parts[2]))
                if end_date_obj >= today:
                    is_active = True

            # 4. 門檻過濾 (整數 >= 30)
            if num_yield >= 30 and is_active:
                high_yield_list.append(
                    f"💰 {stock_name}({stock_code})\n"
                    f"   預估報酬率：~{num_yield}%\n"
                    f"   截止日期：{full_end_date}"
                )

        if high_yield_list:
            # 5. 組合最終訊息格式
            msg = "🔥 高報酬抽籤預警 (>=30%)\n\n"
            msg += "\n\n".join(high_yield_list)
            msg += "\n\n報酬率會因股票市價有所變動\n請鵝仔們評估風險後參與！"
            send_line_notification(msg)
        else:
            print(f"💡 {today} 目前無符合門檻之標的。")

    except Exception as e:
        print(f"執行異常: {e}")

if __name__ == "__main__":
    scrape_high_yield()
