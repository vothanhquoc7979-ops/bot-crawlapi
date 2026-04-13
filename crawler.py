import time
import hmac
import hashlib
import requests
import json
from datetime import datetime

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
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"[CRAWLER ERROR] Lỗi khi gọi API: {e}")
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
    xs_path = f"/api/public/lottery/by-date?date={date_str}&region=all"
    xs_data = call_api(xs_path)
    
    if xs_data:
        results["xs"]["bac"] = xs_data.get("bac", [])
        results["xs"]["trung"] = xs_data.get("trung", [])
        results["xs"]["nam"] = xs_data.get("nam", [])

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
