import time
from datetime import datetime, timedelta
from crawler import fetch_lottery_data
from github_sync import push_to_github
import concurrent.futures

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

def fetch_data_worker(d: str):
    # Khai báo delay nhẹ nếu bị block
    return fetch_lottery_data(d)

def run_crawl_routine(dates: list[str]):
    sys_status["is_crawling"] = True
    total = len(dates)
    success_count = 0
    fail_count = 0
    
    try:
        sys_status["last_status"] = f"Đang cào dữ liệu {total} ngày (Đa luồng 10 Threads)..."
        
        # Bước 1: Fetch song song
        fetched_results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_date = {executor.submit(fetch_data_worker, d): d for d in dates}
            fetched_count = 0
            
            for future in concurrent.futures.as_completed(future_to_date):
                d = future_to_date[future]
                try:
                    data = future.result()
                    fetched_results[d] = data
                except Exception as exc:
                    print(f"Ngày {d} fetch lỗi: {exc}")
                    fetched_results[d] = None
                    
                fetched_count += 1
                sys_status["last_status"] = f"Đang nạp dữ liệu vào RAM ({fetched_count}/{total})..."
        
        # Bước 2: Push tuần tự lên Github
        for idx, d in enumerate(dates, 1):
            sys_status["last_status"] = f"Đang đẩy lên Github: ngày {d} ({idx}/{total})..."
            data = fetched_results.get(d)
            sys_status["last_crawl"] = d
            
            if data is None:
                fail_count += 1
                continue
                
            success, msg = push_to_github(d, data)
            if success: 
                success_count += 1
            else: 
                fail_count += 1
                print(f"[CRAWLER_TASK] Lỗi khi push ngày {d}: {msg}")
            
            # Khựng lại một nhịp nhỏ trước khi push file tiếp theo (Tránh Github 409 Conflict)
            time.sleep(0.3)
            
        sys_status["last_status"] = f"Hoàn thành chuỗi: Thành công {success_count}/{total} ngày. Lỗi {fail_count}."
    except Exception as e:
        sys_status["last_status"] = f"Lỗi Exception nghiêm trọng: {str(e)}"
        print(f"[CRAWLER_TASK] Lỗi: {e}")
    finally:
        sys_status["is_crawling"] = False
