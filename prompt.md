# AI Prompt to Recreate This Project

Sao chép toàn bộ nội dung dưới đây và dán vào một AI Coding Assistant (như Claude, GPT, Gemini) để sinh mã nguồn tái tạo lại chính xác dự án quản lý và hiển thị luồng camera (VMS) này.

---

```markdown
Hãy xây dựng một hệ thống Quản lý và Giám sát Camera (Video Management System - VMS) thời gian thực bằng Python, FastAPI, MongoDB, MediaMTX, FFmpeg và giao diện Web Dashboard thuần (Vanilla HTML/CSS/JS). Hệ thống phải chạy hoàn toàn bằng Docker Compose và có tính năng kiểm soát FPS động bằng Canvas ở Client.

### 1. KIẾN TRÚC & CƠ CHẾ HOẠT ĐỘNG

1. **RTSP Simulation (FFmpeg + MediaMTX):**
   - Đọc các tệp video `.mp4` từ thư mục `resources/videos/` và dùng FFmpeg chạy lặp (loop, stream-copy) để đẩy thành các luồng RTSP lên server MediaMTX nội bộ (ví dụ: `rtsp://mediamtx:8554/demo/garden`, `rtsp://mediamtx:8554/demo/office`).
2. **FastAPI Backend (Cổng 8000):**
   - Quản lý cấu hình camera (CRUD) lưu trong MongoDB.
   - **StreamManager (In-Memory Status):** Theo dõi trạng thái hoạt động thực tế của từng camera (CONNECTED, DISCONNECTED, RECONNECTING) bằng cách polling API kiểm tra source của MediaMTX (không giải mã video trên Python để tối ưu hiệu năng, đáp ứng khả năng scale lên 32-80 kênh).
   - **WebSocket `/api/v1/ws/dashboard`:** Đẩy danh sách trạng thái camera mỗi 1 giây và thông số tài nguyên máy chủ (CPU, RAM qua `psutil`) mỗi 3 giây.
   - **AlertService & Telegram Notifier:** Lưu sự kiện (Events) vào MongoDB. Khi camera mất kết nối thực tế quá 10 giây hoặc CPU/RAM quá tải (CPU > 90%, RAM > 85%), gửi thông báo qua Telegram Bot API (có cooldown 60s để tránh spam).
3. **Web UI (Vanilla JS, HLS.js, Canvas):**
   - Giao diện tối (Sleek Dark Mode) dạng lưới (Grid) hiển thị đồng thời tối thiểu 4 ô video.
   - Tải video bằng giao thức HLS (đọc từ MediaMTX qua thư viện `hls.js`).
   - **Visual FPS Throttling:** Cung cấp menu lựa chọn FPS hiển thị cho từng camera: `[1, 5, 10, 15, 30, 60, 75, 120]`. Vì HLS được phát trực tiếp từ MediaMTX, giao diện phải ẩn thẻ `<video>` đi và vẽ các khung hình lên thẻ `<canvas>` bằng vòng lặp `requestAnimationFrame` giới hạn đúng tốc độ FPS đã chọn để tiết kiệm CPU cho máy khách.
   - **Simulate Buttons (Giả lập lỗi mạng):**
     - Nút "Sim Off" chuyển camera sang trạng thái mất kết nối giả lập (RECONNECTING). Trong code backend, tác vụ giả lập này sẽ tự động khôi phục về CONNECTED sau 15 giây.
     - Nút "Sim On" chủ động khôi phục kết nối ngay lập tức mà không yêu cầu reload trang.

### 2. CẤU TRÚC THƯ MỤC DỰ ÁN

Hệ thống cần được tổ chức như sau:
```
project-root/
├── app/
│   ├── main.py              # Khởi tạo FastAPI + Lifespan (start/stop background tasks)
│   ├── common/              # Serializer MongoDB và Response Schema dùng chung
│   ├── core/                # config.py (Pydantic BaseSettings), logging, constants
│   ├── api/
│   │   └── v1/              # Routes: camera_routes, stream_routes, event_routes, websocket_routes
│   ├── db/                  # Kết nối MongoDB (sử dụng thư viện Motor)
│   ├── models/              # Dataclass RuntimeStatus và Model DB
│   ├── schemas/             # Pydantic Request/Response schemas cho Camera
│   ├── repositories/        # BaseRepository thực hiện CRUD MongoDB và các lớp kế thừa
│   ├── services/            # StreamManager, AlertService, TelegramNotifier, MetricsService
│   ├── utils/               # Tính toán FPS, thời gian và sinh ảnh placeholder khi lỗi
│   └── web/                 # Static files: index.html, styles.css, app.js
├── scripts/
│   ├── init_env.sh          # Tạo file .env từ .env.example
│   ├── init_services.sh     # Khởi động dịch vụ cơ bản
│   ├── start_rtsp_streams.sh # Dùng FFmpeg đẩy luồng RTSP
│   └── register_demo_cameras.sh # Gọi API đăng ký mặc định 4 camera
├── resources/
│   └── videos/              # Chứa các video test (.mp4)
├── Dockerfile               # Build ứng dụng FastAPI
├── docker-compose.yml       # Định nghĩa dịch vụ: mongo, mediamtx, app, demo-publisher
├── setup.sh                 # Script chạy một lệnh duy nhất để thiết lập và chạy hệ thống
└── requirements.txt         # Các thư viện Python cần thiết
```

### 3. YÊU CẦU CHI TIẾT VỀ MÃ NGUỒN

#### Backend:
- **`app/services/stream_manager.py`**:
  - Quản lý một luồng polling chạy nền (background task) gọi đến endpoint `/v3/api/paths/list` của MediaMTX để kiểm tra sự tồn tại của luồng RTSP.
  - Cập nhật trạng thái runtime vào một dictionary lưu trữ trong bộ nhớ: `status` (CONNECTED, RECONNECTING, DISCONNECTED), `reconnect_count`, `uptime_seconds`, `display_fps`.
  - Tích hợp logic cảnh báo: Nếu camera ở trạng thái RECONNECTING và thời gian mất kết nối thực tế lớn hơn 10 giây, kích hoạt hàm cảnh báo của `AlertService`. Chỉ cảnh báo 1 lần cho mỗi đợt ngắt kết nối.
  - Tích hợp hàm `simulate_offline(camera_id)`: đánh dấu giả lập offline, tạo một background task tự động khôi phục kết nối sau 15 giây (`simulate_reconnect(camera_id)`).
- **`app/services/alert_service.py`**:
  - Ghi nhận sự kiện lỗi vào MongoDB.
  - Nếu `TELEGRAM_ENABLED=true` và các cấu hình token/chat_id hợp lệ, gửi tin nhắn cảnh báo định dạng Markdown qua Telegram Bot API. Đảm bảo có cơ chế cooldown (60 giây) cho các cảnh báo trùng loại trên cùng một camera.
- **`app/api/v1/camera_routes.py`**:
  - API `GET /api/v1/cameras` lấy danh sách camera từ MongoDB, đồng thời gộp (merge) trạng thái thời gian thực (`status`, `uptime_seconds`, `simulated_offline`, `reconnect_count`) từ `StreamManager` trước khi trả về cho client.

#### Frontend (`app/web/app.js` & `index.html`):
- HTML chứa template của camera tile có một thẻ `<canvas>` để render và một thẻ `<video style="display:none">` ẩn.
- Thư viện `hls.js` sẽ nạp stream vào thẻ `<video>`.
- Triển khai hàm `startCanvasThrottle(cameraId, videoElement, canvasElement, fps)` sử dụng `requestAnimationFrame`. Vòng lặp sẽ kiểm tra thời gian trôi qua giữa các frame, nếu đủ điều kiện tương ứng với cấu hình FPS (ví dụ: `1000 / fps` ms), thực hiện `canvasContext.drawImage(videoElement, 0, 0, width, height)` để vẽ lên canvas.
- Xử lý bất đồng bộ trạng thái:
  - Lắng nghe WebSocket để cập nhật giao diện (như đổi màu trạng thái, hiển thị badge FPS thực tế, log sự kiện) ngay lập tức khi nhận được gói tin `camera_status_snapshot`.
  - Giữ lại `hls_url` khi gộp dữ liệu từ WebSocket để không làm hỏng trình phát video HLS.
  - Nút bấm Simulation: Gửi yêu cầu POST lên API giả lập ngắt/mở kết nối. Tại thời điểm nhấn nút, thực hiện tìm kiếm object camera động trong mảng `cameras` hiện tại thay vì sử dụng biến bị đóng băng (stale closure) để tránh lỗi trạng thái nút bấm không đồng bộ.

#### Cấu hình Docker & Thiết lập:
- **`docker-compose.yml`**: Mount thư mục `/app/web` của frontend vào container dạng volume `:ro` để khi sửa code JS/CSS thì giao diện cập nhật ngay không cần build lại ảnh Docker.
- **`setup.sh`**:
  - Kiểm tra xem thư mục `resources/videos` đã có file video `.mp4` nào chưa. Nếu chưa có, tự động tải xuống một video mẫu (ví dụ: Big Buck Bunny ~1MB).
  - Chạy `docker compose up -d --build`.
  - Đợi ứng dụng FastAPI khởi động hoàn tất (healthcheck thành công).
  - Gọi tập lệnh đăng ký nhanh 4 camera trỏ đến các luồng RTSP tương ứng.

Hãy triển khai toàn bộ các file code và cấu hình theo đặc tả chi tiết trên, đảm bảo không sử dụng mã giả (placeholder), xử lý tốt các ngoại lệ kết nối và tối ưu hiệu năng đa luồng.
```
