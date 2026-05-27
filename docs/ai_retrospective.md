# Báo Cáo Đánh Giá Quá Trình Sử Dụng AI (AI Retrospective)

Trong suốt quá trình phát triển hệ thống Quản lý và Streaming Camera (VMS) này, việc áp dụng trợ lý AI (cụ thể là công cụ Google DeepMind Antigravity qua mô hình Gemini) đã mang lại sự cải thiện đáng kể về tốc độ và chất lượng mã nguồn. Dưới đây là những đánh giá chi tiết về mức độ hiệu quả, các điểm yếu của AI và những phần tôi phải tự kiểm chứng.

**1. Những khâu AI đã hỗ trợ cực kỳ hiệu quả (Strengths)**

AI thể hiện sức mạnh vượt trội trong việc dựng khung dự án (scaffolding) và áp dụng các Design Pattern tiêu chuẩn. Ngay từ những bước đầu, AI đã giúp tôi thiết lập toàn bộ cấu trúc thư mục chuẩn của một dự án FastAPI, bao gồm việc chia tách rõ ràng các lớp Model, Repository, Service và API Controller. Quá trình cấu hình Pydantic Schema để xác thực dữ liệu đầu vào và các thiết lập Async Motor để kết nối MongoDB không đồng bộ được AI sinh ra gần như hoàn hảo chỉ trong vài giây.

Đặc biệt, trong việc xây dựng giao diện người dùng (UI), AI đã làm rất tốt việc dịch đổi cấu trúc giao diện từ các bản mẫu React/TSX phức tạp sang định dạng thuần Vanilla HTML/CSS/JS (Dark Mode). Nhờ vậy, tôi không cần phải tốn quá nhiều thời gian viết mã CSS để tạo ra một Dashboard lưới hiển thị 4 camera rất mượt mà và chuyên nghiệp. 

**2. Những nội dung bắt buộc phải tự kiểm chứng thủ công (Manual Verification)**

Dù AI viết mã nhanh, khả năng hiểu logic vòng đời dữ liệu (Data Lifecycle) và quản lý tiến trình (Thread-safety) của nó vẫn chưa đủ tin cậy. Tôi đã phải thực hiện rất nhiều khâu kiểm chứng thủ công, điển hình là quyết định về việc phân tách dữ liệu lưu trữ. AI từng gợi ý lưu trạng thái kết nối camera (Connected/Offline) và Uptime trực tiếp vào MongoDB mỗi giây. Tôi nhận định điều này sẽ tạo ra nút thắt cổ chai về Disk I/O khi mở rộng lên 80 kênh. Do đó, tôi phải tự thiết kế lại luồng: chỉ lưu cấu hình vào MongoDB, và lưu trạng thái Runtime vào bộ nhớ RAM (`StreamManager`).

Thêm vào đó, tôi cũng phải tự thân sửa các lỗi Closure của Javascript phía Client (UI). Các hàm sinh bởi AI thường "bắt" (capture) lấy đối tượng `camera` tại thời điểm tạo ra nút bấm, dẫn đến việc khi dữ liệu camera thay đổi, nút bấm không chịu phản hồi do đang tham chiếu đến đối tượng cũ (Stale closure). Tôi đã khắc phục lỗi này bằng cách buộc nút bấm phải duyệt lại mảng `cameras` mỗi lần nhấp chuột.

**3. Thiếu sót và sai lệch của AI (Shortcomings & Hallucinations)**

Điểm yếu lớn nhất của AI bộc lộ khi đối mặt với các kiến trúc cấp hệ thống (System Architecture) đòi hỏi tư duy vận hành thực tế. Ban đầu, khi được yêu cầu "Bắt luồng RTSP và hiển thị lên Web", AI liên tục đưa ra giải pháp dùng thư viện OpenCV (`cv2.VideoCapture`) chạy bên trong FastAPI để đọc từng Frame video, sau đó yield ra ảnh MJPEG. Phương pháp này hoàn toàn sai lệch với yêu cầu mở rộng (Scale) vì nó ngốn 100% CPU chỉ với 3-4 luồng video. Tôi đã phải gạt bỏ hoàn toàn hướng tiếp cận của AI và yêu cầu đổi sang sử dụng MediaMTX đóng vai trò Media Server riêng biệt để xử lý HLS streaming, giúp backend giải phóng hoàn toàn gánh nặng giải mã video.

**Tổng kết:** AI là một "người thợ xây" xuất sắc giúp tự động hóa mã lặp lại, nhưng để hệ thống đạt được hiệu năng và có thể vận hành trơn tru ở quy mô thực tế, tư duy thiết kế kiến trúc và khả năng rà soát (Review) của một Kỹ sư Backend là yếu tố không thể thay thế.
