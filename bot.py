import os
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from crawler import fetch_lottery_data
from github_sync import push_to_github

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# Kiểm soát trạng thái hệ thống
sys_status = {
    "is_crawling": False,
    "last_crawl": "Chưa có",
    "last_status": "OK"
}

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 Chào mừng bạn đến với Bot Quản Lý Xổ Số (Railway Edition)!\n"
        "Các lệnh:\n"
        "/crawl today - Cào dư liệu ngày hôm nay\n"
        "/crawl YYYY-MM-DD - Cào theo ngày cụ thể\n"
        "/status - Xem trạng thái hệ thống"
    )
    await update.message.reply_text(msg)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"🖥️ Trạng Thái Hệ Thống:\n"
        f"Dang chạy luồng cào: {'Có' if sys_status['is_crawling'] else 'Không'}\n"
        f"Lần cào cuối: {sys_status['last_crawl']}\n"
        f"Kết quả cuối: {sys_status['last_status']}"
    )
    await update.message.reply_text(msg)

async def crawl_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not TELEGRAM_TOKEN or not os.getenv("GITHUB_TOKEN"):
        await update.message.reply_text("❌ Thiếu biến môi trường (Telegram hoặc Github token).")
        return

    if sys_status["is_crawling"]:
        await update.message.reply_text("⚠️ Bot đang bận cào một tác vụ khác. Xin chờ.")
        return

    # Lấy tham số ngày
    date_str = ""
    if context.args:
        if context.args[0] == "today":
            date_str = datetime.now().strftime("%Y-%m-%d")
        else:
            date_str = context.args[0]
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")

    # Báo cáo bắt đầu
    await update.message.reply_text(f"⏳ Bắt đầu cào số liệu cho ngày: {date_str}...")
    sys_status["is_crawling"] = True

    try:
        # Bước 1. Cào dữ liệu
        data = fetch_lottery_data(date_str)
        sys_status["last_crawl"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Bước 2. Đẩy lên Github
        success = push_to_github(date_str, data)
        if success:
            sys_status["last_status"] = "Thành công (Đã Push)"
            link = f"https://raw.githubusercontent.com/{os.getenv('GITHUB_REPO')}/{os.getenv('GITHUB_BRANCH', 'main')}/data/{date_str.replace('-', '/')}.json"
            await update.message.reply_text(f"✅ Hoàn tất! Dữ liệu đã được Deploy.\n\nJSON Link: {link}")
        else:
            sys_status["last_status"] = "Thất bại (Lỗi đẩy Git)"
            await update.message.reply_text("❌ Có lỗi khi đẩy file JSON lên Github. Hãy xem logs server.")
            
    except Exception as e:
        sys_status["last_status"] = f"Lỗi Python: {str(e)}"
        await update.message.reply_text(f"❌ Lỗi Exception: {str(e)}")
    finally:
        sys_status["is_crawling"] = False

def init_telegram_bot() -> Application:
    """ Khởi tạo đối tượng Application của Telegram """
    if not TELEGRAM_TOKEN:
        print("[WARNING] Không tìm thấy TELEGRAM_TOKEN, bot sẽ không hoạt động.")
        return None
        
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("crawl", crawl_cmd))
    return app
