# System Processing Flows (Sơ đồ luồng xử lý hệ thống)

Tài liệu này chứa các sơ đồ luồng xử lý chi tiết của dự án, được vẽ bằng ngôn ngữ **PlantUML**. Bạn có thể dùng các công cụ hỗ trợ render PlantUML trực tuyến hoặc plugin trong VS Code để xem trực quan các sơ đồ này.

---

## 1. Luồng Đăng ký Camera & Phát Video (Registration & Streaming Flow)

Mô tả luồng từ lúc người dùng đăng ký một camera mới, video mẫu được phát lặp lại (loop) dưới dạng RTSP bởi FFmpeg/MediaMTX, cho đến khi trình duyệt hiển thị video qua giao thức HLS.

```plantuml
@startuml
actor User as "Client (Web Dashboard)"
participant API as "FastAPI App"
database DB as "MongoDB"
participant SM as "StreamManager"
participant MTX as "MediaMTX"
participant DP as "demo-publisher"

== 1. Đăng ký Camera ==
User -> API : POST /api/v1/cameras\n{name, rtsp_url, target_fps, display_fps}
API -> DB : Lưu cấu hình Camera
API -> SM : Đăng ký runtime status (CREATED)
API --> User : Trả về thông tin Camera

== 2. Phát luồng RTSP (Simulated) ==
DP -> DP : Đọc sample.mp4 trong tài nguyên
DP -> MTX : FFmpeg loop stream-copy đẩy RTSP\nrtsp://mediamtx:8554/demo/<name>

== 3. Lấy thông tin HLS & Hiển thị ==
User -> API : GET /api/v1/streams/{camera_id}/hls-info
API -> SM : Lấy URL HLS tương ứng từ MediaMTX
API --> User : Trả về hls_url (http://localhost:8888/demo/<name>/index.m3u8)
User -> MTX : Trình duyệt kết nối tải m3u8 & ts (Lazy load)
@enduml
```

---

## 2. Luồng Giám sát & Tự động kết nối lại (Status Polling & Reconnect Flow)

Mô tả luồng kiểm tra trạng thái camera định kỳ thông qua API của MediaMTX. Khi xảy ra sự cố mất kết nối thực tế, hệ thống sẽ tự động thử kết nối lại và gửi cảnh báo tới Telegram sau 10 giây nếu sự cố vẫn tiếp diễn.

```plantuml
@startuml
participant SM as "StreamManager (Poller Loop)"
participant MTX as "MediaMTX API"
participant AS as "AlertService"
database DB as "MongoDB"
participant Tele as "Telegram API"

loop Định kỳ mỗi 5 giây (hoặc chu kỳ cấu hình)
    SM -> MTX : GET /v3/paths/list
    MTX --> SM : Trả về danh sách luồng RTSP đang active
    
    alt Luồng RTSP tồn tại (CONNECTED)
        SM -> SM : Cập nhật trạng thái = CONNECTED\nTăng uptime_seconds\nReset reconnect_count & timeout_alerted
    else Luồng RTSP không tồn tại (DISCONNECTED)
        alt Trạng thái trước đó là CONNECTED
            SM -> SM : Chuyển trạng thái = RECONNECTING\nGhi nhận thời điểm last_disconnected_at
            SM -> AS : Phát sự kiện CAMERA_DISCONNECTED
            AS -> DB : Lưu Event (Severity: WARNING)
            AS -> Tele : Gửi thông báo Telegram (nếu enabled)
        else Đang ở trạng thái RECONNECTING
            SM -> SM : Tăng reconnect_count
            alt Quá 10 giây chưa kết nối lại & chưa gửi alert
                SM -> SM : Đánh dấu reconnect_timeout_alerted = True
                SM -> AS : Phát sự kiện RECONNECT_TIMEOUT
                AS -> DB : Lưu Event (Severity: ERROR)
                AS -> Tele : Gửi thông báo Telegram cảnh báo mất kết nối quá 10s
            end
        fi
    fi
end
@enduml
```

---

## 3. Luồng Cảnh báo Telegram & Cơ chế Cooldown (Telegram Alerting & Cooldown Flow)

Mô tả cơ chế kiểm soát và lọc các cảnh báo trùng lặp (ví dụ: cảnh báo quá tải CPU/RAM hoặc camera liên tục mất kết nối) để tránh tình trạng spam tin nhắn Telegram của người dùng bằng cách áp dụng thời gian cooldown (60 giây).

```plantuml
@startuml
participant API as "FastAPI (Background Task / API Call)"
participant AS as "AlertService"
database DB as "MongoDB"
participant Tele as "Telegram API"

== Xử lý cảnh báo (Có Cooldown) ==
API -> AS : trigger_alert(camera_id, event_type, severity, message)
AS -> AS : Kiểm tra Cooldown thời gian gần nhất (ALERT_COOLDOWN_SECONDS=60)
AS -> DB : Lưu Event vào MongoDB

alt Cooldown đã qua & TELEGRAM_ENABLED=true
    AS -> Tele : POST /bot<Token>/sendMessage
    Tele --> AS : Trả về HTTP 200 OK
    AS -> DB : Đánh dấu event.notified = True
else Đang trong thời gian Cooldown
    AS -> AS : Bỏ qua gửi Telegram (tránh spam)
end
@enduml
```

---

## 4. Luồng Canvas Visual FPS Throttling (Client-side Canvas FPS Throttling)

Mô tả luồng hiển thị video giới hạn khung hình (FPS) ở phía giao diện trình duyệt nhằm giảm thiểu việc sử dụng CPU của thiết bị xem mà không cần phải giải mã lại video phía server.

```plantuml
@startuml
actor Browser as "Trình duyệt (Browser)"
participant JS as "app.js (Frontend Script)"
participant HLS as "hls.js Library"
participant Video as "Hidden HTML5 <video>"
participant Canvas as "HTML5 <canvas> (Hiển thị)"

== Khởi tạo luồng hiển thị ==
JS -> HLS : Khởi tạo HLS instance
JS -> Video : Gắn HLS stream vào thẻ Video (style="display:none")
JS -> JS : Khởi chạy startCanvasThrottle(id, videoEl, canvasEl, fps)

== Vòng lặp Render Throttled ==
loop Mỗi chu kỳ render (requestAnimationFrame)
    JS -> JS : Kiểm tra: (Thời gian hiện tại - Lần vẽ cuối) >= (1000 / display_fps) ms
    alt Đủ điều kiện thời gian
        JS -> Video : Đọc khung hình hiện tại (videoEl.readyState >= 2)
        JS -> Canvas : canvasContext.drawImage(videoEl, 0, 0, width, height)
        JS -> JS : Cập nhật thời điểm lần vẽ cuối
    else Chưa đủ thời gian
        JS -> JS : Bỏ qua vẽ (chờ chu kỳ tiếp theo)
    end
end
@enduml
```
