import asyncio
import os
import html
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

from bot import init_telegram_bot
from crawler import fetch_lottery_data, get_random_proxy
from github_sync import push_to_github
from config import get_config, save_config
from crawler_task import sys_status, parse_date, get_date_range, run_crawl_routine

# Biến global lưu context bot
telegram_bot_app = None

async def start_telegram_bot(tele_token: str):
    """Khởi chạy hoặc tải lại Telegram Bot"""
    global telegram_bot_app
    
    # Tắt bot cũ nếu có
    if telegram_bot_app:
        try:
            await telegram_bot_app.updater.stop()
            await telegram_bot_app.stop()
            await telegram_bot_app.shutdown()
        except:
            pass
        telegram_bot_app = None
        
    if tele_token:
        app_bot = init_telegram_bot()
        if app_bot:
            await app_bot.initialize()
            await app_bot.start()
            await app_bot.updater.start_polling()
            print("[SYSTEM] Đã khởi chạy quá trình polling Telegram Bot nền.")
            telegram_bot_app = app_bot

from datetime import datetime, timedelta, timezone

async def scheduler_task():
    # Sử dụng múi giờ Việt Nam (UTC+7) để đảm bảo luôn đúng 20h
    vn_tz = timezone(timedelta(hours=7))
    last_run_date = None
    
    while True:
        now = datetime.now(vn_tz)
        # Quét đúng 22:00 tới 22:05 mỗi ngày
        if now.hour == 22 and now.minute <= 5:
            today_str = now.strftime("%Y-%m-%d")
            if last_run_date != today_str:
                if not sys_status["is_crawling"]:
                    print(f"[SCHEDULER] Kích hoạt tiến trình tự động cào cho ngày hôm nay: {today_str}...")
                    last_run_date = today_str
                    
                    # Cố gắng nhắn tin Tới Bot trước khi cào
                    if telegram_bot_app and telegram_bot_app.bot:
                        chat_id = get_config().get("TELEGRAM_CHAT_ID")
                        if chat_id:
                            try:
                                msg_start = (
                                    '<tg-emoji emoji-id="5427009714745513056">⏰</tg-emoji> Đến hẹn 10h tối rồi Quốc Chề ơi.\n'
                                    '<tg-emoji emoji-id="5368324170671202286">🚀</tg-emoji> T bắt đầu cào nhé!'
                                )
                                await telegram_bot_app.bot.send_message(chat_id=chat_id, text=msg_start, parse_mode="HTML")
                            except Exception as e:
                                msg_start_fb = "⏰ Đến hẹn 10h tối rồi Quốc Chề ơi.\n🚀 T bắt đầu cào nhé!"
                                try: await telegram_bot_app.bot.send_message(chat_id=chat_id, text=msg_start_fb)
                                except: pass

                    # Ném vào luồng chạy như bình thường
                    loop = asyncio.get_event_loop()
                    try:
                        await loop.run_in_executor(None, run_crawl_routine, [today_str])
                    except Exception as e:
                        print(f"[SCHEDULER] Lỗi CRAWLER: {e}")
                        
                    # Nhắn tin Tới Bot sau khi cào xong (Dù lỗi hay không cũng báo xong)
                    if telegram_bot_app and telegram_bot_app.bot:
                        chat_id = get_config().get("TELEGRAM_CHAT_ID")
                        if chat_id:
                            status_escaped = html.escape(str(sys_status["last_status"]))
                            try:
                                msg_end = (
                                    '<tg-emoji emoji-id="5368324170671202286">🎉</tg-emoji> Đã cào xong hết rồi nha Quốc Chề.\n'
                                    '<tg-emoji emoji-id="5427009714745513056">💾</tg-emoji> Đã Push lên Github luôn rồi đó.\n\n'
                                    f'📋 <b>Báo cáo:</b> <code>{status_escaped}</code>'
                                )
                                await telegram_bot_app.bot.send_message(chat_id=chat_id, text=msg_end, parse_mode="HTML")
                            except Exception as e:
                                msg_end_fb = (
                                    f'🎉 Đã cào xong hết rồi nha Quốc Chề.\n'
                                    f'💾 Đã Push lên Github luôn rồi đó.\n\n'
                                    f'📋 Báo cáo: {status_escaped}'
                                )
                                try: await telegram_bot_app.bot.send_message(chat_id=chat_id, text=msg_end_fb)
                                except: pass

        await asyncio.sleep(60) # Cứ 1 phút quét 1 lần

@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_bot_app
    print("[SYSTEM] Bắt đầu khởi động server FastAPI...")
    
    conf = get_config()
    tele_token = conf.get("TELEGRAM_TOKEN")
    
    # Nạp bot lần đầu
    await start_telegram_bot(tele_token)
    
    # Khởi chạy Scheduler tự động cào 22:00
    scheduler = asyncio.create_task(scheduler_task())
            
    yield # Cho phép server FastAPI chạy
    
    print("[SYSTEM] Tắt server...")
    scheduler.cancel()
    if telegram_bot_app:
        await telegram_bot_app.updater.stop()
        await telegram_bot_app.stop()
        await telegram_bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

# --- Routes API UI ---

@app.get("/", response_class=HTMLResponse)
async def read_root():
    try:
        with open("ui/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Lỗi tải UI: {e}</h1>")

# (Dòng 135-140 trong file cũ được thay thế bằng imports ở đầu trang)

class ConfigData(BaseModel):
    github_token: str | None = None
    tele_token: str | None = None
    repo_name: str | None = None
    proxies: str | None = None

class RangeData(BaseModel):
    start_date: str
    end_date: str

@app.get("/api/status")
async def get_status():
    return sys_status

@app.get("/api/config-check")
async def config_check():
    conf = get_config()
    proxies_list = conf.get("PROXIES", [])
    return {
        "telegram_configured": bool(conf.get("TELEGRAM_TOKEN")),
        "github_configured": bool(conf.get("GITHUB_TOKEN")),
        "github_repo": conf.get("GITHUB_REPO") or "CHƯA_CÀI_ĐẶT",
        "proxies_count": len(proxies_list) if isinstance(proxies_list, list) else 0
    }

@app.post("/api/save-config")
async def api_save_config(data: ConfigData):
    new_conf = {}
    if data.github_token: new_conf["GITHUB_TOKEN"] = data.github_token
    if data.tele_token: new_conf["TELEGRAM_TOKEN"] = data.tele_token
    if data.repo_name: new_conf["GITHUB_REPO"] = data.repo_name
    if data.proxies is not None:
        raw_list = [p.strip() for p in data.proxies.split("\n") if p.strip()]
        new_conf["PROXIES"] = raw_list
    
    save_config(new_conf)
    
    if data.tele_token:
        await start_telegram_bot(data.tele_token)
        return {"status": "success", "message": "Đã lưu cấu hình. Bot Telegram ĐÃ ĐƯỢC KÍCH HOẠT!"}
        
    return {"status": "success", "message": "Đã lưu cấu hình thành công."}

async def background_crawl_with_notify(dates_to_crawl: list):
    first_date = dates_to_crawl[0]
    last_date = dates_to_crawl[-1]
    date_info = f"ngày {first_date}" if first_date == last_date else f"từ {first_date} đến {last_date}"
    
    # 1. Báo bắt đầu
    if telegram_bot_app and telegram_bot_app.bot:
        chat_id = get_config().get("TELEGRAM_CHAT_ID")
        if chat_id:
            try:
                msg_start = (
                    f'<tg-emoji emoji-id="5427009714745513056">⏰</tg-emoji> Có lệnh chạy từ Control Panel UI rồi Quốc Chề ơi.\n'
                    f'<tg-emoji emoji-id="5368324170671202286">🚀</tg-emoji> T bắt đầu cào {date_info} nhé!'
                )
                await telegram_bot_app.bot.send_message(chat_id=chat_id, text=msg_start, parse_mode="HTML")
            except Exception as e:
                print(f"[TELEGRAM_ERR] Không thể gửi msg_start (Có thể do Lỗi Custom Emoji): {e}")
                # Fallback gửi không có tg-emoji
                msg_start_fallback = f"⏰ Có lệnh chạy từ Control Panel UI rồi Quốc Chề ơi.\n🚀 T bắt đầu cào {date_info} nhé!"
                try: 
                    await telegram_bot_app.bot.send_message(chat_id=chat_id, text=msg_start_fallback)
                except: pass

    # 2. Chạy thư viện
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, run_crawl_routine, dates_to_crawl)
    except Exception as e:
        print(f"[UI CRAWL] Lỗi CRAWLER: {e}")

    # 3. Báo kết thúc
    if telegram_bot_app and telegram_bot_app.bot:
        chat_id = get_config().get("TELEGRAM_CHAT_ID")
        if chat_id:
            status_escaped = html.escape(str(sys_status["last_status"]))
            try:
                msg_end = (
                    f'<tg-emoji emoji-id="5368324170671202286">🎉</tg-emoji> Đã cào xong {date_info} rồi nha Quốc Chề.\n'
                    f'<tg-emoji emoji-id="5427009714745513056">💾</tg-emoji> Đã Push lên Github luôn rồi đó.\n\n'
                    f'📋 <b>Báo cáo:</b> <code>{status_escaped}</code>'
                )
                await telegram_bot_app.bot.send_message(chat_id=chat_id, text=msg_end, parse_mode="HTML")
            except Exception as e:
                print(f"[TELEGRAM_ERR] Không thể gửi msg_end: {e}")
                msg_end_fb = (
                    f'🎉 Đã cào xong {date_info} rồi nha Quốc Chề.\n'
                    f'💾 Đã Push lên Github luôn rồi đó.\n\n'
                    f'📋 Báo cáo: {status_escaped}'
                )
                try:
                    await telegram_bot_app.bot.send_message(chat_id=chat_id, text=msg_end_fb)
                except: pass


@app.post("/api/crawl-today")
async def api_trigger_crawl(background_tasks: BackgroundTasks):
    if sys_status["is_crawling"]:
        return {"status": "error", "message": "Crawler đang bận xử lý."}
        
    date_str = datetime.now().strftime("%Y-%m-%d")
    background_tasks.add_task(background_crawl_with_notify, [date_str])
    return {"status": "success", "message": "Đã xếp lịch cào ngày hôm nay vào tác vụ nền..."}

@app.post("/api/crawl-range")
async def api_trigger_range(data: RangeData, background_tasks: BackgroundTasks):
    if sys_status["is_crawling"]:
        return {"status": "error", "message": "Crawler đang bận xử lý."}
    
    try:
        dates_to_crawl = get_date_range(data.start_date, data.end_date)
    except Exception as e:
        return {"status": "error", "message": f"Ngày chưa hợp lệ: {e}"}
        
    background_tasks.add_task(background_crawl_with_notify, dates_to_crawl)
    return {"status": "success", "message": f"Đã bắt đầu chuỗi cào {len(dates_to_crawl)} ngày..."}
