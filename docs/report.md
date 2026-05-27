# Báo Cáo Triển Khai Bài Tập
**Bài tập:** B1 - Hệ thống quản lý camera và streaming video

## 1. Phân tích vấn đề
Đề bài yêu cầu xây dựng một hệ thống giám sát và quản lý camera qua giao thức RTSP với các tính năng:
* Tiếp nhận và hiển thị đồng thời tối thiểu 4 luồng video trên giao diện web dạng lưới (Grid).
* Xây dựng API quản lý camera (CRUD) và cho phép tùy chỉnh FPS hiển thị theo từng kênh.
* Hệ thống cần đáp ứng khả năng mở rộng (scale) lên đến 32 - 80 kênh trong tương lai.
* Xử lý độ ổn định: Tự động kết nối lại khi đứt luồng, giám sát tài nguyên (CPU, RAM) và gửi cảnh báo tự động.

**Thách thức cốt lõi (Bottleneck):**
Nếu sử dụng Python/OpenCV để tải và giải mã trực tiếp khung hình từ 32-80 luồng RTSP, CPU máy chủ sẽ bị quá tải ngay lập tức. Bên cạnh đó, việc truyền tải đồng thời hàng chục luồng video thẳng về trình duyệt web sẽ gây nghẽn băng thông và làm treo thiết bị khách (client). 

## 2. Phương pháp triển khai
Để giải quyết bài toán hiệu năng, kiến trúc hệ thống được chia làm hai phần tách biệt: **Luồng Dữ liệu (Data Path)** và **Luồng Điều khiển (Control Path)**.

1. **Luồng Dữ liệu (Media Server):** 
   - Sử dụng **MediaMTX** chuyên dụng để nhận luồng RTSP (được giả lập từ FFmpeg) và đóng gói trực tiếp thành HLS (HTTP Live Streaming) gửi xuống frontend. Python hoàn toàn không can thiệp vào việc đọc và chuyển mã video.
2. **Luồng Điều khiển (FastAPI & MongoDB):** 
   - FastAPI chịu trách nhiệm cung cấp REST API (CRUD camera, thông số tài nguyên). Thay vì đọc video, FastAPI chạy một tác vụ ngầm (Background Task) gọi API của MediaMTX định kỳ mỗi 5 giây để lấy danh sách các luồng đang hoạt động. Từ đó, FastAPI nhanh chóng xác định được trạng thái (CONNECTED, DISCONNECTED) và thời gian sống (uptime) của từng camera.
3. **Quản lý FPS tại giao diện (Client-side Canvas Throttling):**
   - Đề bài yêu cầu thay đổi cấu hình FPS và áp dụng ngay lập tức mà không ngắt luồng. Giải pháp là tải HLS video ẩn trên trình duyệt, sau đó dùng hàm `requestAnimationFrame` kết hợp thẻ `<canvas>` để tự vẽ khung hình lên màn hình theo đúng chu kỳ FPS đã chọn. Cách này giảm thiểu hoàn toàn gánh nặng xử lý FPS cho máy chủ.
4. **Cơ chế Cảnh báo (Telegram Alert):**
   - Sự kiện đứt kết nối hoặc CPU/RAM máy chủ quá tải (đo bằng `psutil`) sẽ kích hoạt logic gửi cảnh báo Telegram. Một bộ lọc Cooldown (60 giây) được tích hợp để chặn gửi tin nhắn spam khi sự cố kéo dài liên tục.

## 3. Kết quả đo lường
*(Thực hiện test thực tế qua script `bash scripts/benchmark_streams.sh 60`)*

- **Môi trường:** Ubuntu 22.04.5 LTS / Docker v29.1.3
- **Thiết bị:** CPU Intel Core i5-1135G7 @ 2.40GHz, RAM 16GB, GPU Intel Iris Xe Graphics.
- **Quy mô luồng:** Chạy mô phỏng 4 luồng video 640x360 H.264 (HLS).
- **Mức tiêu thụ CPU Backend:** Tác vụ Polling FastAPI chỉ tốn ~1-2% CPU.
- **Mức tiêu thụ CPU Tổng:** Cả FFmpeg và MediaMTX tốn khoảng ~15-20% CPU cho 4 luồng, hoàn toàn đáp ứng tốt cho mục tiêu scale lên 32 luồng.
- **Thời gian tự kết nối lại:** Hệ thống nhận diện ngắt kết nối trong vòng < 5 giây và luồng video được khôi phục lên trình duyệt trong vòng < 3 giây sau khi bộ phát hoạt động trở lại.

## 4. Hạn chế và Hướng cải thiện
**Hạn chế hiện tại:**
- Giải pháp HLS tạo độ trễ tĩnh khoảng 2-4 giây do phải đóng gói (muxing) các đoạn segment video.
- Chức năng Canvas Throttling giúp giảm FPS hiển thị nhưng băng thông mạng tải HLS từ server về trình duyệt vẫn được tải ở tốc độ khung hình gốc.

**Hướng cải thiện:**
1. **Sử dụng WebRTC:** Chuyển đổi từ giao thức HLS sang WebRTC (được MediaMTX hỗ trợ sẵn) để đạt độ trễ thời gian thực (Sub-second latency < 500ms).
2. **Triển khai Load Balancer:** Tại mốc 80 kênh, băng thông mạng sẽ là nút thắt cổ chai. Cần tách MediaMTX ra các máy chủ (Node) phân tán độc lập và dùng Nginx điều hướng luồng.
3. **Thêm Redis:** Đẩy trạng thái In-memory (RuntimeStatus) từ RAM của ứng dụng FastAPI vào Redis để sẵn sàng chạy nhiều bản sao (replica) FastAPI đồng thời.
