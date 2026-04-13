import os
import requests
import base64
import json

# Lấy từ biến môi trường của Railway
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "") # Ví dụ: username/xoso-data
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

def push_to_github(date_str: str, json_data: dict) -> bool:
    """
    Push data JSON vào kho lưu trữ thông qua Github REST API.
    Sẽ tạo file mới nếu chưa có, hoặc cập nhật nếu đã tồn tại.
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("[GITHUB] Thiếu GITHUB_TOKEN hoặc GITHUB_REPO trong file env.")
        return False

    # Tách năm, tháng để tạo thư mục logic. VD: 2026/04/11.json
    year, month, day = date_str.split("-")
    file_path = f"data/{year}/{month}/{day}.json"
    
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. Kiểm tra xem file đã tồn tại chưa để lấy chỉ số SHA (bắt buộc khi update)
    sha = None
    res_get = requests.get(url, headers=headers)
    if res_get.status_code == 200:
        sha = res_get.json().get("sha")
        print(f"[GITHUB] File {file_path} đã tồn tại. Chuẩn bị ghi đè.")
    else:
        print(f"[GITHUB] File {file_path} chưa có. Chuẩn bị tạo mới.")

    # 2. Xây dựng payload để Tạo/Cập nhật file
    content_str = json.dumps(json_data, indent=2, ensure_ascii=False)
    content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

    payload = {
        "message": f"Auto-sync Ket Qua Xo So for {date_str}",
        "content": content_b64,
        "branch": GITHUB_BRANCH
    }
    
    if sha:
        payload["sha"] = sha

    res_put = requests.put(url, headers=headers, json=payload)
    if res_put.status_code in [200, 201]:
        print(f"[GITHUB] \u2705 Đã đẩy thành công file {file_path} lên repo {GITHUB_REPO}")
        return True
    else:
        print(f"[GITHUB] \u274c Lỗi khi đẩy lên Github: {res_put.status_code} - {res_put.text}")
        return False
