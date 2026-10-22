# AI BINANCE TRADING COMPANY

Ứng dụng giao dịch tự động 100% trên **Binance Spot** chạy trên máy tính Windows, tích hợp mô hình **Công ty Giao dịch Đa tác nhân (Multi-Agent AI)** qua một API Gateway duy nhất kết nối hai mô hình AI kiểm tra chéo lẫn nhau:
- **Gemini Flash (High Reasoning)**: Chief Market Analyst / Strategy Generator.
- **GPT-6 Luna**: Chief Risk Reviewer / Independent Analyst có quyền phủ quyết (Veto).

Hệ thống có **Risk Engine độc lập** bằng Python thuần, mặc định **Paper Trading**, hỗ trợ **Binance Testnet**, và cơ chế bảo vệ tối đa với **LIVE SPOT LOCKED** và nút **Emergency Stop**.

---

## 1. YÊU CẦU HỆ THỐNG TRÊN WINDOWS
- Hệ điều hành: Windows 10 hoặc Windows 11 (64-bit).
- Python: 3.12+ (đã kiểm thử tương thích hoàn toàn với Python 3.14).
- Node.js: v18+ và npm (dành cho việc biên dịch frontend).

---

## 2. HƯỚNG DẪN CÀI ĐẶT NHANH (MỘT CHẠM)

Mở **PowerShell** tại thư mục dự án và chạy:

```powershell
# 1. Chạy kịch bản cài đặt tự động
.\scripts\setup_windows.ps1
```

Kịch bản sẽ tự động:
1. Tạo môi trường ảo Python `.venv`.
2. Cài đặt toàn bộ thư viện backend (`fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `greenlet`, `httpx`, `apscheduler`, `cryptography`, `pytest`,...).
3. Cài đặt các gói npm và biên dịch mã nguồn frontend React + Vite + Tailwind CSS vào thư mục `frontend/dist`.
4. Tạo file cấu hình môi trường `.env` từ `.env.example`.

---

## 3. KHỞI CHẠY ỨNG DỤNG

Sau khi cài đặt xong, bạn chỉ cần chạy:

```powershell
.\scripts\start_app.ps1
```

- Máy chủ Backend FastAPI sẽ khởi động tại: `http://127.0.0.1:8000`.
- Giao diện Dashboard Bloomberg Terminal Dark Mode tiếng Việt sẽ tự động được mở trên trình duyệt.

*(Nếu muốn chạy frontend ở chế độ Hot-Reload phục vụ phát triển, bạn có thể mở thêm một terminal: `cd frontend; npm run dev`)*.

---

## 4. CHẠY CÁC BÀI KIỂM THỬ TỰ ĐỘNG (18 KỊCH BẢN BẮT BUỘC)

Để chạy bộ kiểm thử 23 bài test tự động bao quát toàn bộ 18 kịch bản lỗi và biên an toàn, chạy lệnh:

```powershell
.\scripts\run_tests.ps1
```

### 18 Kịch bản đã được kiểm tra:
1. **API Key Binance không hợp lệ**: Chặn gửi lệnh khi thiếu chữ ký bảo mật.
2. **Một mô hình AI lỗi**: Chuyển trạng thái an toàn, không mở vị thế.
3. **Hai mô hình AI bất đồng**: Gemini đề xuất BUY nhưng GPT-6 Luna REJECT -> Tự động đưa về HOLD.
4. **JSON AI không đúng cấu trúc**: Trích xuất linh hoạt từ markdown code fences, bắt lỗi JSON hỏng.
5. **Thiếu / trễ dữ liệu nến**: Từ chối dữ liệu nến cũ (stale candles) trên 2 chu kỳ.
6. **Số dư nhỏ hơn lệnh tối thiểu (Small Balance Mode)**: Kiểm tra `MIN_NOTIONAL` và `minQty` của sàn Binance bằng `Decimal`.
7. **Không đủ số dư USDT khả dụng**: Ngăn chặn lệnh vượt số dư thực tế.
8. **Vượt giới hạn rủi ro**:
   - Chặn khi chạm giới hạn lỗ ngày (2%).
   - Chặn khi chạm giới hạn Drawdown đỉnh (5%).
   - Chặn khi vượt quá 2 vị thế đồng thời.
   - Chặn nhồi lệnh lỗ (Anti-Martingale).
   - Bắt buộc thời gian nghỉ Cooldown 20 phút sau khi đóng lệnh.
9. **Lệnh khớp một phần**: Đối soát trạng thái `PARTIALLY_FILLED` và cập nhật khối lượng thực khớp.
10. **Timeout khi đặt lệnh**: Không đặt lệnh mới bừa bãi; tra cứu bằng `clientOrderId` để xác minh trạng thái trên sàn.
11. **Restart khi có lệnh chưa xác định**: Tự động reconciliation đối soát với Binance ngay khi khởi động lại.
12. **WebSocket mất kết nối**: Bộ quản lý kết nối tự động loại bỏ socket chết mà không ảnh hưởng tới luồng khác.
13. **Binance trả về rate limit (429/418)**: Tự động backoff theo tiêu đề `Retry-After`.
14. **AI cố yêu cầu tắt Risk Engine**: Tách biệt hoàn toàn quyết định AI với mã nguồn Python của Risk Engine.
15. **Prompt Injection trong dữ liệu bên ngoài**: Module `sanitizer.py` lọc và vô hiệu hóa các câu lệnh override hệ thống.
16. **Người dùng chưa mở khóa LIVE**: Lệnh LIVE mặc định bị từ chối nếu chưa mở khóa thủ công.
17. **Emergency Stop đang bật**: Phong tỏa tức thì mọi tác vụ tạo lệnh mới.
18. **Mất kết nối trong lúc đang có vị thế**: Position Manager nội bộ tiếp tục giám sát theo giá thị trường để kích hoạt Stop Loss / Take Profit.

---

## 5. HƯỚNG DẪN VẬN HÀNH DASHBOARD

### A. Trang Tổng Quan (Overview)
- Hiển thị số dư Spot thực tế đọc từ Binance (USDT khả dụng và các đồng coin khác).
- Vốn cấp cho bot (mặc định 100 USDT, chỉ giao dịch trong hạn mức này).
- PnL thực nhận, PnL chưa thực nhận, Win Rate, tổng số lệnh.
- Danh sách các vị thế đang mở và nút **Đóng lệnh thủ công** khi cần.

### B. Trang Giao Dịch Trực Tiếp (Trading)
- Biểu đồ nến TradingView / Lightweight Charts với khung thời gian 5m, 15m, 1h, 4h.
- Thống kê thị trường theo thời gian thực: Spread, Giá Bid/Ask tốt nhất, Biên độ 24h.
- Bảng chỉ báo kỹ thuật thời gian thực từ Quant Engine (EMA 9/21/50/200, RSI 14, MACD, Bollinger Bands, ATR, ADX, Volume Ratio).

### C. Trang Hội Đồng AI (AIPipelinePage)
- Trực quan hóa quy trình 6 bước: `Market Data -> Quant Engine -> Gemini -> GPT-6 Luna -> Risk Engine -> Execution`.
- Xem cuộc tranh luận và phản biện chi tiết bằng Tiếng Việt giữa Gemini Analyst và GPT-6 Luna Reviewer.
- Nút **Phân tích ngay** để kích hoạt chu kỳ đánh giá theo yêu cầu.

### D. Trang Quản Trị Rủi Ro (Risk Control)
- Đồng hồ đo Drawdown thời gian thực so với mức trần 5%.
- Đồng hồ đo mức lỗ trong ngày so với mức trần 2%.
- Biểu mẫu siết chặt các tham số quản trị rủi ro (người dùng có thể giảm rủi ro, nhưng hệ thống chặn việc nới lỏng vượt mức an toàn).
- Nhật ký thẩm định của Risk Engine ghi lại lý do PASS hoặc REJECT từng lệnh.

### E. Trang Kiểm Thử (Backtest)
- Chạy thử nghiệm 5 chiến lược giao dịch plugin:
  1. *Trend Following* (Theo xu hướng EMA + ADX).
  2. *EMA Crossover* (Giao cắt vàng EMA 9/21 trên EMA 50).
  3. *RSI Mean Reversion* (Hồi quy trung bình quá bán trong thị trường đi ngang).
  4. *MACD Momentum* (Xung lượng MACD kết hợp bùng nổ khối lượng).
  5. *Multi-timeframe Confirmation* (Đồng thuận đa khung thời gian).
- Báo cáo chi tiết: Lợi nhuận ròng, Max Drawdown, Win Rate, Profit Factor, Sharpe Ratio, Tổng phí sàn.

### F. Trang Cài Đặt (Settings)
- Nhập `AI_BASE_URL` và `AI_API_KEY` (Chỉ cần 1 Gateway để chạy cả hai model).
- Nút **Kiểm tra kết nối AI** đo độ trễ và kiểm tra structured JSON output của cả hai mô hình.
- Nhập API Key/Secret của Binance Live và Binance Testnet.
- Nút **Kiểm tra kết nối Binance** xác minh độ lệch thời gian máy chủ.

---

## 6. QUY TRÌNH MỞ KHÓA LIVE SPOT

Chế độ LIVE SPOT mặc định luôn ở trạng thái **KHÓA (LOCKED)** khi khởi động ứng dụng:
1. Vào thanh điều hướng, nhấn vào nút **LIVE SPOT** (đang có biểu tượng ổ khóa màu vàng).
2. Hộp thoại xác thực an toàn sẽ xuất hiện.
3. Nhập số vốn Spot muốn phân bổ cho bot (ví dụ: `50` hoặc `100` USDT).
4. Nhập chính xác cụm từ bảo mật: `ENABLE LIVE SPOT`.
5. Nhấn **Xác nhận mở khóa LIVE**.
6. Khi khởi động lại ứng dụng hoặc khi nhấn Emergency Stop, chế độ LIVE SPOT sẽ tự động khóa lại.

---

## 7. NÚT DỪNG KHẨN CẤP (EMERGENCY STOP)
Nút **EMERGENCY STOP** màu đỏ nổi bật luôn hiển thị ở góc trên bên phải màn hình:
- Khi nhấn: Hệ thống lập tức phong tỏa việc tạo lệnh mới, dừng mọi luồng AI đang chờ, và đặt cờ khóa an toàn bền vững vào cơ sở dữ liệu.
- Hệ thống **không tự ý bán tháo hoảng loạn** tài sản Spot hiện có; người dùng có thể chủ động bấm đóng từng vị thế trên bảng điều khiển sau khi xem xét kỹ lưỡng.
- Để tiếp tục vận hành sau khi kiểm tra xong, nhấn **Mở khóa khẩn cấp**.
