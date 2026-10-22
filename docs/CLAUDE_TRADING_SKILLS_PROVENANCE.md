# Provenance & Audit: Claude Trading Skills Integration

## 1. Nguồn Gốc và Phiên Bản
- **Repository Nguồn:** [https://github.com/agiprolabs/claude-trading-skills](https://github.com/agiprolabs/claude-trading-skills)
- **Commit Hash:** `981e1d736cdc02bdc1c55c74ec9224e956414706`
- **Tác Giả:** Jonathan Owens / AGIPro
- **Giấy Phép:** MIT License
- **Đường Dẫn Lưu Bản Gốc:** `external/claude-trading-skills/`
- **Đường Dẫn Cài Đặt Agent Skills:** `.agents/skills/`
- **Ngày Tích Hợp:** 22/10/2026

## 2. Kiểm Tra An Toàn & Bảo Mật (Security Audit)
1. **Cô Lập Môi Trường Thực Thi:**
   - Các file script trong kho `external/` và `.agents/skills/` được lưu giữ dạng tài liệu tham khảo (knowledge base) và công thức toán học.
   - Không cho phép hệ thống tự động chạy bất kỳ script bên ngoài nào trực tiếp bằng shell hoặc eval.
   - Các logic định lượng được tuyển chọn và chuyển thể (ported) sang mã nguồn Python nội bộ an toàn trong `backend/app/skills/` và `backend/app/trading/`.
2. **Loại Trừ Các Chức Năng Không Thuộc Binance Spot:**
   - Loại trừ hoàn toàn các skill DEX, Raydium, PumpFun, Solana RPC, Solana Transaction Building, Jito Bundles, Futures, Margin, Leverage khỏi luồng thực thi lệnh của sàn Binance Spot.
   - Không chứa bất kỳ hàm nào yêu cầu cấp Binance API Secret ra bên ngoài hoặc đưa vào prompt của AI.

## 3. Danh Sách 25 Kỹ Năng Đã Cài Đặt Vào `.agents/skills/`
1. `ohlcv-processing`: Chuẩn hóa nến, resample, phát hiện thiếu dữ liệu, tính toán khối lượng
2. `pandas-ta`: Thư viện tính toán chỉ báo kỹ thuật mở rộng
3. `ta-lib`: Các mẫu hình nến và chỉ báo định lượng
4. `custom-indicators`: Chỉ báo tùy biến (VWAP, Choppiness Index, Supertrend, Keltner)
5. `regime-detection`: Phân loại trạng thái thị trường 4 góc phần tư (Trending vs Ranging / High Vol vs Low Vol)
6. `volatility-modeling`: Ước lượng biến động Parkinson, Garman-Klass, Yang-Zhang, ATR percentile
7. `mean-reversion`: Chiến lược giao dịch hồi quy về giá trị trung bình, Bollinger Bands %B, Z-score
8. `correlation-analysis`: Phân tích ma trận tương quan giữa các cặp giao dịch Spot
9. `position-sizing`: Định cỡ vị thế theo biến động (Volatility parity, ATR sizing, Fixed Fractional)
10. `risk-management`: Quản trị rủi ro đa tầng, Value-at-Risk (VaR), Conditional VaR, Max Drawdown
11. `portfolio-analytics`: Đo lường hiệu quả danh mục, tỷ số Sharpe, Sortino, Calmar, Profit Factor
12. `slippage-modeling`: Mô hình hóa độ trượt giá dựa trên độ sâu order book Binance Spot
13. `exit-strategies`: Chiến lược chốt lời, trailing stop ATR, time-based exits
14. `strategy-framework`: Khung chuẩn hóa tín hiệu chiến lược giao dịch
15. `vectorbt`: Khung backtest tốc độ cao bằng vectorization
16. `backtrader`: Khung mô phỏng chiến lược dựa trên sự kiện
17. `walk-forward-validation`: Kiểm định tối ưu hóa tránh overfitting theo phương pháp Walk-Forward
18. `feature-engineering`: Trích xuất đặc trưng định lượng từ dữ liệu nến và khối lượng
19. `signal-classification`: Phân loại và chấm điểm chất lượng tín hiệu giao dịch
20. `trade-journal`: Ghi chép nhật ký phân tích, quyết định và kết quả giao dịch
21. `trading-visualization`: Biểu đồ hóa hiệu suất và phân tích kỹ thuật
22. `market-microstructure`: Phân tích vi cấu trúc thị trường, Order Book Imbalance, bid-ask spread
23. `liquidity-analysis`: Đánh giá thanh khoản thực tế trên cặp Spot
24. `kelly-criterion`: Định cỡ vốn tối ưu theo tiêu chuẩn Kelly phân số (Fractional Kelly)
25. `cointegration-analysis`: Kiểm định đồng tích hợp Engle-Granger cho các cặp giao dịch

## 4. Quản Lý Phiên Bản & Bản Quyền
Mọi file gốc trong `external/claude-trading-skills/` được giữ nguyên vẹn bản quyền MIT của tác giả AGIPro.
Mọi bản chuyển thể Python nội bộ tuân thủ nguyên tắc an toàn, không sao chép nguyên trạng mà chuyển thành các hàm định lượng tính toán trực tiếp với thư viện chuẩn (math, statistics, typing, numpy/pandas nếu có).
