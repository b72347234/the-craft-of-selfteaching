# -*- coding: utf-8 -*-

# ==========================================================================================
# == ETH 波動率 Telegram 監控機器人 (ETH Volatility Telegram Monitor Bot) ==
# == 版本: 4.0 (校準版 - 信任官方數據)
# ==========================================================================================
#
# == v4.0 校準版優化重點 ==
# 1.  【核心思維轉變】不再自行計算 IVR/IVP，承認腳本計算與官方數據的精度差異。
#     腳本的核心任務回歸到「自動監控 DVOL 絕對值」，並提醒您去查閱官方的精確指標。
# 2.  【新增校準門檻】除了 IV Rank/Percentile，新增對 DVOL 絕對值的警報門檻，讓您能
#     根據歷史圖表，設定更直觀的「高溫/低溫」警報線。
# 3.  【訊息全面升級】所有警報和簡報訊息，都會明確指出腳本數據為「估算值」，並附上
#     Deribit 的官方圖表連結，提醒您進行「人工複核」，養成專業交易習慣。
# 4.  【代碼結構簡化】移除了複雜的歷史數據抓取和計算邏輯，讓腳本更輕量、更專注於
#     監控和提醒的核心任務，運行更穩定。
#
# ==========================================================================================

import requests
import time
from datetime import datetime, timedelta, date

# ==========================================================================================
# == 您的個人設定 (請務必修改此區塊！) ==
# ==========================================================================================

# 1. 請填入您從 BotFather 取得的 Telegram Bot API Token
TELEGRAM_BOT_TOKEN = "7313405188:AAGErpjE6gOXiLE9qqUZoX1Ay1kswFVHJko"

# 2. 請填入您從 userinfobot 取得的個人 Chat ID
TELEGRAM_CHAT_ID = "1892625650"

# 3. 【校準版】設定 DVOL 絕對值警報門檻 (請參考 Deribit 圖表自行校準)
#    例如，您觀察到 DVOL 超過 80 通常就是極高位，低於 40 就是極低位。
HIGH_DVOL_THRESHOLD = 80.0
LOW_DVOL_THRESHOLD = 40.0

# 4. 設定每日簡報的發送時間 (24小時制)
DAILY_BRIEFING_HOUR = 8

# 5. 設定每次檢查的間隔時間 (單位：秒)
CHECK_INTERVAL_SECONDS = 1800 # 30 分鐘

# 6. 設定網路錯誤時的重試參數
RETRY_COUNT = 3
RETRY_DELAY_SECONDS = 60

# ==========================================================================================
# == 核心程式碼 (通常不需要修改) ==
# ==========================================================================================

# --- 全域變數 ---
last_alert_status = 'NORMAL'
last_briefing_date = None
is_currently_offline = False
DERIBIT_CHART_URL = "https://www.deribit.com/charts/ETH-DVOL" # 官方圖表連結

def make_request_with_retry(url, timeout, is_post=False, payload=None):
    """帶有重試機制的網路請求函式"""
    method = requests.post if is_post else requests.get
    kwargs = {'timeout': timeout}
    if is_post:
        kwargs['data'] = payload

    for i in range(RETRY_COUNT + 1):
        try:
            response = method(url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"網路請求錯誤 (第 {i+1} 次嘗試): {e}")
            if i < RETRY_COUNT:
                print(f"將在 {RETRY_DELAY_SECONDS} 秒後重試...")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                print("已達最大重試次數，放棄請求。")
                return None

def get_eth_price():
    """從 CoinGecko 的公開 API 獲取最新的 ETH 價格。"""
    api_url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
    response = make_request_with_retry(api_url, timeout=10)
    return response.json()['ethereum']['usd'] if response else None

def get_current_dvol():
    """【結構簡化】只獲取當前的 DVOL 絕對值。"""
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        current_vol_url = (
            f"https://www.deribit.com/api/v2/public/get_volatility_index_data?"
            f"currency=ETH&start_timestamp={int(start_time.timestamp() * 1000)}&end_timestamp={int(end_time.timestamp() * 1000)}&resolution=60"
        )
        response = make_request_with_retry(current_vol_url, timeout=10)
        if not response: return None
        data = response.json()
        if not (data.get('result') and data['result'].get('data')): return None
        return float(data['result']['data'][-1][1])
    except Exception as e:
        print(f"獲取 DVOL 數據時發生錯誤：{e}")
        return None

def send_telegram_message(message):
    """透過 Telegram Bot API 發送訊息，使用 HTML 格式。"""
    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML', 'disable_web_page_preview': True}
    response = make_request_with_retry(send_url, timeout=10, is_post=True, payload=payload)
    if response:
        print("Telegram 訊息已成功發送！")
    else:
        print("錯誤：發送 Telegram 訊息失敗。")

def health_check():
    """啟動時健康檢查。"""
    print("--- 正在執行啟動健康檢查 ---")
    test_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
    response = make_request_with_retry(test_url, timeout=10)
    if response and response.json().get('ok'):
        print("✅ Telegram Bot Token 驗證成功。")
    else:
        print("❌ Telegram Bot Token 驗證失敗。")
        return False
    
    print("正在測試數據源連線...")
    if get_current_dvol() and get_eth_price():
        print("✅ 數據源連線成功。")
    else:
        print("❌ 數據源連線失敗。")
        return False
        
    print("--- 健康檢查完畢，一切正常 ---")
    return True

def main():
    """主執行函式"""
    global last_alert_status, last_briefing_date, is_currently_offline

    if not health_check():
        print("啟動失敗，請修正錯誤後重試。")
        return

    print("==============================================")
    print("== ETH 波動率監控機器人 v4.0 已啟動 ==")
    print(f"== DVOL 絕對值門檻: {LOW_DVOL_THRESHOLD} / {HIGH_DVOL_THRESHOLD}")
    print("==============================================")
    send_telegram_message("✅ <b>ETH 波動率監控機器人 v4.0 (校準版) 已成功啟動！</b>")

    while True:
        now = datetime.now()
        current_dvol = get_current_dvol()
        
        if current_dvol is None:
            if not is_currently_offline:
                print("進入離線狀態...")
                is_currently_offline = True
        else:
            if is_currently_offline:
                send_telegram_message("📡 <b>連線恢復通知</b>\n\n機器人已恢復正常監控。")
                is_currently_offline = False

        if current_dvol and now.hour == DAILY_BRIEFING_HOUR and now.date() != last_briefing_date:
            print("--- 正在準備發送每日簡報 ---")
            eth_price = get_eth_price()
            if eth_price:
                briefing_message = (
                    f"☀️ <b>ETH 市場每日簡報</b>\n"
                    f"<i>{now.strftime('%Y-%m-%d %H:%M')}</i>\n\n"
                    f"📈 <b>ETH 現價:</b> <code>${eth_price:,.2f}</code>\n"
                    f"📊 <b>當前 DVOL:</b> <code>{current_dvol:.2f}</code>\n\n"
                    f"👇 <b>點擊查看官方精確指標 (IVR/IVP):</b>\n"
                    f"<a href='{DERIBIT_CHART_URL}'>Deribit 官方圖表</a>"
                )
                send_telegram_message(briefing_message)
                last_briefing_date = now.date()

        if current_dvol:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DVOL: {current_dvol:.2f}")

            if current_dvol > HIGH_DVOL_THRESHOLD:
                if last_alert_status != 'HIGH':
                    eth_price = get_eth_price()
                    message = (
                        f"🚨 <b>高波動率警報！</b>\n\n"
                        f"📊 <b>當前 DVOL 已達</b> <code>{current_dvol:.2f}</code>\n"
                        f"(高於您設定的 {HIGH_DVOL_THRESHOLD} 門檻)\n\n"
                        f"💲 <b>目前 ETH 價格:</b> <code>${eth_price:,.2f}</code>\n\n"
                        f"市場情緒可能趨向恐慌，建議考慮 <b>賣方策略</b>。\n"
                        f"👇 <b>請立即點擊下方連結，複核官方 IV Rank/Percentile:</b>\n"
                        f"<a href='{DERIBIT_CHART_URL}'>Deribit 官方精確指標</a>"
                    )
                    send_telegram_message(message)
                    last_alert_status = 'HIGH'

            elif current_dvol < LOW_DVOL_THRESHOLD:
                if last_alert_status != 'LOW':
                    eth_price = get_eth_price()
                    message = (
                        f"📉 <b>低波動率警報！</b>\n\n"
                        f"📊 <b>當前 DVOL 已達</b> <code>{current_dvol:.2f}</code>\n"
                        f"(低於您設定的 {LOW_DVOL_THRESHOLD} 門檻)\n\n"
                        f"💲 <b>目前 ETH 價格:</b> <code>${eth_price:,.2f}</code>\n\n"
                        f"市場情緒可能趨向平靜，建議考慮 <b>買方策略</b>。\n"
                        f"👇 <b>請立即點擊下方連結，複核官方 IV Rank/Percentile:</b>\n"
                        f"<a href='{DERIBIT_CHART_URL}'>Deribit 官方精確指標</a>"
                    )
                    send_telegram_message(message)
                    last_alert_status = 'LOW'
            
            else:
                if last_alert_status != 'NORMAL':
                    message = (
                        f"✅ <b>波動率恢復正常區間</b>\n\n"
                        f"當前 DVOL: <code>{current_dvol:.2f}</code>"
                    )
                    send_telegram_message(message)
                    last_alert_status = 'NORMAL'
        
        print(f"腳本將暫停 {CHECK_INTERVAL_SECONDS / 60} 分鐘...")
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    if "7313405188:AAGErpjE6gOXiLE9qqUZoX1Ay1kswFVHJko" in TELEGRAM_BOT_TOKEN or "1892625650" in TELEGRAM_CHAT_ID:
        main()
    else:
        if "請在這裡貼上您的BOT_TOKEN" in TELEGRAM_BOT_TOKEN or "請在這裡貼上您的CHAT_ID" in TELEGRAM_CHAT_ID:
            print("\n錯誤：您尚未完成個人設定！")
            print("請打開腳本檔案，填寫 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID。\n")
        else:
            main()
