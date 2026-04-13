import os
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from config import get_config
from crawler_task import sys_status, parse_date, get_date_range, run_crawl_routine

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    conf = get_config()
    
    if conf.get("TELEGRAM_CHAT_ID") != chat_id:
        from config import save_config
        new_conf = conf.copy()
        new_conf["TELEGRAM_CHAT_ID"] = chat_id
        save_config(new_conf)

    msg = (
        "👋 Chào mừng bạn đến với Bot Quản Lý Xổ Số (Railway Edition)!\n\n"
        "📜 **DANH SÁCH LỆNH:**\n"
        "🔹 `/crawl today` - Cào một ngày duy nhất (hôm nay).\n"
        "🔹 `/crawl <ngày>` - Cào chuỗi từ <ngày> đến tận hôm nay. (Dùng định dạng DD-MM-YYYY hoặc YYYY-MM-DD).\n"
        "   👉 *VD: /crawl 10/04/2026*\n\n"
        "🔹 `/status` - Xem trạng thái máy chủ crawler."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"🖥️ **Trạng Thái Hệ Thống:**\n\n"
        f"Đang chạy Crawler: {'⚠️ CÓ' if sys_status['is_crawling'] else '✅ KHÔNG'}\n"
        f"Đang xử lý tại ngày: `{sys_status['last_crawl']}`\n"
        f"Trạng thái cuối cùng: `{sys_status['last_status']}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def _background_crawl(update: Update, dates_to_crawl: list, conf: dict):
    first_date = dates_to_crawl[0]
    last_date = dates_to_crawl[-1]
    date_info = f"ngày {first_date}" if first_date == last_date else f"từ {first_date} đến {last_date}"

    # Báo bắt đầu
    msg_start = (
        f'<tg-emoji emoji-id="5427009714745513056">⏰</tg-emoji> Lệnh từ Telegram nhận được rồi Quốc Chề ơi.\n'
        f'<tg-emoji emoji-id="5368324170671202286">🚀</tg-emoji> T bắt đầu cào {date_info} nhé!'
    )
    try: await update.message.reply_html(msg_start)
    except Exception:
        await update.message.reply_text(f"⏰ Lệnh từ Telegram nhận được rồi Quốc Chề ơi.\n🚀 T bắt đầu cào {date_info} nhé!")

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_crawl_routine, dates_to_crawl)
        
        gh_repo = conf.get("GITHUB_REPO", "username/repo")
        branch = os.getenv("GITHUB_BRANCH", "main")
        y, m, d = last_date.split("-")
        api_link = f"https://raw.githubusercontent.com/{gh_repo}/{branch}/data/{y}/{m}/{d}.json"
        
        msg_end = (
            f'<tg-emoji emoji-id="5368324170671202286">🎉</tg-emoji> Đã cào xong {date_info} rồi nha Quốc Chề.\n'
            f'<tg-emoji emoji-id="5427009714745513056">💾</tg-emoji> Đã Push lên Github luôn rồi đó.\n\n'
            f'🔗 <b>API Mới Nhất ({last_date}):</b>\n{api_link}\n\n'
            f'📋 <b>Báo cáo:</b> <code>{sys_status["last_status"]}</code>'
        )
        try: await update.message.reply_html(msg_end, disable_web_page_preview=True)
        except Exception:
            msg_end_fb = (
                f'🎉 Đã cào xong {date_info} rồi nha Quốc Chề.\n'
                f'💾 Đã Push lên Github luôn rồi đó.\n\n'
                f'🔗 API Mới Nhất ({last_date}):\n{api_link}\n\n'
                f'📋 Báo cáo: {sys_status["last_status"]}'
            )
            await update.message.reply_text(msg_end_fb, disable_web_page_preview=True)
            
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        if len(err_msg) > 3000: err_msg = err_msg[-3000:] 
        await update.message.reply_html(f"🛑 <b>LỖI HỆ THỐNG GÂY TREO BOT:</b>\n<code>\n{err_msg}\n</code>")

async def crawl_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conf = get_config()
    if not conf.get("TELEGRAM_TOKEN") or not conf.get("GITHUB_TOKEN"):
        await update.message.reply_text("❌ Thiếu biến môi trường cục bộ (Telegram hoặc Github PAT token).")
        return

    if sys_status["is_crawling"]:
        await update.message.reply_text("⚠️ Đang bận xử lý một hàng đợi khác. Vui lòng quay lại sau.")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    dates_to_crawl = []
    
    if not context.args or context.args[0].lower() == "today":
        dates_to_crawl = [today_str]
    else:
        try:
            input_date = context.args[0]
            # Sẽ cào từ ngày nhập vào cho tới biến today
            dates_to_crawl = get_date_range(input_date, today_str)
        except Exception as e:
            await update.message.reply_text(f"❌ Lỗi format ngày: {e}")
            return
            
    if not dates_to_crawl:
        await update.message.reply_text("❌ Không có ngày nào để cào.")
        return

    await update.message.reply_text(f"⏳ Bắt đầu cào {len(dates_to_crawl)} ngày (từ {dates_to_crawl[0]} tới {dates_to_crawl[-1]}). Vui lòng gõ /status để xem tiến trình...")
    
    # Chạy dưới nền Task Asyncio để không block chat của Telegram
    asyncio.create_task(_background_crawl(update, dates_to_crawl, conf))

def init_telegram_bot() -> Application:
    conf = get_config()
    token = conf.get("TELEGRAM_TOKEN")
    if not token:
        print("[WARNING] Không tìm thấy TELEGRAM_TOKEN, bot sẽ không hoạt động.")
        return None
        
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("crawl", crawl_cmd))
    return app
