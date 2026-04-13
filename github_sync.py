import os
import requests
import base64
import json
from config import get_config

import copy

GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

def get_core_for_compare(d: dict):
    c = copy.deepcopy(d)
    c.pop("timestamp", None)
    return json.dumps(c, sort_keys=True)

def merge_datasets(old_d: dict, new_d: dict) -> dict:
    merged = copy.deepcopy(old_d) if isinstance(old_d, dict) else {}
    if "date" not in merged: merged["date"] = new_d.get("date")
    if "xs" not in merged: merged["xs"] = {"bac":[], "trung":[], "nam":[]}
    if "vietlott" not in merged: merged["vietlott"] = {}
    
    # Bổ sung XS nếu thiếu
    for r in ["bac", "trung", "nam"]:
        od_len = len(merged.get("xs", {}).get(r, []))
        nd = new_d.get("xs", {}).get(r, [])
        if nd and len(nd) >= od_len:
            merged["xs"][r] = nd
            
    # Bổ sung Vietlott nếu thiếu
    for game in ["mega645", "power655", "max3d", "max3dpro", "lotto535"]:
        nd = new_d.get("vietlott", {}).get(game)
        if nd:
            merged["vietlott"][game] = nd
            
    merged["timestamp"] = new_d.get("timestamp")
    return merged

def push_to_github(date_str: str, json_data: dict) -> tuple[bool, str]:
    conf = get_config()
    gh_token = conf.get("GITHUB_TOKEN")
    gh_repo = conf.get("GITHUB_REPO")
    """
    Push data JSON vào kho lưu trữ thông qua Github REST API.
    Sẽ tạo file mới nếu chưa có, hoặc cập nhật nếu đã tồn tại.
    """
    if not gh_token or not gh_repo:
        return False, "Thiếu biến GITHUB_TOKEN hoặc GITHUB_REPO"

    # Tách năm, tháng để tạo thư mục logic. VD: 2026/04/11.json
    year, month, day = date_str.split("-")
    file_path = f"data/{year}/{month}/{day}.json"
    
    url = f"https://api.github.com/repos/{gh_repo}/contents/{file_path}"
    headers = {
        "Authorization": f"token {gh_token}",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. Kiểm tra xem file đã tồn tại chưa để lấy chỉ số SHA (bắt buộc khi update)
    sha = None
    res_get = requests.get(url, headers=headers)
    old_data = None
    
    if res_get.status_code == 200:
        file_info = res_get.json()
        sha = file_info.get("sha")
        content_b64 = file_info.get("content", "")
        if content_b64:
            try:
                old_data_str = base64.b64decode(content_b64).decode('utf-8')
                old_data = json.loads(old_data_str)
            except:
                old_data = None
    elif res_get.status_code not in [200, 404]:
        return False, f"Lỗi check file: HTTP {res_get.status_code} - {res_get.json().get('message', '')}"

    if old_data:
        merged_data = merge_datasets(old_data, json_data)
        if get_core_for_compare(old_data) == get_core_for_compare(merged_data):
            return True, f"Bỏ qua (Skip): Dữ liệu ngày {date_str} trên Github đã đầy đủ."
        final_data = merged_data
    else:
        final_data = json_data

    # 2. Xây dựng payload để Tạo/Cập nhật file
    content_str = json.dumps(final_data, indent=2, ensure_ascii=False)
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
        return True, f"Thành công! JSON URL: https://raw.githubusercontent.com/{gh_repo}/{GITHUB_BRANCH}/{file_path}"
    else:
        error_msg = res_put.json().get("message", res_put.text)
        return False, f"Lỗi API Github: {res_put.status_code} - {error_msg}"

def push_batch_to_github(files_dict: dict) -> tuple[bool, str]:
    """
    Sử dụng Github Git Database API (Trees API) để chèn hàng chục ngàn file trong 1 thao tác duy nhất.
    files_dict: {"2026-04-11": {<json_data>}, ...}
    """
    conf = get_config()
    gh_token = conf.get("GITHUB_TOKEN")
    gh_repo = conf.get("GITHUB_REPO")
    
    if not gh_token or not gh_repo:
        return False, "Thiếu biến GITHUB_TOKEN hoặc GITHUB_REPO"
        
    if not files_dict:
        return True, "Không có dữ liệu mới để push."
        
    headers = {
        "Authorization": f"token {gh_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # 1. Get branch info
    ref_url = f"https://api.github.com/repos/{gh_repo}/git/ref/heads/{GITHUB_BRANCH}"
    ref_res = requests.get(ref_url, headers=headers)
    if ref_res.status_code != 200:
        return False, f"Lỗi lấy nhánh {GITHUB_BRANCH}: {ref_res.text}"
        
    commit_sha = ref_res.json()["object"]["sha"]
    
    # 2. Get commit info to find base tree
    commit_res = requests.get(f"https://api.github.com/repos/{gh_repo}/git/commits/{commit_sha}", headers=headers)
    if commit_res.status_code != 200:
        return False, f"Lỗi lấy commit gốc: {commit_res.text}"
        
    base_tree_sha = commit_res.json()["tree"]["sha"]
    
    # Github limit 500 files per tree creation request. 
    chunk_size = 500
    items = list(files_dict.items())
    
    current_base_tree = base_tree_sha
    current_commit_sha = commit_sha
    
    try:
        total_pushed = 0
        for i in range(0, len(items), chunk_size):
            chunk = items[i:i + chunk_size]
            tree_data = []
            
            for date_str, data in chunk:
                year, month, day = date_str.split("-")
                file_path = f"data/{year}/{month}/{day}.json"
                content_str = json.dumps(data, indent=2, ensure_ascii=False)
                
                tree_data.append({
                    "path": file_path,
                    "mode": "100644",
                    "type": "blob",
                    "content": content_str
                })
                
            # Create Tree
            tree_payload = {
                "base_tree": current_base_tree,
                "tree": tree_data
            }
            res_tree = requests.post(f"https://api.github.com/repos/{gh_repo}/git/trees", headers=headers, json=tree_payload)
            if res_tree.status_code != 201:
                return False, f"Lỗi Create Tree: {res_tree.text}"
            
            new_tree_sha = res_tree.json()["sha"]
            
            # Create Commit
            first_date = chunk[0][0]
            last_date = chunk[-1][0]
            commit_payload = {
                "message": f"Auto-sync Batch {len(chunk)} days ({first_date} to {last_date})",
                "tree": new_tree_sha,
                "parents": [current_commit_sha]
            }
            res_commit = requests.post(f"https://api.github.com/repos/{gh_repo}/git/commits", headers=headers, json=commit_payload)
            if res_commit.status_code != 201:
                return False, f"Lỗi Create Commit: {res_commit.text}"
                
            current_commit_sha = res_commit.json()["sha"]
            current_base_tree = new_tree_sha
            total_pushed += len(chunk)
            
        # 3. Update Ref (Di chuyển cờ nhánh trỏ vào commit cuối)
        ref_payload = {"sha": current_commit_sha}
        res_ref = requests.patch(ref_url, headers=headers, json=ref_payload)
        
        if res_ref.status_code != 200:
            return False, f"Lỗi Update Ref: {res_ref.text}"
            
        return True, f"Thành công đẩy up Batch {total_pushed} ngày siêu tốc!"
    except Exception as e:
        return False, f"Lỗi Exception: {e}"
