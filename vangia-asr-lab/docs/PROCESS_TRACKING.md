# Theo dõi benchmark trực tiếp

Đóng cửa sổ ứng dụng cũ rồi mở lại `launch-asrlab.bat` để nạp bản cập nhật.

Khung **Live process tracking** luôn nằm phía trên các tab. Nó hiển thị:

- Model đang chạy và số thứ tự trong hàng đợi.
- Giai đoạn kiểm tra dữ liệu/weights, nạp model, nhận diện và lưu kết quả.
- Mã audio đang xử lý, số lượt thành công, lỗi, bị hủy và còn lại.
- Thời gian theo dõi, thời gian model hiện tại đã chạy, thời gian từ sự kiện gần nhất.
- Tiến trình worker và bộ nhớ RSS của worker (cộng các tiến trình, có thể tính trùng bộ nhớ chia sẻ).
- Nút **Cancel benchmark** ngay trên bảng tiến độ; trạng thái **STOPPING** khi đang dừng.

Trong **Results & Export**, bảng tiến độ từng model tự cập nhật khoảng mỗi giây. Bảng kết quả phía dưới cập nhật khi từng model kết thúc và dữ liệu đã được đóng dấu kiểm tra toàn vẹn. Không cần chờ cả 9 model.

Thanh tiến độ đếm các lượt đã có trạng thái thành công/lỗi; số bị hủy hiển thị riêng và không được coi là thành công. Thời gian từ sự kiện gần nhất không phải bằng chứng máy bị treo: một audio dài có thể mất nhiều thời gian nhận diện. Không hiển thị ETA đoán khi chưa đủ dữ liệu.

Khi benchmark kết thúc, ứng dụng đổi trạng thái và phát chuông hệ thống nếu hệ thống cho phép âm thanh. Nút Start/Resume bị khóa trong khi cửa sổ đang chạy hoặc đang theo dõi benchmark còn hoạt động.

## Tiếp tục lần đã hủy

1. Mở ứng dụng mới → **New benchmark (ZIP)**.
2. Sang **Models & Run** → **Resume saved benchmark**.
3. Chọn thư mục `runs/benchmark-93073d56` cho lần đã hủy trước đó.
4. Theo dõi khung tiến độ. Resume giữ các audio đã hoàn thành và thử lại phần chưa thành công theo cấu hình cũ.

Nếu chỉ muốn xem kết quả cũ: **Results & Export** → **Open saved benchmark / run** → chọn thư mục đó. Thao tác này không tự chạy lại.

Không thay đổi dữ liệu, cấu hình đã đóng băng hoặc timeout của benchmark cũ trong bản cập nhật này. Lỗi timeout vẫn được hiển thị trong cột Latest error để xử lý riêng.
