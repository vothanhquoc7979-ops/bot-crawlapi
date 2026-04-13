# Hướng Dẫn Deploy Khung Xổ Số Bot Lên Railway

Bộ mã nguồn này đóng vai trò như một cầu nối (**Agent Serverless**). Nó sẽ chạy trên [Railway.app](https://railway.app/), chờ lệnh từ Telegram hoặc Web UI để cào api trên trang `ketqua.plus`. Sau đó, nó tự động dồn dữ liệu (.jsons) lên một nhánh riêng trên kho Github của bạn thông qua REST API.

## Bước 1. Chuẩn bị tài nguyên
1. **GitHub Data Repo**: Tạo 1 Repo trống trên Github làm nơi lưu dữ liệu (ví dụ: tên là `username/xoso-data`, nhớ sửa `username` thành tài khoản github của bạn). Để là Public Repos (nếu muốn làm link raw API).
2. **GitHub PAT (Personal Access Token)**: Vào tài khoản Github -> `Settings` -> `Developer settings` -> `Personal access tokens (classic)` -> `Generate new token (classic)`. Tick quyền **repo (Trọng yếu nhất là quyền write content)**. Copy lấy dãy mã token đó lại.
3. **Telegram Bot Token**: Inbox BotFather tren Telegram, tạo 1 bot mới và copy mã API Token của nó.

## Bước 2. Upload source code bot này lên Github
Tạo một Github Repo thứ hai để chứa đống source code này (riêng tư hay public đều được, ví dụ repo là `username/railway-crawler-source`). Up đẩy toàn bộ file Python, html... vào đó.

## Bước 3. Deploy trên Railway
1. Đăng nhập vào [Railway](https://railway.app/).
2. Nhấn nút tạo dự án mới: `New` -> `GitHub Repo` -> Chọn cái `username/railway-crawler-source` bạn vừa up.
3. Railway sẽ nhận ra file `Procfile` và cài đặt FastApi thông qua `requirements.txt`.
4. Trong giao diện Railway app, bạn vào thẻ **Variables** và điền 4 biến sau. (ĐỀU PHẢI VIẾT HOA)

*   `TELEGRAM_TOKEN` = `(Mã API lấy ở bước chuẩn bị phần 3)`
*   `GITHUB_TOKEN` = `(Mã chuẩn PAT lấy từ bước chuẩn bị phần 2)`
*   `GITHUB_REPO` = `username/xoso-data` (Nơi mà bạn muốn đẩy file kết quả trúng vào)
*   `GITHUB_BRANCH` = `main` (Nhánh sẽ commit vào tài liệu bên Repo xoso-data)

> [!NOTE] 
> Biến `PORT` đã được cấu hình mặc định nên bạn không cần lo. Railway sẽ tự hiểu và trích xuất.

## Bước 4. Chạy & Tận hưởng
Đợi Railway deploy thành công (biểu tượng hiện Tick xanh).
Xong rồi! Bạn có thể vào Webiste mà Railway generate ra để bấm nút trực quan, hoặc nhắn tin lệnh `/crawl` thẳng vào Telegram Bot để nó thực thi việc cào ngay lập tức!
Tất cả File JSON cào được sẽ tự động tống vào `username/xoso-data` bằng các Commit riêng biệt. Xịn xò!
