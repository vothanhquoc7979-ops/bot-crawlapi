import time
from datetime import datetime, timedelta
from crawler import fetch_lottery_data
from github_sync import push_to_github

sys_status = {
    "is_crawling": False,
    "last_crawl": "Chưa có",
    "last_status": "Đang chờ"
}

def parse_date(date_str: str) -> datetime:
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    raise ValueError(f"Định dạng ngày '{date_str}' không hợp lệ. Hãy dùng YYYY-MM-DD hoặc DD/MM/YYYY.")

def get_date_range(start_str: str, end_str: str) -> list[str]:
    start = parse_date(start_str)
    end = parse_date(end_str)
    if start > end:
        start, end = end, start # Đảo ngược nếu nhập sai thứ tự
        
    delta = end - start
    return [(start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta.days + 1)]

def run_crawl_routine(dates: list[str]):
    sys_status["is_crawling"] = True
    total = len(dates)
    success_count = 0
    fail_count = 0
    
    try:
        for idx, d in enumerate(dates, 1):
            sys_status["last_status"] = f"Đang xử lý {d} ({idx}/{total})..."
            data = fetch_lottery_data(d)
            sys_status["last_crawl"] = d
            
            success, msg = push_to_github(d, data)
            if success: 
                success_count += 1
            else: 
                fail_count += 1
                print(f"[CRAWLER_TASK] Lỗi khi push ngày {d}: {msg}")
            
            # Khựng lại 1 giây chống spam API
            time.sleep(1) 
            
        sys_status["last_status"] = f"Hoàn thành chuỗi: Thành công {success_count}/{total} ngày. Lỗi {fail_count}."
    except Exception as e:
        sys_status["last_status"] = f"Lỗi Exception nghiêm trọng: {str(e)}"
        print(f"[CRAWLER_TASK] Lỗi: {e}")
    finally:
        sys_status["is_crawling"] = False
