import time
import hmac
import hashlib
import requests
import json
from datetime import datetime
from config import get_config
import random

SECRET = "xs365-api-sign-key-2026"
BASE_URL = "https://ketqua.plus"

def gen_sig(method, path):
    ts = str(int(time.time() * 1000))
    raw = f"{ts}:{method}:{path}"
    sig = hmac.new(
        SECRET.encode(),
        raw.encode(),
        hashlib.sha256
    ).hexdigest()
    return sig, ts

def get_random_proxy():
    conf = get_config()
    proxies = conf.get("PROXIES", [])
    if not proxies or not isinstance(proxies, list):
        return None
        
    p = random.choice(proxies).strip()
    if not p: return None
    
    parts = p.split(":")
    # Format: host:port:user:pass
    if len(parts) == 4:
        host, port, user, pwd = parts
        proxy_url = f"http://{user}:{pwd}@{host}:{port}"
    # Format: host:port
    elif len(parts) == 2:
        proxy_url = f"http://{p}"
    else:
        proxy_url = f"http://{p}" # fallback
        
    return {"http": proxy_url, "https": proxy_url}

def call_api(path):
    url = f"{BASE_URL}{path}"
    sig, ts = gen_sig("GET", path)
    headers = {
        "x-sig": sig,
        "x-ts": ts,
        "user-agent": "Mozilla/5.0",
        "referer": "https://ketqua.plus/",
        "accept": "application/json"
    }
    
    proxy_dict = get_random_proxy()
    
    try:
        if proxy_dict:
            res = requests.get(url, headers=headers, proxies=proxy_dict, timeout=20)
        else:
            res = requests.get(url, headers=headers, timeout=15)
            
        res.raise_for_status()
        return res.json()
    except Exception as e:
        prx_info = f" (Proxy: {proxy_dict['http']})" if proxy_dict else ""
        print(f"[CRAWLER ERROR] Lỗi khi gọi API{prx_info}: {e}")
        return None

def fetch_lottery_data(date_str: str):
    """
    Fetch both XS (3 miền) and Vietlott data for a given date
    Format date_str: YYYY-MM-DD
    """
    results = {
        "date": date_str,
        "timestamp": datetime.now().isoformat(),
        "xs": {"bac": [], "trung": [], "nam": []},
        "vietlott": {}
    }
    
    # Lấy XS 3 Miền
    for region in ["bac", "trung", "nam"]:
        xs_path = f"/api/public/lottery/by-date?date={date_str}&region={region}"
        xs_data = call_api(xs_path)
        if xs_data and isinstance(xs_data, dict):
            # API trả về luôn dict chứa key là tên đài (ví dụ {"bac": [...] })
            results["xs"][region] = xs_data.get(region, [])

    # Lấy Vietlott
    vietlott_games = ["mega645", "power655", "max3d", "max3dpro", "lotto535"]
    for game in vietlott_games:
        v_path = f"/api/public/vietlott/by-date?gameType={game}&date={date_str}"
        v_data = call_api(v_path)
        if v_data:
            results["vietlott"][game] = v_data
        else:
            results["vietlott"][game] = None
            
    return results

if __name__ == "__main__":
    # Test crawler script
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    data = fetch_lottery_data("2026-04-11")
    print(f"Bắc: {len(data['xs']['bac'])}, Trung: {len(data['xs']['trung'])}, Nam: {len(data['xs']['nam'])}")
    print("Vietlott games fetched:", list(data['vietlott'].keys()))
