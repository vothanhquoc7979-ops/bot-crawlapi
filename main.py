import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from bot import init_telegram_bot, sys_status
from bot import TELEGRAM_TOKEN
from crawler import fetch_lottery_data
from github_sync import push_to_github
from datetime import datetime

# Biến global lưu context bot
telegram_bot_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_bot_app
    print("[SYSTEM] Bắt đầu khởi động server FastAPI...")
    
    # Khởi chạy bot Telegram trong nền (nếu có TOKEN)
    if TELEGRAM_TOKEN:
        telegram_bot_app = init_telegram_bot()
        if telegram_bot_app:
            await telegram_bot_app.initialize()
            await telegram_bot_app.start()
            await telegram_bot_app.updater.start_polling()
            print("[SYSTEM] Đã khởi chạy quá trình polling Telegram Bot nền.")
            
    yield # Cho phép server FastAPI chạy
    
    print("[SYSTEM] Tắt server...")
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

@app.get("/api/status")
async def get_status():
    return sys_status

@app.get("/api/config-check")
async def config_check():
    return {
        "telegram_configured": bool(os.getenv("TELEGRAM_TOKEN")),
        "github_configured": bool(os.getenv("GITHUB_TOKEN")),
        "github_repo": os.getenv("GITHUB_REPO", "CHƯA_CÀI_ĐẶT")
    }

@app.post("/api/crawl-today")
async def api_trigger_crawl():
    if sys_status["is_crawling"]:
        return {"status": "error", "message": "Crawler đang bận xử lý."}
        
    sys_status["is_crawling"] = True
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Chạy đồng bộ trong luồng này (Nên đưa vào background task bằng asyncio.create_task trong ứng dụng thực tế lớn)
    try:
        data = fetch_lottery_data(date_str)
        sys_status["last_crawl"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        success, git_msg = push_to_github(date_str, data)
        if success:
            sys_status["last_status"] = "Thành công (Web UI kích hoạt)"
            return {"status": "success", "message": git_msg}
        else:
            sys_status["last_status"] = f"Lỗi Github: {git_msg}"
            return {"status": "error", "message": git_msg}
    except Exception as e:
        sys_status["last_status"] = f"Lỗi Python API: {str(e)}"
        return {"status": "error", "message": f"Exception: {str(e)}"}
    finally:
        sys_status["is_crawling"] = False
