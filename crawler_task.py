import time
from datetime import datetime, timedelta
from crawler import fetch_lottery_data
from github_sync import push_batch_to_github
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
    CHUNK_SIZE = 500
    
    try:
        total_chunks = (total + CHUNK_SIZE - 1) // CHUNK_SIZE
        
        for chunk_idx in range(0, total, CHUNK_SIZE):
            chunk_dates = dates[chunk_idx : chunk_idx + CHUNK_SIZE]
            current_chunk = (chunk_idx // CHUNK_SIZE) + 1
            
            # Bước 1: Fetch song song cho gói hiện tại
            fetched_results = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_date = {executor.submit(fetch_data_worker, d): d for d in chunk_dates}
                fetched_count = 0
                sys_status["last_status"] = f"[Gói {current_chunk}/{total_chunks}] Đang cào dữ liệu {len(chunk_dates)} ngày (Đa luồng)..."
                
                for future in concurrent.futures.as_completed(future_to_date):
                    d = future_to_date[future]
                    try:
                        data = future.result()
                        fetched_results[d] = data
                    except Exception as exc:
                        print(f"Ngày {d} fetch lỗi: {exc}")
                        fetched_results[d] = None
                        
                    fetched_count += 1
                    sys_status["last_status"] = f"[Gói {current_chunk}/{total_chunks}] Đang nạp RAM ({fetched_count}/{len(chunk_dates)})..."
            
            # Bước 2: Push Batch gói hiện tại lên Github
            valid_files = {}
            for d in chunk_dates:
                if fetched_results.get(d):
                    valid_files[d] = fetched_results[d]
                    sys_status["last_crawl"] = d
                else:
                    fail_count += 1
                    
            if valid_files:
                sys_status["last_status"] = f"[Gói {current_chunk}/{total_chunks}] Đang nén {len(valid_files)} ngày vào Github..."
                success, msg = push_batch_to_github(valid_files)
                if success:
                    success_count += len(valid_files)
                else:
                    fail_count += len(valid_files)
                    sys_status["last_status"] = f"[Gói {current_chunk}/{total_chunks}] Lỗi đẩy Github: {msg}"
            
        sys_status["last_status"] = f"Hoàn thành chuỗi siêu tốc: Thành công {success_count}/{total} ngày. Lỗi {fail_count}."
            
    except Exception as e:
        sys_status["last_status"] = f"Lỗi Exception nghiêm trọng: {str(e)}"
        print(f"[CRAWLER_TASK] Lỗi: {e}")
        # Re-raise to let bot.py catch it
        raise e
    finally:
        sys_status["is_crawling"] = False
