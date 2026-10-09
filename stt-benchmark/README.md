# STT Bench

Tool độc lập để nhập dataset, chọn cấu hình model và so sánh chỉ số. Không import code của app dạy–học. Tool không tự chọn model hay gán mục đích sử dụng.

## Chạy tất cả trong một báo cáo

Chọn dataset → **Phạm vi benchmark** → **Tất cả model phù hợp trong danh mục + cấu hình đã lưu**. Tool lọc ngôn ngữ, ưu tiên cấu hình đã lưu thay vì preset trùng checkpoint. Preset mới dùng CPU INT8 (faster-whisper) hoặc CPU float32; muốn cấu hình GPU hãy lưu cấu hình trước. Mục **Tất cả cấu hình đã lưu phù hợp** chỉ chạy các model bạn đã thêm.

Backend chưa cài và cloud chưa cho phép được liệt kê là bỏ qua trước khi chạy, không đưa vào số model đã test. Weights chưa có sẽ báo lỗi trong báo cáo trừ khi cho phép tải. Không tự cài dependencies, không tự bật cloud. Chạy tối đa 50 cấu hình tuần tự; một model lỗi không dừng các model sau. Bấm **CSV tổng hợp** để lấy mỗi model một dòng, hoặc **CSV từng mẫu** để xem chi tiết. Nếu một model thất bại mọi mẫu, giao các mẫu chung có thể rỗng; không coi điểm trống là 0 lỗi.

## Nhiều backend và chỉ số (2026-10-09)

Danh mục EN/VI có Whisper, Distil-Whisper, PhoWhisper, Qwen3-ASR, Parakeet, Canary, SenseVoice, wav2vec2, MMS, Vosk và API ElevenLabs/Google Chirp. Danh mục là cấu hình ứng viên, không phải thông báo tất cả weights đã cài hoặc đã được kiểm chứng trên máy này.

1. Chọn ngôn ngữ ở **Lọc danh mục model**.
2. Chọn checkpoint → **Điền cấu hình model này**.
3. Kiểm tra backend, Python, thiết bị, ngôn ngữ và model path. Bật tải model nếu dùng tên remote. Vosk cần tải/giải nén model trước.
4. **Lưu cấu hình**, chọn các checkbox model rồi chạy cùng dataset (tối đa 8 cấu hình/lượt).
5. Đọc WER, CER, số lỗi/thành công, thời gian và RTF; tải JSON/CSV để lưu kết quả.

### Cài backend độc lập

Không cài toàn bộ ML stack vào môi trường của app. Từ workspace:

```powershell
.\stt-benchmark\install-backend.ps1 -Backend transformers-whisper
.\stt-benchmark\install-backend.ps1 -Backend vosk
```

Backend hợp lệ: `faster-whisper`, `transformers-whisper`, `transformers-ctc`, `qwen-asr`, `nemo`, `sensevoice`, `vosk`, `elevenlabs`, `google-chirp`. Script tạo `.backends/<backend>`; refresh giao diện rồi chọn lại preset sẽ điền Python tương ứng. Cũng có thể nhập đường dẫn Python riêng đã cài backend. NeMo ưu tiên Linux/GPU theo model card; script Windows không bảo đảm NeMo cài thành công. Worker hiện chỉ gọi Python local trên cùng OS, chưa điều khiển WSL/remote tự động.

Thư viện được import lazily. Việc phát hiện module/venv không chứng minh model đã tải hoặc CUDA sẵn sàng. Thiếu dependency/weights được ghi thành lỗi, không chấm thành transcript rỗng thành công. Các adapter ngoài những model có smoke test thật trong QA_REPORT còn cần xác minh trên phần cứng và checkpoint bạn chọn.

### Giao thức đo

- **Cả file:** đưa audio đầy đủ vào adapter. Transformers và SenseVoice chia block tối đa 30 giây, không overlap; giữ các block để tránh cắt mất phần cuối file. Biên block có thể ảnh hưởng WER. CTC dùng greedy, không LM ngoài. Các backend khác dùng decoder mặc định trừ Whisper có beam cấu hình được.
- **Chia đoạn tuần tự:** cắt cố định 1–15 giây, không overlap/context giữa đoạn. Một worker giả định mỗi đoạn sẵn sàng tại thời điểm cuối đoạn; `emitted_at = max(chunk_end, previous_emitted_at) + processing_time`. Không sleep theo thời gian thực. Báo P95 xử lý đoạn, P95 trễ sau cuối đoạn, P95 thời điểm có chữ đầu và số đoạn xử lý lâu hơn thời lượng đoạn. Đây không phải phép đo microphone, native streaming hay logic của app.
- CER dùng cùng chuẩn hóa WER, loại khoảng trắng, giữ dấu tiếng Việt; tổng hợp tổng lỗi ký tự/tổng ký tự. WER VI vẫn là đơn vị cách nhau bởi khoảng trắng.
- Không so trực tiếp khác ngôn ngữ/giao thức/cấu hình. Không tự chọn người thắng. Các chỉ số chung dựa trên giao các mẫu thành công; thời gian/P95 trong bảng chính vẫn theo mẫu thành công của từng model. JSON có common_summary tương ứng.
- Worker riêng: timer nhận dạng gồm IPC và giải mã audio. Mỗi worker load model một lần/lượt. Không đưa reference vào worker. Thư viện backend được lưu trong `runtime` của model.
- Thời gian load không tính vào RTF; chưa warm-up riêng. Chưa đo RAM/VRAM hoặc tự tính tiền API.

### Cloud tùy chọn

ElevenLabs cần biến môi trường `ELEVENLABS_API_KEY`; Google cần Application Default Credentials, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION` phù hợp Chirp 3. Google adapter dùng synchronous Recognize, giới hạn 60 giây/mẫu. Đặt biến trước khi khởi động server. Không nhập key vào model config; key không lưu trong JSON report. Chỉ gửi audio khi chọn model API và tick đồng ý cloud; có thể phát sinh phí. Chưa chạy kiểm chứng API với tài khoản thật.

Nguồn tích hợp: [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [PhoWhisper](https://huggingface.co/vinai/PhoWhisper-small), [Qwen3-ASR](https://huggingface.co/Qwen/Qwen3-ASR-0.6B), [Parakeet](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2), [Canary](https://huggingface.co/nvidia/canary-1b-v2), [SenseVoice](https://github.com/QwenAudio/SenseVoice), [MMS](https://huggingface.co/facebook/mms-1b-all), [Vosk](https://alphacephei.com/vosk/models), [ElevenLabs](https://elevenlabs.io/docs/api-reference/speech-to-text/convert), [Chirp](https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3).

## Chạy trên workspace hiện tại

Từ thư mục VANGIA_PROJECT, chạy PowerShell:

```powershell
.\stt-benchmark\start.ps1
```

Mở `http://127.0.0.1:8766`. Script ưu tiên `.venv` của tool, rồi dùng Python đã có trong app nếu tìm thấy. Đây chỉ là dùng chung môi trường thư viện, không phụ thuộc mã nguồn app. Có thể chạy trực tiếp:

```powershell
.\facial-cue-prototype\.venv\Scripts\python.exe .\stt-benchmark\server.py
```

Dừng server bằng Ctrl+C trong terminal. Không dừng giữa benchmark nếu muốn giữ một lần chạy hoàn chỉnh. Lần chạy bị ngắt sẽ được đánh dấu khi khởi động lại; dữ liệu từng mẫu đã lưu được giữ lại. Chưa hỗ trợ tiếp tục đúng từ mẫu đang dở; tạo lần chạy mới để so sánh đầy đủ.

## Môi trường riêng (tùy chọn)

Python 3.10+:

```powershell
cd stt-benchmark
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1
```

Server/giao diện chỉ cần thư viện chuẩn Python; import audio cần PyAV. Model dùng backend tương ứng trong danh mục ở trên.

## Dataset

Upload một ZIP:

```text
english_pilot.zip
  audio/EN001.mp3
  audio/EN002.m4a
  transcripts/EN001.txt
  transcripts/EN002.txt
```

- Nhận 1–1.000 cặp; không bắt buộc đủ 100 để thử quy trình.
- ID audio/TXT giống nhau, phân biệt hoa/thường; không trùng ID ở thư mục khác. Không đặt EN001.mp3 và EN001.wav cùng một ZIP vì chúng trùng ID.
- Nhận WAV, MP3, M4A, FLAC, OGG, OPUS, AAC, WebM; có thể trộn định dạng giữa các mẫu. File cần giải mã được và có đúng một audio stream. Đây không phải cam kết đọc mọi codec, file mã hóa hoặc file hỏng mang các đuôi này.
- Tối đa 10 phút/mẫu sau giải mã, 128 MB/file nguồn. Giữ nguyên file gốc trong `originals/`; giải mã/downmix/resample một lần khi import thành WAV PCM16 mono 16 kHz trong `audio/`. Mọi model dùng cùng bản này; không tách người nói. Thời lượng tính từ số mẫu đã giải mã. Không áp dụng khử nhiễu hoặc tự tăng âm lượng.
- Hash file gốc và bản đã chuyển đổi, thông số nguồn, cùng phiên bản xử lý audio được lưu trong manifest/report. Chuyển MP3 sang PCM không khôi phục thông tin đã mất do nén. Thời gian chuyển đổi khi import không nằm trong RTF model.
- TXT UTF-8, chỉ chứa lời nói thực tế, không thêm nhãn vai nếu audio không đọc nhãn.
- ZIP tối đa 512 MB; tổng dung lượng khai báo sau giải nén tối đa 1 GB; tổng audio chuẩn hóa tối đa 1 GB.
- Nghe lại bản thu và sửa transcript trước khi chấm. Kịch bản AI chưa được nghe kiểm tra không phải đáp án chuẩn.
- Bộ hiện tại: `../datasets/stt_english_ai70_general30_v1/conversations.md`. Thu thử EN001, EN027, EN053, EN070, EN074.
- Import sao chép dữ liệu vào `data/datasets/<id>`; không chỉnh sửa bản gốc. Muốn sửa dữ liệu, chỉnh bộ nguồn rồi import phiên bản mới.
- Dataset cũ vẫn chạy theo audio đã lưu trước đây. Nếu muốn so sánh tất cả theo quy trình chuẩn hóa mới, import lại nguồn thành phiên bản mới và chạy mọi model trên phiên bản đó.

## Model

Lần chạy đầu tool dò hai thư mục `base.en`, `small.en` trong app hiện tại để tạo cấu hình. Không sao chép model. Bạn có thể nhập bất kỳ đường dẫn thư mục model tương thích CTranslate2/faster-whisper, hoặc tên model được backend hỗ trợ khi bật tải model.

Đường dẫn local được ưu tiên; mặc định không tải từ mạng. CUDA cần môi trường GPU phù hợp, tool sẽ báo lỗi nếu thiếu. Model tiếng Anh `.en` không dùng cho dataset tiếng Việt. Với tiếng Việt, chọn model đa ngôn ngữ.

Chọn một hoặc nhiều cấu hình để chạy tuần tự; nạp từng model một lần. Không đưa transcript chuẩn hoặc kịch bản vào prompt của model. Mỗi lần chạy lưu bản chụp cấu hình, ngôn ngữ, phiên bản dependencies, thông tin môi trường, hash dataset, transcript gốc và dự đoán.

## Diễn giải kết quả

- WER = (substitutions + deletions + insertions) / số từ chuẩn, tổng hợp bằng tổng lỗi/tổng từ. Có thể lớn hơn 100% khi model thêm nhiều từ.
- Chuẩn hóa NFKC, không phân biệt hoa/thường, phần lớn dấu câu thành khoảng trắng; giữ apostrophe và dấu tiếng Việt. Không chuyển `25` thành `twenty-five`: khác biệt biểu diễn số vẫn có thể được tính là lỗi. Chính sách được lưu cùng báo cáo.
- Với tiếng Việt, cách chấm hiện tại tách theo khoảng trắng, gần mức âm tiết; không gọi đây là benchmark đã tách từ tiếng Việt theo ngôn ngữ học.
- WER từng model chỉ tính các mẫu thành công. Báo cả số thành công/thất bại và WER trên giao các mẫu mọi model thành công, tránh xếp hạng lệch khi một model bỏ sót mẫu khó.
- Thời gian nhận dạng bao gồm đọc/giải mã audio, VAD và tiêu thụ toàn bộ generator đầu ra; không gồm nạp model, hash input và chấm điểm. Không có warm-up riêng, nên mẫu đầu có thể chậm hơn. RTF = tổng thời gian nhận dạng thành công / tổng thời lượng audio tương ứng.
- Không đo native streaming hoặc hành vi chia cửa sổ của app. Có tùy chọn chia đoạn cố định để đo mô phỏng như mô tả ở trên; không dùng gain, bộ lọc segment hay deduplication riêng của app.
- Lưu đường dẫn model, không khóa revision của model remote và không hash toàn bộ weights. Để tái hiện chặt chẽ, dùng thư mục model local bất biến và lưu phiên bản nguồn tải bên ngoài.
- Lưu `data/runs/<id>/run.json` sau mỗi mẫu; tải CSV hoặc JSON từ giao diện. Có thể dừng giữa các mẫu; không ngắt ngay tác vụ inference hoặc tải model đang chạy.

## Thêm backend

1. Viết adapter trong `benchmark/adapters.py` hoặc module khác, có `load()`, `transcribe(audio_path, language)`, `close()`.
2. `transcribe` nhận audio, trả về `{"text": "...", "segments": [...]}`; không nhận reference.
3. Đăng ký trong `ADAPTERS`, thêm validation/config UI cho backend mới.
4. Dataset, chấm điểm, lưu báo cáo và so sánh tiếp tục dùng chung.

## Kiểm tra

```powershell
python -m unittest discover -s tests -v
node --test tests/test_ui.cjs
```

Tests dùng dữ liệu tạm và adapter giả để kiểm tra scoring, ZIP validation, công bằng tập so sánh, lỗi model, persistence và HTTP. Không tạo kết quả nhận dạng giả dưới tên model thật.

JavaScript tests kiểm tra phối hợp request và trạng thái báo cáo, không thay thế kiểm tra trực quan bằng trình duyệt. Xem `QA_REPORT.md` để biết phạm vi đã kiểm chứng và giới hạn còn lại.
