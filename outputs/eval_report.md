# Báo cáo đánh giá – PolicyAssist AI (V1.0)

- Mã lần chạy (run_id): `RUN-20261110-113148-e54bc1` · thời điểm 10/11/2026 11:32
- Data Pack: v1-snapshot-2026-10-17 · corpus fingerprint `7357afec5ef0` (toàn bộ Data Pack, corpus_manifest) · `08eaac52973a` (6 file CSV, cách tính trong báo cáo ngày 1 của đội) – cùng một bộ dữ liệu.
- Mã nguồn `policyassist.py` sha256 `e54bc1616a48` · không dùng mô hình ngôn ngữ (pipeline tất định: chạy lại cho cùng kết quả, trừ latency) · hồ sơ đầy đủ: `outputs/run_manifest.json`.
- Đo trên bộ câu hỏi mẫu của BTC và bộ câu do đội gán nhãn/tự viết, không phải người dùng thật.

## 1. Tập đánh giá

- **Dev-30** (30 câu): 30 câu có đáp án mẫu của BTC (answer_key_sample.csv)
- **Ext-60** (60 câu): 60 câu public còn lại – nhãn của đội: 2 người gán độc lập, hội chẩn câu bất đồng (data/eval/ext60_labels.csv)
- **Public-90** (90 câu): Dev-30 + Ext-60: toàn bộ 90 câu public
- **Stress-60** (60 câu): 60 câu kiểm thử chịu tải do đội viết; đã dùng để phân tích lỗi (24/10 và 10/11/2026) nên không còn hoàn toàn độc lập (data/eval/stress60_labels.csv)
- **Probe-25** (25 câu): 25 câu thăm dò: ngoài phạm vi, diễn đạt lại, versioning mốc mới (data/eval/probe_questions.csv)
- **Paraphrase-52** (52 câu): 52 câu diễn đạt lại câu mẫu, viết tắt, gõ không dấu + câu phải ABSTAIN (data/eval/paraphrase_questions.csv)

## 2. Bảng KPI theo tập – hệ thống CHRONOS-LEDGER

Ô = giá trị (tổng điểm hoặc số câu đúng / số câu được tính). Recall@5, Answer Correctness: câu nhãn ANSWER (câu bị ABSTAIN tính 0). Citation: câu nhãn ANSWER đã trả lời. Unsupported: mọi câu đã trả lời. Abstention: toàn bộ tập (ABSTAIN là lớp dương). Versioning: câu VERSIONING. Source Priority: câu MIXED.

| Chỉ số | Dev-30 | Ext-60 | Public-90 | Stress-60 | Probe-25 | Paraphrase-52 | Mục tiêu |
|---|---|---|---|---|---|---|---|
| 1. Retrieval Recall@5 | 0.936 (24.33/26) | 0.887 (44.33/50) | 0.904 (68.67/76) | 0.710 (36.93/52) | — | 0.853 (35.83/42) | ≥ 0.8 (đề thi) |
| · MRR@5 | 0.962 (25/26) | 0.844 (42.18/50) | 0.884 (67.18/76) | 0.839 (43.62/52) | — | 0.887 (37.25/42) |  |
| · Recall@5 theo văn bản | 0.962 (25/26) | 0.940 (47/50) | 0.947 (72/76) | 0.868 (45.13/52) | — | 0.956 (40.17/42) |  |
| 2. Answer Accuracy / Correctness (độ phủ ý chính) | 0.831 (21.61/26) | 0.645 (32.23/50) | 0.708 (53.84/76) | 0.668 (12.69/19) | — | 0.775 (20.14/26) | ≥ 0.7 (đội) |
| · thang 0 / 0,5 / 1 (tự động) | 0.904 (23.5/26) | 0.650 (32.5/50) | 0.737 (56/76) | 0.684 (13/19) | — | 0.808 (21/26) |  |
| 3. Citation Accuracy (đúng nhãn) | 0.891 (23.17/26) | 0.953 (47.67/50) | 0.932 (70.83/76) | 0.758 (39.42/52) | — | 0.821 (34.5/42) | ≥ 0.8 (đề thi) |
| · citation đủ 4 điều kiện | 1.000 (26/26) | 1.000 (50/50) | 1.000 (76/76) | 1.000 (52/52) | 1.000 (11/11) | 1.000 (42/42) |  |
| 4. Unsupported Answer Rate | 0.000 (0/26) | 0.000 (0/50) | 0.000 (0/76) | 0.000 (0/52) | 0.000 (0/11) | 0.000 (0/42) | ≤ 0.1 (đội) |
| 5. Abstention Quality (F1) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | ≥ 0.9 (đội) |
| · Precision ABSTAIN | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |  |
| · Recall ABSTAIN | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |  |
| 6. Versioning Accuracy | 1.000 (4/4) | 1.000 (6/6) | 1.000 (10/10) | 1.000 (14/14) | 1.000 (6/6) | 1.000 (6/6) | ≥ 0.9 (đội) |
| 7. Latency trung bình (ms) | 34 | 40 | 38 | 41 | 22 | 36 | ≤ 10000 (đề thi) |
| · Latency p95 (ms) | 97 | 90 | 97 | 85 | 43 | 79 |  |
| Chỉ số phụ: Source Priority (câu MIXED) | 0.667 (2/3) | 0.444 (4/9) | 0.500 (6/12) | 1.000 (1/1) | — | 0.250 (1/4) | ≥ 0.85 (đội) |
| Quyết định ANSWER/ABSTAIN đúng | 1.000 (30/30) | 1.000 (60/60) | 1.000 (90/90) | 1.000 (60/60) | 1.000 (25/25) | 1.000 (52/52) |  |

### Cách đo

- **Retrieval Recall@5**: |chunk đáp án ∩ 5 chunk đầu của retrieved_chunk_ids| / |chunk đáp án|, trung bình trên 26 câu ANSWER của answer_key (câu bị ABSTAIN tính 0, đúng như file nộp).
- **Answer Accuracy / Correctness (độ phủ ý chính)**: Tỷ lệ từ khóa nội dung (bỏ hư từ) của reference_answer xuất hiện trong câu trả lời, trung bình trên 26 câu ANSWER (ABSTAIN tính 0). Kèm ROUGE-L tham khảo; không thay chấm tay.
- **Citation Accuracy**: Trong các câu đã trả lời: |citation dẫn ∩ citation_labels đáp án| / |citation dẫn| (chặt, theo nhãn). Kèm tỷ lệ citation hợp lệ về thời gian trên 90 câu public.
- **Unsupported Answer Rate**: Theo đề/README: câu đã trả lời mà lẽ ra phải ABSTAIN, hoặc có câu khẳng định không được chính nguồn nó dẫn xác nhận (kiểm chứng độc lập: ≥ 90% từ có trong chunk, ngày hiệu lực khớp metadata) / tổng câu đã trả lời (Dev-30 + Probe-25). Kèm 'evidence_mismatch_rate' = câu Dev không có citation nào trùng nhãn đáp án.
- **Abstention Quality (F1)**: F1 của lớp ABSTAIN trên 30 câu Dev + 25 câu probe (kèm precision, recall, accuracy quyết định).
- **Versioning Accuracy**: Câu VERSIONING (4 Dev + 6 probe có expected_documents): văn bản LAW đầu tiên được dẫn còn hiệu lực tại mốc áp dụng phải thuộc tập văn bản đúng.
- **Latency trung bình (ms)**: Thời gian xử lý trung bình mỗi câu (ms) trên Dev + probe + 90 câu public, đo trong tiến trình.
- **MRR@5**: trung bình 1/hạng của chunk chính đầu tiên trong retrieved_chunk_ids (không có → 0). **Recall@5 theo văn bản**: |văn bản đáp án ∩ văn bản của 5 chunk đầu| / |văn bản đáp án|.
- **Citation đủ 4 điều kiện**: (a) có trong citation_map.csv; (b) ứng với chunk đã truy xuất; (c) chunk chứa căn cứ cho mọi câu gắn citation (≥ 90% từ); (d) còn hiệu lực tại reference_date (hoặc dẫn như văn bản lịch sử trong câu hỏi phiên bản) – kiểm tự động trên 100% citation.
- **Source Priority** (chỉ số phụ, câu MIXED): có căn cứ pháp luật còn hiệu lực; pháp luật đứng trước nội bộ; không dùng văn bản hết hiệu lực/hợp nhất làm căn cứ; nội bộ dẫn luật cũ thì phải dẫn văn bản kế nhiệm hoặc cảnh báo.
- **Answer Correctness** (độ phủ ý chính và thang 0 / 0,5 / 1) trên Stress-60 chỉ chấm tự động các kiểu giữ nguyên đáp án câu gốc (ABBREV_CODEMIX, ABBREV_TYPO, INJECTION, NO_DIACRITIC, PARAPHRASE); các kiểu còn lại cần chấm tay theo ghi_chu (cột grading_note trong outputs/eval_results_all.csv).

## 3. Baseline B0 (BM25 thuần) trên cùng các tập

| Chỉ số | Dev-30 | Ext-60 | Public-90 | Stress-60 | Probe-25 | Paraphrase-52 | Mục tiêu |
|---|---|---|---|---|---|---|---|
| 1. Retrieval Recall@5 | 0.538 | 0.647 | 0.610 | 0.360 | — | 0.540 | ≥ 0.8 (đề thi) |
| · MRR@5 | 0.508 | 0.673 | 0.616 | 0.438 | — | 0.573 |  |
| · Recall@5 theo văn bản | 0.771 | 0.850 | 0.823 | 0.654 | — | 0.798 |  |
| 2. Answer Accuracy / Correctness (độ phủ ý chính) | 0.619 | 0.549 | 0.573 | 0.393 | — | 0.645 | ≥ 0.7 (đội) |
| · thang 0 / 0,5 / 1 (tự động) | 0.577 | 0.500 | 0.526 | 0.342 | — | 0.577 |  |
| 3. Citation Accuracy (đúng nhãn) | 0.442 | 0.690 | 0.605 | 0.385 | — | 0.512 | ≥ 0.8 (đề thi) |
| · citation đủ 4 điều kiện | 0.900 | 0.883 | 0.889 | 0.900 | 0.760 | 0.885 |  |
| 4. Unsupported Answer Rate | 0.133 | 0.167 | 0.156 | 0.133 | 0.560 | 0.192 | ≤ 0.1 (đội) |
| 5. Abstention Quality (F1) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | ≥ 0.9 (đội) |
| · Precision ABSTAIN | — | — | — | — | — | — |  |
| · Recall ABSTAIN | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |  |
| 6. Versioning Accuracy | 0.250 | 0.500 | 0.400 | 0.214 | 0.167 | 0.333 | ≥ 0.9 (đội) |
| 7. Latency trung bình (ms) | 11 | 13 | 12 | 12 | 10 | 10 | ≤ 10000 (đề thi) |
| · Latency p95 (ms) | 17 | 21 | 20 | 17 | 14 | 13 |  |
| Chỉ số phụ: Source Priority (câu MIXED) | 0.000 | 0.111 | 0.083 | 0.000 | — | 0.000 | ≥ 0.85 (đội) |
| Quyết định ANSWER/ABSTAIN đúng | 0.867 | 0.833 | 0.844 | 0.867 | 0.440 | 0.808 |  |

### Kiểm định ghép cặp CHRONOS-LEDGER so với B0

McNemar chính xác cho quyết định đúng/sai từng câu (+ = câu chỉ hệ thống đúng, − = câu chỉ B0 đúng); bootstrap ghép cặp 2000 lần cho chênh lệch các chỉ số có điểm lẻ.

| tập | quyết định đúng | Recall@5 | Answer Correctness | Citation Accuracy |
|---|---|---|---|---|
| Dev-30 | +4 / −0 câu · McNemar p = 0.125 | Δ = +0.397 (95%: +0.218 … +0.577; 26 câu) | Δ = +0.212 (95%: +0.098 … +0.336; 26 câu) | Δ = +0.449 (95%: +0.269 … +0.622; 26 câu) |
| Ext-60 | +10 / −0 câu · McNemar p = 0.00195 | Δ = +0.240 (95%: +0.120 … +0.363; 50 câu) | Δ = +0.095 (95%: +0.038 … +0.160; 50 câu) | Δ = +0.263 (95%: +0.150 … +0.393; 50 câu) |
| Public-90 | +14 / −0 câu · McNemar p = 0.000122 | Δ = +0.294 (95%: +0.197 … +0.390; 76 câu) | Δ = +0.135 (95%: +0.078 … +0.194; 76 câu) | Δ = +0.327 (95%: +0.232 … +0.428; 76 câu) |
| Stress-60 | +8 / −0 câu · McNemar p = 0.00781 | Δ = +0.351 (95%: +0.233 … +0.467; 52 câu) | Δ = +0.275 (95%: +0.129 … +0.429; 19 câu) | Δ = +0.373 (95%: +0.221 … +0.518; 52 câu) |
| Probe-25 | +14 / −0 câu · McNemar p = 0.000122 | — | — | — |
| Paraphrase-52 | +10 / −0 câu · McNemar p = 0.00195 | Δ = +0.313 (95%: +0.179 … +0.452; 42 câu) | Δ = +0.130 (95%: +0.022 … +0.244; 26 câu) | Δ = +0.310 (95%: +0.167 … +0.452; 42 câu) |

## 4. Khoảng tin cậy 95% (bootstrap theo câu hỏi)

Với 60 câu, mỗi câu ≈ 1,7 điểm phần trăm; nhóm 6–14 câu VERSIONING mỗi câu 7–17 điểm – nên đọc kèm số câu.

| tập | Quyết định đúng | Recall@5 | Answer Correctness | Citation Accuracy | Unsupported | Abstention F1 | Versioning |
|---|---|---|---|---|---|---|---|
| Dev-30 | 1.000 [1.000–1.000] | 0.936 [0.859–1.000] | 0.831 [0.764–0.897] | 0.891 [0.808–0.962] | 0.000 [0.000–0.000] | 1.000 [1.000–1.000] | 1.000 [1.000–1.000] |
| Ext-60 | 1.000 [1.000–1.000] | 0.887 [0.827–0.940] | 0.645 [0.563–0.721] | 0.953 [0.910–0.990] | 0.000 [0.000–0.000] | 1.000 [1.000–1.000] | 1.000 [1.000–1.000] |
| Public-90 | 1.000 [1.000–1.000] | 0.904 [0.855–0.947] | 0.708 [0.645–0.769] | 0.932 [0.893–0.967] | 0.000 [0.000–0.000] | 1.000 [1.000–1.000] | 1.000 [1.000–1.000] |
| Stress-60 | 1.000 [1.000–1.000] | 0.710 [0.633–0.788] | 0.668 [0.548–0.778] | 0.758 [0.662–0.846] | 0.000 [0.000–0.000] | 1.000 [1.000–1.000] | 1.000 [1.000–1.000] |
| Probe-25 | 1.000 [1.000–1.000] | — | — | — | 0.000 [0.000–0.000] | 1.000 [1.000–1.000] | 1.000 [1.000–1.000] |
| Paraphrase-52 | 1.000 [1.000–1.000] | 0.853 [0.762–0.925] | 0.775 [0.698–0.848] | 0.821 [0.714–0.917] | 0.000 [0.000–0.000] | 1.000 [1.000–1.000] | 1.000 [1.000–1.000] |

## 5. Ablation thêm dần B0 → B6 (Public-90 = Dev-30 + Ext-60)

Mỗi dòng bật thêm một khối của pipeline so với dòng trước; B2′ thay CHRONOS bằng cách của pipeline tham khảo (lọc cứng chunk không còn hiệu lực tại reference_date trước khi xếp hạng) để so hai cách xử lý phiên bản. B6 là hệ thống nộp bài.

| cấu hình | Recall@5 | MRR@5 | Answer Correctness | Citation Accuracy | Unsupported | Abstention P | Abstention R | Abstention F1 | Versioning | Source Priority | quyết định đúng | latency TB (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 – BM25 thuần (baseline) | 0.610 | 0.616 | 0.573 | 0.605 | 0.156 | — | 0.000 | 0.000 | 0.400 | 0.083 | 0.844 | 12.400 |
| B1 – + truy hồi lai, chuẩn hóa truy vấn | 0.725 | 0.701 | 0.617 | 0.678 | 0.156 | — | 0.000 | 0.000 | 0.400 | 0.083 | 0.844 | 21.300 |
| B2 – + CHRONOS (chuyển hướng phiên bản) | 0.797 | 0.777 | 0.658 | 0.783 | 0.156 | — | 0.000 | 0.000 | 0.700 | 0.333 | 0.844 | 23.900 |
| B2′ – B1 + lọc cứng theo ngày | 0.766 | 0.732 | 0.628 | 0.724 | 0.156 | — | 0.000 | 0.000 | 0.600 | 0.083 | 0.844 | 20.000 |
| B3 – + xếp hạng thẩm quyền, cấu trúc Điều, truy nguồn FAQ | 0.904 | 0.884 | 0.676 | 0.961 | 0.156 | — | 0.000 | 0.000 | 1.000 | 0.083 | 0.844 | 42.200 |
| B4 – + Guard, cổng đủ căn cứ | 0.904 | 0.884 | 0.676 | 0.961 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.083 | 1.000 | 41.600 |
| B5 – + soạn nhiều căn cứ, kiểm toán citation | 0.904 | 0.884 | 0.708 | 0.932 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.500 | 1.000 | 43.000 |
| B6 – + ngưỡng độ tin cậy (= hệ thống đầy đủ) | 0.904 | 0.884 | 0.708 | 0.932 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.500 | 1.000 | 37.900 |

## 6. Ablation bỏ từng thành phần (Dev-30 + Probe-25)

| hệ thống | recall_at_5 | answer_accuracy | citation_accuracy | unsupported_rate | abstention_f1 | versioning_accuracy | latency_ms_avg | citation_recall | evidence_mismatch_rate | decision_accuracy | brier | ece |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B0 – BM25 thuần (baseline) | 0.538 | 0.619 | 0.442 | 0.327 | 0.0 | 0.2 | 5.2 | 0.282 | 0.5 | 0.673 | 0.383 | 0.432 |
| CHRONOS-LEDGER (đầy đủ) | 0.936 | 0.831 | 0.891 | 0.0 | 1.0 | 1.0 | 13.9 | 0.724 | 0.0 | 1.0 | 0.01 | 0.062 |
| – bỏ CHRONOS (versioning) | 0.891 | 0.775 | 0.776 | 0.0 | 1.0 | 0.5 | 13.2 | 0.547 | 0.115 | 1.0 | 0.058 | 0.068 |
| – bỏ Authority rerank | 0.708 | 0.755 | 0.692 | 0.0 | 1.0 | 0.8 | 8.9 | 0.528 | 0.154 | 1.0 | 0.073 | 0.078 |
| – bỏ truy nguồn FAQ (PRF) | 0.904 | 0.821 | 0.795 | 0.0 | 1.0 | 1.0 | 9.8 | 0.654 | 0.077 | 1.0 | 0.044 | 0.049 |
| – bỏ cấu trúc Điều | 0.891 | 0.822 | 0.865 | 0.0 | 1.0 | 1.0 | 20.5 | 0.699 | 0.0 | 1.0 | 0.01 | 0.061 |
| – bỏ Guard & Gate | 0.936 | 0.831 | 0.891 | 0.327 | 0.0 | 1.0 | 33.3 | 0.724 | 0.0 | 0.673 | 0.159 | 0.169 |
| – bỏ TF-IDF (chỉ BM25) | 0.904 | 0.791 | 0.853 | 0.0 | 1.0 | 1.0 | 30.4 | 0.686 | 0.038 | 1.0 | 0.028 | 0.044 |

## 7. KPI chính trên giao diện (Dev-30 – đáp án BTC + Probe-25)

| KPI | Giá trị | Mục tiêu | Nguồn mục tiêu | Trạng thái | Baseline B0 | Chỉ số kèm |
|---|---|---|---|---|---|---|
| 1. Retrieval Recall@5 | 0.936 | >= 0.8 | đề thi | ✅ Đạt | 0.538 | MRR@5 0.962 (1 = đoạn đúng luôn đứng đầu) · Recall@5 theo văn bản 0.962 |
| 2. Answer Accuracy / Correctness (độ phủ ý chính) | 0.831 | >= 0.7 | đội đề xuất | ✅ Đạt | 0.619 | Thang 0 / 0,5 / 1: 0.904 (26 câu ANSWER, chấm tự động) |
| 3. Citation Accuracy | 0.891 | >= 0.8 | đề thi | ✅ Đạt | 0.442 | 100% citation đạt đủ 4 điều kiện kiểm tra |
| 4. Unsupported Answer Rate | 0.0 | <= 0.1 | đội đề xuất | ✅ Đạt | 0.327 | 0/37 câu trả lời có nội dung thiếu căn cứ |
| 5. Abstention Quality (F1) | 1.0 | >= 0.9 | đội đề xuất | ✅ Đạt | 0.0 | Từ chối đúng 18/18 câu cần từ chối · từ chối nhầm 0 (P 1.000 · R 1.000) |
| 6. Versioning Accuracy | 1.0 | >= 0.9 | đội đề xuất | ✅ Đạt | 0.2 | Đúng 10/10 câu hỏi phiên bản |
| 7. Latency trung bình (ms) | 28.9 | <= 10000 | đề thi | ✅ Đạt | 5.2 | p95 78 ms · 145 lượt đo |

## 8. KPI tách theo answer_scope (hệ thống đầy đủ)

| tập | phạm vi | số câu | quyết định đúng | Recall@5 | MRR@5 | Answer Correctness | Citation Accuracy | Unsupported | Versioning | Source Priority | latency TB (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Dev-30 | LEGAL | 10 | 1.000 | 1.000 | 0.950 | 0.877 | 1.000 | 0.000 | — | — | 18.700 |
| Dev-30 | INTERNAL | 9 | 1.000 | 0.870 | 1.000 | 0.798 | 0.722 | 0.000 | — | — | 53.100 |
| Dev-30 | MIXED | 3 | 1.000 | 0.833 | 0.833 | 0.717 | 0.889 | 0.000 | — | 0.667 | 82.300 |
| Dev-30 | VERSIONING | 4 | 1.000 | 1.000 | 1.000 | 0.877 | 1.000 | 0.000 | 1.000 | — | 25.200 |
| Dev-30 | OUT_OF_SCOPE | 4 | 1.000 | — | — | — | — | — | — | — | 1.200 |
| Ext-60 | LEGAL | 10 | 1.000 | 1.000 | 0.950 | 0.721 | 1.000 | 0.000 | — | — | 24.100 |
| Ext-60 | INTERNAL | 25 | 1.000 | 0.860 | 0.829 | 0.696 | 0.940 | 0.000 | — | — | 53.300 |
| Ext-60 | MIXED | 9 | 1.000 | 0.815 | 0.717 | 0.582 | 0.907 | 0.000 | — | 0.444 | 68.400 |
| Ext-60 | VERSIONING | 6 | 1.000 | 0.917 | 0.917 | 0.396 | 1.000 | 0.000 | 1.000 | — | 31.700 |
| Ext-60 | OUT_OF_SCOPE | 10 | 1.000 | — | — | — | — | — | — | — | 1.000 |
| Public-90 | LEGAL | 20 | 1.000 | 1.000 | 0.950 | 0.799 | 1.000 | 0.000 | — | — | 21.400 |
| Public-90 | INTERNAL | 34 | 1.000 | 0.863 | 0.875 | 0.723 | 0.882 | 0.000 | — | — | 53.200 |
| Public-90 | MIXED | 12 | 1.000 | 0.819 | 0.746 | 0.616 | 0.903 | 0.000 | — | 0.500 | 71.900 |
| Public-90 | VERSIONING | 10 | 1.000 | 0.950 | 0.950 | 0.589 | 1.000 | 0.000 | 1.000 | — | 29.100 |
| Public-90 | OUT_OF_SCOPE | 14 | 1.000 | — | — | — | — | — | — | — | 1.100 |
| Stress-60 | LEGAL | 7 | 1.000 | 0.929 | 0.833 | 0.654 | 0.786 | 0.000 | — | — | 27.600 |
| Stress-60 | INTERNAL | 30 | 1.000 | 0.640 | 0.836 | 0.676 | 0.717 | 0.000 | — | — | 58.100 |
| Stress-60 | VERSIONING | 14 | 1.000 | 0.760 | 0.871 | — | 0.851 | 0.000 | 1.000 | — | 26.400 |
| Stress-60 | OUT_OF_SCOPE | 8 | 1.000 | — | — | — | — | — | — | — | 14.200 |
| Stress-60 | MIXED | 1 | 1.000 | 0.600 | 0.500 | — | 0.500 | 0.000 | — | 1.000 | 68.000 |
| Probe-25 | OUT_OF_SCOPE | 14 | 1.000 | — | — | — | — | — | — | — | 16.200 |
| Probe-25 | (không nhãn) | 5 | 1.000 | — | — | — | — | 0.000 | — | — | 40.000 |
| Probe-25 | VERSIONING | 6 | 1.000 | — | — | — | — | 0.000 | 1.000 | — | 20.800 |
| Paraphrase-52 | LEGAL | 14 | 1.000 | 0.929 | 0.929 | 0.834 | 0.929 | 0.000 | — | — | 27.000 |
| Paraphrase-52 | INTERNAL | 18 | 1.000 | 0.759 | 0.875 | 0.745 | 0.722 | 0.000 | — | — | 56.300 |
| Paraphrase-52 | MIXED | 4 | 1.000 | 0.792 | 0.750 | 0.529 | 0.625 | 0.000 | — | 0.250 | 58.800 |
| Paraphrase-52 | VERSIONING | 6 | 1.000 | 1.000 | 0.917 | 0.877 | 1.000 | 0.000 | 1.000 | — | 26.500 |
| Paraphrase-52 | OUT_OF_SCOPE | 10 | 1.000 | — | — | — | — | — | — | — | 7.700 |

## 9. Bảng lỗi (retrieval / citation / abstain / versioning / generation)

Chi tiết từng câu: `outputs/error_table.csv` (21 dòng) và `outputs/eval_results_all.csv`.

| error | Ext-60 | Paraphrase-52 | Stress-60 | Tổng |
|---|---|---|---|---|
| CITATION – không citation nào đúng nhãn | 0 | 2 | 5 | 7 |
| GENERATION – thiếu ý chính | 9 | 0 | 2 | 11 |
| RETRIEVAL – chunk chính không có trong top-5 | 0 | 2 | 1 | 3 |
| Tổng | 9 | 4 | 8 | 21 |

## 9b. Đối chiếu 90 câu public với đáp án

Dev-30 so với `answer_key_sample.csv` của BTC; Ext-60 so với nhãn đội. **khớp đủ** = mọi citation đúng và có đủ citation của chunk chính; **đúng nhưng thiếu** = mọi citation đúng nhưng chưa đủ; **một phần** = có citation đúng lẫn sai; **không khớp** = không citation nào đúng. Chi tiết từng câu (câu trả lời, đáp án tham chiếu, trace_id): `outputs/public90_audit.csv`.

| đối chiếu citation | Dev-30 | Ext-60 | Tổng |
|---|---|---|---|
| ABSTAIN đúng | 4 | 10 | 14 |
| khớp đủ | 12 | 20 | 32 |
| một phần | 6 | 5 | 11 |
| đúng nhưng thiếu | 8 | 25 | 33 |
| Tổng | 30 | 60 | 90 |

## 10. Kịch bản demo – output thật

Dùng để thay cột kỳ vọng của demo script (ghi trace_id từng case).

| case | mã | reference_date | hành vi kỳ vọng | kỳ vọng | quyết định | citations | chunk được dẫn | độ tin cậy | latency_ms | trace_id | khớp kỳ vọng |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A – một nguồn | Q001 | 2026-10-17 | ANSWER | LAW01_C001 | ANSWER | LAW01 – Điều 3 khoản 3 | LAW01_C001 | 0.971 | 14 | T20261110-113236-d7459a | Có |
| B1 – nhiều nguồn | Q042 | 2026-10-17 | ANSWER | LAW12_C009;LAW12_C011;SIM02_C006 | ANSWER | LAW12 – Điều 10 khoản 1 điểm b; LAW12 – Điều 10 khoản 1; SIM02 – Điều 7 | LAW12_C009;LAW12_C011;SIM02_C006 | 0.969 | 102 | T20261110-113236-6453b0 | Có |
| B2 – versioning | tự đặt | 2025-05-15 | ANSWER | LAW09 | ANSWER | LAW09 – Điều 1 | LAW09_C001 | 0.969 | 15 | T20261110-113236-ef05b9 | Có |
| B2 – versioning | tự đặt | 2025-06-15 | ANSWER | LAW06 | ANSWER | LAW06 – Điều 12 khoản 1 | LAW06_C016 | 0.970 | 21 | T20261110-113236-b70ebe | Có |
| B2 – versioning | tự đặt | 2026-08-15 | ANSWER | LAW12 | ANSWER | LAW12 – Điều 24–25 | LAW12_C014 | 0.969 | 28 | T20261110-113236-a5755e | Có |
| C – ABSTAIN | Q077 | 2026-10-17 | ABSTAIN |  | ABSTAIN |  |  | 0.050 | 2 | T20261110-113236-602615 | Có |

## 11. Toàn bộ 90 câu public

- n_questions: 90
- answered: 76
- abstained: 14
- abstained_ids: Q077, Q078, Q079, Q080, Q081, Q082, Q083, Q084, Q085, Q086, Q087, Q088, Q089, Q090
- citation_in_citation_map: 1.0
- citation_valid_at_reference_date: 1.0
- latency_ms_avg: 38.1
- latency_ms_p95: 90.8
- latency_ms_max: 119

## 12. Độ bền với câu hỏi ngoài đáp án mẫu (không dùng để tinh chỉnh)

| tập | số câu | quyết định đúng | căn cứ đúng trong top-5 | citation [1] đúng | có citation đúng | độ chính xác citation | versioning |
|---|---|---|---|---|---|---|---|
| Ext-60 – 60 câu public còn lại (nhãn đội) | 60 | 1.000 | 1.000 | 0.920 | 1.000 | 0.953 | 1.000 |
| Paraphrase-52 – diễn đạt lại, viết tắt, ngoài phạm vi | 52 | 1.000 | 0.952 | 0.857 | 0.905 | 0.821 | 1.000 |
| Probe-25 – thăm dò ngoài phạm vi, versioning mốc mới | 25 | 1.000 | — | — | — | — | 1.000 |
| Stress-60 – kiểm thử chịu tải (đội viết; đã dùng phân tích lỗi từ 10/11/2026) | 60 | 1.000 | 0.981 | 0.769 | 0.885 | 0.758 | 1.000 |
