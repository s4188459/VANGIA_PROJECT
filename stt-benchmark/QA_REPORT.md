# Kiểm tra STT Bench — 2026-10-07

## Mở rộng audio input — 2026-10-08

- Hỗ trợ nhập WAV, MP3, M4A, FLAC, OGG, OPUS, AAC và WebM. Test tạo/giải mã audio thật ở tám định dạng này, kiểm tra bản gốc được giữ nguyên, hash khớp và đầu ra chung PCM16 mono 16 kHz.
- Dataset được chuẩn hóa một lần tại import, mỗi model dùng cùng file đã chuẩn hóa. Dataset đã nhập trước đó không tự bị viết lại.
- Test hồi quy chặn hai audio khác đuôi nhưng cùng ID và báo đúng ID cho audio hỏng; giữ giới hạn thời lượng và dung lượng cả sau giải mã.
- Kết quả: **26 tests Python + 3 tests JavaScript đạt**, kiểm tra cú pháp JS/compile Python đạt.
- MP3 giọng máy được chạy qua HTTP upload → preview → base.en/small.en → scoring → CSV/JSON; bản gốc được giữ nguyên và các kết quả xuất khớp report. Báo cáo: `data/smoke/http-9f08f28705c144a2a14b229409958296/runs/7aec36ec3e684418bf12fbf807f58b48/run.json`.
- Lệnh: `python tests/smoke_http.py --audio data/smoke/SMOKE001.mp3`.
- Chưa kiểm thử mọi codec/biến thể container hay file từ mọi thiết bị; audio cần giải mã được, có đúng một audio stream. Không cam kết nhận file hỏng, mã hóa hoặc mọi loại file tùy ý. Chưa kiểm tra trực quan trình duyệt; giới hạn WER và chất lượng dữ liệu tham chiếu vẫn áp dụng.

## Kiểm tra bổ sung — 2026-10-08

- Python runtime khi gọi trực tiếp không có `faster_whisper`, nhưng không thể kết luận môi trường server chỉ từ đường dẫn executable của tiến trình con: Windows `.venv` có thể khởi chạy Python nền đó và vẫn dùng thư viện của virtual environment. Điều tra cây tiến trình xác định còn server cũ từ `.venv` giữ cổng sau khi một phiên khác bị dừng. Đã dừng đúng cặp cha–con khi không có benchmark hoạt động và khởi động một server duy nhất bằng `facial-cue-prototype/.venv/Scripts/python.exe`. Dùng `start.ps1` hoặc đường dẫn Python cụ thể trong README để chọn môi trường đã kiểm thử.

- **23 tests Python + 3 tests JavaScript đạt.** Kiểm tra cú pháp JavaScript và compile Python đạt.
- WER được đối chiếu với một thuật toán tìm khoảng cách chỉnh sửa đệ quy độc lập trên **930 cặp** chuỗi ngắn, bao gồm từ lặp và hypothesis rỗng. Tổng lỗi S/D/I, mẫu số và WER đều khớp. Đây là bằng chứng cho tập trường hợp đã kiểm tra, không phải chứng minh mọi dữ liệu có thể có.
- Phát hiện và sửa lỗi khởi động server thứ hai trên cùng cổng Windows: tắt address reuse, dùng exclusive socket khi khả dụng, chiếm cổng trước khi phục hồi trạng thái run. Test xác nhận lần mở thất bại không sửa trạng thái benchmark đang lưu.
- Test end-to-end qua HTTP với **model thật base.en và small.en**, dùng WAV giọng máy khoảng 6,53 giây cùng TXT nhiều dòng CRLF: upload ZIP, xem audio/reference, inference, chấm điểm, tải CSV và JSON đều đạt. ZIP hỏng được từ chối. Nội dung audio giữ nguyên; kết quả CSV và JSON khớp với report lưu.
- Báo cáo model thật mới: `data/smoke/http-67ecfe1f75fb4fd696c8b8468c139c69/runs/f19a820d5acb4a4a843a77cee46965d0/run.json`.
- Lệnh tái chạy end-to-end: `python tests/smoke_http.py --audio data/smoke/SMOKE001.wav`.
- Tool browser vẫn trả về `apps: [], browsers: []`. Chưa thể xác nhận bố cục, file picker, playback và toàn bộ thao tác trong trình duyệt thật. HTTP test và test logic giao diện không thay thế những kiểm tra này.
- Chưa có 100 bản thu người dùng đã duyệt để đánh giá thực tế. Chưa đo GPU, tải model qua mạng hoặc benchmark nhiều người nói. WER theo chính sách hiện tại vẫn phân biệt số viết bằng chữ với chữ số; không đồng nghĩa độ chính xác ngữ nghĩa.

Các mục bên dưới là biên bản kiểm tra trước đó; số kiểm thử cập nhật nằm ở mục này.

## Lỗi đã tái hiện và sửa

- Transcript TXT xuống dòng CRLF trên Windows bị kiểm tra hash sai sau import. Chuẩn hóa xuống dòng và ghi UTF-8 nhất quán; giữ hash dữ liệu nguồn riêng.
- Phản hồi chậm từ báo cáo cũ ghi đè báo cáo vừa chọn. Loại bỏ phản hồi của yêu cầu không còn hiện hành.
- Xóa lựa chọn báo cáo nhưng phản hồi đang chờ lại mở báo cáo cũ. Vô hiệu hóa yêu cầu cũ ngay khi đổi lựa chọn.
- Xem báo cáo cũ làm nút chạy bật dù benchmark khác đang chạy. Theo dõi trạng thái chạy nền riêng và cập nhật khi hoàn tất.
- Cấu hình beam/thread tự cắt số thập phân thành số nguyên, nhận boolean và nhận null làm tên model. Kiểm tra kiểu dữ liệu và báo lỗi rõ ràng.
- Model chỉ tiếng Anh có thể vượt kiểm tra tiếng Việt khi đổi tên thư mục. Kiểm tra khả năng đa ngôn ngữ của model đã nạp trước inference.

Các test hồi quy đã thất bại trên code cũ và đạt sau sửa.

## Kết quả xác minh

- `python -m unittest discover -s tests -v`: 21 tests đạt.
- `node --test tests/test_ui.cjs`: 3 tests đạt. Đây là test logic JavaScript với DOM/network tối thiểu, không phải kiểm tra hiển thị trên trình duyệt.
- `node --check web/app.js`: đạt.
- `python -m compileall -q benchmark server.py`: đạt.
- Dataset giả lập 100 cặp WAV/TXT chạy hai adapter giả: đủ 200 kết quả, 100 mẫu chung, CSV đủ 200 hàng. Mục đích kiểm tra điều phối và persistence, không đo nhận dạng.
- Chạy model thật `base.en` và `small.en` trên một đoạn giọng máy khoảng 6,53 giây: cả hai hoàn tất và trả lời nói. Báo cáo tại `data/smoke/state/runs/e9b3192c1c3244a2bca2c07cf1cd22a4/run.json`. Dữ liệu này tách khỏi dataset người dùng.
- Các kiểm tra khác bao gồm ZIP không an toàn, thiếu/trùng cặp, WAV hỏng/cắt ngắn, TXT sai UTF-8 hoặc rỗng, Unicode tiếng Việt, WER có trọng số, model load/decode lỗi, dừng giữa mẫu, chặn chạy đồng thời, khôi phục lần chạy bị ngắt, HTTP upload/preview/download, CSV formula escaping và input bị sửa sau import.

## Phạm vi chưa xác minh / giới hạn

- Chưa kiểm tra trực quan, playback và file picker bằng trình duyệt thật: công cụ browser trả danh sách rỗng.
- Chưa chạy 100 bản thu thật; chưa đánh giá chất lượng model trên dataset của người dùng.
- Chưa thử CUDA, model tải qua mạng, hoặc model đa ngôn ngữ thật.
- Chuẩn hóa vẫn phân biệt `20` và `twenty`. Smoke test ghi một lỗi từ do khác biệt biểu diễn này; WER hiện tại là so sánh chữ sau chuẩn hóa đã công bố, không phải độ chính xác ngữ nghĩa. Xem thêm README.
- Không khẳng định tool không còn lỗi trong mọi điều kiện. Có thể bắt đầu pilot 5 bản ghi, kiểm tra quy trình thực tế trước khi thu cả 100.

## Chạy lại

Từ thư mục `stt-benchmark`, dùng Python có dependencies của tool:

```powershell
..\facial-cue-prototype\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/test_ui.cjs
node --check web/app.js
..\facial-cue-prototype\.venv\Scripts\python.exe tests/smoke_local_models.py --audio data/smoke/SMOKE001.wav
```
# Update 2026-10-09: multi-backend benchmark

Scope: neutral benchmark metrics only, no automatic model selection or application roles.

- Catalog: 38 presets across 9 backend keys, language filtering and language validation; optional isolated Python workers.
- New metrics: corpus-weighted CER (same normalization as WER, whitespace excluded), inference seconds, optional fixed-chunk replay processing P95, simulated lag P95, first nonempty result P95. No native-streaming/microphone claim, no RAM/VRAM or automatic API cost measurement.
- Regression suite: 31 Python tests (includes independent CER oracle over 961 string pairs, catalog validation, causal queue/tail/cancel, runner CER/replay and cloud gate), 4 JavaScript tests including preset defaults. These do not constitute visual browser QA.
- Real HTTP MP3 test passed with base.en + small.en: upload/normalization/preview/inference/scoring/CSV-JSON parity. Report `data/smoke/http-bcc58c3718714f44a7342b3fb3425a47/runs/3cdf75ed62424df0bf6de18918f3244e/run.json`.
- Vosk 0.3.45, model `vosk-model-small-en-us-0.15`: real recognition through isolated worker passed, complete-file and fixed 3-second chunks; results under `data/smoke/multibackend-20261009`. One synthetic English fixture only; not quality evidence for the user's dataset.
- PhoWhisper-tiny: real weights loaded and inference returned nonempty text using Transformers 5.19.0 / Torch 2.14.1 CPU. Technical smoke on canonicalized English fixture with Vietnamese decoding only, explicitly NOT a Vietnamese accuracy benchmark. Initial direct raw fixture test correctly rejected non-16k audio; canonical dataset path passed.
- Installed isolated environments for Vosk and Transformers Whisper. Ready saved configurations: existing base.en/small.en plus Vosk small EN and PhoWhisper tiny VI. Existing user dataset and reports retained.
- Qwen, NeMo/Parakeet/Canary, SenseVoice, Transformers CTC/MMS, Google and ElevenLabs adapters are implemented but NOT real-checkpoint/account validated here. Model/OS/package compatibility remains to be tested per configuration. No cloud credentials used or audio uploaded.
- No GPU performance measurement. No guarantee that every catalog checkpoint runs on this Windows CPU. NeMo upstream favors Linux/GPU. Worker launcher handles local Python environments, not WSL commands.
- Worker request timeout: 30 minutes model loading, 10 minutes per inference. Download and inference cannot be immediately cancelled by the UI; cancellation is checked between samples/chunks.
