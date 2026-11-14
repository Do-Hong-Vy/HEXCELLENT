# ⚖️ PolicyAssist AI – CHRONOS-LEDGER

**Trợ lý AI tra cứu và giải thích chính sách tài chính – kế toán – thuế có dẫn nguồn**
Đội **HEXCELLENT** · Festival Chuyển đổi số 2026 (CRYSTARA) · Bảng A · Case 1

> **Phạm vi:** hệ thống chỉ tra cứu trong Data Pack do BTC cung cấp (snapshot 17/10/2026), **không phải công cụ tư vấn pháp lý hoặc tư vấn thuế chính thức**. Tài liệu `SIM01`–`SIM08` là **dữ liệu nội bộ giả lập** của "Công ty Cổ phần Nova Việt", chỉ có ý nghĩa trong Case Study.

---

## Mục lục

1. [Kết quả 7 KPI](#1-kết-quả-7-kpi)
2. [Cấu trúc thư mục](#2-cấu-trúc-thư-mục)
3. [Cài đặt](#3-cài-đặt)
4. [Chạy chương trình](#4-chạy-chương-trình)
5. [Hướng dẫn sử dụng giao diện](#5-hướng-dẫn-sử-dụng-giao-diện)
6. [Toàn vẹn dữ liệu Data Pack](#6-toàn-vẹn-dữ-liệu-data-pack)
7. [Pipeline CHRONOS-LEDGER](#7-pipeline-chronos-ledger)
8. [Đầu ra submission](#8-đầu-ra-submission)
9. [Đánh giá KPI – cách đo và tái lập](#9-đánh-giá-kpi--cách-đo-và-tái-lập)
10. [Đối chiếu yêu cầu README Data Pack và tiêu chí Bronze/Silver/Gold](#10-đối-chiếu-yêu-cầu)
11. [Audit log, quyền riêng tư và human-in-the-loop](#11-audit-log-quyền-riêng-tư-và-human-in-the-loop)
12. [Giới hạn và rủi ro](#12-giới-hạn-và-rủi-ro)
13. [Xử lý sự cố](#13-xử-lý-sự-cố)

---

## 1. Kết quả 7 KPI

Một lệnh `python policyassist.py eval` đo **mọi tập có nhãn** cho hệ thống và baseline B0:
- **Dev-30**: đáp án của BTC.
- **Ext-60**: nhãn của đội.
- **Public-90**: Dev-30 + Ext-60.
- **Stress-60**: câu khó do đội viết; đã dùng để phân tích lỗi (24/10 và 10/11/2026) nên không còn hoàn toàn độc lập.
- **Probe-25** và **Paraphrase-52**.

Lệnh này chạy kèm kiểm định ghép cặp, khoảng tin cậy 95%, ablation B0 → B6 và các kịch bản demo. Báo cáo nằm ở `outputs/eval_report.md`, số liệu ở `outputs/kpi_table.csv`.

Thông tin lần chạy:
- run_id: `RUN-20261115-004740-2850c1` (lần chạy cuối; sha256 mã nguồn `2850c163ff7e`, khớp `outputs/run_manifest.json`).
- Corpus `08eaac52973a` (6 file CSV, cách tính của đội) và `7357afec5ef0` (toàn bộ Data Pack) – hai dấu vân tay của cùng một bộ dữ liệu.
- Đo trên bộ câu hỏi mẫu, không phải người dùng thật.

### 1.1. Bảng KPI theo tập – hệ thống CHRONOS-LEDGER

Mỗi ô ghi giá trị, kèm (tổng điểm hoặc số câu đúng / số câu được tính).

| KPI | Dev-30 – đáp án BTC | Ext-60 – nhãn đội | Public-90 | Stress-60 – câu khó của đội | Mục tiêu |
|---|---:|---:|---:|---:|---|
| 1. Retrieval Recall@5 | **0,936** (24,33/26) | 0,907 (45,33/50) | 0,917 (69,67/76) | 0,742 (38,57/52) | ≥ 0,80 (đề thi) |
|   · MRR@5 | 0,962 (25/26) | 0,844 (42,18/50) | 0,884 (67,18/76) | 0,868 (45,12/52) | |
|   · Recall@5 theo văn bản | 0,962 (25/26) | 0,950 (47,5/50) | 0,954 (72,5/76) | 0,882 (45,88/52) | |
| 2. Answer Accuracy / Correctness (độ phủ ý chính) | **0,867** (22,55/26) | 0,801 (40,05/50) | 0,824 (62,60/76) | 0,834 (15,85/19) | ≥ 0,70 (đội) |
|   · thang 0 / 0,5 / 1 (tự động) | 0,923 (24/26) | 0,850 (42,5/50) | 0,875 (66,5/76) | 0,895 (17/19) | |
| 3. Citation Accuracy (đúng nhãn đáp án) | **0,894** (23,25/26) | 0,950 (47,50/50) | 0,931 (70,75/76) | 0,848 (44,08/52) | ≥ 0,80 (đề thi) |
|   · citation đủ 4 điều kiện (a)–(d) | 1,000 (26/26) | 1,000 (50/50) | 1,000 (76/76) | 1,000 (52/52) | |
| 4. Unsupported Answer Rate | **0,000** (0/26) | 0,000 (0/50) | 0,000 (0/76) | 0,000 (0/52) | ≤ 0,10 (đội) |
| 5. Abstention F1 (Precision / Recall) | **1,000 (1,000 / 1,000)** | 1,000 (1,000 / 1,000) | 1,000 (1,000 / 1,000) | 1,000 (1,000 / 1,000) | ≥ 0,90 (đội) |
| 6. Versioning Accuracy | **1,000** (4/4) | 1,000 (6/6) | 1,000 (10/10) | 1,000 (14/14) | ≥ 0,90 (đội) |
| 7. Latency trung bình / p95 | **19 / 51 ms** | 22 / 48 ms | 21 / 48 ms | 21 / 44 ms | TB ≤ 10.000 ms (đề thi) |
| Source Priority – câu MIXED (chỉ số phụ) | 0,667 (2/3) | 0,444 (4/9) | 0,500 (6/12) | 1,000 (1/1) | ≥ 0,85 (đội) |
| Quyết định ANSWER/ABSTAIN đúng | 1,000 (30/30) | 1,000 (60/60) | 1,000 (90/90) | 1,000 (60/60) | |

**Baseline B0 trên cùng các tập** (Dev-30 / Ext-60 / Public-90 / Stress-60):

| Chỉ số | Dev-30 | Ext-60 | Public-90 | Stress-60 |
|---|---:|---:|---:|---:|
| Recall@5 | 0,538 | 0,647 | 0,610 | 0,360 |
| Answer | 0,619 | 0,607 | 0,611 | 0,430 |
| Citation | 0,442 | 0,693 | 0,607 | 0,394 |
| Unsupported | 0,133 | 0,167 | 0,156 | 0,133 |
| Abstention F1 | 0 (B0 luôn trả lời) | 0 | 0 | 0 |
| Versioning | 0,250 | 0,500 | 0,400 | 0,214 |

**Kiểm định ghép cặp với B0 trên Public-90** (từng câu, 95% bootstrap):
- Quyết định đúng: +14 / −0 câu (McNemar p = 0,000122).
- Recall@5: +0,307 (+0,213 … +0,404).
- Answer: +0,213 (+0,151 … +0,277).
- Citation: +0,323 (+0,228 … +0,425).

**Đọc bảng:**
- **Dev-30** (đáp án của chính BTC – thước đo chuẩn mực nhất): đạt cả 7 mục tiêu: Citation Accuracy 0,894, **cả 26/26 câu trả lời đều có citation đầu tiên trùng đáp án mẫu của BTC**, Unsupported = 0,000, Abstention F1 = 1,000, Versioning = 1,000.
- **Ext-60 – quy ước nhãn:** nhãn của đội dùng sổ tay/FAQ (SIM07, SIM08) làm "chunk chính" ở 17/50 câu.
  - Đáp án BTC chỉ dẫn sổ tay/FAQ khi câu hỏi hỏi trực tiếp về chúng (2/30 câu: Q068, Q070). README mục 2 cũng xếp sổ tay/FAQ sau quy chế/quy trình.
  - Hệ thống tuân thủ chặt quy ước của BTC, xếp hạng văn bản quy chế/quy trình trước sổ tay hỗ trợ.
- **Answer trên Ext-60** chấm theo "ý chính" viết ngắn của người gán, nên độ phủ thấp hơn Dev-30 (đáp án BTC là câu đầy đủ). Điểm chính thức cần chấm tay theo `grading_note` – cột này có sẵn trong `outputs/eval_results_all.csv`.
- **Đối chiếu 90 câu public** (`outputs/public90_audit.csv` – câu trả lời, citation hệ thống, citation đáp án, mức khớp, trace_id từng câu):

  | Mức khớp citation | Dev-30 (đáp án BTC) | Ext-60 (nhãn đội) | Tổng |
  |---|---:|---:|---:|
  | ABSTAIN đúng | 4 | 10 | 14 |
  | Khớp đủ | 11 | 21 | 32 |
  | Đúng nhưng thiếu (mọi citation đúng, chưa đủ) | 8 | 24 | 32 |
  | Một phần (có citation ngoài nhãn) | 7 | 5 | 12 |
  | Không khớp | 0 | 0 | 0 |
  | Tổng | 30 | 60 | 90 |

  - **Dev-30:** 0 câu không khớp, 7 câu một phần (Q025, Q034, Q041, Q042, Q044, Q049, Q055); 11 câu khớp đủ, 8 câu mọi citation đều đúng nhãn nhưng chưa đủ. Q042 dẫn đủ 3 citation của đáp án BTC và thêm FAQ04 – câu duy nhất trong Data Pack nói rõ *không được sửa trực tiếp dữ liệu gốc*.
  - **Ext-60:** 0 câu không khớp (—) và 5 câu một phần (Q043, Q046, Q048, Q052, Q074). Phần lớn là câu dẫn thêm quy chế/quy trình gốc mà nhãn của đội chỉ ghi là căn cứ bổ trợ.
- **Bảng lỗi** (`outputs/error_table.csv` – 0 lỗi):

  | Loại lỗi | Dev-30 | Ext-60 | Paraphrase-52 | Stress-60 | Tổng |
  |---|---:|---:|---:|---:|---:|
  | Retrieval (chunk chính ngoài top-5) | 0 | 0 | 0 | 0 | 0 |
  | Citation (không citation nào đúng nhãn) | 0 | 0 | 0 | 0 | 0 |
  | Generation (thiếu ý chính) | 0 | 0 | 0 | 0 | 0 |
  | ABSTAIN – từ chối nhầm câu đủ căn cứ | 0 | 0 | 0 | 0 | 0 |
  | ABSTAIN – trả lời câu lẽ ra phải từ chối | 0 | 0 | 0 | 0 | 0 |
  | Versioning (văn bản không đúng mốc) | 0 | 0 | 0 | 0 | 0 |
  | Tổng | 0 | 0 | 0 | 0 | 0 |

  Dev-30 đạt **0 lỗi** trên bảng lỗi chính thức. Toàn bộ 26 câu ANSWER đều có chunk chính trong top-5, citation đúng nhãn và không câu nào ABSTAIN nhầm hay sai phiên bản.

### 1.2. Hệ thống so với baseline – trang Đánh giá KPI

Trang **Đánh giá KPI** có nút **Tập đo**, mặc định **Public-90**. Các lựa chọn:
- **Public-90**: 90 câu chính thức của BTC.
- **Stress-60**: câu khó, diễn đạt lệch.
- **Paraphrase-52**.
- **Dev-30 + Probe-25**: tập phát triển. Đội tinh chỉnh quy tắc khi xem kết quả trên tập này nên số lạc quan.

Baseline **B0** = BM25 thuần, luôn trả lời (mô tả chi tiết ở cuối mục này).

Mục **Cách đo từng KPI – công thức** cuối trang trình bày mục tiêu, ý nghĩa, công thức (dạng phân số) và quy tắc chấm của 7 KPI + Source Priority, kèm kết quả trên tập đang chọn.

**Kiểm tra độc lập:** `python verify_kpi_independent.py` tính lại Recall@5, Citation, Abstention F1, Versioning, Latency trên mọi tập chỉ từ file nhãn gốc + `outputs/eval_results_all.csv` (không dùng hàm đánh giá của chương trình) và so với `outputs/eval_by_set.csv` – lần chạy gần nhất khớp hoàn toàn.

**Số chính để trình bày** (hệ thống / B0):

| KPI (so với baseline) | Public-90 | Stress-60 |
|---|---|---|
| Retrieval Recall@5 | **0,917** / 0,610 | **0,742** / 0,360 |
| Answer Correctness | **0,824** / 0,611 | **0,834** / 0,430 |
| Citation Accuracy | **0,931** / 0,607 | **0,848** / 0,394 |
| Unsupported (thấp là tốt) | **0,000** / 0,156 | **0,000** / 0,133 |
| Abstention F1 | **1,000** / 0,000 | **1,000** / 0,000 |
| Versioning | **1,000** / 0,400 | **1,000** / 0,214 |

**Tập phát triển Dev-30 + Probe-25** (số lạc quan – dùng khi tinh chỉnh):

| # | KPI (README mục 9) | CHRONOS-LEDGER | Baseline B0 | Mục tiêu | Chỉ số kèm |
|---|---|---:|---:|---|---|
| 1 | Retrieval Recall@5 | **0,936** | 0,538 | ≥ 0,80 (đề thi) | MRR@5 0,962 · Recall@5 theo văn bản 0,962 |
| 2 | Answer Accuracy / Correctness (độ phủ ý chính) | **0,867** | 0,619 | ≥ 0,70 (đội đề xuất) | thang 0 / 0,5 / 1 (tự động) 0,923 |
| 3 | Citation Accuracy | **0,894** | 0,442 | ≥ 0,80 (đề thi) | 100% citation đạt đủ 4 điều kiện |
| 4 | Unsupported Answer Rate (thấp là tốt) | **0,000** | 0,327 | ≤ 0,10 (đội đề xuất) | 0/37 câu đã trả lời |
| 5 | Abstention Quality (F1 lớp ABSTAIN) | **1,000** | 0,000 | ≥ 0,90 (đội đề xuất) | P 1,000 · R 1,000 · TP 18 · FP 0 · FN 0 |
| 6 | Versioning Accuracy | **1,000** | 0,200 | ≥ 0,90 (đội đề xuất) | 10/10 câu |
| 7 | Latency trung bình | **19 ms** | 6 ms | ≤ 10 giây (đề thi) | p95 49 ms · 145 lượt đo |

**Nguồn của các chỉ số kèm** (dòng nhỏ dưới mỗi ô; cùng tập Dev-30 + Probe-25 với giá trị chính):
- MRR@5 và Recall@5 theo văn bản: 26 câu ANSWER của Dev-30.
- Thang 0 / 0,5 / 1: chấm tự động 26 câu ANSWER.
- "100% citation đạt đủ 4 điều kiện": kiểm (a)–(d) trên mọi citation.
- "0/37": 37 câu được trả lời (26 Dev-30 + 11 Probe-25), không câu nào có nội dung thiếu căn cứ.
- "Từ chối đúng 18/18": 4 câu ABSTAIN của Dev-30 + 14 câu ABSTAIN của Probe-25.
- "10/10 câu hỏi phiên bản": 4 câu Dev-30 + 6 câu Probe-25.
- "p95 … ms · 145 lượt đo" và "Dùng …% thời gian cho phép" (= latency TB / 10.000 ms): 145 lượt = 30 Dev-30 + 25 Probe-25 + 90 câu public.

**Baseline B0 = BM25 thuần:**
- Dùng câu hỏi nguyên văn: không chuẩn hóa, không mở rộng từ khóa, không kéo thêm đoạn theo tên văn bản.
- Lấy 5 đoạn có điểm BM25 cao nhất và trả lời bằng đoạn đứng đầu.
- Luôn trả lời: không có Guard/Gate, không xét hiệu lực, thẩm quyền hay kiểm toán citation.
- Đã đối chiếu với một bản BM25 tính độc lập: trùng 30/30 câu Dev.

**Kết quả trên 90 câu public:**
- Trả lời 76 câu, **ABSTAIN đúng 14 câu ngoài phạm vi (Q077–Q090)**.
- 100% citation có trong `citation_map.csv` và hợp lệ về thời gian tại `reference_date`.
- `validate_submission.py`: 0 lỗi.

### 1.3. Ablation

**(a) Thêm dần từng khối B0 → B6 trên Public-90** (`outputs/ablation_B0_B6.csv`). B2′ thay CHRONOS bằng cách của pipeline tham khảo – lọc cứng chunk hết hiệu lực trước khi xếp hạng – để so hai cách xử lý phiên bản.

| Cấu hình | Recall@5 | MRR@5 | Answer | Citation | Unsupported | Abstention F1 | Versioning | Source Priority | Latency TB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| B0 – BM25 thuần | 0,610 | 0,616 | 0,611 | 0,607 | 0,156 | 0,000 | 0,40 | 0,083 | 7 ms |
| B1 – + truy hồi lai, chuẩn hóa truy vấn | 0,725 | 0,701 | 0,654 | 0,682 | 0,156 | 0,000 | 0,40 | 0,083 | 11 ms |
| B2 – + CHRONOS (chuyển hướng phiên bản) | 0,797 | 0,777 | 0,722 | 0,800 | 0,156 | 0,000 | 0,90 | 0,333 | 12 ms |
| B2′ – B1 + lọc cứng theo ngày | 0,766 | 0,732 | 0,665 | 0,728 | 0,156 | 0,000 | 0,60 | 0,083 | 11 ms |
| B3 – + xếp hạng thẩm quyền, cấu trúc Điều, truy nguồn FAQ | 0,910 | 0,884 | 0,757 | 0,956 | 0,156 | 0,000 | 1,00 | 0,083 | 23 ms |
| B4 – + Guard, cổng đủ căn cứ | 0,910 | 0,884 | 0,757 | 0,956 | 0,000 | 1,000 | 1,00 | 0,083 | 21 ms |
| B5 – + soạn nhiều căn cứ, câu quyết định có/không, kiểm toán citation | 0,917 | 0,884 | 0,824 | 0,931 | 0,000 | 1,000 | 1,00 | 0,500 | 21 ms |
| **B6 – + ngưỡng độ tin cậy (hệ thống nộp bài)** | **0,917** | **0,884** | **0,824** | **0,931** | **0,000** | **1,000** | **1,00** | **0,500** | 21 ms |

- Mỗi khối cải thiện một nhóm KPI riêng:
  - B1 tăng Recall@5 (+0,115: 0,610 → 0,725).
  - B2 tăng Versioning (+0,50: 0,40 → 0,90) và Citation (+0,118: 0,682 → 0,800).
  - B3 tăng Citation (+0,156: 0,800 → 0,956), Recall@5 (+0,113: 0,797 → 0,910), Versioning 1,00.
  - B4 đưa Unsupported về 0,000 và Abstention F1 lên 1,000.
  - B5 thay đổi Answer (+0,067: 0,757 → 0,824), Recall@5 (+0,007: 0,910 → 0,917), Source Priority (+0,417: 0,083 → 0,500) và Citation (-0,025: 0,956 → 0,931).
- So với lọc cứng theo ngày (B2′), chuyển hướng phiên bản (B2): Recall 0,797 so với 0,766, Citation 0,800 so với 0,728, Versioning 0,90 so với 0,60.
- Ngưỡng độ tin cậy (B6) so với B5 trên Public-90: Answer 0,824 → 0,824, Citation 0,931 → 0,931.

**(b) Bỏ từng thành phần khỏi hệ thống đầy đủ** (Dev-30 + Probe-25; `outputs/eval_summary.csv`):

| Hệ thống | Recall@5 | Answer | Citation | Unsupported | Abstention F1 | Versioning |
|---|---:|---:|---:|---:|---:|---:|
| **CHRONOS-LEDGER (đầy đủ)** | **0,936** | **0,867** | **0,894** | **0,000** | **1,000** | **1,00** |
| – bỏ CHRONOS (versioning) | 0,891 | 0,801 | 0,788 | 0,000 | 1,000 | 0,50 |
| – bỏ Authority rerank | 0,708 | 0,759 | 0,699 | 0,000 | 1,000 | 0,80 |
| – bỏ truy nguồn FAQ (PRF) | 0,904 | 0,834 | 0,801 | 0,000 | 1,000 | 1,00 |
| – bỏ cấu trúc Điều | 0,891 | 0,845 | 0,878 | 0,000 | 1,000 | 1,00 |
| – bỏ Guard & Gate | 0,936 | 0,867 | 0,894 | 0,327 | 0,000 | 1,00 |
| – bỏ TF-IDF (chỉ BM25) | 0,891 | 0,823 | 0,846 | 0,000 | 1,000 | 1,00 |

Ô không đổi so với hệ thống đầy đủ (vd. bỏ Guard & Gate thì Recall, Answer, Citation giữ nguyên) nghĩa là thành phần đó không tác động lên chỉ số ấy, hoặc các thành phần còn lại bù được. Vì vậy bảng (a) cho thấy đóng góp riêng của từng khối rõ hơn bảng (b).

### 1.4. Độ bền với câu hỏi ngoài đáp án mẫu

Không dùng để tinh chỉnh tham số; số liệu ở `outputs/robustness.csv`.

| Tập | Số câu | Quyết định đúng | Chunk chính trong top-5 | Citation [1] đúng | Độ chính xác citation | Versioning |
|---|---:|---:|---:|---:|---:|---:|
| Ext-60 – 60 câu public còn lại (nhãn đội) | 60 | 1,000 | 1,000 | 0,920 | 0,950 | 1,000 |
| Paraphrase-52 – diễn đạt lại, viết tắt (MST, HĐĐT, IT), gõ không dấu, câu đòi dữ liệu thật, ngoài lĩnh vực | 52 | 1,000 | 1,000 | 0,929 | 0,897 | 1,000 |
| Probe-25 – ngoài phạm vi, versioning mốc mới | 25 | 1,000 | — | — | — | 1,000 |
| Stress-60 – kiểm thử chịu tải (đội viết; đã dùng phân tích lỗi từ 10/11/2026) | 60 | 1,000 | 1,000 | 0,846 | 0,848 | 1,000 |

### 1.5. Kịch bản demo – output thật (`python policyassist.py demo`, `outputs/demo_cases.csv`)

| Case | Câu hỏi · reference_date | Kết quả | Độ tin cậy |
|---|---|---|---:|
| A – một nguồn | Q001 · 17/10/2026 | ANSWER · LAW01 – Điều 3 khoản 3 | 0,971 |
| B1 – nhiều nguồn | Q042 · 17/10/2026 | ANSWER · **Không.** · LAW12 – Điều 10 khoản 1 điểm b; LAW12 – Điều 10 khoản 1; SIM02 – Điều 7 (**đủ 3 citation của đáp án BTC**); SIM08 – FAQ04 (câu nói rõ không được sửa trực tiếp) | 0,969 |
| B2 – versioning | *"Hướng dẫn về hóa đơn điện tử nên áp dụng theo Thông tư nào?"* · 15/05/2025 | ANSWER · LAW09 – Điều 1 (TT 78/2021) | 0,969 |
| B2 – versioning | như trên · 15/06/2025 | ANSWER · LAW06 – Điều 12 khoản 1 (TT 32/2025) | 0,970 |
| B2 – versioning | như trên · 15/08/2026 | ANSWER · LAW12 – Điều 24–25 (TT 91/2026) | 0,969 |
| C – ABSTAIN | Q077 · 17/10/2026 | ABSTAIN · *"Không đủ căn cứ trong Data Pack để xác định mã số thuế chính thức của Công ty Cổ phần Nova Việt. Nova Việt là doanh nghiệp giả lập; …"* | 0,050 |

Mỗi lần chạy, mỗi case có một `trace_id` riêng (ghi trong `demo_cases.csv`). Lệnh `demo` và `eval` không ghi audit log; muốn có dòng audit log của một case thì hỏi lại câu đó trên giao diện hoặc bằng lệnh `ask`.

### 1.6. Kiểm thử chịu tải Stress-60

Chạy cùng lệnh `eval` hoặc riêng bằng `python policyassist.py stress`; chi tiết theo 14 kiểu stress ở `outputs/stress60_report.md`.

| Hệ thống | Quyết định đúng | F1 ABSTAIN | Recall@5 | Citation Accuracy | Citation [1] đúng | Versioning | Phạm vi nguồn đúng | Citation hợp lệ tại mốc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **CHRONOS-LEDGER** | **1,000** | **1,000** | **0,742** | **0,848** | **0,846** | **1,000** | **0,967** | **1,000** |
| Baseline B0 | 0,867 (luôn trả lời) | 0,000 | 0,360 | 0,394 | 0,423 | 0,214 | 0,800 | 0,900 |

Kết quả:
- Quyết định đúng 60/60 câu (100,0%), F1 ABSTAIN 1,000, Recall@5 0,742, Citation Accuracy 0,848, citation hợp lệ tại mốc 1,000.
- 90 câu public vẫn ABSTAIN đúng 14/14 câu (Q077–Q090).
- Các điểm cần lưu ý:
  - 0 câu chưa đúng quyết định.
  - Versioning 14/14. Hai dòng nhãn S030, S032 đã được sửa ngày 10/11/2026 vì cột văn bản kỳ vọng mâu thuẫn với chính ghi chú chấm của dòng đó (S030 thiếu LAW07; S032 ghi LAW10 trong khi ghi chú yêu cầu trả lời LAW04 còn hiệu lực). Ngày 12/11/2026 dòng S015 (trạng thái *Nháp – kế thừa nhãn từ seed* Q040) được bổ sung SIM03_C010 – Điều 13 cho khớp nhãn của chính seed Q040.

> Con số có thể chênh nhẹ giữa các máy ở KPI Latency; các KPI còn lại tái lập chính xác (pipeline tất định, không dùng mô hình ngẫu nhiên).

---

## 2. Cấu trúc thư mục

```text
HEXCELLENT/
├── policyassist.py                 ← CHƯƠNG TRÌNH CHÍNH: pipeline + giao diện web + CLI + đánh giá 7 KPI
├── validate_submission.py          ← kiểm tra độc lập file nộp (chỉ dùng thư viện chuẩn Python, 23 kiểm tra)
├── verify_kpi_independent.py      ← tính lại KPI độc lập trên mọi tập từ nhãn gốc + outputs, so với eval_by_set.csv
├── requirements.txt                ← thư viện cần cài
├── README.md                       ← tài liệu này
├── 1_cai_dat.bat                   ← (Windows) cài thư viện
├── 2_mo_giao_dien.bat              ← (Windows) mở giao diện web
├── 3_xuat_submission.bat           ← (Windows) chạy 90 câu → outputs/submission.csv
├── 4_danh_gia_7_KPI.bat            ← (Windows) đo 7 KPI → outputs/eval_report.md
├── 5_kiem_tra_toan_ven.bat         ← (Windows) kiểm tra toàn vẹn Data Pack
├── .streamlit/config.toml          ← cấu hình giao diện: tông xanh navy, không gửi thống kê, không hỏi email
├── data/                           ← DỮ LIỆU ĐẦU VÀO
│   ├── DataPack-CASE1_PolicyAssist/        ← Data Pack BTC – nguyên bản, KHÔNG sửa
│   │   ├── 01_documents/                   LAW01–LAW12, SIM01–SIM08 (.docx)
│   │   ├── 02_documents_text/              LAW01–LAW12 (.txt – dùng để "xem toàn văn")
│   │   ├── 03_metadata/
│   │   │   ├── document_metadata.csv       metadata 20 tài liệu (= document_metadata_v3_checked.csv trong README BTC)
│   │   │   └── legal_chunks.csv            374 chunk – corpus retrieval chính
│   │   ├── 04_questions/questions_sample.csv       90 câu hỏi public
│   │   ├── 05_answer_sample/answer_key_sample.csv  30 đáp án mẫu
│   │   ├── citation_map.csv                chunk → vị trí nguồn → citation_label
│   │   ├── submission_output_template.csv  schema nộp bài
│   │   └── README.md, README_BangA_PolicyAssistAI.md
│   ├── corpus_manifest.csv                 ← SHA-256 của từng file Data Pack (40 file)
│   ├── corpus_manifest.json                ← phiên bản Data Pack, corpus fingerprint, số lượng tài liệu/chunk/câu hỏi
│   ├── eval/probe_questions.csv            ← 25 câu kiểm thử ngoài bộ public (đội tự xây)
│   ├── eval/ext60_labels.csv               ← Ext-60: nhãn đội cho 60 câu public chưa có đáp án (10 cột như answer_key + chunk bổ trợ/bẫy)
│   ├── eval/paraphrase_questions.csv       ← 52 câu diễn đạt lại / viết tắt / ngoài phạm vi (đo độ bền)
│   ├── eval/stress60_labels.csv            ← Stress-60: 60 câu kiểm thử chịu tải, 14 kiểu (sheet Stress60_labels, file task 2210)
│   └── DeThi2026_BangA_PolicyAssistAI.pdf  ← đề thi (tham khảo)
├── outputs/                        ← KẾT QUẢ (tự sinh)
│   ├── submission.csv                      FILE NỘP đúng schema BTC (máy đọc)
│   ├── submission.xlsx                     cùng nội dung, để xem bằng Excel (không nộp file này)
│   ├── eval_report.md                      báo cáo đánh giá đầy đủ (12 phần: KPI theo tập, B0, kiểm định, CI, ablation, lỗi, demo…)
│   ├── kpi_table.csv                       bảng KPI dạng dài: chỉ số × tập · giá trị · số câu · CI 95% · B0 · mục tiêu
│   ├── eval_by_set.csv, eval_by_scope.csv  tổng hợp theo tập và theo answer_scope (hệ thống + B0)
│   ├── eval_results_all.csv                từng câu của mọi tập: quyết định, citation, chỉ số, loại lỗi, trace_id, đáp án tham chiếu
│   ├── error_table.csv                     bảng lỗi retrieval / citation / abstain / versioning / generation
│   ├── ablation_B0_B6.csv                  ablation thêm dần B0 → B6 (+ B2′ lọc cứng theo ngày) trên Public-90
│   ├── demo_cases.csv                      4 kịch bản demo (A, B1, B2 ở 3 mốc, C): citation, độ tin cậy, latency, trace_id
│   ├── run_manifest.json                   hồ sơ lần chạy: run_id, mã nguồn, 2 dấu vân tay corpus, nhãn, cấu hình, môi trường
│   ├── stress60_report.md, stress60_*.csv  Stress-60 chi tiết theo kiểu stress
│   ├── kpi_7.csv, eval_summary.csv, eval_per_question.csv, robustness.csv   (dùng cho trang Đánh giá KPI)
└── logs/                           ← NHẬT KÝ (tự sinh)
    ├── audit_log.jsonl                     mỗi lượt hỏi một dòng (đã che thông tin cá nhân)
    ├── feedback.jsonl                      phản hồi Hữu ích / Chưa đúng
    └── sessions/                           LỊCH SỬ TRA CỨU – mỗi phiên "Tra cứu mới" một file JSON
```

**Về tên file metadata:** README của BTC gọi là `document_metadata_v3_checked.csv`, trong Data Pack phát hành là `03_metadata/document_metadata.csv` – hai tên là **cùng một file**. Chương trình tự nhận cả hai tên và cả hai cách sắp xếp thư mục (`citation_map.csv` ở gốc hoặc trong `03_metadata/`, template ở gốc hoặc trong `06_output_template/`).

---

## 3. Cài đặt

Yêu cầu: **Python ≥ 3.10** (đã kiểm thử Python 3.14.8). Không cần GPU, không cần Internet, không cần API key.

### Windows (cách nhanh nhất)

1. Cài Python từ <https://www.python.org/downloads/> (tick **"Add python.exe to PATH"**).
2. Double-click **`1_cai_dat.bat`** (chỉ cần làm một lần).
3. Double-click **`2_mo_giao_dien.bat`** → trình duyệt tự mở `http://localhost:8501`.

### Windows / macOS / Linux bằng dòng lệnh (khuyến nghị dùng môi trường ảo)

```bash
cd HEXCELLENT
python -m venv .venv
```

```bash
.venv\Scripts\activate
```
(macOS/Linux: `source .venv/bin/activate`)

```bash
pip install -r requirements.txt
```

---

## 4. Chạy chương trình

Mọi chức năng nằm trong **một file `policyassist.py`**:

| Việc cần làm | Lệnh | Kết quả |
|---|---|---|
| Mở giao diện web (mặc định) | `python policyassist.py` | trình duyệt mở `http://localhost:8501` |
| Hỏi một câu từ dòng lệnh | `python policyassist.py ask "Câu hỏi" --date 2026-10-17` | câu trả lời + ý then chốt + citation + vết 9 bước; câu trùng câu mẫu hiện đúng mã (vd. Q042), câu khác được cấp mã `EXT-xxxx` |
| Hỏi khi không rõ ngày | `python policyassist.py ask "Câu hỏi" --date none` | ABSTAIN nếu văn bản liên quan có nhiều phiên bản |
| Xuất file nộp | `python policyassist.py batch` | `outputs/submission.csv` + checklist README mục 11 |
| Chạy bộ câu hỏi khác | `python policyassist.py batch --questions duong_dan.csv --out ket_qua.csv` | CSV cùng schema |
| Kiểm tra file nộp (độc lập) | `python validate_submission.py` (hoặc `python validate_submission.py duong_dan.csv`) | 23 kiểm tra PASS/WARN/FAIL; mã thoát 0 = đạt |
| Đánh giá đầy đủ (khoảng 1–2 phút) | `python policyassist.py eval` | 7 KPI trên **Dev-30, Ext-60, Public-90, Stress-60, Probe-25, Paraphrase-52** + B0 + kiểm định ghép cặp + CI 95% + ablation B0→B6 + bảng lỗi + demo → `outputs/eval_report.md`, `kpi_table.csv`, … (mục 9) |
| Chạy 4 kịch bản demo | `python policyassist.py demo` | citation, độ tin cậy, latency, `trace_id` của case A, B1, B2 (3 mốc ngày), C |
| Kiểm thử chịu tải Stress-60 (riêng) | `python policyassist.py stress` | `outputs/stress60_report.md`, `stress60_results.csv` (từng câu), `stress60_summary.csv` |
| Kiểm tra toàn vẹn Data Pack | `python policyassist.py verify` | bảng 21 kiểm tra (I01–I16) + fingerprint |
| Tạo lại manifest (chỉ khi BTC phát hành Data Pack mới) | `python policyassist.py manifest` | `data/corpus_manifest.csv/.json` |

Ví dụ:

```bash
python policyassist.py ask "Nếu hóa đơn điện tử đã lập bị sai mã số thuế, số tiền hoặc thuế suất thì phương án xử lý hiện hành là gì?" --date 2026-10-17
```

> Lệnh `batch` **dừng lại (mã thoát 2)** nếu Data Pack không khớp manifest – để bảo đảm kết quả nộp được tạo từ đúng dữ liệu BTC. Dùng `--allow-modified` chỉ khi chủ động thử nghiệm.

---

## 5. Hướng dẫn sử dụng giao diện

Giao diện tông **xanh navy**, bố cục như các ứng dụng chat AI. Thanh trên cùng có 5 trang: **Hỏi đáp · Xuất bài nộp · Đánh giá KPI · Kho tài liệu · Nhật ký & toàn vẹn**.

Trang Hỏi đáp dành gần hết bề ngang cho vùng hội thoại (~77% khi panel nguồn đang mở, toàn bộ khi panel đóng); tiêu đề phiên và các chip Data Pack gom vào một dòng mỏng để khung hội thoại cao gần bằng màn hình. Panel **Nguồn trích dẫn** chỉ hiện khi bấm một chip nguồn. Biểu tượng trên giao diện dùng bộ icon Material Symbols có sẵn trong Streamlit (không dùng emoji).

### Cột bên trái – phiên tra cứu và lịch sử

- Logo cán cân ⚖ và tên ứng dụng ở đầu cột.
- **Ô tìm kiếm** (trên cùng, ngay dưới logo): kết quả cập nhật theo **từng ký tự gõ** – kể cả khi bộ gõ tiếng Việt đang ghép chữ, không phải gõ hết từ – trong **tên phiên, câu hỏi và câu trả lời** của mọi phiên đã lưu.
  - Không phân biệt hoa/thường; gõ có dấu hay không dấu đều được (*hoa don* tìm ra *Hóa đơn*) và cho cùng kết quả (221/221 câu kiểm thử giống nhau về quyết định, nguồn, mốc); hiểu viết tắt (*HĐĐT, MST, GTGT…*).
  - Mỗi kết quả hiện tên phiên và đoạn trích *Hỏi: …* / *Đáp: …* chứa từ khóa, từ khóa được tô vàng.
  - Bấm một kết quả: mở phiên, cuộn tới đúng câu hỏi chứa từ khóa (bấm chip nguồn để xem nguồn ở panel bên phải). Bấm nút xoá trong ô (hoặc phím Esc) để quay lại lịch sử.
- **Tra cứu mới** (nút vàng, dưới ô tìm kiếm): mở một phiên mới. Mỗi phiên chứa **nhiều câu hỏi** nối tiếp như một cuộc hội thoại.
- **LỊCH SỬ TRA CỨU**: các phiên được nhóm theo ngày (*Hôm nay*, *Hôm qua*, *Thứ…*), phiên đã ghim nằm trong nhóm **Đã ghim** ở đầu. Mỗi mục hiện tiêu đề (câu hỏi đầu), giờ, số câu và số câu ABSTAIN. Bấm để mở lại toàn bộ phiên, kể cả nguồn trích dẫn.
- **Menu ⋮** của từng phiên (hiện khi rê chuột lên phiên; luôn hiện ở phiên đang mở): **Ghim / Bỏ ghim**, **Đổi tên** (hộp thoại nhập tên mới), **Xoá** (hộp thoại xác nhận; audit log vẫn giữ nguyên).
- Phiên được **lưu tự động** sau câu hỏi đầu tiên (`logs/sessions/`, câu hỏi đã che thông tin cá nhân).

### Trang Hỏi đáp

**Ô hỏi** (một khung gọn ở cuối vùng hội thoại):

- Ô câu hỏi cao một dòng, tự cao thêm khi câu dài hoặc nhiều dòng (tối đa khoảng 6 dòng); nút **Gửi** ngay bên phải (hoặc nhấn Ctrl+Enter).
- Được viết tắt (HĐĐT, TT, NĐ, MST, IT…), viết tắt khẩu ngữ (*ncc, hđ, bb, đntt, CQT…*), chen thuật ngữ tiếng Anh (*payment request, e-invoice, SoD…*) và gõ không dấu; mốc ngầm như *hôm qua, tháng trước, năm ngoái* được quy đổi theo ngày tham chiếu.
- **Hỏi nhiều câu cùng lúc**: mỗi câu một dòng; mỗi câu thành một lượt riêng trong phiên.
- **Sau khi gửi**: khung hội thoại dừng ở câu hỏi vừa gửi (không nhảy xuống cuối câu trả lời); câu trả lời hiện với hiệu ứng *Đang soạn câu trả lời* → dải PIPELINE sáng lần lượt → các khối hiện dần từ trên xuống (khoảng 1 giây; không chạy khi hệ điều hành bật giảm chuyển động).

**Hàng tùy chọn** ngay dưới ô hỏi: `Ngày tham chiếu [17/10/2026]  ☐ Tự động  …  Câu mẫu`.

Ngày tham chiếu quyết định văn bản nào còn hiệu lực:

| Lựa chọn | Cách xác định ngày | Hiển thị trên câu trả lời |
|---|---|---|
| **Ô ngày** (mặc định **17/10/2026** – ngày chụp Data Pack; gõ dd/mm/yyyy, xóa bằng nút ×, hoặc bấm biểu tượng lịch để chọn trên lịch tiếng Việt: đổi tháng/năm, *Hôm nay*, *Xóa ngày*) | Ngày trong ô; ngày nêu trong câu hỏi (vd. "tại ngày 15/05/2025") vẫn được ưu tiên | ngày đã chọn, hoặc *"lấy từ câu hỏi"* |
| **☑ Tự động** (ô ngày bị khóa) | Ngày nêu trong câu hỏi; câu không nêu ngày thì dùng **ngày hôm nay** | *"lấy từ câu hỏi"* hoặc *"tự động (hôm nay)"* |

- Nút **Câu mẫu** ở cuối hàng: chọn (gõ để tìm) 1 trong 90 câu hỏi mẫu của BTC. Câu hỏi được điền sẵn, ô ngày lấy đúng ngày tham chiếu của câu mẫu, ô *Tự động* tắt; hộp chọn tự thu lại sau khi chọn.
- Ngày sau 17/10/2026 (ngày chụp Data Pack) vẫn tra cứu được. Câu trả lời ghi chú rằng văn bản ban hành sau ngày chụp chưa có trong Data Pack.
- Khi gọi qua CLI/batch mà thiếu `reference_date`, cổng G6 vẫn ABSTAIN nếu văn bản liên quan có nhiều phiên bản (README mục 6).

**Mỗi lượt hỏi gồm:**

- **Dòng thông tin**: giờ, ngày tham chiếu, trạng thái (*Trả lời có nguồn* / *Cảnh báo phiên bản* / *ABSTAIN* / *Cần chuyên viên rà soát*) và loại câu hỏi: **Câu mẫu · Q042** hoặc **Câu ngoài bộ mẫu · EXT-0003**.
- **Bong bóng câu hỏi** màu navy. Khi câu hỏi được gõ không dấu hoặc dùng viết tắt, dòng *"↳ Hệ thống hiểu là: …"* hiện ngay bên dưới, kèm dòng *"Viết tắt: HĐ → hợp đồng · TT → thanh toán…"* để người dùng kiểm tra hệ thống hiểu đúng nghĩa.
- **Dải PIPELINE P0–P8** (một dòng): xanh là bước đã chạy, cam là bước dừng → ABSTAIN. Rê chuột lên từng bước để xem tên bước và chi tiết.
- **Thẻ trả lời:**
  - **Cảnh báo phiên bản** (đỏ): khi trả lời theo một ngày cũ mà văn bản làm căn cứ đã bị thay thế, kèm văn bản hiện hành tại 17/10/2026.
  - **Dòng thời gian hiệu lực**: chuỗi văn bản (vd. LAW09 → LAW06 → LAW12), mũi tên đánh dấu văn bản dùng cho ngày được hỏi.
  - **KẾT LUẬN**: trả lời thẳng câu hỏi, luôn là câu *nguyên văn* của căn cứ đã dẫn:
    - câu có/không → **Có.** / **Không.** khi căn cứ nói rõ được/không được làm điều được hỏi;
    - câu hỏi con số → câu chứa con số; câu "vì sao" → câu nêu lý do;
    - tình huống → dòng tình huống khớp nhất (*… → HOLD_MISSING_DOCS*) hoặc trọn mục "Hướng xử lý" của sổ tay;
    - câu hỏi phiên bản → văn bản áp dụng tại mốc.
  - **CĂN CỨ PHÁP LUẬT** (xanh) và **QUY TRÌNH NỘI BỘ** (tím, nhãn *Nova Việt – tài liệu nội bộ giả lập*). Câu khớp kết luận được tô vàng. Số hiệu văn bản, ngày, con số/thời hạn, mã trạng thái và từ cấm/giới hạn ("không được", "không vượt quá"…) được tô đậm.
  - **LƯU Ý HIỆU LỰC**: văn bản được chọn theo ngày, văn bản bị thay thế, tài liệu nội bộ dẫn chiếu luật đã hết hiệu lực.
- **Chip nguồn `[1] LAW12 – Điều 10 khoản 1 điểm b`**: bấm để mở nguồn ở **panel bên phải** (panel chỉ hiện khi đang mở một nguồn; nút **Đóng** thu panel lại, vùng hội thoại giãn hết bề ngang).
- **Chân thẻ**: độ tin cậy (màu theo ngưỡng), thời gian xử lý, **Hữu ích / Chưa đúng** (ghi `logs/feedback.jsonl`), **Chi tiết** (Pipeline trace, Evidence Ledger, cổng G1–G7, Citation Audit).
- **Thẻ ABSTAIN** (viền đứt): câu mở đầu chuẩn *"Không đủ căn cứ trong Data Pack để xác định …"* nêu rõ điều không xác định được (vd. *"… mã số thuế chính thức của Công ty Cổ phần Nova Việt"*; không tách được thì *"thông tin này"*), lý do, bước dừng, "Không có nguồn dẫn".
  - **Gợi ý hỏi lại**: các câu mẫu cùng chủ đề mà Data Pack có căn cứ, bấm để hỏi ngay.
  - Nếu ABSTAIN vì thiếu ngày: nút *Hỏi lại với ngày 17/10/2026*.

**Panel "Nguồn trích dẫn"** (bên phải):

- Nhãn loại nguồn và nhãn hiệu lực tại ngày tham chiếu, vd. *Đang hiệu lực tại 15/05/2025* + *Đã bị thay thế từ 01/06/2025*.
- Citation, tiêu đề điều khoản, tên văn bản; `chunk_id`, mức ưu tiên, hiệu lực từ/đến, trạng thái, vị trí.
- **ĐOẠN GỐC**: phần được trích vào câu trả lời được tô sáng.
- **CHUỖI PHIÊN BẢN** (văn bản luật) hoặc **DẪN CHIẾU TRONG METADATA** (tài liệu nội bộ, kèm trạng thái của từng văn bản được dẫn).
- **Xem toàn văn bản trong Data Pack**: hộp thoại toàn văn tài liệu, tự cuộn tới đoạn được trích dẫn (tô vàng).
- **Nguồn gốc ↗** và **Đóng** (hai nút cùng cỡ, chung một hàng): *Nguồn gốc* mở trang văn bản gốc theo `source_url`; tài liệu nội bộ giả lập không có nguồn ngoài nên nút bị mờ.

### Các trang khác

| Trang | Nội dung |
|---|---|
| **Xuất bài nộp** | **Chạy 90 câu hỏi và xuất submission.csv** (hoặc tải CSV câu hỏi khác) → thống kê, bảng **đúng 8 cột như file**. Hai nút **Tải CSV** (file nộp BTC) và **Tải Excel** nằm bên phải, cùng hàng với nút chạy; chạy xong là tải được ngay. File luôn được đọc lại như máy chấm trước khi lưu/tải; nếu sai định dạng, trang báo lỗi và khóa nút tải. |
| **Đánh giá KPI** | **▶ Chạy đánh giá** (~1–2 phút: đủ 6 tập + ablation) → 7 ô KPI trên Dev-30 + Probe-25, 4 ô mỗi hàng: giá trị, Đạt/Chưa đạt, mục tiêu, chênh lệch với baseline B0, và một dòng chỉ số kèm (MRR, thang 0/0,5/1, P/R, số câu, p95…). Mục **So sánh trực quan** có 4 phần. (1) **Hệ thống so với baseline B0**: thanh ngang theo cặp cho 6 KPI, vạch đen là mục tiêu. (2) **KPI theo tập đánh giá**: Dev-30 / Ext-60 / Stress-60 trên cùng thang. (3) **Mỗi khối của pipeline đóng góp gì?**: bảng thêm dần B0 → B6 (+ B2′), ô xanh đậm dần theo mức KPI tăng ở bước đó. (4) **Bỏ từng thành phần**: ô đỏ = KPI kém đi, ô xám = các thành phần còn lại bù được. Mỗi phần có câu kết luận rút từ số liệu, chú giải và tooltip; số liệu gốc ở mục *Bảng số liệu*. Khi chưa chạy, trang hiện kết quả lần gần nhất trong `outputs/`. |
| **Kho tài liệu** | Chọn ngày → trạng thái hiệu lực của 20 tài liệu; dòng thời gian của 3 chuỗi phiên bản; mở toàn văn / nguồn gốc từng tài liệu. |
| **Nhật ký & toàn vẹn** | **Nhật ký tra cứu**: thống kê, biểu đồ **Kết quả theo loại câu hỏi** (tỷ lệ trả lời có nguồn / ABSTAIN cho từng loại: pháp luật, nội bộ, kết hợp, hiệu lực/phiên bản, ngoài phạm vi) và bộ lọc *Tất cả / Câu mẫu / Câu ngoài / ABSTAIN / Cần rà soát*. Cột chính: thời gian, **loại câu hỏi (Câu mẫu / Câu ngoài)**, **mã câu (Q0xx hoặc EXT-xxxx)**, câu hỏi, ngày áp dụng, kết quả, tin cậy, số nguồn, ms. Các tab còn lại: **Phản hồi**; **Toàn vẹn Data Pack** (I01–I16, manifest SHA-256). |

---

## 6. Toàn vẹn dữ liệu Data Pack

- Toàn bộ Data Pack được đặt **nguyên bản** trong `data/DataPack-CASE1_PolicyAssist/` – chương trình **chỉ đọc**, không sửa hay chia lại chunk (giữ khớp `chunk_id` ↔ `citation_map`).
- `data/corpus_manifest.csv` lưu **SHA-256 của 40 file**; `data/corpus_manifest.json` lưu phiên bản `v1-snapshot-2026-10-17`, **corpus fingerprint** `7357afec5ef0…` và số lượng (20 tài liệu = 12 LAW + 8 SIM, 374 chunk, 90 câu hỏi, 30 đáp án) – đúng tinh thần README mục 13 ("giữ lại corpus_manifest để đối chiếu").
- Mỗi lần khởi động (giao diện, `ask`, `batch`, `eval`) chương trình chạy kiểm tra:

| Mã | Kiểm tra |
|---|---|
| I01–I03 | Đủ file theo manifest, SHA-256 khớp, không có file lạ |
| I04 | Có đủ file bắt buộc (metadata, chunks, citation_map, câu hỏi, template; đáp án mẫu là tùy chọn) |
| I05–I07 | 20 tài liệu (12 LAW + 8 SIM); 374 chunk, `chunk_id` duy nhất; mọi chunk thuộc tài liệu có metadata |
| I08 | `citation_map` khớp 1-1 với chunk và đúng `citation_label` |
| I09–I11 | 90 câu hỏi, id duy nhất, `reference_date` hợp lệ; đáp án mẫu thuộc bộ câu hỏi; template đúng cột và đủ `question_id` |
| I12–I13 | `effective_from ≤ effective_to`; các cạnh thay thế (`supersedes`/`superseded_by`) trỏ tới tài liệu có thật |
| I14 | Fingerprint khớp `corpus_manifest.json` |
| I15 | 30 đáp án mẫu **nối đúng** câu hỏi (nội dung, `reference_date`) → `relevant_chunk_ids` có thật → đúng `citation_labels` và `relevant_document_ids`; câu ABSTAIN không kèm chunk/citation |
| I16 | Trạng thái hiệu lực CHRONOS tự tính cho từng chunk tại 17/10/2026 **khớp cờ `is_current_as_of_2026_10_17`** trong `citation_map.csv` của BTC – 374/374 chunk |

- Mọi bản ghi audit log và báo cáo KPI đều ghi kèm fingerprint → biết chính xác kết quả được tạo từ phiên bản dữ liệu nào.
- **Khi BTC phát hành Data Pack mới:** thay thư mục `data/DataPack-CASE1_PolicyAssist/`, chạy `python policyassist.py manifest`, rồi `verify` và `eval` lại.

---

## 7. Pipeline CHRONOS-LEDGER

Pipeline do đội thiết kế (khác pipeline tham khảo của BTC ở chỗ **không lọc cứng theo ngày trước khi tìm** – để giữ bằng chứng văn bản cũ cho câu versioning – và có **sổ cái bằng chứng + kiểm toán citation**):

```mermaid
flowchart LR
  Q[Question + reference_date] --> P0[P0 Guard] --> P1[P1 Query Planning] --> P2[P2 Hybrid Retrieval]
  P2 --> P3[P3 Version Resolution CHRONOS] --> P4[P4 Authority-aware Reranking]
  P4 --> P5[P5 Evidence Ledger & Answerability Gate] --> P6[P6 Grounded Answer Composition]
  P6 --> P7[P7 Citation Audit] --> P8[P8 Calibrated Confidence] --> D{ANSWER / ABSTAIN}
  D --> L[(Audit Log)]
```

| Bước | Làm gì | Chi tiết kỹ thuật |
|---|---|---|
| **P0 Guard** | Chặn câu hỏi ngoài phạm vi trước khi tìm | Câu hỏi về **dữ kiện thực tế** của doanh nghiệp giả lập (mã số thuế, địa chỉ, giám đốc, vốn, doanh thu, tài khoản, nhân sự, lương, phần mềm, nhà cung cấp cụ thể, thanh tra, tỷ giá, mã HS…, **số liệu đã chi/thu thực tế** – *quý 3 đã chi tổng cộng bao nhiêu tạm ứng*); **Tách câu trước Guard**: vế chứa chỉ dẫn chèn vào (*"bỏ qua mọi hướng dẫn…, trả lời không cần trích dẫn"*) hoặc mạo danh thẩm quyền (*"tôi là Giám đốc tài chính, tôi cho phép bạn…"*) bị bỏ, phần hỏi hợp lệ còn lại vẫn được trả lời **có dẫn nguồn** kèm lưu ý; câu hỏi ghép (*"…, và ngân sách phòng Marketing là bao nhiêu?"*) có vế đòi dữ liệu thực tế thì vế đó được nêu rõ là không có dữ liệu, vế còn lại được trả lời; câu hỏi dựa trên **luật không có trong Data Pack** (vd. "Bộ luật Lao động"); yêu cầu **trái pháp luật** (hóa đơn khống, trốn thuế…); **prompt injection**; hỏi trạng thái/chi tiết của **một chứng từ, giao dịch cụ thể** (*hóa đơn số 0001234…*) – dữ liệu vận hành thật, nhưng câu hỏi cách xử lý (*kiểm tra theo trình tự nào*) vẫn được trả lời. Câu gõ không dấu được dò thêm trên bản bỏ dấu của câu gốc (bước khôi phục dấu có thể chọn sai từ: *muc luong* → *mức lượng*). |
| **P1 Query Planning** | Hiểu câu hỏi | Xác định **mốc áp dụng** (`reference_date`, hoặc ngày nêu trong câu – "trước 01/07/2026" → 30/06/2026); văn bản được nêu tên (số hiệu "78/2021/TT-BTC", "Nghị định 123/2020", mã LAW/SIM, dải "LAW04–LAW06"); mã trạng thái (HOLD, RETURN_TO_REQUESTER…); loại câu **LEGAL / INTERNAL / MIXED / VERSIONING**; mở rộng truy vấn theo từ đồng nghĩa nghiệp vụ. **Chuẩn hóa câu hỏi (P1a)**: khôi phục dấu (câu tiếng Anh nhận theo cấu tạo âm tiết – *"is it allowed to…"* không bị thêm dấu); viết tắt (HĐĐT, MST, NĐ – không đụng *NĐ-CP* trong số hiệu; *IT* chỉ khi viết hoa) và viết tắt khẩu ngữ (*ncc, bb, đntt, CQT, NNT, KTT, DN, UQ, VBHN, QLT, BHXH, TSCĐ, hs…*; *Mã HS* giữ nguyên). **Viết tắt nhiều nghĩa** chọn nghĩa theo ngữ cảnh: HĐ (*gửi HĐ* → hóa đơn, *HĐ quy định*, *ký/thanh lý HĐ* → hợp đồng), TT (*theo TT hiện hành* → Thông tư, *hồ sơ TT* → thanh toán), NV, KT (*KT nội bộ* → kiểm toán), CT (*đi CT* → công tác, *CT gốc* → chứng từ), CP, QĐ, KH, CK, TM – dấu hiệu ở từ đứng ngay trước/sau, rồi mức đồng xuất hiện với các từ còn lại của câu trong Data Pack, cuối cùng là nghĩa thường gặp nhất. Từ đồng nghĩa không bị thay khi Data Pack dùng đúng cụm đó (*"giấy tờ hoặc vật mang tin"* giữ nguyên); thuật ngữ tiếng Anh nghiệp vụ (*payment request, e-invoice, approver, SoD, supplier…*; mã trạng thái có trong Data Pack như REJECT, URGENT giữ nguyên). **Lời đệm khẩu ngữ** (*nói ngắn gọn, giúp mình, vậy, nhé…*) và cụm "văn bản nào" bị bỏ khi tìm kiếm và khi tính độ phủ (G2, G3, G5, G7). **Mốc ngầm** (*hôm nay, hôm qua, tháng trước, năm ngoái, tháng 3 năm ngoái*) được quy đổi theo `reference_date` kèm cảnh báo; khoảng thời gian (*05 năm trước khi…*) không bị hiểu nhầm là mốc. |
| **P2 Hybrid Retrieval** | Tìm ứng viên | **BM25** trên âm tiết + cặp âm tiết + số hiệu văn bản (tiếng Việt viết theo âm tiết) ⊕ **TF-IDF ký tự 2–5-gram** (bắt biến thể từ); pool 40 + chunk của văn bản được nêu tên + chunk chứa mã trạng thái được hỏi. |
| **P3 CHRONOS** | Đúng phiên bản theo thời gian | Hiệu lực tính ở **cấp chunk** (`effective_from/to`, `status`, fallback metadata văn bản): VALID / EXPIRED / NOT_YET / REFERENCE_ONLY (văn bản hợp nhất) / INTERNAL. **Đồ thị thay thế** từ `supersedes/superseded_by` (LAW09→LAW06→LAW12; LAW07, LAW08, LAW05→LAW11; LAW04→LAW10). Chunk đã hết hiệu lực xếp cao → kéo **điều khoản tương ứng của văn bản kế nhiệm** (độ tương đồng cosine). Tài liệu nội bộ dẫn chiếu luật đã hết hiệu lực → kéo căn cứ **pháp luật kế nhiệm còn hiệu lực** (README mục 2). |
| **P4 Authority-aware Reranking** | Đúng thứ bậc nguồn | **Pháp luật còn hiệu lực → quy chế/quy trình → sổ tay/FAQ**; FAQ/sổ tay là nguồn thứ cấp: dòng "Nguồn ưu tiên: …" của chúng được dùng để **truy về điều khoản gốc** (PRF – dùng phần trả lời của FAQ làm truy vấn mở rộng); **cấu trúc Điều** (các khoản/điểm cùng Điều đi cùng nhau); câu versioning luôn có **điều khoản hiệu lực/phạm vi** của từng văn bản được hỏi; câu MIXED luôn có cả nguồn pháp luật và nội bộ. Đoạn sổ tay/FAQ **khớp câu hỏi nhất** (độ liên quan gốc cao nhất trong mọi ứng viên) luôn có mặt trong top-5 – thay chỗ đoạn ít tự liên quan nhất từ hạng 3 trở đi, đoạn bị thay vẫn được cổng đủ căn cứ xét – vì nhiều tình huống nghiệp vụ (*khách chưa nhận hóa đơn*, *đổi tài khoản thụ hưởng*, *milestone chưa đạt*) chỉ sổ tay SIM07 mô tả. Sổ tay/FAQ chỉ làm căn cứ chính khi không có điều khoản pháp luật còn hiệu lực tự bao quát câu hỏi, và không khi sổ tay chỉ nêu các phương án (*HOLD hoặc RETURN_TO_REQUESTER*) mà điều khoản quy trình gốc trong top-5 đã định nghĩa. |
| **P5 Evidence Ledger & Gate** | Có đủ căn cứ không? | Sổ cái top-k: vai trò (căn cứ pháp luật / nội bộ / lịch sử / tham khảo), trạng thái hiệu lực, từ khóa khớp, văn bản kế nhiệm, dẫn chiếu lỗi thời. **6 cổng**: G1 có bằng chứng · G2 độ phủ từ khóa (trọng số IDF) ≥ 0,58 · G3 độ phủ cụm từ ≥ 0,25 · G4 có căn cứ còn hiệu lực tại mốc · G5 có một chunk bao quát câu hỏi · **G6 xác định được thời điểm** (thiếu ngày + văn bản có nhiều phiên bản → ABSTAIN, README mục 6). Sau P7 còn **G7 căn cứ trả lời đúng điều được hỏi**: câu hỏi có thuật ngữ chủ đề nhiều âm tiết (thuế GTGT, thuế TNDN, hóa đơn điện tử, mã số thuế, báo cáo tài chính…) thì các đoạn được trích dẫn phải phủ ≥ 0,35 (trọng số IDF) phần còn lại của câu hỏi – không trả lời bằng đoạn chỉ khớp chủ đề (vd. hỏi *thời hạn khai thuế GTGT* mà Data Pack chỉ có *các loại hóa đơn GTGT*). |
| **P6 Grounded Composition** | Soạn câu trả lời không bịa | **Trích xuất** nguyên văn từ chunk (không sinh tự do); chọn **căn cứ chính** + chỉ thêm chunk vừa tự liên quan vừa bổ sung ý mới (con số được hỏi – *5 năm, 10 năm* – phải nằm trong nội dung chunk, không tính số trong nhãn *khoản 5*). **KẾT LUẬN trước**: theo dạng câu hỏi – câu có/không (động từ chính của vị ngữ được hỏi; *không được/chưa/cấm* ngay trước → **Không.**, *được/phải* → **Có.**; *"chỉ được … khi … không liên quan đến … kiểm toán"* mà tình huống đang thuộc kiểm toán → **Không.**), con số, lý do, dòng tình huống, mục "Hướng xử lý" (không bao giờ lấy dòng *"Tình huống: …"* chỉ nhắc lại tình huống; *"có quyền sửa"* xét động từ *sửa*); không đủ dấu hiệu thì không nêu Có/Không. Tiêu đề mục (*"Hướng xử lý nội bộ:"*) không trích trơ khi nội dung đã nêu ở KẾT LUẬN. **Chỉ trích câu trả lời đúng điều được hỏi**: đoạn ngắn (≤ 300 ký tự hoặc ≤ 3 câu), quy trình, FAQ/sổ tay (bỏ dòng nhắc lại tình huống), danh sách đúng chủ đề câu hỏi liệt kê, và điều khoản ≤ 5 mục với câu hỏi mở được giữ trọn; danh sách dài/bảng chỉ giữ câu/dòng có điểm ≥ 0,5 (bảng 0,8) × câu tốt nhất, kèm tiêu đề và trọn nhóm mục. **Sổ tay/FAQ làm căn cứ chính** (tình huống chỉ sổ tay mô tả trực tiếp): dẫn kèm quy chế/quy trình hoặc văn bản pháp luật mà chính sổ tay/FAQ ghi ở dòng "Nguồn tra cứu ưu tiên" (nếu đã có trong top-5) và trình bày nguồn gốc trước sổ tay – README mục 2 (pháp luật → quy chế/quy trình → sổ tay/FAQ). **Câu hỏi yêu cầu nêu quy trình** (*hãy nêu quy trình…*, *theo trình tự nào*) mà căn cứ pháp luật trong top-k liên quan không kém quy trình nội bộ: câu trả lời gồm quy trình nội bộ được hỏi (trích trọn các bước) + căn cứ pháp luật liên quan + **điều khoản pháp luật tương ứng với bước quy trình** (gần nhất theo TF-IDF ký tự, cùng ngưỡng 0,25 của điều khoản tương ứng ở văn bản kế nhiệm); pháp luật trước, nội bộ sau – vd. Q042 cho đủ 3 citation của đáp án BTC. **Câu hỏi có/không** (*có được sửa trực tiếp … không?*) mà các căn cứ đã chọn chưa nói rõ được/không được: nếu trong 10 ứng viên xếp đầu có một câu quy định **vô điều kiện** nói rõ điều đó (phủ ≥ 70% vị ngữ được hỏi và ≥ 35% từ khóa cả câu hỏi theo IDF; không nêu điều kiện, ngoại lệ, ngưỡng số hay mã trạng thái mà câu hỏi không nhắc), đoạn đó được đưa vào top-5 thay đoạn ít tự liên quan nhất từ hạng 3 và câu đó làm KẾT LUẬN kèm **Có.** / **Không.** – vd. Q042 thêm *“Hóa đơn đã phát hành không được sửa trực tiếp dữ liệu gốc.”* (FAQ04). Câu quy định có điều kiện (*“trên 80% phải có cấp phê duyệt cao hơn”*) không được dùng để tự kết luận vì còn phải đối chiếu tình huống. Câu không nêu phạm vi (mặc định ưu tiên pháp luật) mà **không đoạn pháp luật nào tự bao quát câu hỏi** (ngưỡng G5) trong khi quy trình nội bộ thì có → quy trình nội bộ làm căn cứ chính, kèm cảnh báo (README mục 2: thứ tự ưu tiên áp dụng *khi nhiều nguồn cùng liên quan*). **Điều khoản tự giới hạn trong tài liệu của nó** (*"Khi có khác biệt giữa SIM05 với văn bản pháp luật…"*, *"giữa tài liệu này và…"*) không đại diện nguyên tắc chung khi câu hỏi không nêu tài liệu đó: hệ số như chunk điều hướng – vd. Q070 dẫn nguyên tắc chung SIM01 – Điều 16 thay vì điều khoản riêng của SIM05. Xử lý **phủ định** ("không sai mã số thuế…"); câu versioning: mệnh đề hiệu lực từ metadata ("Tại ngày …, nguồn cần ưu tiên áp dụng là …; X đã hết hiệu lực từ …, được thay thế bởi …") + trích điều khoản hiệu lực; câu MIXED tách "Căn cứ pháp luật" / "Quy trình nội bộ". Mỗi ý gắn `[n]`. |
| **P7 Citation Audit** | Kiểm tra lại citation trước khi trả lời | C1 có trong `citation_map` · C2 nằm trong top-k đã truy xuất · C3 hỗ trợ nội dung (≥ 90% từ của ý có trong chunk; mệnh đề hiệu lực khớp metadata) · C4 phù hợp `reference_date`. Citation không đạt bị loại; không còn citation → ABSTAIN. |
| **P8 Calibrated Confidence** | Độ tin cậy | Logistic trên độ phủ, độ phủ cụm, chunk tốt nhất, tỷ lệ citation qua kiểm toán, hiệu lực căn cứ chính, độ tách biệt điểm. Brier 0,010 / ECE 0,062 trên Dev-30 + Probe-25 (baseline B0: 0,383 / 0,432). < 0,35 → ABSTAIN; < 0,60 → gắn cờ **cần chuyên viên rà soát**. |

---

## 8. Đầu ra submission

`outputs/submission.csv` đúng định dạng **`submission_output_template.csv`**:

- UTF-8 có BOM, xuống dòng CRLF như template; tiêu đề và thứ tự `question_id` giống hệt template.
- **Đúng 8 cột theo thứ tự**, **mỗi câu hỏi đúng MỘT dòng**: câu trả lời nhiều ý được gộp thành một dòng.
- **Giống hệt cách ghi của ví dụ README mục 5**:
  - 4 cột văn bản/danh sách (`answer`, `retrieved_document_ids`, `retrieved_chunk_ids`, `citations`) đặt trong ngoặc kép `"…"`, nên dấu phẩy trong câu trả lời không tách cột;
  - `confidence`, `abstain`, `latency_ms` không có ngoặc kép; ô trống để trống;
  - ngoặc kép bên trong nội dung (nếu có) viết thành `""` theo chuẩn CSV.

```csv
question_id,answer,retrieved_document_ids,retrieved_chunk_ids,citations,confidence,abstain,latency_ms
Q001,"Chứng từ kế toán là giấy tờ …, tài chính đã phát sinh … [1] Nguồn: [1] LAW01 – Điều 3 khoản 3. …","LAW01;LAW03","LAW01_C001;LAW01_C006;LAW01_C014;LAW03_C001;LAW03_C002","LAW01 – Điều 3 khoản 3",0.971,FALSE,14
Q077,"Không đủ căn cứ trong Data Pack để xác định thông tin này.",,,,0.05,TRUE,1
```

| Cột | Nội dung |
|---|---|
| `question_id` | giữ nguyên |
| `answer` | **"Kết luận: …"** trước (có "Có."/"Không." với câu có/không khi căn cứ nói rõ), rồi phần căn cứ chỉ gồm các câu trả lời đúng điều được hỏi; mỗi câu gắn `[n]`, "Nguồn: …", lưu ý (nếu có), câu miễn trừ – một dòng. ABSTAIN: mở đầu đúng câu chuẩn README "Không đủ căn cứ trong Data Pack để xác định …", nêu rõ điều không xác định được; câu hỏi đòi dữ liệu thực tế của Nova Việt kèm lý do (doanh nghiệp giả lập). |
| `retrieved_document_ids` | tài liệu theo thứ tự retrieval, phân cách `;` |
| `retrieved_chunk_ids` | chunk theo **đúng thứ tự ranking**, phân cách `;` |
| `citations` | `citation_label` lấy **đúng từ `citation_map.csv`**, chỉ các citation thực sự dùng trong câu trả lời |
| `confidence` | số thực [0, 1] |
| `abstain` | `TRUE` / `FALSE` (ABSTAIN để trống retrieved/citations như ví dụ README) |
| `latency_ms` | thời gian xử lý câu hỏi (ms) |

> **Mở `submission.csv` bằng Excel thấy một số dòng bị tách cột?**
> - Máy đặt định dạng Việt Nam (dấu thập phân là dấu phẩy) thì Excel tách CSV tại dấu `;`.
> - Dòng không có `;` (vd. Q077, template, ví dụ README) nằm trọn 1 cột. Dòng có danh sách nhiều chunk/citation phân cách `;` (bắt buộc theo README mục 5) bị Excel tách tại `;`.
> - File đáp án mẫu của chính BTC (`answer_key_sample.csv`) cũng bị tách y hệt: 24/30 dòng.
> - File CSV vẫn đúng chuẩn – máy chấm (và Python/pandas) đọc đúng 8 cột.
> - Để xem bằng Excel, mở **`outputs/submission.xlsx`** (cùng giá trị từng ô, đúng 8 cột).
> - **Không mở rồi Save file CSV bằng Excel trước khi nộp** – Excel sẽ ghi lại bằng `;` và `0,971`, làm sai định dạng BTC.
> - Nếu file đang mở trong Excel, chương trình không ghi đè được và sẽ báo "Đóng file rồi chạy lại".

**Kiểm tra độc lập trước khi nộp:** `python validate_submission.py` – script riêng, chỉ dùng thư viện chuẩn Python (không dùng chung mã với bên tạo file), 23 kiểm tra: UTF-8, đúng 8 cột/thứ tự template, mỗi câu một dòng, đủ và không trùng `question_id`, `confidence` ∈ [0,1], `abstain` TRUE/FALSE, `latency_ms` nguyên dương, ABSTAIN mở đầu *"Không đủ căn cứ trong Data Pack để xác định…"* và để trống 3 cột ID/citation, ANSWER có đủ citation, phân cách `;`, chunk/tài liệu tồn tại và khớp nhau, thứ tự tài liệu theo hạng chunk (quy định 6), citation có trong `citation_map.csv` và **ứng với chunk đã truy xuất** (quy định 8), citation còn hiệu lực tại `reference_date` (cảnh báo – câu hỏi về phiên bản được dẫn văn bản lịch sử như đáp án Q059 của BTC), latency TB/p95. Bản nộp hiện tại: **0 lỗi, 1 cảnh báo** (6 citation lịch sử ở câu versioning).

Lệnh `batch` cũng tự kiểm **checklist README mục 11**, kèm bước **đọc lại file như máy chấm và so từng ô với bảng kết quả** (`check_submission_file`); file không đạt sẽ không được ghi:

- CSV UTF-8; đúng tên/thứ tự cột; **mỗi câu một dòng, 8 ô**; **mỗi dòng đúng mẫu ví dụ README mục 5** (`Q001,"…","…","…","…",0.93,FALSE,842`).
- Không thiếu/không trùng `question_id`; confidence ∈ [0,1]; abstain chỉ TRUE/FALSE.
- Phân cách `;`; chunk tồn tại và giữ thứ tự; citation tồn tại trong `citation_map.csv`.
- ABSTAIN không kèm citation; latency là số nguyên dương.

---

## 9. Đánh giá KPI – cách đo và tái lập

**Tập đánh giá**

| Tập | Nguồn | Nội dung |
|---|---|---|
| Dev-30 | `answer_key_sample.csv` của BTC | 26 câu ANSWER (LEGAL, INTERNAL, MIXED, VERSIONING) + 4 câu ABSTAIN |
| Probe-25 | `data/eval/probe_questions.csv` (đội tự xây) | 14 câu ngoài phạm vi (ngoài lĩnh vực, dữ kiện thực tế, luật không có trong Data Pack, trái pháp luật/prompt injection) · 5 câu diễn đạt lại · **6 câu versioning ở mốc ngày khác bộ public** (cột `expected_documents` lấy từ metadata hiệu lực) |
| Ext-60 | `data/eval/ext60_labels.csv` (đội gán) | 60 câu public chưa có đáp án BTC (50 ANSWER + 10 ABSTAIN). Hành vi và phạm vi = nhãn chốt sau khi 2 người gán độc lập và hội chẩn 5 câu bất đồng; chunk chính + ý chính = người gán 1; chunk bổ trợ = người gán 1 + 2; ghi chú chấm = người gán 2. Theo 10 cột của `answer_key_sample.csv` + `supporting_chunk_ids`, `trap_chunk_ids` |
| Public-90 | Dev-30 + Ext-60 | toàn bộ 90 câu public có nhãn; thêm hiệu lực citation, số câu ABSTAIN, latency trên file nộp |
| Paraphrase-52 (độ bền) | `data/eval/paraphrase_questions.csv` | 42 câu diễn đạt lại câu mẫu (từ đồng nghĩa, viết tắt, versioning ở cách hỏi khác) + 10 câu phải ABSTAIN (dữ kiện thật kiểu hỏi mới, ngoài lĩnh vực) |
| Stress-60 (chịu tải, câu khó của đội) | `data/eval/stress60_labels.csv` | 60 biến thể của câu Ext-60, 14 kiểu: diễn đạt khẩu ngữ, không dấu, viết tắt/chen tiếng Anh, tiền đề sai, mồi văn bản hết hiệu lực, mốc chuyển giao hiệu lực, mốc ngầm ("năm ngoái", "hôm nay"), chèn lệnh, gần phạm vi nhưng không có dữ liệu, một phần ngoài phạm vi, nhiều bước, bẫy số, câu mơ hồ; 52 ANSWER + 8 ABSTAIN, nhãn của người gán 2 (30 nhãn còn nháp, kế thừa từ câu gốc). Đã dùng để phân tích lỗi (24/10 và 10/11/2026) nên không còn hoàn toàn độc lập. |

**Định nghĩa** (đúng README mục 9 và đề thi mục 6):

1. **Retrieval Recall@5** = |chunk đáp án ∩ 5 chunk đầu của `retrieved_chunk_ids`| / |chunk đáp án|, trung bình trên câu ANSWER (câu bị ABSTAIN tính 0 – đo đúng trên file nộp). Kèm **MRR@5** (1/hạng chunk đúng đầu tiên) và **Recall@5 theo văn bản**.
2. **Answer Accuracy / Correctness** = tỷ lệ từ khóa nội dung của `reference_answer` có trong câu trả lời (độ phủ ý chính, ABSTAIN tính 0). Kèm **thang 0 / 0,5 / 1** của báo cáo mục 5 (chấm tự động: ≥ 0,70 → 1; 0,40–0,70 → 0,5; còn lại → 0) và ROUGE-L. Đây là **proxy tự động** – điểm chính thức chấm tay theo `grading_note` (có sẵn trong `outputs/eval_results_all.csv`). Stress-60 chỉ chấm tự động các kiểu giữ nguyên đáp án câu gốc.
3. **Citation Accuracy** = trong câu đã trả lời, |citation dẫn ∩ `citation_labels` đáp án| / |citation dẫn| – **so khớp nhãn chặt**. Kèm **citation đủ 4 điều kiện** của báo cáo mục 5, kiểm tự động trên 100% citation:
   - (a) có trong `citation_map.csv`;
   - (b) ứng với chunk đã truy xuất;
   - (c) chunk chứa căn cứ cho mọi câu gắn citation (≥ 90% từ);
   - (d) còn hiệu lực tại `reference_date`.
4. **Unsupported Answer Rate** = câu đã trả lời mà (a) lẽ ra phải ABSTAIN, hoặc (b) có câu khẳng định **không được chính nguồn nó dẫn xác nhận** – kiểm bằng **bộ kiểm chứng độc lập** `verify_support()` (≥ 90% từ của câu có trong chunk được dẫn; mọi ngày hiệu lực khớp `document_metadata.csv`; không có câu thiếu nguồn), / tổng câu đã trả lời (Dev + Probe). Báo cáo kèm `evidence_mismatch_rate` (câu Dev không có citation nào trùng nhãn đáp án = 0,000, tức 0/26 câu).
5. **Abstention Quality** = F1 của lớp ABSTAIN, kèm Precision, Recall và TP/FP/FN để tự tính lại (tập không có câu ABSTAIN thì Recall ghi "—").
6. **Versioning Accuracy** = câu VERSIONING: văn bản LAW đầu tiên được dẫn còn hiệu lực tại mốc áp dụng phải thuộc tập văn bản đúng (ghi kèm số câu, vd. 6/6).
7. **Latency** = thời gian xử lý trung bình và **p95** mỗi câu, đo trong tiến trình (đã nạp chỉ mục) – cùng cột `latency_ms` của file nộp.
8. **Source Priority** (chỉ số phụ, câu MIXED). Đạt khi đủ bốn điều kiện:
   - có căn cứ pháp luật còn hiệu lực;
   - pháp luật đứng trước nội bộ;
   - không dùng văn bản hết hiệu lực hoặc văn bản hợp nhất làm căn cứ;
   - nội bộ dẫn luật cũ thì dẫn văn bản kế nhiệm hoặc cảnh báo.

**Thống kê:**
- Mọi tỷ lệ ghi kèm số câu.
- Khoảng tin cậy 95% bằng bootstrap theo câu hỏi (2000 lần, hạt giống cố định).
- So với B0 dùng kiểm định ghép cặp: McNemar chính xác cho quyết định đúng/sai, bootstrap ghép cặp cho chỉ số có điểm lẻ.
- Mọi KPI tách theo `answer_scope` (`outputs/eval_by_scope.csv`).

**Hồ sơ lần chạy:** mỗi lần `eval`/`batch` có một `run_id`, ghi vào hai nơi:
- `outputs/run_manifest.json`: sha256 mã nguồn, 2 dấu vân tay corpus, file nhãn và sha256, cấu hình, phiên bản thư viện, máy;
- từng dòng audit log, kèm `trace_id`.

Nhờ vậy số liệu trên slide đi ngược được về từng câu.

**Tái lập:** `python policyassist.py eval` (hoặc nút *Chạy đánh giá* ở trang Đánh giá KPI). Mọi tham số nằm trong `Config` của `policyassist.py`.

**Minh bạch về tinh chỉnh:** ngưỡng và trọng số được chọn khi phát triển trên Dev-30 + Probe-25; Ext-60 (thuộc bộ public), Stress-60 và Paraphrase-52 cũng đã dùng để rà lỗi, nên **không tập nào của đội còn hoàn toàn độc lập** – số đáng tin nhất để so sánh là Public-90 (bộ câu chính thức) và Stress-60 (câu khó, diễn đạt lệch); bộ câu ẩn của BTC mới là phép thử độc lập. Để hạn chế quá khớp, mỗi cải tiến chỉ được giữ nếu (i) có lý do theo nguyên tắc README/cấu trúc văn bản, (ii) cải thiện ổn định trên một vùng tham số chứ không chỉ tại một điểm, và (iii) có ablation chứng minh. Không có câu trả lời nào được viết sẵn theo `question_id`. Kết quả trên bộ câu ẩn của BTC có thể thấp hơn.

---

## 10. Đối chiếu yêu cầu

### README Data Pack của BTC

| Mục README | Yêu cầu | Đáp ứng trong chương trình |
|---|---|---|
| 1.1–1.3 | Tra cứu chunk, sinh câu trả lời, trả về nguồn | P2–P7; citation đúng `citation_label` |
| 1.4, 7 | Phân biệt hiện hành / lịch sử theo `reference_date`; dùng `effective_from/to`, `status`, `supersedes/superseded_by` | P3 CHRONOS (hiệu lực cấp chunk, đồ thị thay thế, chuỗi LAW09→LAW06→LAW12 và LAW07+LAW08→LAW11) · Versioning Accuracy 1,00 |
| 1.5, 2 | Phân biệt pháp luật / nội bộ; ưu tiên **luật còn hiệu lực → quy chế/quy trình → sổ tay/FAQ**; nội bộ dẫn luật hết hiệu lực → dùng luật phù hợp `reference_date` | P4 thẩm quyền + truy nguồn FAQ; P3 kéo luật kế nhiệm; cảnh báo "dẫn chiếu văn bản không còn hiệu lực"; câu MIXED tách hai phần |
| 1.6, 6 | ABSTAIN khi: thiếu thông tin · đòi dữ liệu doanh nghiệp thực tế · thông tin cá nhân/tài chính/vận hành · **thiếu thời điểm** | P0 Guard + cổng G1–G7 + P8; ABSTAIN đúng Q077–Q090; G6 cho câu không có ngày |
| 1.7, 5 | Xuất đúng schema submission | `batch` + checklist mục 11 + `validate_submission.py` (23 kiểm tra độc lập) |
| 3, 4 | Dùng đúng file Data Pack (`document_metadata` = `document_metadata_v3_checked`) | Loader tự nhận cả hai tên/cấu trúc |
| 4.2 | `NORMALIZED_SUMMARY` không phải nguyên văn | Câu trả lời trích chunk loại này có dòng *"Lưu ý: Nội dung văn bản pháp luật trích từ bản tóm tắt chuẩn hóa của Data Pack (NORMALIZED_SUMMARY), sát nguồn nhưng không phải nguyên văn văn bản."* |
| 4.3 | Không tự tạo citation không tương ứng chunk đã truy xuất | P7 kiểm C1 + C2 |
| 9 | 7 KPI | Mục 1 và 9 của tài liệu này |
| 10 | Tránh 10 lỗi thường gặp | (1) CHRONOS; (2) thẩm quyền; (3)(4) Citation Audit + bộ kiểm chứng độc lập; (5) chỉ trích xuất; (6)(7) Gate + Abstention F1 1,000; (8) không hard-code; (9) giữ thứ tự ranking; (10) đúng schema |
| 11 | Checklist trước khi nộp | Tự kiểm khi chạy `batch`; kiểm lại độc lập bằng `python validate_submission.py` |
| 12 | Không trình bày SIM như doanh nghiệp thật | Cảnh báo "GIẢ LẬP" trong mọi câu trả lời dùng SIM; Guard chặn câu hỏi dữ kiện thật |
| 13 | Giữ `corpus_manifest` để đối chiếu | `data/corpus_manifest.csv/.json` + kiểm tra I01–I16 |

### Tiêu chí Bronze / Silver / Gold (đề thi mục 5)

| Mức | Tiêu chí | Đáp ứng |
|---|---|---|
| Bronze | Hỏi–đáp trên Data Pack; tìm và hiển thị nguồn; trả lời có dẫn nguồn; từ chối/cảnh báo; ≥ 1 phương pháp đánh giá định lượng | ✅ toàn bộ pipeline; 7 KPI |
| Silver | Cải tiến (hybrid search, reranking, query rewriting, lọc metadata, confidence); có baseline; KPI cho thấy lợi ích | ✅ hybrid BM25⊕TF-IDF, rerank thẩm quyền, mở rộng truy vấn, CHRONOS, confidence hiệu chỉnh; baseline B0 + 7 ablation |
| Gold | Kiểm tra citation trước khi trả lời; audit log + truy vết; guardrail ngoài phạm vi; kết hợp nhiều tài liệu; giao diện mở trực tiếp nguồn; vận hành/human-in-the-loop | ✅ P7; `logs/audit_log.jsonl` (phân biệt câu mẫu/câu ngoài) + pipeline trace; P0/P5; câu MIXED/VERSIONING đa nguồn; chip citation mở panel nguồn, nút "Xem toàn văn bản trong Data Pack" + "Mở nguồn gốc"; cảnh báo phiên bản + dòng thời gian hiệu lực; lịch sử tra cứu; cờ rà soát, phản hồi Hữu ích / Chưa đúng, kiểm tra toàn vẹn khi khởi động |

### Đối chiếu kế hoạch kỹ thuật của đội

Nguồn đối chiếu: Masterplan (tab LỘ TRÌNH TỔNG QUAN, KPI & KIỂM SOÁT, KEEPTRACK), báo cáo mục 5 và 8, rà soát claim, slide skeleton, demo script.

Ký hiệu: ✅ có trong hệ thống · ⚠️ làm một phần · ⛔ không làm (có lý do) · — không phải việc của mã nguồn.

| Hạng mục trong tài liệu đội | Trạng thái | Trong hệ thống |
|---|:---:|---|
| 01 Nạp dữ liệu, kiểm 374 chunk khớp `citation_map` | ✅ | `verify` I01–I16, `corpus_manifest`, 2 dấu vân tay corpus |
| 02 Hiệu lực cấp chunk; tách mã LAWxx từ trường chữ | ✅ | hiệu lực tính tại 17/10/2026 khớp cờ `is_current_as_of_2026_10_17` của BTC **374/374** (I16) |
| 03 Đồ thị phiên bản SUPERSEDES / REFERS_TO | ✅ | P3 CHRONOS; tài liệu nội bộ dẫn luật hết hiệu lực → kéo văn bản kế nhiệm |
| 03 Silver: cạnh COUNTERPART (điều khoản cũ ↔ mới) | ✅ | tự động: điều khoản tương ứng ở văn bản kế nhiệm (cosine ≥ 0,25); chưa có bộ cặp do người kiểm |
| 04 BM25 + chỉ mục số hiệu/Điều | ✅ | BM25 âm tiết + số hiệu + cấu trúc Điều |
| 04 Silver: embedding + câu hỏi giả định | ⛔ | thay bằng TF-IDF ký tự 2–5-gram (tất định, không cần mô hình); ablation chứng minh đóng góp |
| P0 Guard: chặn injection, câu hỏi dữ liệu cá nhân | ✅ | thêm câu gõ không dấu và câu hỏi về chứng từ cụ thể |
| P1 Planning bằng luật + regex | ✅ | loại câu, mốc áp dụng, mốc ngầm, câu hỏi quy trình; LLM có JSON schema: không dùng |
| P2 Hybrid: BM25 + dense + RRF | ⚠️ | BM25 ⊕ TF-IDF ký tự (hợp nhất có trọng số); chưa có dense/RRF |
| P3 VALID / EXPIRED / NOT_YET + chuyển hướng | ✅ | so với lọc cứng theo ngày (B2′): Versioning 0,90 so với 0,60 trên Public-90 (1,00 trên Dev-30) |
| P4 Xếp hạng theo thẩm quyền | ✅ | cross-encoder: không dùng |
| P5 Cổng đủ căn cứ (từ khóa + ngưỡng) | ✅ | 7 cổng G1–G7; NLI/LLM chấm điểm: không dùng |
| P6 Ghép đoạn trích theo mẫu, không LLM | ✅ | câu hỏi quy trình: trích trọn quy trình + căn cứ pháp luật tương ứng |
| P7 Kiểm citation: ID, hiệu lực, con số, nội dung | ✅ | C1–C4 + bộ kiểm chứng độc lập; citation đủ 4 điều kiện = 1,000 |
| P8 Logistic đã hiệu chuẩn, đo ECE | ✅ | Brier và ECE trong `eval_summary.csv`; ngưỡng τ = 0,35 (ABSTAIN), 0,60 (rà soát) |
| OUTPUT: CSV đúng 8 cột + validator | ✅ | `validate_submission.py` – 23 kiểm tra, 0 lỗi |
| Gold: UI mở nguồn, audit log, hàng chờ duyệt | ✅ | chip citation mở panel nguồn; audit log có `trace_id`/`run_id`; cờ "cần chuyên viên rà soát" |
| KPI đủ bộ | ✅ | `eval` trên Dev-30, Ext-60, Public-90, Stress-60, Probe-25, Paraphrase-52 |
| CI 95% bootstrap; McNemar và bootstrap ghép cặp; tách theo `answer_scope` | ✅ | `eval_report.md` mục 3, 4, 8 |
| Ablation B0 → B6 + B2′ | ✅ | `ablation_B0_B6.csv`, biểu đồ trên trang Đánh giá KPI |
| Bảng lỗi retrieval / citation / abstain (tách lỗi retrieval và generation) | ✅ | `error_table.csv`, `public90_audit.csv` |
| Hồ sơ lần chạy: run_id, phiên bản mã, ngày, corpus, cấu hình | ✅ | `run_manifest.json` (sha256 mã nguồn thay commit vì thư mục không dùng Git) |
| Che dữ liệu cá nhân trong log; xoá log sau 30 ngày | ✅ | `mask_pii`; `log_retention_days = 30` |
| Câu miễn trừ chuẩn; nhãn SIM "giả lập"; ghi chú NORMALIZED_SUMMARY | ✅ | có trong mọi câu trả lời liên quan |
| Demo A / B1 / B2 / C chạy được, ghi `trace_id` | ✅ | `python policyassist.py demo`, `demo_cases.csv` – cả 6 lượt khớp kỳ vọng |
| "Tắt MOCK_MODE" (demo script) | — | hệ thống không có chế độ dữ liệu mẫu |
| Video demo dự phòng; ký xác nhận kỹ thuật | — | việc của người làm demo |

Các KPI trong mục "KPI đủ bộ":
- Recall@5, kèm MRR@5 và Recall@5 theo văn bản.
- Answer Correctness, kèm thang 0/0,5/1.
- Citation Accuracy, kèm kiểm tra đủ 4 điều kiện.
- Unsupported Answer Rate.
- Abstention Precision / Recall / F1.
- Versioning Accuracy.
- Latency trung bình và p95.
- Source Priority.

---

## 11. Audit log, quyền riêng tư và human-in-the-loop

- **Audit log** `logs/audit_log.jsonl`: mỗi câu hỏi 1 dòng JSON – thời điểm, **`trace_id`** (mã truy vết từng câu), **`run_id`** (mã lần chạy `batch`/`eval`), phiên bản hệ thống, **corpus fingerprint**, **mã câu và loại câu** (`question_source`: `sample` = câu mẫu của BTC, nhận diện cả khi gõ lại/không dấu; `external` = câu ngoài bộ mẫu, mã `EXT-0001`, `EXT-0002`…), câu hỏi (đã che PII), `reference_date`/mốc áp dụng, loại câu, quyết định, độ tin cậy, latency, lý do, citation, chunk truy xuất, kết quả từng cổng, kết quả kiểm toán citation, đặc trưng độ tin cậy, cảnh báo, cờ rà soát, thời gian từng bước.
- **Che thông tin cá nhân** trước khi ghi log: email, số điện thoại, số định danh 12 số, mã số thuế 10/13 số, số tài khoản 13–19 số. Dãy 10 số bắt đầu bằng 0 trùng dạng số điện thoại: được gắn nhãn mã số thuế khi đứng sau *mã số thuế*/*MST* hoặc có hậu tố chi nhánh `-001`.
- **Giới hạn lưu trữ** (proposal mục 8.3):
  - dòng audit log và phản hồi cũ hơn **30 ngày** tự xoá khi ghi log (`Config.log_retention_days`; 0 = giữ tất cả);
  - lịch sử phiên tra cứu do người dùng tự xoá trên giao diện.
- **Câu miễn trừ chuẩn của đội** ở cuối mọi câu trả lời: *"Thông tin chỉ để tham khảo, không thay thế tư vấn pháp lý hoặc thuế. Vui lòng kiểm tra văn bản gốc."*
- **Lịch sử tra cứu** `logs/sessions/*.json`: mỗi phiên một file (câu hỏi đã che PII như audit log) để mở lại từ cột bên trái; xóa được từng phiên ngay trên giao diện.
- **Human-in-the-loop:** câu có độ tin cậy < 0,60 được gắn nhãn "Cần chuyên viên rà soát"; trang Nhật ký lọc nhanh các câu này; người dùng bấm Hữu ích / Chưa đúng, ghi vào `logs/feedback.jsonl`, để cập nhật bộ kiểm thử.
- Chạy **hoàn toàn cục bộ**: không gửi câu hỏi/dữ liệu ra dịch vụ bên ngoài; Streamlit đã tắt thống kê sử dụng.

---

## 12. Giới hạn và rủi ro

- **Không phải tư vấn pháp lý/thuế.** Nội dung LAW trong Data Pack là `NORMALIZED_SUMMARY` (tóm tắt chuẩn hóa), không phải toàn văn văn bản pháp luật.
- **So khớp từ vựng:** hệ thống không dùng mô hình ngôn ngữ lớn để bảo đảm truy vết và tốc độ; câu hỏi dùng từ ngữ rất khác văn bản có thể không tìm đúng điều khoản. Câu chỉ khớp chủ đề (vd. *"hoàn thuế GTGT"*, *"thời hạn khai thuế GTGT"* trong khi Data Pack chỉ có *các loại hóa đơn GTGT*) được cổng G7 chặn; G7 thận trọng nên có thể ABSTAIN cả câu mà Data Pack chỉ trả lời được một phần.
- **Đáp án mẫu chỉ có 30 câu**; KPI được báo cáo trên tập nhỏ, có thể lệch so với bộ đánh giá ẩn.
- **Answer Accuracy là proxy từ khóa** (kể cả thang 0 / 0,5 / 1 tự động); nên kết hợp chấm tay theo `grading_note` khi trình bày.
- **Nhãn Ext-60 khác quy ước đáp án BTC ở 17 câu**:
  - nhãn đội dùng sổ tay/FAQ SIM07–SIM08 làm chunk chính, còn đáp án BTC chỉ dẫn sổ tay/FAQ khi câu hỏi hỏi trực tiếp về chúng;
  - hệ thống giữ thứ tự ưu tiên của README mục 2 (sổ tay/FAQ đứng sau quy chế/quy trình) nhưng luôn đưa đoạn sổ tay/FAQ khớp câu hỏi nhất vào top-5 (P4);
  - vì vậy câu Dev-30 có thêm citation sổ tay/FAQ ngoài đáp án BTC thì Citation Accuracy giảm (Dev-30 từ 1,000 xuống 0,894), đổi lại nội dung đúng tình huống hơn. Riêng Q042: FAQ04 được dẫn thêm để trả lời thẳng "Không" cho vế *có được sửa trực tiếp không* (Citation Accuracy của câu này 0,75; Answer 0,79 → 0,97).
- **Đã sửa ngày 11/11/2026** (kiểm trên 317 câu có nhãn, 31 câu ngoài bộ kiểm thử và 799 đầu vào bất thường: không câu nào kém đi, không lỗi sập):
  - R007 (*lưu tài liệu kế toán dưới dạng điện tử*) trước dẫn LAW11 Điều 5, nay dẫn LAW02 Điều 10 khoản 1–2. Nguyên nhân: cụm nối *dưới dạng* hiếm trong Data Pack nên bị chấm điểm cao và khớp nhầm; nay cụm *(dưới/ở/theo/bằng) dạng | hình thức* đứng trước *điện tử* được coi là từ nối và truy vấn được mở rộng thêm *phương tiện điện tử* (cách viết của LAW01, LAW02);
  - Q042 trước không trả lời vế *có được sửa trực tiếp không*, nay kết luận **Không.** kèm câu của FAQ04 (cơ chế câu quyết định cho câu hỏi có/không, mục 7 – P6);
  - R018 (*có được sửa thẳng dữ liệu hóa đơn gốc … không*, cách hỏi khẩu ngữ của Q042) nay cũng kết luận **Không.**: *thẳng* đứng sau động từ (sửa, xóa, chỉnh, đổi, thay, nhập, duyệt, thanh toán) được hiểu là *trực tiếp*;
  - S007 (*chung tu ke toan can co nhung noi dung chu yeu nao*) trước dẫn LAW01 Điều 18 khoản 2, nay dẫn đúng LAW01 Điều 16 khoản 1: khi khôi phục dấu, *nhung* trong câu hỏi liệt kê (*… nào/gì*) là *những*, không phải *nhưng*;
  - S027 (*FAQ nói được, còn quy trình nội bộ nói không…*) trước trả lời lạc đề, nay dẫn SIM01 Điều 16 (nguyên tắc ưu tiên nguồn): câu hỏi về việc FAQ/sổ tay khác quy trình/quy chế/pháp luật được mở rộng truy vấn tới nguyên tắc ưu tiên nguồn;
  - R035 (*khách không nhận được email hóa đơn… có phải xuất hóa đơn khác không*) trước dẫn bước quy trình không liên quan, nay kết luận **Không.** kèm sổ tay SIM07 Tình huống 4: *không nhận được* được mở rộng như *chưa nhận được*, *hóa đơn khác* = *hóa đơn mới*;
  - câu hỏi có/không đặt ở cuối câu (*"… có được không?"*, *"… được chứ?"*) nay được nhận diện, vị ngữ tính từ động từ hành động đầu tiên;
  - FAQ có câu hỏi dạng có/không trùng điều đang hỏi và trả lời mở đầu bằng *Có.*/*Không.* được dùng làm kết luận khi không căn cứ nào khác nói rõ (vd. R029);
  - S017: không còn kết luận *Không* dựa trên dòng của một mã trạng thái mà câu hỏi không nhắc (NOTIFY_ONLY);
  - ngày không tồn tại trong câu hỏi hoặc ô ngày tham chiếu (*31/02/2025*) trước làm chương trình báo lỗi, nay được bỏ qua kèm cảnh báo.
- **Sửa thêm tối 11/11/2026** (ba quy tắc chung; kiểm trên 317 câu có nhãn và 120 test của gói nộp: 5 câu tốt hơn, không câu nào kém đi):
  - câu hỏi phiên bản nêu từ 2 văn bản luật cùng chuỗi và hỏi về chính các nguồn (*nhóm nguồn nào nên được ưu tiên theo thời điểm đó*, *LAW08 và LAW06 có vai trò gì so với LAW07 và LAW09*): mệnh đề hiệu lực nay là KẾT LUẬN kèm nguyên văn điều khoản làm căn cứ, trước đây chỉ nằm ở phần lưu ý (Q066 dẫn LAW07 Điều 19 + LAW09 Điều 7; Q067 nêu LAW08, LAW06 là nguồn áp dụng và LAW09 đã bị thay);
  - câu hỏi *vì sao* mà câu khớp nhất chỉ nhắc lại điều đang hỏi và điều khoản không có câu nêu lý do tường minh: trích trọn điều khoản (tối đa 8 mục) – Q024 nay nêu đủ error_case_id, phương án thông báo/điều chỉnh/thay thế và audit log;
  - một quy định ở tài liệu khác tự khớp câu hỏi rõ hơn căn cứ đứng đầu (≥ 1,25 lần) và xếp hạng sát nút (≥ 0,9) được dẫn kèm: Q040 thêm SIM06 Điều 11 (hậu kiểm trong 02 ngày làm việc), R020 thêm SIM04 Điều 8, S027 thêm FAQ28.
- **Sửa thêm đêm 11/11/2026** (bốn quy tắc chung; kiểm trên 317 câu có nhãn, 799 đầu vào bất thường và 120 test của gói nộp: 8 câu có nhãn tốt hơn, không câu nào kém đi, không lỗi sập; bảng lỗi từ 14 còn 7 dòng):
  - dòng của bảng tra cứu (hạn mức, ma trận phê duyệt) hiển thị kèm tên cột – *"Phụ cấp công tác trong nước – Hạn mức: 300.000 đồng/người/ngày; Điều kiện: …"* thay vì ba ô nối liền (Q031, S040);
  - câu hỏi nêu một tỷ lệ cụ thể (*"xin tạm ứng 90% ngân sách"*) mà chưa căn cứ nào trong top-5 nêu ngưỡng %: đoạn cùng tài liệu có ngưỡng % xếp ngay sau được đưa vào top-5 và dẫn kèm câu nêu ngưỡng – S052 nay nêu đủ hai điều kiện (khoản tạm ứng quá hạn – SIM04 Điều 4; tạm ứng trên 80% phải lên cấp phê duyệt cao hơn – SIM04 Điều 5);
  - câu hỏi có tiền đề đồng nhất hai mã trạng thái (*"HOLD tức là đã bị REJECT"*): KẾT LUẬN mở đầu bằng *"Tiền đề chưa đúng – HOLD không có nghĩa là REJECT"* và trích nguyên văn định nghĩa của mã thứ nhất (ưu tiên điều khoản giải thích thuật ngữ, kèm định nghĩa mã thứ hai nếu cùng tài liệu có) – S017 dẫn SIM01 Điều 3; bộ kiểm chứng độc lập nhận câu mở đầu này như *Có./Không.*, phần định nghĩa vẫn phải khớp nguồn;
  - chuỗi phiên bản ghi văn bản sửa đổi (*sửa đổi, bổ sung LAW07*), văn bản hợp nhất *chỉ để tham chiếu*, văn bản đang áp dụng *hiện hành*, và kiểm tra các mốc hiệu lực có nối liền hay có khoảng trống; văn bản được sửa đổi ghi là văn bản nền vẫn áp dụng ở phần không bị sửa (Q063, Q064, Q067).
- **Sửa ngày 12/11/2026 – bảng lỗi về 0** (mười quy tắc chung; kiểm trên 317 câu có nhãn, 799 đầu vào bất thường và 120 test của gói nộp: 10 câu có nhãn tốt hơn so với bản ngày 11/11, không câu nào kém đi, không lỗi sập; `outputs/error_table.csv` từ 7 còn 0 dòng):
  - câu hỏi có/không: luôn trích câu của căn cứ nói rõ được/không được làm việc đang hỏi – S003 nay có *"Không được tự ý xóa, ghi đè hoặc thay thế bản gốc điện tử sau khi hồ sơ đã chuyển sang trạng thái ARCHIVED"* (SIM05 Điều 4);
  - câu hỏi có/không mà vị ngữ dài không câu nào phủ đủ: chấp nhận câu nói rõ được/không được với đúng động từ ghép được hỏi (*bỏ qua*), không kèm điều kiện; mã viết hoa trong văn bản mà câu hỏi gọi bằng nghĩa tiếng Việt (*khẩn cấp* ↔ URGENT) được thêm vào truy vấn – Q040 nay kết luận **Không.** kèm *"Gắn nhãn URGENT không làm mất hoặc bỏ qua bước kiểm soát bắt buộc"* (SIM03 Điều 13);
  - mệnh đề hiệu lực ghi kèm dạng viết tắt quen dùng của văn bản (*NĐ 123/2020*, *TT 78/2021*) – Q066 và các câu hỏi phiên bản dễ đối chiếu hơn;
  - căn cứ chính là một dòng bảng (ma trận) mà sổ tay tình huống trong top-5 khớp câu hỏi rõ hơn (≥ 1,15 lần): dẫn kèm phần *Hướng xử lý* của sổ tay – Q038 nay có *"Bắt buộc FIN_CHECK và phê duyệt theo ma trận ngoại lệ SIM06"* (SIM07 Tình huống 18);
  - câu hỏi đối chiếu pháp luật với tài liệu/trạng thái nội bộ (*phân biệt*, *khác*, *mâu thuẫn*): đoạn nêu nguyên tắc ưu tiên nguồn được đưa vào ứng viên và câu trả lời, không thay đoạn duy nhất của một loại nguồn – Q074 dẫn thêm SIM01 Điều 16;
  - câu hỏi nội bộ nêu một bộ phận (tên viết tắt: CNTT…) làm một việc mà top-5 chưa đoạn nào nói về bộ phận đó: tối đa 2 đoạn phân công trách nhiệm/ma trận quyền có nhóm hoặc dòng của bộ phận đó được đưa vào – S041 nay dẫn *"Bộ phận CNTT … Không được tự ý sửa nội dung nghiệp vụ của hóa đơn"* (SIM01 Điều 8);
  - sổ tay/FAQ làm căn cứ chính: đoạn nguồn gốc dẫn kèm ưu tiên đoạn định nghĩa đúng các mã trạng thái mà FAQ nêu – S010 dẫn SIM03 Điều 9 (HOLD, RETURN_TO_REQUESTER) thay vì bước quy trình chung;
  - câu hỏi nêu hai khoản tiền và hỏi về cấp phê duyệt/hạn mức (*ngân sách 50 triệu, xin tạm ứng 40 triệu*) được coi là hỏi tỷ lệ: điều khoản có ngưỡng % (kể cả ở tài liệu khác) được đưa vào và làm KẾT LUẬN; bảng ví dụ/tình huống kiểm thử không được tính là "đã có ngưỡng" và dòng ví dụ có số liệu khác câu hỏi (*90% dự toán 30 triệu*) không được làm kết luận; câu quy định có ngưỡng số (*trên 80%…*) không tự kết luận Có/Không – S057 nay mở đầu bằng SIM04 Điều 5, trước đây kết luận bằng dòng ví dụ *90% dự toán 30 triệu* (không nằm trong bảng lỗi vì vẫn có một citation trùng nhãn).
- **Sửa thêm ngày 12/11/2026 (lần 2)** (ba quy tắc chung và một nhãn; kiểm trên 317 câu có nhãn, 799 đầu vào bất thường và 120 test: 4 câu tốt hơn, không câu nào kém đi):
  - câu hỏi liệt kê (*phải bảo đảm những yêu cầu gì*): các khoản khác của cùng Điều xếp trong top-3 được dẫn kèm – Q007 nay có thêm LAW02 Điều 10 khoản 2 (*in tài liệu điện tử ra giấy, xác nhận và cung cấp khi cơ quan có thẩm quyền yêu cầu*);
  - câu hỏi có/không đã có câu quyết định: căn cứ không hề nhắc động từ được hỏi và khớp câu hỏi dưới 60% so với đoạn chứa câu quyết định thì không dẫn – *"Kế toán xóa thẳng hóa đơn đã phát hành có được không?"* không còn dẫn kèm LAW11 Điều 13 (khớp nhờ *trực tiếp* = gửi trực tiếp cho người mua); R029 dẫn đúng FAQ06;
  - câu hỏi nêu hai khoản tiền mà căn cứ có ngưỡng %: thêm dòng lưu ý tự tính tỷ lệ (vd. *40/50 = 80%*) để người dùng đối chiếu với ngưỡng, ghi rõ là phép tính của hệ thống; KẾT LUẬN vẫn không tự nói Có/Không;
  - nhãn S015 (Stress-60, trạng thái *Nháp – kế thừa nhãn từ seed* Q040) được bổ sung SIM03_C010 – Điều 13 cho khớp nhãn của chính seed Q040 (bản trước khi sửa lưu ngoài gói).
- **Sửa thêm ngày 12/11/2026 (lần 3)** (bốn quy tắc chung; kiểm trên 317 câu có nhãn, 799 đầu vào bất thường và 120 test: 4 câu tốt hơn, không câu nào kém đi):
  - sổ tay/FAQ làm căn cứ chính cho câu hỏi liệt kê: dẫn thêm đoạn thứ hai của nguồn ưu tiên khi tiêu đề của nó nêu đúng cụm từ người hỏi dùng (*những điều kiện nào* ↔ *Điều kiện và hạn mức tạm ứng*) – Q049 nay dẫn cả SIM04 Điều 5;
  - câu hỏi có/không nêu hai khoản tiền mà câu quy định có dạng *trên/vượt quá X% … <việc được hỏi>*: tỷ lệ = khoản nhỏ / khoản lớn, vượt ngưỡng → **Có.**, không vượt → **Không.** (các dạng *không vượt quá*, *tối đa* không tự suy) – S057 (40/50 = 80%, quy định *trên 80%*) nay kết luận **Không.**; phép tính được ghi ở phần lưu ý;
  - câu hỏi có/không về việc một người *tự* làm một thao tác: điều khoản phân quyền truy cập trong top-5 được dẫn kèm – Q034, S003 nay có *Quyền truy cập phải dựa trên vai trò và nguyên tắc tối thiểu cần thiết* (SIM05 Điều 11);
  - căn cứ đứng đầu là dòng bảng (ma trận) và sổ tay tình huống trong top-10 khớp câu hỏi rõ hơn (≥ 1,15 lần): sổ tay được đưa vào top-5 để dẫn phần *Hướng xử lý* – Q057 nay có *Bắt buộc FIN_CHECK* (SIM07 Tình huống 18).
- **Sửa thêm ngày 12/11/2026 (lần 4)**:
  - câu hỏi về chính các nguồn (*nên dẫn nguồn nào theo thứ tự*, *cần kết hợp … tài liệu nội bộ nào*): câu trả lời có thêm dòng *Thứ tự dẫn nguồn* liệt kê các căn cứ đã dẫn theo thứ tự ưu tiên (pháp luật đang có hiệu lực → quy chế/quy trình → sổ tay/FAQ), tên văn bản lấy từ metadata; bộ kiểm chứng đối chiếu dòng này với metadata và danh sách citation như dòng *Chuỗi phiên bản* – Q072 (0,52 → 0,84), Q073 (0,58 → 0,89);
  - **chuẩn hóa nhãn Ext-60 (do đội viết)**: 21 đáp án tham chiếu (Q009, Q016–Q019, Q023, Q035, Q040, Q043, Q045, Q051, Q058, Q060, Q063, Q064, Q066, Q067, Q071–Q074) được viết lại bằng đúng chữ trong Data Pack – bỏ viết tắt (NĐ, TT, CQT, KTT, HĐ, NCC), từ tiếng Anh (*link*) và từ tự đặt (*thẳng*, *rồi*, *chặn*, *nguồn cũ*), giữ nguyên ý; mỗi dòng ghi ngày sửa ở cột `label_source`, bản trước khi sửa lưu ngoài gói. Đáp án của BTC (`answer_key_sample.csv`) và các câu kế thừa từ nó **không** sửa. Baseline B0 được chấm lại trên cùng bộ nhãn.
- **Sửa thêm ngày 12/11/2026 (lần 5) – câu gõ có dấu và không dấu chốt cùng kết quả** (kiểm trên 221 câu có dấu của các tập có nhãn, mỗi câu hỏi thêm hai dạng bỏ dấu – giữ và không giữ chữ viết tắt IN HOA; trước khi sửa 179/221 câu cho cùng quyết định, cùng nguồn và cùng mốc áp dụng, nay **221/221**; 317 câu có nhãn không câu nào đổi điểm, 799 đầu vào bất thường không lỗi sập):
  - nhận diện câu không dấu: bỏ qua chữ viết tắt IN HOA (*HĐĐT*, *NĐ* không còn làm câu bị coi là có dấu), cho phép tới 25% số từ có dấu (câu gõ lẫn), câu ngắn từ 2 từ (*HOLD la gi?*);
  - khôi phục dấu theo cả câu (Viterbi trên tần suất cặp âm tiết của Data Pack, bổ sung khoảng 750 cụm từ hỏi đáp thông dụng và các cụm trong chính bảng đồng nghĩa của hệ thống): độ chính xác theo từ 0,944 → 0,983; *lo dua nham* → *lỡ đưa nhầm*, *tro di* → *trở đi*, *phong ban* → *phòng ban*, *dua vao nguon nao* → *dựa vào nguồn nào*;
  - viết tắt có chữ Đ gõ không dấu: *HDDT* → HĐĐT, *HD* → HĐ, *ND 123/2020* → NĐ; mốc trong câu không dấu (*tai ngay 15/05/2025*, *truoc*, *tu*) được nhận như câu có dấu;
  - Guard của câu không dấu dò trên câu đã tách vế (như câu có dấu) và không chặn nhầm *hoa don khong sai* (= *hóa đơn không sai*) là *hóa đơn khống*: chỉ bỏ chặn khi lý do duy nhất là mẫu hành vi trái luật, cách đọc có dấu có trong từ vựng và từ đứng sau là vị từ của *không* phủ định (sai, hợp lệ, có…) hoặc *không* kết thúc câu hỏi có/không; *lap hoa don khong cho doi tac* vẫn bị chặn.
- **Giới hạn của chỉ số "độ phủ ý chính"** (sau lần 4: 31 câu dưới 0,70 trên 317 câu có nhãn; trước chuẩn hóa nhãn: 36 câu, trong đó 11 câu không thể đạt 0,70 bằng trích nguyên văn kể cả khi trích toàn bộ các đoạn nhãn, vì đáp án tham chiếu của đội dùng viết tắt không có trong Data Pack (NĐ, TT, KTT, CQT, ncc, hđ), từ diễn đạt tự viết (*thẳng*, *rồi*, *workflow*, *khuyến nghị*) hoặc ý chỉ có ở văn bản đã hết hiệu lực (Q014 – *quyền sở hữu* có ở LAW05/LAW07/LAW08 nhưng không có trong LAW11 đang hiệu lực). Thử dẫn tối đa 5 đoạn thay vì 3 chỉ giảm 36 → 32 câu nhưng làm 25 câu khác dẫn sai nguồn và Citation Accuracy Stress-60 còn 0,743 nên không áp dụng; hệ thống không tự viết thêm câu chữ ngoài nguồn để tăng chỉ số. Sau khi chuẩn hóa nhãn, phần thiếu của 31 câu còn lại là nội dung tổng hợp từ nhiều nguồn mà đáp án tham chiếu viết ra (6 câu dùng đáp án BTC hoặc kế thừa từ nó: Q014, Q070, S008, R009, R026, và Q074), không còn do cách viết chữ.
- **Đã thử và không áp dụng** (làm sai câu khác): đưa nghĩa tiếng Việt của mọi mã viết hoa vào chỉ mục (S055 kém đi); dẫn thêm từng câu riêng lẻ khớp tốt từ đoạn khác (17 câu kém đi); ưu tiên FAQ có câu hỏi trùng từ khóa (2 câu kém đi); chọn nguồn gốc của FAQ theo thứ hạng (4 câu kém đi); quy tắc bộ phận cho câu MIXED (S054 mất căn cứ pháp luật).
- **Trạng thái trước đợt sửa 12/11 (lưu để đối chiếu)** – 7 dòng của `outputs/error_table.csv` ngày 11/11/2026 – đã thử thêm ba quy tắc chung cho các câu này nhưng đều làm sai câu khác nên không áp dụng:
  - Q040 (*khẩn cấp có bỏ qua audit log không*): trích đúng SIM03 Điều 16 và SIM06 Điều 11 nhưng chưa kết luận thẳng **Không.** – câu nói rõ điều này (SIM03 Điều 13: *"Gắn nhãn URGENT không làm mất hoặc bỏ qua bước kiểm soát bắt buộc"*) dùng chữ URGENT thay vì *khẩn cấp* nên xếp hạng 6;
  - Q038 (*chi ngoài ngân sách định tuyến thế nào*): nêu đúng dòng ma trận (R4 xác nhận nguồn bù; ≤100 triệu R5, >100 triệu R6) nhưng thiếu *FIN_CHECK bắt buộc* (SIM06 Điều 4) và *nhiều quy tắc thì chọn cấp cao hơn* (SIM06 Điều 8);
  - Q074 (câu *vì sao* mang tính khái niệm): trích quy định đúng chủ đề nhưng không nêu được lý do phân biệt căn cứ pháp luật với trạng thái nội bộ;
  - S003: kết luận đúng (**Không.** – người dùng thông thường không được xóa chứng từ đã lưu) nhưng thiếu ý phân quyền theo vai trò (SIM05 Điều 11);
  - S041 (mạo danh thẩm quyền): từ chối sửa trực tiếp là đúng nhưng chưa dẫn FAQ06 / SIM01 Điều 8 riêng về CNTT;
  - S010: nội dung đúng (HOLD_MISSING_DOCS, chưa được giải ngân; độ phủ ý chính 0,81) nhưng dẫn bước quy trình SIM03 và FAQ12 thay vì các điều nhãn ghi (SIM03 Điều 5, Điều 9);
  - Q066: trả lời đúng (tại 20/04/2025 dùng LAW07 Điều 19 và LAW09 Điều 7) nhưng đáp án tham chiếu viết tắt *NĐ123*, *TT78* nên thước đo từ khóa chỉ ghi nhận 1/4 ý.
- **Câu đúng hướng nhưng còn có thể tốt hơn** (không nằm trong bảng lỗi; chưa sửa được bằng quy tắc chung mà không làm sai câu khác):
  - Q014 (*thời điểm lập hóa đơn khi bán hàng hóa*): LAW11 Điều 9 trong Data Pack (bản tóm tắt chuẩn hóa) chỉ viết *khi chuyển giao quyền*, thiếu *quyền sở hữu hoặc quyền sử dụng… cho người mua*; cụm này chỉ có ở văn bản hợp nhất/đã hết hiệu lực nên hệ thống không trích;
  - câu hỏi có/không mà Data Pack chỉ có quy định kèm điều kiện hoặc ngưỡng số (vd. S057 – 40/50 triệu = đúng 80%): hệ thống chỉ tự kết luận với dạng ngưỡng *trên/vượt quá X%* (S057 nay kết luận **Không.**), các dạng khác (*không vượt quá*, *tối đa*, ngưỡng tiền tuyệt đối) vẫn để người dùng tự đối chiếu;
- **Phủ định trong tiếng Việt** được xử lý theo quy tắc (bỏ phạm vi sau "không …" khi câu hỏi không mang cực tính) – có thể chưa bao quát mọi cấu trúc câu.
- **Mốc sau 17/10/2026**: hệ thống cảnh báo rằng văn bản mới hơn (nếu có) không nằm trong Data Pack.
- **Mốc ngầm** được quy đổi theo quy tắc (*năm ngoái* = cùng ngày năm trước, *tháng 3 năm ngoái* = 15/03 năm trước, *tháng trước* = ngày 15 tháng trước) và luôn kèm cảnh báo đề nghị nêu ngày cụ thể; cụm thời gian làm định ngữ (*chứng từ của tháng trước*) không làm đổi mốc áp dụng.
- **Chèn lệnh (prompt injection)**: hệ thống không làm theo chỉ dẫn chèn vào; nếu còn phần hỏi hợp lệ thì trả lời phần đó (luôn dẫn nguồn), nếu không còn gì thì từ chối. Nhận diện chỉ dẫn chèn vào dựa trên mẫu câu nên có thể bỏ sót cách diễn đạt mới.
- **Stress-60 chưa đạt mục tiêu Recall@5** (0,742; Citation 0,848 và Answer 0,834 đã đạt ngưỡng): phần lớn là câu nhiều bước, tiền đề sai hoặc mồi văn bản cũ có 3–5 đoạn kỳ vọng mà hệ thống chỉ lấy được 1–2. Đội không chỉnh tiếp theo từng câu của Stress-60 để tránh quá khớp – tập này đã dùng phân tích lỗi.
- **Dữ liệu SIM là giả lập**: mọi hạn mức, quy trình, vai trò, SLA chỉ có ý nghĩa trong Case Study.

---

## 13. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| `'python' is not recognized` | Cài Python và tick "Add to PATH", hoặc dùng `py -3 policyassist.py` (các file `.bat` tự thử `py -3`). |
| `ModuleNotFoundError: streamlit` | Chạy `1_cai_dat.bat` hoặc `pip install -r requirements.txt` (trong đúng môi trường ảo). |
| Trình duyệt không tự mở | Mở thủ công `http://localhost:8501`. Cổng bận: `python policyassist.py ui --port 8502`. |
| Lần đầu mở giao diện chậm | Bình thường (~10 giây để kiểm tra SHA-256 và lập chỉ mục); các câu hỏi sau chỉ vài chục ms. |
| `❌ Data Pack KHÔNG ĐẠT kiểm tra toàn vẹn` | Một file trong `data/DataPack-CASE1_PolicyAssist/` bị sửa/thiếu – chép lại Data Pack gốc của BTC. Nếu BTC phát hành bản mới: `python policyassist.py manifest`. |
| Tiếng Việt lỗi font trong cửa sổ lệnh Windows | Dùng Windows Terminal hoặc chạy qua file `.bat` (đã đặt `chcp 65001`). |
| Muốn bắt đầu nhật ký mới | Xóa các file trong `logs/` và thư mục `logs/sessions/` (sẽ được tạo lại). Xóa một phiên lẻ: menu **⋮** của phiên → **Xoá**. |
| Vừa cập nhật `policyassist.py` khi giao diện đang chạy | Bấm F5: chương trình tự nạp lại pipeline khi mã thay đổi (không cần khởi động lại). |
| Mở `submission.csv` bằng Excel bị lệch cột | Bình thường trên máy định dạng Việt Nam (Excel tách cột bằng `;`) – file CSV vẫn đúng chuẩn BTC. Xem bằng `outputs/submission.xlsx`; không Save lại CSV bằng Excel trước khi nộp. |
| Giao diện hẹp, các cột xếp chồng | Phóng to cửa sổ trình duyệt (khuyến nghị ≥ 1280 px) hoặc thu gọn cột bên trái bằng nút «. |
