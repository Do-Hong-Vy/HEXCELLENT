# TÀI LIỆU TOÀN VĂN: HƯỚNG DẪN TRÌNH BÀY & BỘ CÂU HỎI ĐÁP PHẢN BIỆN VÒNG SƠ KHẢO
## FESTIVAL CHUYỂN ĐỔI SỐ 2026 (CRYSTARA) · BẢNG A · CASE 1
**Dự án:** PolicyAssist AI – CHRONOS-LEDGER  
**Đơn vị thực hiện:** Đội HEXCELLENT  

> **Cập nhật 12/11/2026 (dùng cho Vòng 3):** mọi số liệu trong tài liệu này lấy từ lần chạy `RUN-20261112-020732-826e17` (mã nguồn sha256 `826e17d8d910`); chi tiết ở `README.md` mục 1 và thư mục `outputs/`. Số liệu bản Vòng sơ khảo đã cũ, không dùng để trả lời. Chức năng nào đã chạy được, chức năng nào còn là định hướng: xem tài liệu sản phẩm, mục 4 và mục 9.

---

## MỤC LỤC
1. [Phần 1: Trả lời 10 nội dung cốt lõi của giải pháp (Mục 3)](#phần-1-trả-lời-10-nội-dung-cốt-lõi-của-giải-pháp)
2. [Phần 2: Nâng cấp hạng Đồng – Bạc – Vàng và minh chứng lợi ích (Mục 4)](#phần-2-nâng-cấp-hạng-đồng--bạc--vàng-và-minh-chứng-lợi-ích)
3. [Phần 3: Bộ câu hỏi và đáp án phản biện chuyên sâu của Ban Giám khảo (Mục 6)](#phần-3-bộ-câu-hỏi-và-đáp-án-phản-biện-chuyên-sâu-của-ban-giám-khảo)
4. [Phần 4: Chi tiết cách tính và công thức 7 chỉ số đánh giá cốt lõi (Key Performance Indicators – KPI)](#phần-4-chi-tiết-cách-tính-và-công-thức-7-chỉ-số-đánh-giá-cốt-lõi-key-performance-indicators--kpi)
5. [Phần 5: Bảng đối chiếu số liệu thực tế và cẩm nang đối đáp nhanh 15–20 giây](#phần-5-bảng-đối-chiếu-số-liệu-thực-tế-và-cẩm-nang-đối-đáp-nhanh-1520-giây)

---

# PHẦN 1: TRẢ LỜI 10 NỘI DUNG CỐT LÕI CỦA GIẢI PHÁP

### 1. Đội đang giải quyết vấn đề gì?
**Trả lời:**  
Đội giải quyết bài toán tra cứu chính sách tài chính, kế toán và thuế nội bộ kết hợp với pháp luật nhà nước nhưng **loại bỏ hoàn toàn 3 rủi ro nghiêm trọng của Trí tuệ nhân tạo (Artificial Intelligence – AI)**:
1. Trả lời sai do văn bản pháp luật đã hết hiệu lực tại thời điểm tra cứu (bẫy phiên bản thời gian).
2. Trộn lẫn thứ bậc thẩm quyền giữa Luật hiện hành và Quy trình nội bộ của doanh nghiệp.
3. Ảo giác (Hallucination) của mô hình trí tuệ nhân tạo (tự bịa đặt câu trả lời hoặc trích dẫn các điều khoản không có thật khi thiếu dữ liệu).

### 2. Người sử dụng hoặc đối tượng hưởng lợi là ai?
**Trả lời:**  
- **Đối tượng trực tiếp:** Chuyên viên kế toán, tài chính, kiểm soát nội bộ và người phê duyệt thanh toán chi tiêu tại doanh nghiệp (mô phỏng tại Nova Việt) cần tra cứu nhanh điều kiện thanh toán, xử lý hóa đơn, hạn mức phê duyệt theo đúng mốc thời gian phát sinh giao dịch.
- **Đối tượng gián tiếp:** Ban Pháp chế và Ban Giám đốc doanh nghiệp có được một hệ thống tra cứu minh bạch, lưu lại toàn bộ nhật ký kiểm toán (Audit Trail) phục vụ công tác giải trình thuế và thanh kiểm tra.

### 3. Dữ liệu đầu vào là gì?
**Trả lời:**  
- **Kho dữ liệu gốc:** Giữ nguyên bản 100% gói dữ liệu (Data Pack) do Ban Tổ chức cung cấp (chụp tại ngày 17/10/2026, được kiểm chứng toàn vẹn bằng thuật toán băm an toàn 256-bit: Secure Hash Algorithm 256-bit – SHA-256), gồm **20 tài liệu** (12 văn bản pháp luật: LAW01–LAW12 và 8 tài liệu nội bộ giả lập: SIM01–SIM08 của Công ty Cổ phần Nova Việt), tương ứng với **374 đoạn văn bản chuẩn hóa** (Chunks) và bảng ánh xạ nguồn trích dẫn (Citation Map).
- **Đầu vào của mỗi lượt hỏi:** Câu hỏi tự nhiên của người dùng (hỗ trợ cả trường hợp viết tắt, ngôn ngữ khẩu ngữ, gõ không dấu) kèm theo **ngày tham chiếu áp dụng** (Reference Date).

### 4. Giải pháp xử lý dữ liệu như thế nào?
**Trả lời:**  
Hệ thống xử lý qua quy trình 9 bước hoàn toàn tất định (Deterministic Pipeline từ Bước 0 đến Bước 8):
- **Bước 0 (Bảo vệ – Guardrail):** Chặn các câu hỏi đòi hỏi dữ liệu vận hành thực tế của doanh nghiệp giả lập, câu hỏi ngoài phạm vi dữ liệu (Out of Scope – OOS) hoặc câu lệnh cố tình tấn công hệ thống (Prompt Injection).
- **Bước 1 (Lập kế hoạch truy vấn – Query Planning):** Chuẩn hóa từ viết tắt như Hóa đơn điện tử (E-Invoice), Mã số thuế (Tax Identification Number – TIN), Nguyên tắc phân tách trách nhiệm (Segregation of Duties – SoD); khôi phục dấu tiếng Việt; phân tách mốc thời gian áp dụng và mã trạng thái.
- **Bước 2 (Truy hồi lai – Hybrid Retrieval):** Kết hợp thuật toán tìm kiếm theo âm tiết (Best Matching 25 – BM25) và tần suất ký tự 2–5 gram (Term Frequency–Inverse Document Frequency – TF-IDF) để bắt trọn các biến thể từ ngữ.
- **Bước 3 (Giải quyết phiên bản CHRONOS):** Tính toán hiệu lực tại từng đoạn văn bản theo đồ thị thay thế của các văn bản pháp luật, tự động chuyển hướng sang điều khoản kế nhiệm tương ứng.
- **Bước 4 (Tái xếp hạng theo thẩm quyền – Authority-aware Reranking):** Ưu tiên Văn bản Pháp luật còn hiệu lực cao hơn Quy chế và Quy trình, Quy trình cao hơn Sổ tay và Hỏi đáp thường gặp (Frequently Asked Questions – FAQ); tự động truy về điều khoản gốc nhờ cơ chế phản hồi tương quan giả định (Pseudo-Relevance Feedback – PRF).
- **Bước 5 (Sổ cái bằng chứng và 7 cổng kiểm tra – Evidence Ledger & Gates):** Kiểm tra điều kiện đủ căn cứ, độ bao phủ từ khóa và tính liên quan trực tiếp đến câu hỏi.
- **Bước 6 (Soạn thảo câu trả lời trích xuất – Grounded Composition):** Trích xuất nguyên văn có cấu trúc (luôn đưa kết luận Có hoặc Không lên trước, căn cứ theo sau), không sử dụng mô hình sinh tự do để ngăn chặn hoàn toàn hiện tượng ảo giác.
- **Bước 7 (Kiểm toán nguồn trích dẫn – Citation Audit):** Kiểm tra lại nguồn trích dẫn qua 4 điều kiện khắt khe trước khi xuất câu trả lời.
- **Bước 8 (Hiệu chuẩn độ tin cậy – Calibrated Confidence):** Đánh giá độ tin cậy thực tế bằng mô hình hồi quy Logistic đã được hiệu chuẩn để đưa ra quyết định trả lời (Answer), từ chối trả lời (Abstain) hoặc gắn cờ cần chuyên viên rà soát.

### 5. Đầu ra của hệ thống là gì?
**Trả lời:**  
- **Tệp nộp bài cho Ban Tổ chức (`submission.csv`):** Đúng hoàn toàn định dạng 8 cột theo mẫu (Schema), vượt qua **23 bài kiểm tra độc lập** và không phát sinh bất kỳ lỗi nào (0 lỗi).
- **Giao diện người dùng (User Interface – UI):** Câu trả lời trực diện, khối căn cứ pháp luật và quy trình nội bộ tách biệt rõ ràng, các nút bấm trích dẫn cho phép mở trực tiếp đoạn văn bản gốc và toàn văn tài liệu, cảnh báo phiên bản khi áp dụng văn bản lịch sử và nhật ký kiểm toán ghi lại từng lượt hỏi có mã truy vết (Trace ID) riêng biệt.

### 6. Điểm khác biệt hoặc giá trị nổi bật của giải pháp là gì?
**Trả lời:**  
Giải pháp có 3 điểm nổi bật cốt lõi:
1. **Giải quyết triệt để bài toán hiệu lực theo thời gian bằng cơ chế CHRONOS:** Không sử dụng biện pháp lọc cứng làm mất ngữ cảnh của các văn bản cũ, mà tự động chuyển hướng điều khoản tương ứng giữa các thế hệ thông tư thay thế nhau.
2. **Kiểm toán nguồn trích dẫn khép kín (Citation Audit):** 100% citation qua kiểm toán 4 điều kiện; độ chính xác nguồn trích dẫn **0,894** trên 26 câu có đáp án của Ban Tổ chức (26/26 câu có nguồn đầu tiên trùng đáp án mẫu) và tỷ lệ câu trả lời không có căn cứ bằng **0,000**.
3. **Hoạt động hoàn toàn nội bộ và tốc độ siêu nhanh:** Không phụ thuộc vào đường truyền mạng hay dịch vụ bên ngoài, thời gian xử lý khoảng **18 mili-giây** cho 1 câu hỏi (chưa tới 0,3% mức trần 10 giây của Ban Tổ chức).

### 7. Chỉ số nào được sử dụng để đánh giá?
**Trả lời:**  
Đội đo lường bằng bộ 7 chỉ số hiệu quả cốt lõi (Key Performance Indicators – KPI) theo đề thi:
1. Độ bao phủ trong 5 kết quả đầu tiên (Retrieval Recall at 5 – Recall@5).
2. Độ chính xác câu trả lời và độ bao phủ ý chính (Answer Accuracy / Correctness).
3. Độ chính xác của nguồn trích dẫn (Citation Accuracy).
4. Tỷ lệ câu trả lời không có căn cứ (Unsupported Answer Rate).
5. Chất lượng từ chối trả lời (Điểm số điều hòa F1 của việc từ chối: F1-Score).
6. Độ chính xác xác định phiên bản hiệu lực theo thời gian (Versioning Accuracy).
7. Thời gian xử lý trung bình và phân vị thứ 95 (Latency trung bình & p95).
*(Kèm theo chỉ số phụ: Thứ tự ưu tiên nguồn cho câu hỏi kết hợp cả pháp luật và quy trình nội bộ: Source Priority).*

### 8. Kết quả hoặc minh chứng hiện có là gì?
**Trả lời:**  
- **Trên tập dữ liệu phát triển 30 câu có đáp án chuẩn của Ban Tổ chức (Development Set – Dev-30):**
  - Recall tại 5: đạt **0,936** (vượt mục tiêu ≥ 0,80 của đề thi).
  - Độ phủ ý chính (Answer Accuracy): đạt **0,867** (thang 0 / 0,5 / 1 tự động: 0,923).
  - Độ chính xác nguồn trích dẫn: đạt **0,894** (23,25/26); 26/26 câu có nguồn đầu tiên trùng đáp án của Ban Tổ chức. Điểm chưa đạt 1,000 vì một số câu dẫn thêm sổ tay/FAQ ngoài đáp án để trả lời đủ tình huống (vd. Q042 dẫn thêm FAQ04 để trả lời thẳng "Không").
  - Tỷ lệ câu trả lời không có căn cứ: bằng **0,000**.
  - Điểm F1 từ chối trả lời: đạt **1,000 tuyệt đối** (từ chối chuẩn xác 4/4 câu ngoài phạm vi).
  - Độ chính xác phiên bản: đạt **1,000 tuyệt đối** (4/4 câu).
  - Thời gian xử lý trung bình: là **18,5 mili-giây/câu** (phân vị thứ 95 đạt 49,6 mili-giây).
- **Trên tập công khai 90 câu (Public Set – Public-90):** Đưa ra quyết định đúng toàn bộ 90/90 câu, từ chối chính xác 14/14 câu ngoài phạm vi (từ câu Q077 đến câu Q090); Recall@5 **0,917**, độ phủ ý chính **0,824**, độ chính xác nguồn trích dẫn **0,931**.
- **Trên tập câu khó do đội viết (Stress-60):** quyết định đúng 60/60; Recall@5 **0,742** (chưa đạt mục tiêu 0,80 – giới hạn chính hiện nay), độ chính xác nguồn trích dẫn 0,848.
- **Kiểm định thống kê so sánh với hệ thống cơ sở BM25 (Baseline – B0):** Kiểm định McNemar cho thấy độ vượt trội có ý nghĩa thống kê rất cao (xác suất sai số chỉ là p = 0,000122).

### 9. Kế hoạch triển khai sản phẩm khả dụng tối thiểu (Minimum Viable Product – MVP) trong 2 – 3 tuần như thế nào?
**Trả lời:**  
Bản hiện tại đã chạy được trọn luồng hỏi đáp, xuất bài nộp và đánh giá trên Data Pack. Các bước dưới đây là **định hướng** để đưa vào môi trường doanh nghiệp, **chưa có trong mã nguồn nộp**:
- **Tuần 1:** Đóng gói ứng dụng vào môi trường độc lập (Docker container), tích hợp cơ chế đăng nhập một lần (Single Sign-On – SSO) của doanh nghiệp và mở cổng giao diện lập trình ứng dụng đại diện truyền tải trạng thái (Representational State Transfer API – RESTful API).
- **Tuần 2:** Kết nối dữ liệu vào kho lưu trữ tài liệu nội bộ và phần mềm hoạch định nguồn lực doanh nghiệp (Enterprise Resource Planning – ERP); thiết lập phân quyền người dùng theo nguyên tắc phân tách trách nhiệm (Segregation of Duties – SoD).
- **Tuần 3:** Thử nghiệm thực tế với khoảng 20 chuyên viên kế toán và kiểm soát nội bộ; ghi nhận ý kiến phản hồi trực tiếp trên giao diện để bổ sung từ điển nghiệp vụ chuyên ngành qua vòng lặp phản hồi (Feedback Loop).

### 10. Những rủi ro, giới hạn và phương án kiểm soát chính là gì?
**Trả lời:**  
- **Rủi ro 1: Người dùng lầm tưởng hệ thống là công cụ tư vấn pháp lý chính thức.**  
  *Phương án kiểm soát:* Luôn gắn lời miễn trừ trách nhiệm ở chân mọi câu trả lời và cung cấp nút mở xem toàn văn văn bản gốc để chuyên viên tự đối chiếu.
- **Rủi ro 2: Dữ liệu văn bản pháp luật trong gói dữ liệu chỉ là bản tóm tắt chuẩn hóa (Normalized Summary).**  
  *Phương án kiểm soát:* Hệ thống tự động phát hiện và ghi rõ thông báo cảnh báo khi câu trả lời trích xuất từ bản tóm tắt chuẩn hóa.
- **Rủi ro 3: Câu hỏi sử dụng từ ngữ khẩu ngữ hoặc diễn đạt quá xa lạ.**  
  *Phương án kiểm soát:* Cổng kiểm tra số 7 tự động phát hiện câu hỏi chỉ khớp chủ đề mà không khớp nội dung cụ thể; những câu có độ tin cậy thấp (< 0,60) sẽ được chuyển sang trạng thái từ chối hoặc gắn cờ cần chuyên viên rà soát (Human-in-the-loop) thay vì trả lời bừa bãi.

---

# PHẦN 2: NÂNG CẤP HẠNG ĐỒNG – BẠC – VÀNG VÀ MINH CHỨNG LỢI ÍCH

### 1. Đáp ứng trọn vẹn yêu cầu hạng Đồng (Bronze)
- **Giải pháp nền tảng:** Xây dựng hệ thống hỏi đáp hoàn chỉnh trên gói dữ liệu do Ban Tổ chức cung cấp; hiển thị nguồn dẫn chứng; trả lời có trích dẫn; biết cảnh báo và từ chối khi không đủ căn cứ; có phương pháp đo lường định lượng bằng 7 chỉ số cốt lõi (KPI).
- **Minh chứng:** Tệp nộp bài đạt chuẩn 100% định dạng của Ban Tổ chức và vượt qua toàn bộ 23/23 bài kiểm tra tự động độc lập (0 lỗi).

### 2. Cải tiến vượt trội ở hạng Bạc (Silver)
Theo đúng nguyên tắc: **Cải tiến là gì → Vì sao cần cải tiến → Minh chứng mang lại lợi ích gì**.
1. **Truy hồi lai (BM25 + TF-IDF n-gram) kết hợp chuẩn hóa câu hỏi:**
   - *Vì sao cần:* Người dùng thường xuyên viết tắt (HĐĐT, MST), gõ không dấu hoặc dùng thuật ngữ tiếng Anh trong nghiệp vụ kế toán (Payment Request, SoD).
   - *Minh chứng:* Tăng Recall tại 5 từ 0,610 lên **0,725** (tăng thêm +11,5% so với hệ thống cơ sở B0).
2. **Cơ chế xử lý phiên bản theo dòng thời gian CHRONOS:**
   - *Vì sao cần:* Văn bản thuế thay đổi liên tục, cách lọc cứng theo ngày sẽ làm mất các văn bản cũ khi người dùng hỏi so sánh các thời kỳ.
   - *Minh chứng:* Nâng độ chính xác phiên bản từ 0,40 lên **0,90** (phương pháp lọc cứng theo ngày chỉ đạt 0,60).
3. **Tái xếp hạng theo thẩm quyền và truy tìm nguồn gốc:**
   - *Vì sao cần:* Tránh việc hệ thống trích dẫn sổ tay hoặc câu hỏi thường gặp (FAQ) thay vì dẫn điều khoản luật chính thức.
   - *Minh chứng:* Đưa độ chính xác nguồn trích dẫn từ 0,800 lên **0,956** (+0,156) và đưa độ chính xác phiên bản đạt **1,00** (ablation trên Public-90).
4. **Hiệu chuẩn độ tin cậy:**
   - *Vì sao cần:* Cung cấp con số tin cậy thực chất để phân luồng câu hỏi thay vì những con số ước lượng ngẫu nhiên.
   - *Minh chứng:* Sai số hiệu chuẩn kỳ vọng (Expected Calibration Error – ECE) giảm từ 0,432 (baseline B0) xuống **0,062**.

### 3. Đóng góp thực tế ở hạng Vàng (Gold)
1. **Kiểm toán nguồn trích dẫn khép kín (Citation Audit):** Kiểm tra tính hợp lệ của nguồn qua 4 điều kiện trước khi trả lời, đưa tỷ lệ câu trả lời không có căn cứ về mức **0,000 tuyệt đối**.
2. **Hệ thống bảo vệ đa tầng (Multi-layer Guardrails):** Đưa điểm F1 của việc từ chối trả lời đạt **1,000 tuyệt đối**, chặn đứng toàn bộ các câu hỏi đòi thông tin bí mật kinh doanh hoặc câu lệnh tấn công hệ thống (Prompt Injection).
3. **Xử lý câu hỏi kết hợp đa nguồn (Multi-document Synthesis):** Tách bạch rõ ràng giữa Căn cứ Pháp luật và Quy trình Nội bộ, dẫn chứng chính xác đồng thời cả luật và quy chế như câu hỏi số Q042 trong đề thi (dẫn chuẩn xác cả Thông tư 91/2026 và Quy trình SIM02).
4. **Khả năng kiểm toán và có con người tham gia giám sát (Human-in-the-loop):** Mỗi câu hỏi đều sinh ra một dòng nhật ký kiểm toán có mã truy vết (Trace ID) riêng, tự động che giấu thông tin nhận dạng cá nhân (Personally Identifiable Information – PII: email, số điện thoại, tài khoản ngân hàng) và gắn cờ những câu có độ tin cậy < 0,60 để chuyên viên rà soát.

---

# PHẦN 3: BỘ CÂU HỎI VÀ ĐÁP ÁN PHẢN BIỆN CHUYÊN SÂU CỦA BAN GIÁM KHẢO

### 1. Về logic và tính đúng đắn của giải pháp:
**Ban Giám khảo hỏi:** *"Tại sao đội không dùng mô hình ngôn ngữ lớn (Large Language Model – LLM) để câu trả lời sinh ra được trôi chảy, tự nhiên hơn mà lại dùng phương pháp trích xuất nguyên văn?"*
> **Bạn trả lời:**  
> *"Dạ thưa Ban Giám khảo, trong lĩnh vực kế toán, tài chính và thuế, tính chính xác và khả năng chịu trách nhiệm pháp lý là ưu tiên số 1, văn phong trôi chảy chỉ là yếu tố thứ yếu. Nếu dùng mô hình sinh tự do, hệ thống chắc chắn tiềm ẩn nguy cơ ảo giác (Hallucination) và tự ý sửa đổi câu chữ của điều luật. Phương pháp trích xuất nguyên văn có kiểm toán của đội bảo đảm 100% thông tin đều có căn cứ chuẩn xác trong tài liệu, loại bỏ hoàn toàn rủi ro bịa đặt, đồng thời giúp hệ thống hoạt động hoàn toàn nội bộ với tốc độ khoảng 18 mili-giây mỗi câu."*

### 2. Về cách tính chỉ số đánh giá:
**Ban Giám khảo hỏi:** *"Tại sao độ chính xác câu trả lời trên tập mở rộng 60 câu (Ext-60 đạt 0,801) lại thấp hơn tập 30 câu có đáp án của Ban Tổ chức (Dev-30 đạt 0,867)?"*
> **Bạn trả lời:**  
> *"Dạ thưa Ban Giám khảo, đây là đặc thù của phương pháp chấm điểm tự động dựa trên độ bao phủ từ khóa. Trên tập phát triển 30 câu của Ban Tổ chức, đáp án mẫu là các câu hoàn chỉnh nên độ bao phủ từ khóa đạt trên 80%. Trên tập mở rộng, đáp án mẫu do đội viết thường tổng hợp ý từ nhiều nguồn, còn hệ thống chỉ trích nguyên văn tối đa 3 đoạn, nên một số câu đúng hướng nhưng chưa đủ ý. Đội đã chuẩn hóa đáp án mẫu về đúng câu chữ trong Data Pack để thước đo không bị lệch vì viết tắt; hiện 31/317 câu có nhãn có độ phủ ý chính dưới 0,70, và đội công khai danh sách này. Điểm chính thức vẫn cần chấm tay theo hướng dẫn nghiệp vụ (grading note)."*

### 3. Về dữ liệu và cách xử lý dữ liệu:
**Ban Giám khảo hỏi:** *"Nếu người dùng gõ không dấu, viết tắt lộn xộn hoặc dùng từ khẩu ngữ, hệ thống xử lý thế nào để không tìm sai đoạn văn bản?"*
> **Bạn trả lời:**  
> *"Dạ thưa Ban Giám khảo, đội có bước chuẩn hóa câu hỏi độc lập (Query Normalization): tự động khôi phục dấu tiếng Việt theo ngữ cảnh, giải mã từ viết tắt dựa trên các từ đi kèm (ví dụ: 'gửi HĐ' là hóa đơn, nhưng 'ký HĐ' là hợp đồng), và loại bỏ toàn bộ các lời đệm khẩu ngữ trước khi đưa vào tìm kiếm. Thực tế trên tập kiểm thử 52 câu diễn đạt khẩu ngữ và viết tắt (Paraphrase-52), hệ thống vẫn đạt 100% quyết định đúng, Recall@5 đạt 0,901 và nguồn trích dẫn đầu tiên đúng 92,9%."*

### 4. Về tính khả thi của sản phẩm khả dụng tối thiểu:
**Ban Giám khảo hỏi:** *"Sản phẩm này đã có thể đưa cho người dùng thật sử dụng được chưa và đòi hỏi máy chủ thế nào?"*
> **Bạn trả lời:**  
> *"Dạ thưa Ban Giám khảo, bản hiện tại chạy được trọn luồng trên Data Pack với giao diện web đầy đủ; để dùng thật trong doanh nghiệp cần thêm các bước định hướng ở câu 9 (đăng nhập, kết nối kho tài liệu, thử với người dùng thật). Ứng dụng có giao diện web trực quan, cho phép tra cứu lịch sử, tìm kiếm tức thì theo từng ký tự gõ và mở xem toàn văn văn bản gốc. Về hạ tầng, hệ thống hoàn toàn không cần bộ xử lý đồ họa chuyên dụng (Graphics Processing Unit – GPU) đắt tiền, chạy trên máy tính văn phòng thông thường. Phần xử lý 90 câu hỏi mất khoảng 2 giây (chưa kể thời gian nạp chỉ mục lúc khởi động)."*

### 5. Về khả năng tái lập kết quả:
**Ban Giám khảo hỏi:** *"Làm sao Ban Giám khảo biết những con số tuyệt đối này không phải do đội tự vẽ ra hoặc cài đặt cố định trong mã nguồn?"*
> **Bạn trả lời:**  
> *"Dạ thưa Ban Giám khảo, toàn bộ kết quả có tính tái lập (Reproducibility) 100%. Ban Giám khảo chỉ cần bấm vào tệp lệnh đánh giá có sẵn, hệ thống sẽ tự động đo lường lại trên toàn bộ các tập dữ liệu và xuất ra tệp báo cáo chi tiết. Mỗi lần chạy đều tạo ra một mã định danh phiên chạy (Run ID) duy nhất gắn liền với mã băm an toàn SHA-256 của toàn bộ mã nguồn và kho dữ liệu."*

### 6. Về các trường hợp ngoại lệ:
**Ban Giám khảo hỏi:** *"Hệ thống xử lý thế nào nếu người dùng cố tình đưa ra tiền đề sai hoặc hỏi về một văn bản chưa có hiệu lực?"*
> **Bạn trả lời:**  
> *"Dạ thưa Ban Giám khảo, đội đã kiểm thử trên 60 kịch bản chịu tải phức tạp (Stress-60). Với câu hỏi chứa tiền đề sai (False Premise), hệ thống trích xuất đúng căn cứ thực tế chứ không hùa theo người hỏi; riêng dạng đồng nhất hai mã trạng thái (ví dụ 'HOLD tức là đã bị REJECT'), câu trả lời mở đầu bằng 'Tiền đề chưa đúng – HOLD không có nghĩa là REJECT' kèm định nghĩa nguyên văn của HOLD. Với văn bản chưa có hiệu lực tại ngày hỏi, cổng kiểm tra số 4 sẽ ngăn chặn và chuyển hướng sang văn bản tiền nhiệm hoặc thông báo rõ văn bản chưa đến thời điểm áp dụng."*

### 7. Về rủi ro và giới hạn của giải pháp:
**Ban Giám khảo hỏi:** *"Hạn chế kỹ thuật lớn nhất hiện nay của hệ thống là gì?"*
> **Bạn trả lời:**  
> *"Dạ thưa Ban Giám khảo, hạn chế lớn nhất hiện nay là hệ thống tập trung vào việc so khớp từ vựng nghiệp vụ (Lexical Matching) kết hợp với đồ thị siêu dữ liệu, chưa tích hợp mô hình tìm kiếm ngữ nghĩa chuyên sâu (Dense Semantic Search). Do đó, nếu người dùng sử dụng những từ đồng nghĩa hoàn toàn xa lạ nằm ngoài từ điển nghiệp vụ, hệ thống có thể thận trọng chuyển sang trạng thái từ chối trả lời. Hướng phát triển (định hướng, chưa có trong mã nguồn nộp) là thêm một tầng tìm kiếm ngữ nghĩa chạy cục bộ để bổ trợ cho tìm kiếm từ vựng, giữ nguyên các cổng và bước kiểm toán nguồn trích dẫn."*

### 8. Về mức độ đóng góp thực sự của các nội dung nâng cao:
**Ban Giám khảo hỏi:** *"Nếu tắt bỏ thành phần kiểm toán nguồn trích dẫn và xử lý phiên bản, hệ thống sẽ ra sao?"*
> **Bạn trả lời:**  
> *"Dạ thưa Ban Giám khảo, kết quả thử nghiệm bóc tách từng thành phần (Ablation Study) đã chứng minh: nếu bỏ cơ chế xử lý phiên bản CHRONOS, độ chính xác phiên bản lập tức giảm từ 1,00 xuống còn 0,50; nếu bỏ thành phần kiểm toán nguồn trích dẫn và các cổng bảo vệ, tỷ lệ câu trả lời không có căn cứ sẽ vọt từ 0,000 lên 0,327 (nghĩa là gần 1/3 số câu trả lời sẽ bị tình trạng trích dẫn sai hoặc không có căn cứ)."*

### 9. Về khả năng triển khai thực tế:
**Ban Giám khảo hỏi:** *"Khi có một thông tư hoặc quy định mới được ban hành, việc cập nhật vào hệ thống mất bao lâu?"*
> **Bạn trả lời:**  
> *"Dạ thưa Ban Giám khảo, không cần sửa mã nguồn: quản trị viên thêm văn bản mới vào dữ liệu, khai báo quan hệ thay thế trong metadata, tạo lại bảng kiểm tra toàn vẹn (lệnh `manifest`) và chạy lại bộ kiểm thử; hệ thống tự dựng lại đồ thị thay thế từ metadata khi khởi động. Việc tự động hóa trọn quy trình cập nhật này là hướng phát triển, chưa có trong bản nộp."*

---

# PHẦN 4: CHI TIẾT CÁCH TÍNH VÀ CÔNG THỨC 7 CHỈ SỐ ĐÁNH GIÁ CỐT LÕI (KEY PERFORMANCE INDICATORS – KPI)

---

## 1. Độ bao phủ trong 5 đoạn trích đầu tiên (Retrieval Recall at 5 – Recall@5)
*Mục tiêu đề thi: Đạt ≥ 0,80 (80%).*

> **Ý nghĩa:** Trong 5 đoạn văn bản đầu tiên tìm được, có chứa các đoạn văn bản đáp án chuẩn của Ban Tổ chức hay không.

### Công thức tính cho từng câu:
```text
                  Số đoạn trích đáp án nằm trong Top 5 tìm được
Recall tại 5   = ───────────────────────────────────────────────
                     Tổng số đoạn trích đáp án chuẩn của câu đó
```

### Công thức tính trung bình toàn tập:
```text
Recall tại 5 trung bình = (Tổng điểm Recall của tất cả các câu) / (Tổng số câu có đáp án)
```
- **Quy tắc:** Chỉ tính trên các câu có đáp án (26 câu trong tập phát triển 30 câu: Dev-30). **Nếu câu có đáp án mà hệ thống từ chối trả lời nhầm thì bị tính 0 điểm.**
- **Kết quả thực tế:**
  - Tập phát triển 30 câu (Dev-30): đạt **0,936** (tương đương 24,33 / 26 điểm, tức 93,6%).
  - Tập công khai 90 câu (Public-90): đạt **0,917** (69,67 / 76 điểm).
  - Tập câu khó do đội viết (Stress-60): đạt **0,742** – chưa đạt mục tiêu.
- **Chỉ số phụ:** 
  - Nghịch đảo thứ hạng trung bình trong 5 kết quả đầu (Mean Reciprocal Rank at 5 – MRR@5): đạt **0,962**.
  - Độ bao phủ theo tên văn bản (Document-level Recall): đạt **0,962**.

---

## 2. Độ chính xác câu trả lời / Độ bao phủ ý chính (Answer Accuracy / Correctness)
*Mục tiêu đội đề xuất: Đạt ≥ 0,70 (70%).*

> **Ý nghĩa:** Đo mức độ đầy đủ các ý cốt lõi của câu trả lời so với đáp án mẫu.

### Công thức tính độ phủ ý chính:
```text
                 Số từ khóa nội dung của đáp án mẫu có trong câu trả lời
Độ phủ ý chính = ─────────────────────────────────────────────────────────
                        Tổng số từ khóa nội dung của đáp án mẫu
```

### Thang điểm tự động 0 / 0,5 / 1,0 (Theo hướng dẫn của Ban Tổ chức):
- **Đạt 1,0 điểm:** Độ bao phủ ý chính **≥ 0,70** (từ 70% trở lên – đủ ý hoàn chỉnh).
- **Đạt 0,5 điểm:** Độ bao phủ ý chính **từ 0,40 đến dưới 0,70** (trả lời được một phần ý).
- **Đạt 0,0 điểm:** Độ bao phủ ý chính **< 0,40** (thiếu ý nghiêm trọng hoặc từ chối nhầm).
- **Kết quả thực tế:** Tập phát triển 30 câu (Dev-30) đạt độ bao phủ trung bình **0,867** (86,7%); Thang điểm tự động đạt **0,923** (24 / 26 điểm). Public-90: 0,824; Stress-60: 0,834.

---

## 3. Độ chính xác của nguồn trích dẫn (Citation Accuracy)
*Mục tiêu đề thi: Đạt ≥ 0,80 (80%).*

> **Ý nghĩa:** Đo độ chính xác của các điều khoản luật được trích dẫn (phạt việc dẫn thừa nguồn hoặc dẫn sai điều khoản).

### Công thức tính:
```text
                         Số nguồn trích dẫn trùng khớp hoàn toàn với đáp án
Độ chính xác trích dẫn = ───────────────────────────────────────────────────
                           TỔNG SỐ NGUỒN mà hệ thống đã đưa ra câu trả lời
```
- **Quy tắc phạt:** Nếu câu hỏi chỉ cần 1 điều khoản mà hệ thống dẫn 3 điều khoản (1 đúng, 2 thừa) thì mẫu số là 3 và điểm số bị giảm xuống 1/3 = 0,33 ngay lập tức.
- **Kết quả thực tế:**
  - Tập phát triển 30 câu (Dev-30): đạt **0,894** (23,25 / 26); 26/26 câu có nguồn đầu tiên trùng đáp án của Ban Tổ chức. Điểm bị trừ ở 7 câu dẫn thêm sổ tay/FAQ hoặc điều khoản bổ trợ ngoài đáp án (Q025, Q034, Q041, Q042, Q044, Q049, Q055).
  - Tập công khai 90 câu (Public-90): đạt **0,931** (93,1%).
- **Tiêu chuẩn 4 điều kiện kiểm toán nguồn trích dẫn:**
  1. Điều khoản có trong bảng ánh xạ nguồn (Citation Map).
  2. Nguồn ứng với đoạn trích thực tế nằm trong Top tìm kiếm.
  3. Đoạn trích chứa ≥ 90% từ ngữ của ý khẳng định trong câu trả lời.
  4. Văn bản còn hiệu lực tại ngày tham chiếu.
  *(Hệ thống của đội đạt **1,000 tuyệt đối** trên tiêu chuẩn 4 điều kiện này).*

---

## 4. Tỷ lệ câu trả lời không có căn cứ (Unsupported Answer Rate)
*Mục tiêu đội đề xuất: ≤ 0,10 (dưới 10%) — Càng thấp càng tốt.*

> **Ý nghĩa:** Đo lường tỷ lệ ảo giác (Hallucination) – câu trả lời khẳng định nhưng không có tài liệu chứng minh.

### Công thức tính:
```text
                        Số câu trả lời bị xác định là không có căn cứ
Tỷ lệ không có căn cứ = ──────────────────────────────────────────────
                               Tổng số câu hệ thống đã trả lời
```
- **Điều kiện vi phạm lỗi không có căn cứ:**
  1. Câu hỏi ngoài phạm vi dữ liệu (Out of Scope – OOS) mà hệ thống cố tình trả lời.
  2. Hoặc câu trả lời phát biểu khẳng định nhưng bộ kiểm chứng độc lập thấy: **< 90% từ ngữ** xuất hiện trong đoạn trích dẫn, hoặc ngày hiệu lực không khớp.
- **Kết quả thực tế:** Đạt **0,000 tuyệt đối** (0/26 câu tập phát triển và 0/76 câu tập công khai vi phạm).

---

## 5. Chất lượng từ chối trả lời (Điểm số F1: F1-Score)
*Mục tiêu đội đề xuất: Đạt ≥ 0,90 (90%).*

> **Ý nghĩa:** Khả năng nhận biết câu hỏi ngoài phạm vi dữ liệu để từ chối an toàn.

### Định nghĩa các trường hợp:
- **Dương tính thật (True Positive – TP):** Câu hỏi ngoài phạm vi và hệ thống **từ chối đúng**.
- **Dương tính giả (False Positive – FP):** Câu hỏi có đủ căn cứ nhưng hệ thống **từ chối nhầm**.
- **Âm tính giả (False Negative – FN):** Câu hỏi ngoài phạm vi nhưng hệ thống **trả lời bừa**.

### Công thức tính:
```text
Độ chính xác từ chối (Precision – P) = TP / (TP + FP)

Độ bao phủ từ chối (Recall – R)       = TP / (TP + FN)

Điểm số F1 (F1-Score)                = 2 * (Precision * Recall) / (Precision + Recall)
```
- **Kết quả thực tế:**
  - Tập phát triển 30 câu (Dev-30): Có 4 câu ngoài phạm vi -> TP = 4, FP = 0, FN = 0.  
    => **Precision = 1,000; Recall = 1,000; F1 = 1,000 tuyệt đối**.
  - Tập công khai 90 câu (Public-90): Có 14 câu ngoài phạm vi (từ câu Q077 đến Q090) -> Từ chối chuẩn xác cả 14 câu.  
    => **F1 = 1,000 tuyệt đối**.

---

## 6. Độ chính xác xác định phiên bản hiệu lực (Versioning Accuracy)
*Mục tiêu đội đề xuất: Đạt ≥ 0,90 (90%).*

> **Ý nghĩa:** Trích dẫn đúng thông tư, nghị định còn hiệu lực theo từng mốc thời gian.

### Công thức tính:
```text
Độ chính xác phiên bản = (Số câu dẫn đúng văn bản luật còn hiệu lực) / (Tổng số câu hỏi phiên bản)
```
- **Điều kiện tính là đúng:** Văn bản luật đầu tiên được trích dẫn **bắt buộc phải còn hiệu lực tại ngày tham chiếu** và thuộc danh mục văn bản thay thế hợp lệ.
- **Kết quả thực tế:**
  - Tập phát triển 30 câu (Dev-30): đạt **1,000 tuyệt đối** (4/4 câu).
  - Tập thăm dò 25 câu (Probe-25 mốc ngày mở rộng): đạt **1,000 tuyệt đối** (6/6 câu).
  - Tập công khai 90 câu (Public-90): đạt **1,000 tuyệt đối** (10/10 câu).

---

## 7. Thời gian phản hồi trung bình và phân vị thứ 95 (Latency trung bình & p95)
*Mục tiêu đề thi: Trung bình ≤ 10.000 mili-giây (dưới 10 giây).*

> **Ý nghĩa:** Tốc độ phản hồi và độ ổn định của hệ thống.

### Công thức tính:
- **Thời gian trung bình:** Tổng thời gian xử lý tất cả các câu chia cho tổng số câu hỏi.
- **Phân vị thứ 95 (95th Percentile Latency – p95):** Mức thời gian đảm bảo **95% số câu hỏi** được xử lý nhanh hơn mức này.
- **Kết quả thực tế:**
  - **Thời gian trung bình:** **18,5 – 21,4 mili-giây/câu** tùy tập (lần chạy cuối).
  - **Phân vị thứ 95 (p95):** **42,1 – 49,6 mili-giây/câu**.  
  *(Chưa tới 0,3% giới hạn 10.000 mili-giây của Ban Tổ chức; số đo phụ thuộc máy và tải lúc đo).*

---

## CHỈ SỐ PHỤ: Thứ tự ưu tiên nguồn cho câu hỏi kết hợp (Source Priority)
*Mục tiêu đội đề xuất: Đạt ≥ 0,85 (85%).*

> **Ý nghĩa:** Phân định thứ bậc giữa Căn cứ Pháp luật và Quy trình Nội bộ.

### Điều kiện đạt 1 điểm (thỏa mãn đồng thời cả 4 điều kiện):
1. Có căn cứ pháp luật còn hiệu lực.
2. Căn cứ pháp luật được xếp **trước** Quy trình nội bộ trong câu trả lời.
3. Không dùng văn bản hết hiệu lực hoặc văn bản hợp nhất làm căn cứ chính.
4. Nếu tài liệu nội bộ dẫn chiếu luật cũ thì phải tự động kéo văn bản mới kế nhiệm hoặc phát cảnh báo.

---

# PHẦN 5: BẢNG ĐỐI CHIẾU SỐ LIỆU VÀ CẨM NANG ĐỐI ĐÁP NHANH 15–20 GIÂY

| Chỉ số đánh giá cốt lõi (KPI) | Kết quả của đội | Yêu cầu đề thi / Mục tiêu | Ý nghĩa thực tế |
|---|:---:|:---:|---|
| **Độ chính xác nguồn trích dẫn (Citation Accuracy)** | **0,894** (Dev-30) / **0,931** (Public-90) | ≥ 0,80 | 100% citation qua kiểm toán 4 điều kiện; điểm bị trừ khi dẫn thêm sổ tay/FAQ ngoài đáp án |
| **Tỷ lệ trả lời không căn cứ (Unsupported Rate)** | **0,000 tuyệt đối** (0/26 câu) | ≤ 0,10 | Tuyệt đối không ảo giác hay bịa đặt căn cứ |
| **Chất lượng từ chối trả lời (F1-Score)** | **1,000 tuyệt đối** (14/14 câu) | ≥ 0,90 | Nhận diện và từ chối an toàn toàn bộ câu hỏi ngoài dữ liệu |
| **Độ chính xác phiên bản (Versioning Accuracy)** | **1,000 tuyệt đối** (10/10 câu) | ≥ 0,90 | Áp dụng chuẩn xác thông tư theo từng mốc thời gian |
| **Độ bao phủ trong 5 kết quả đầu (Recall@5)** | **0,936** (tập Dev-30) / **0,917** (Public-90) / 0,742 (Stress-60) | ≥ 0,80 | Đạt trên tập của Ban Tổ chức; chưa đạt trên câu khó nhiều bước |
| **Thời gian phản hồi trung bình (Latency)** | **18,5 mili-giây** (p95: 49,6 mili-giây) | ≤ 10.000 mili-giây | Chưa tới 0,03 giây mỗi câu |
| **Kiểm tra tệp nộp bài (`submission.csv`)** | **23/23 bài kiểm tra đạt (0 lỗi)** | Khớp 100% định dạng Schema | Máy chấm tự động của Ban Tổ chức đọc bài trơn tru |

### Ba câu trả lời mẫu 20 giây khi Ban Giám khảo hỏi xoáy:
1. **Khi hỏi về mẫu số của Recall tại 5 (Recall@5):**  
   *"Dạ thưa Ban Giám khảo, mẫu số là Tổng số đoạn trích đáp án chuẩn của câu hỏi đó trên tập dữ liệu phát triển (Dev-30). Nếu câu nào hệ thống từ chối trả lời nhầm, câu đó bị tính 0 điểm ngay lập tức."*
2. **Khi hỏi về việc phạt dẫn thừa nguồn trong Citation Accuracy:**  
   *"Dạ thưa Ban Giám khảo, hệ thống phạt rất nặng việc dẫn thừa. Mẫu số là Tổng số nguồn mà hệ thống đã trích dẫn trong câu trả lời. Nếu dẫn thừa nguồn không liên quan, điểm số bị trừ ngay. Đội đạt 0,894 trên Dev-30: cả 26/26 câu có nguồn đầu tiên đúng đáp án; phần bị trừ là các câu dẫn thêm sổ tay/FAQ để trả lời đủ tình huống, ví dụ Q042 dẫn thêm FAQ04 – câu duy nhất nói rõ không được sửa trực tiếp hóa đơn đã phát hành."*
3. **Khi hỏi về kiểm soát ảo giác (Unsupported Answer Rate):**  
   *"Dạ thưa Ban Giám khảo, đội có bộ kiểm chứng độc lập. Một câu bị coi là không có căn cứ nếu câu ngoài phạm vi (Out of Scope – OOS) mà cố trả lời, hoặc câu trả lời có dưới 90% từ ngữ nằm trong đoạn trích dẫn. Đội kiểm soát tỷ lệ này bằng 0,000 tuyệt đối."*
