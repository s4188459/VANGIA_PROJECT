# Cấu hình model ngày 17/10/2026

## Đã làm

- Kiểm kê đúng 11 model trong danh sách của ứng dụng.
- Kiểm tra import thành công cả bốn backend: Faster Whisper, NeMo, Qwen ASR và Transformers CTC.
- Tái sử dụng môi trường Python và weights đã có trên máy; không cài trùng các thư viện lớn.
- Bổ sung `config.json`, `generation_config.json`, `README.md` còn thiếu của Qwen 1.7B từ repository Qwen chính thức, revision `7278e1e70fe206f11671096ffdd38061171dd6e5`. Giữ nguyên cache cũ; tạo bản đầy đủ trong `runs/backend-setup/qwen17-complete`.
- Lưu đường dẫn Python/weights, phiên bản repository và SHA-256 cho các cấu hình mới.
- Chạy nhận diện thực tế đoạn đầu 5 giây của EN001, từng model một, không cho phép tải model tự động trong lúc chạy. Kết thúc tiến trình sau mỗi lượt để giải phóng model.
- Chín model đã qua nạp weights, nhận diện audio và giải phóng: Parakeet v2, Parakeet v3, Qwen 0.6B, Qwen 1.7B, Whisper small.en, small, large-v2, large-v3 và large-v3-turbo.
- Lưu chín preset thành công trong `runs/zz-installed-*-config.json` để giao diện tự đọc khi mở lại.
- Kiểm thử liên quan benchmark: 5 passed, 1 bài GUI bỏ qua do chưa bật chế độ kiểm thử desktop.

## Để sau khi nâng RAM

- **Canary 1B v2:** đã có backend, weights và cấu hình. Lần thử đầu dừng do áp lực RAM: Windows báo dùng 98% RAM, tiến trình worker yêu cầu khoảng 14,37 GB bộ nhớ committed (không đồng nghĩa tất cả đều nằm trong RAM vật lý). Chưa xác nhận nhận diện thành công.
- **MMS 1B:** đã có backend, weights và cấu hình, kiểm tra hash đạt. Chưa thử inference; chưa có bằng chứng nó bắt buộc cần hơn 16 GB.

Hai model này tạm hoãn theo yêu cầu làm trước phần phù hợp máy hiện tại. Nâng lên 32 GB tăng khoảng trống bộ nhớ, nhưng vẫn cần chạy lại kiểm tra; không bảo đảm tốc độ CPU hoặc khả năng xử lý mọi audio dài.

## Dùng ngay

1. Đóng ứng dụng cũ, mở lại `launch-asrlab.bat`.
2. `New benchmark (ZIP)` → nhập audio/TXT → `Import & validate`.
3. Sang `Models & Run`. Chọn `batch_file`, `Repeats = 1`.
4. Chọn chín model đã qua kiểm tra ở trên. Tích `Explicitly enable deferred diagnostic models` để thấy Qwen 1.7B; chưa chọn MMS và Canary lúc này. Giữ Ctrl để chọn/bỏ từng dòng.
5. `Check prerequisites` → `Start benchmark`. Mỗi model chạy tuần tự trên toàn bộ bộ dữ liệu đã nhập.
6. `Results & Export` → xuất CSV/JSON.

Đây là kiểm tra khả năng chạy với audio ngắn, không phải benchmark độ chính xác toàn bộ dữ liệu. Audio dài hơn có thể cần nhiều RAM và thời gian hơn. Không mở nhiều benchmark cùng lúc.

## Bằng chứng và đường dẫn cần giữ

- `runs/backend-setup/RESULTS.md`: bảng kết quả từng model.
- `runs/backend-setup/smoke-results.json`: phản hồi thực từ worker.
- `runs/backend-setup/*stdout.jsonl`, `*stderr.log`: log gốc.
- `runs/backend-setup/preflight-results.json`: kiểm tra cấu hình/hash, tách khỏi kết quả nhận diện.
- `runs/backend-setup/TASKS.md`: nhật ký task.

Các preset dùng môi trường trong `facial-cue-prototype/.venv` và `stt-benchmark/.backends`, cùng weights ở cache của dự án cũ. Không xóa những thư mục đó hoặc `runs/backend-setup` khi còn dùng các preset này.

## Lệnh kiểm tra tiếp sau khi nâng RAM

Từ thư mục `vangia-asr-lab`:

```powershell
.\.venv\Scripts\python.exe runs/backend-setup/smoke_all.py nvidia/canary-1b-v2 facebook/mms-1b-all
.\.venv\Scripts\python.exe runs/backend-setup/report_setup.py
```

Script chỉ kích hoạt preset khi thực sự nạp/nhận diện/giải phóng thành công. Nếu lỗi, giữ log để xử lý tiếp; không tự coi là chạy được.
