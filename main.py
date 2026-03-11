import os
import time
import requests
import datetime
import re
from bs4 import BeautifulSoup
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage, FlexMessage
)
# 引用新的 Flex 管理器
from flex_manager import get_percento_flex

# 環境變數與設定
LINE_ACCESS_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
GROUP_ID = os.environ.get('GROUP_ID')
API_URL = f"https://www.twse.com.tw/rwd/zh/announcement/publicForm?response=json&_={int(time.time() * 1000)}"
LAST_ID_FILE = "last_stock_id.txt"

def get_histock_data():
    """從 HiStock 獲取即時的申購行情資訊 (價差、申購價、報酬率)"""
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
                # 取得代號
                code_match = re.search(r'(\d{4,})', cells[1].get_text())
                if not code_match: continue
                code = code_match.group(1)
                
                # 取得 申購價(item[3]), 價差(item[7]), 報酬率(item[9])
                prices[code] = {
                    'sub_price': cells[3].get_text(strip=True),
                    'diff_price': cells[7].get_text(strip=True),
                    'yield': cells[9].get_text(strip=True).replace('%', '')
                }
    except Exception as e:
        print(f"抓取 HiStock 輔助資料失敗: {e}")
    return prices

def get_today_tw():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    return f"{now.year - 1911}/{now.strftime('%m/%d')}"

def run_crawler():
    conf = Configuration(access_token=LINE_ACCESS_TOKEN)
    with ApiClient(conf) as api_client:
        line_bot_api = MessagingApi(api_client)
        try:
            print("正在獲取最新申購資訊...")
            res = requests.get(API_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
            twse_data = res.json().get('data', [])
            if not twse_data: return

            histock_prices = get_histock_data() # 獲取價差資訊
            today_tw = get_today_tw()
            messages_to_send = []
            trigger_flex = False

            # 處理最新一筆 (邏輯 A: 新案)
            top = twse_data[0]
            name, code, end_date = top[2].strip(), str(top[3]).strip(), top[6].strip()
            
            last_code = ""
            if os.path.exists(LAST_ID_FILE):
                with open(LAST_ID_FILE, "r") as f: last_code = f.read().strip()

            if code != last_code:
                # 格式化輸出
                p_info = histock_prices.get(code, {'diff_price': 'N/A', 'sub_price': 'N/A', 'yield': 'N/A'})
                msg = (
                    f"📢 抽籤通知\n"
                    f"{name}({code})\n"
                    f"　價差：{p_info['diff_price']}元（~{int(float(p_info['yield'])) if p_info['yield'] != 'N/A' else 'N/A'}%）\n"
                    f"　申購價：{p_info['sub_price']}元\n"
                    f"　截止日期：{end_date}"
                )
                messages_to_send.append(TextMessage(text=msg))
                trigger_flex = True
                with open(LAST_ID_FILE, "w") as f: f.write(code)

            # 邏輯 B: 截止提醒
            for item in twse_data:
                if item[6].strip() == today_tw:
                    n, c = item[2].strip(), str(item[3]).strip()
                    p_info = histock_prices.get(c, {'diff_price': 'N/A', 'sub_price': 'N/A', 'yield': 'N/A'})
                    msg = (
                        f"⏰ 截止提醒\n"
                        f"{n}({c})\n"
                        f"　價差：{p_info['diff_price']}元（~{int(float(p_info['yield'])) if p_info['yield'] != 'N/A' else 'N/A'}%）\n"
                        f"　申購價：{p_info['sub_price']}元\n"
                        f"　今日截止，請把握機會！"
                    )
                    messages_to_send.append(TextMessage(text=msg))
                    trigger_flex = True

            if trigger_flex:
                flex = FlexMessage(alt_text="🎁 領取您的 Percento 專屬折扣", contents=get_percento_flex())
                messages_to_send.append(flex)
            
            if messages_to_send:
                line_bot_api.push_message(PushMessageRequest(to=GROUP_ID, messages=messages_to_send[:5]))
                print(f"✅ 發送成功！")

        except Exception as e:
            print(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    run_crawler()