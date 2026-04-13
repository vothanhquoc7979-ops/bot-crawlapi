import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from bot import init_telegram_bot
from crawler import fetch_lottery_data
from github_sync import push_to_github
from datetime import datetime

# Biến global lưu context bot
telegram_bot_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_bot_app
    print("[SYSTEM] Bắt đầu khởi động server FastAPI...")
    
    conf = get_config()
    tele_token = conf.get("TELEGRAM_TOKEN")
    
    # Khởi chạy bot Telegram trong nền (nếu có TOKEN)
    if tele_token:
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

from config import get_config, save_config
from pydantic import BaseModel
from fastapi import BackgroundTasks
import asyncio
from crawler_task import sys_status, parse_date, get_date_range, run_crawl_routine

class ConfigData(BaseModel):
    github_token: str | None = None
    tele_token: str | None = None
    repo_name: str | None = None

class RangeData(BaseModel):
    start_date: str
    end_date: str

@app.get("/api/status")
async def get_status():
    return sys_status

@app.get("/api/config-check")
async def config_check():
    conf = get_config()
    return {
        "telegram_configured": bool(conf.get("TELEGRAM_TOKEN")),
        "github_configured": bool(conf.get("GITHUB_TOKEN")),
        "github_repo": conf.get("GITHUB_REPO") or "CHƯA_CÀI_ĐẶT"
    }

@app.post("/api/save-config")
async def api_save_config(data: ConfigData):
    new_conf = {}
    if data.github_token: new_conf["GITHUB_TOKEN"] = data.github_token
    if data.tele_token: new_conf["TELEGRAM_TOKEN"] = data.tele_token
    if data.repo_name: new_conf["GITHUB_REPO"] = data.repo_name
    
    save_config(new_conf)
    return {"status": "success", "message": "Đã lưu cấu hình. (Telegram token cần khởi động lại máy chủ để nhận diện)"}

@app.post("/api/crawl-today")
async def api_trigger_crawl(background_tasks: BackgroundTasks):
    if sys_status["is_crawling"]:
        return {"status": "error", "message": "Crawler đang bận xử lý."}
        
    date_str = datetime.now().strftime("%Y-%m-%d")
    background_tasks.add_task(run_crawl_routine, [date_str])
    return {"status": "success", "message": "Đã xếp lịch cào ngày hôm nay vào tác vụ nền..."}

@app.post("/api/crawl-range")
async def api_trigger_range(data: RangeData, background_tasks: BackgroundTasks):
    if sys_status["is_crawling"]:
        return {"status": "error", "message": "Crawler đang bận xử lý."}
    
    try:
        dates_to_crawl = get_date_range(data.start_date, data.end_date)
    except Exception as e:
        return {"status": "error", "message": f"Ngày chưa hợp lệ: {e}"}
        
    background_tasks.add_task(run_crawl_routine, dates_to_crawl)
    return {"status": "success", "message": f"Đã bắt đầu chuỗi cào {len(dates_to_crawl)} ngày..."}
