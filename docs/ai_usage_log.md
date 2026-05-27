# Nhật Ký Sử Dụng AI (AI Usage Log)

## 1. Thông Tin Công Cụ
- **Tên công cụ:** Antigravity (Google DeepMind AI Assistant)
- **Tên mô hình:** Gemini
- **Phiên bản:** Gemini 3.1 Pro / Gemini 3.5 Flash, Claude Sonet
- **Mục đích sử dụng:** Trợ lý lập trình hỗ trợ thiết kế cấu trúc, sinh mã boilerplate (FastAPI, Docker), đề xuất thuật toán (đếm FPS, Canvas throttling) và tư vấn gỡ lỗi (debugging) cho hệ thống VMS.

## 2. 5 Đoạn Hội Thoại Chính (Prompts & Tasks)

| STT | Khâu xử lý | Nội dung Prompt / Yêu cầu chính gửi cho AI | Kết quả sinh ra bởi AI |
|:---:|:---|:---|:---|
| 1 | **Thiết kế cấu trúc dự án (Project Scaffolding)** | *"Đọc yêu cầu bài toán VMS B1 (FastAPI, RTSP, UI) và tạo ra một bản Kế hoạch triển khai (Implementation Plan) định hình thư mục dự án và mô hình dữ liệu MongoDB."* | AI sinh ra toàn bộ thư mục `app/api/v1/`, `app/models/`, `app/services/` và cấu trúc REST API tiêu chuẩn, phân chia rõ lớp Controller và Repository. |
| 2 | **Cấu hình MediaMTX & Docker** | *"Viết `docker-compose.yml` để chạy MongoDB, ứng dụng FastAPI và MediaMTX. Bổ sung script bash thiết lập 4 luồng RTSP mẫu từ file mp4."* | AI tạo `docker-compose.yml` với healthcheck cho Mongo, sinh ra script `setup.sh` và `demo-publisher` FFmpeg để lặp luồng video MP4 mà không gây quá tải CPU. |
| 3 | **Cơ chế Polling & Giám sát** | *"Làm thế nào để backend FastAPI theo dõi trạng thái online/offline của luồng RTSP mà không dùng OpenCV đọc frame gây nghẽn CPU? Hãy cập nhật `StreamManager`."* | AI gợi ý sử dụng vòng lặp `asyncio` để truy vấn REST API của MediaMTX (`GET /v3/paths/list`) mỗi 5s, tự động cập nhật trạng thái In-memory và phát hiện sự kiện đứt kết nối. |
| 4 | **Canvas Visual FPS Throttling** | *"Yêu cầu đề bài có chỉnh FPS động. Với HLS thì backend khó can thiệp FPS ngay lập tức. Cập nhật frontend Javascript để render video lên `<canvas>` thay vì `<video>`, dùng `requestAnimationFrame` giới hạn FPS hiển thị."* | AI sinh ra logic `startCanvasThrottle` cực kỳ hoàn thiện, giúp kiểm tra thời gian giữa các khung hình (delta time) và chỉ vẽ lên canvas khi đủ thời lượng, tiết kiệm CPU đáng kể. |
| 5 | **Báo cáo sự cố Telegram & Cooldown** | *"Cài đặt `AlertService` ghi log vào MongoDB và gửi tin nhắn qua Telegram Bot. Thêm logic nếu camera offline liên tục quá 10s mới gửi tin nhắn và phải có cooldown 60s để tránh spam."* | AI tự động thiết kế lớp service lưu cooldown vào Dictionary in-memory, tích hợp lời gọi `requests.post` gửi markdown sang API của Telegram. |

## 3. Nội Dung Đã Tự Kiểm Tra & Chỉnh Sửa Thủ Công (Manual Verification)

Mặc dù AI hỗ trợ rất tốt ở mức định hình khung mã (boilerplate) và đề xuất thuật toán, tôi đã phải tự mình kiểm chứng và can thiệp điều chỉnh (refactor) lại những điểm sau để code có thể hoạt động chính xác trên thực tế:

1. **Khắc phục lỗi Closure của JavaScript trên Giao diện:**
   - **Tình trạng do AI sinh ra:** Nút bấm "Sim Off" / "Sim On" bắt sự kiện dựa trên biến `cam` cục bộ tại thời điểm khởi tạo thẻ (stale closure). Khi trạng thái bị cập nhật qua API, nút bấm không đổi màu do vẫn giữ object tham chiếu cũ.
   - **Cách tôi chỉnh sửa:** Sửa logic Javascript để hàm click luôn sử dụng `cameraId` và tra cứu lại `cameras.find(c => c.id === cam.id)` tại đúng thời điểm nhấn.
2. **Khắc phục lỗi mất URL Video sau khi cập nhật trạng thái:**
   - **Tình trạng do AI sinh ra:** Hàm `updateTile()` đồng bộ dữ liệu WebSocket từ Server đè lên dữ liệu cũ (Sử dụng `Object.assign`), làm mất biến `hls_url` (do Server chỉ push metadata, không push URL tĩnh).
   - **Cách tôi chỉnh sửa:** Thêm biến trung gian lưu tạm `prevHlsUrl`, gán ngược lại cho object sau khi đồng bộ để trình phát video không bị sập.
3. **Cơ chế đồng bộ hóa Healthcheck trong Docker:**
   - **Tình trạng do AI sinh ra:** Container FastAPI khởi động trước khi MongoDB sẵn sàng, dẫn đến ngoại lệ mất kết nối DB khi chạy lệnh cài đặt một click.
   - **Cách tôi chỉnh sửa:** Bổ sung thuộc tính `depends_on: condition: service_healthy` vào tệp docker-compose và viết lệnh `mongosh --eval "db.adminCommand('ping')"` cho MongoDB.
4. **Phân tích giới hạn mô hình kết nối:**
   - AI từng đề xuất đọc frame H.264 bằng `cv2.VideoCapture` trên FastAPI. Tôi đã chủ động từ chối và thiết kế lại kiến trúc sử dụng luồng MediaMTX HLS thuần túy để phù hợp với yêu cầu "Scaling 80 luồng" mà không làm treo hệ thống.
