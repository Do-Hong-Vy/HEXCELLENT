# BẢNG A – CASE 1: POLICYASSIST AI
## Festival Chuyển đổi số 2026 – Vòng sơ khảo

**Tên bài toán:** PolicyAssist AI – Trợ lý tra cứu chính sách tài chính, kế toán và thuế có dẫn nguồn  
**Mục tiêu:** Xây dựng hệ thống hỏi–đáp dựa trên tập tài liệu được cung cấp, có khả năng tra cứu đúng nguồn, trả lời có căn cứ, xử lý phiên bản văn bản và biết từ chối khi dữ liệu không đủ.

> Lưu ý: Data Pack này được xây dựng phục vụ cuộc thi. Một số tài liệu nội bộ là **tài liệu giả lập** của Công ty Cổ phần Nova Việt và **không phải văn bản quy phạm pháp luật**.

---

## 1. Nhiệm vụ của đội thi

Đội thi cần xây dựng một hệ thống cho phép người dùng nhập câu hỏi bằng ngôn ngữ tự nhiên và nhận được câu trả lời có căn cứ từ Data Pack.

Hệ thống tối thiểu cần thực hiện được các chức năng sau:

1. Tra cứu các tài liệu/chunk liên quan đến câu hỏi.
2. Sinh câu trả lời dựa trên nội dung đã tra cứu.
3. Trả về nguồn dẫn tương ứng.
4. Phân biệt văn bản hiện hành và văn bản lịch sử khi câu hỏi phụ thuộc thời điểm.
5. Phân biệt nguồn pháp luật với quy trình/chính sách nội bộ.
6. Từ chối trả lời khi corpus không có đủ căn cứ.
7. Xuất kết quả theo đúng định dạng submission quy định.

Không bắt buộc sử dụng một kiến trúc cụ thể. Đội thi có thể sử dụng keyword search, TF-IDF, BM25, embedding, hybrid retrieval, reranking, RAG, LLM hoặc các kỹ thuật phù hợp khác.

---

## 2. Nguyên tắc nguồn và thứ tự ưu tiên

Khi nhiều nguồn cùng liên quan, cần ưu tiên theo nguyên tắc:

**Văn bản pháp luật đang có hiệu lực → Quy chế/Quy trình nội bộ → Sổ tay/FAQ nội bộ.**

Nếu tài liệu nội bộ dẫn chiếu một văn bản pháp luật đã hết hiệu lực, hệ thống phải kiểm tra metadata và sử dụng văn bản pháp luật phù hợp với `reference_date`.

Tại mốc corpus **17/10/2026**, các văn bản pháp luật hiện hành ưu tiên trong Data Pack gồm:

- `LAW10` – Luật Quản lý thuế 108/2025/QH15;
- `LAW11` – Nghị định 254/2026/NĐ-CP;
- `LAW12` – Thông tư 91/2026/TT-BTC.

Một số tài liệu `LAW04`–`LAW09` vẫn được giữ lại để phục vụ câu hỏi lịch sử và đánh giá khả năng xử lý versioning.

---

## 3. Cấu trúc Data Pack

Gợi ý cấu trúc thư mục phát hành cho đội thi:

```text
CASE1_POLICYASSIST/
├── README.md
├── 01_documents/
│   ├── LAW01...
│   ├── ...
│   └── SIM08...
├── 02_documents_text/
│   ├── LAW01.txt
│   ├── ...
│   └── SIM08.txt
├── 03_metadata/
│   ├── document_metadata_v3_checked.csv
│   ├── legal_chunks.csv
│   └── citation_map.csv
├── 04_questions/
│   └── questions_sample.csv
├── 05_answer_sample/
│   └── answer_key_sample.csv
└── 06_output_template/
    └── submission_output_template.csv
```


---

## 4. Các tệp dữ liệu chính

### 4.1. `document_metadata_v3_checked.csv`

Chứa metadata của toàn bộ 20 tài liệu:

- `LAW01`–`LAW12`: văn bản pháp luật;
- `SIM01`–`SIM08`: tài liệu nội bộ giả lập.

Một số trường quan trọng:

- `document_id`: mã tài liệu;
- `title`: tên tài liệu;
- `source_type`: loại nguồn;
- `document_type`: loại văn bản;
- `issue_date`: ngày ban hành;
- `effective_date`: ngày hiệu lực;
- `status`: trạng thái;
- `corpus_role`: vai trò trong corpus;
- `supersedes`: văn bản bị thay thế;
- `superseded_by`: văn bản thay thế;
- `priority_level`: mức ưu tiên;
- `source_url`: nguồn tham chiếu.

---

### 4.2. `legal_chunks.csv`

Đây là corpus retrieval chính.

Mỗi dòng tương ứng với một chunk. Các trường chính:

| Trường | Ý nghĩa |
|---|---|
| `chunk_id` | Mã chunk duy nhất |
| `document_id` | Mã tài liệu nguồn |
| `document_title` | Tên tài liệu |
| `source_type` | LEGAL hoặc SIMULATED_INTERNAL |
| `section` | Phần/Mục |
| `article` | Điều hoặc định danh nội dung |
| `clause` | Khoản nếu có |
| `heading` | Tiêu đề chunk |
| `topic` | Chủ đề |
| `subtopic` | Chủ đề chi tiết |
| `effective_from` | Thời điểm bắt đầu áp dụng |
| `effective_to` | Thời điểm kết thúc áp dụng nếu có |
| `status` | Trạng thái văn bản |
| `source_locator` | Vị trí trong nguồn |
| `content_type` | Loại nội dung |
| `chunk_text` | Nội dung dùng cho retrieval |
| `citation_label` | Nhãn citation chuẩn |
| `source_url` | URL nguồn nếu có |

Corpus hiện gồm **374 chunks**.

Đối với các tài liệu pháp luật, `content_type=NORMALIZED_SUMMARY` nghĩa là nội dung đã được chuẩn hóa và tóm tắt sát nguồn để phục vụ retrieval; đây không phải bản sao nguyên văn toàn bộ văn bản pháp luật.

---

### 4.3. `citation_map.csv`

Ánh xạ chuẩn giữa:

`chunk_id → document → vị trí nguồn → citation_label`.

Đội thi nên ưu tiên sử dụng `citation_label` đúng như trong file này khi xuất trường `citations`.

Ví dụ:

```text
LAW01 – Điều 16
SIM04 – Điều 5
```

Không tự tạo citation nếu không tương ứng với chunk đã truy xuất.

---

### 4.4. `questions_sample.csv`

Bộ câu hỏi public để đội thi phát triển và kiểm thử hệ thống.

Các cột:

```text
question_id
question_text
reference_date
```

`reference_date` đặc biệt quan trọng với các câu hỏi versioning.

---

### 4.5. `answer_key_sample.csv`

Cung cấp đáp án mẫu cho một phần câu hỏi public.

Mục đích:

- minh họa loại câu trả lời kỳ vọng;
- minh họa relevant document/chunk;
- minh họa citation chuẩn;
- minh họa trường hợp `ANSWER` và `ABSTAIN`.

Không nên hard-code hệ thống theo các câu hỏi mẫu.

---

## 5. Định dạng đầu ra bắt buộc

Đội thi phải xuất file CSV theo đúng cấu trúc của:

`submission_output_template.csv`

Các cột:

| Cột | Yêu cầu |
|---|---|
| `question_id` | Giữ nguyên mã câu hỏi |
| `answer` | Câu trả lời của hệ thống |
| `retrieved_document_ids` | Danh sách document theo thứ tự retrieval, phân cách bằng `;` |
| `retrieved_chunk_ids` | Danh sách chunk theo thứ tự retrieval, phân cách bằng `;` |
| `citations` | Citation đã thực sự dùng trong câu trả lời, phân cách bằng `;` |
| `confidence` | Số thực từ 0 đến 1 |
| `abstain` | `TRUE` hoặc `FALSE` |
| `latency_ms` | Thời gian xử lý câu hỏi, đơn vị ms |

Ví dụ:

```csv
question_id,answer,retrieved_document_ids,retrieved_chunk_ids,citations,confidence,abstain,latency_ms
Q001,"Chứng từ kế toán là ...","LAW01","LAW01_C001","LAW01 – Điều 3",0.93,FALSE,842
```

Nếu hệ thống không đủ căn cứ để trả lời:

```csv
Q077,"Không đủ căn cứ trong Data Pack để xác định thông tin này.",,,,0.18,TRUE,615
```

---

## 6. Quy tắc `ABSTAIN`

Hệ thống phải biết từ chối trả lời khi:

- Data Pack không chứa thông tin cần thiết;
- câu hỏi yêu cầu dữ liệu doanh nghiệp thực tế nhưng corpus chỉ có dữ liệu giả lập;
- câu hỏi đòi hỏi thông tin cá nhân, thông tin tài chính cụ thể hoặc dữ liệu vận hành không tồn tại trong corpus;
- không thể xác định văn bản phù hợp do thiếu thông tin thời điểm và không đủ cơ sở để suy luận an toàn.

Không được tự suy đoán hoặc bịa dữ liệu để tránh `ABSTAIN`.

Ví dụ nội dung trả lời phù hợp:

```text
Không đủ căn cứ trong Data Pack để xác định thông tin này.
```

---

## 7. Xử lý versioning

Một câu hỏi có thể yêu cầu áp dụng pháp luật tại một thời điểm trong quá khứ.

Ví dụ:

- trước 01/06/2025;
- từ 01/06/2025;
- trước 01/07/2026;
- từ 01/07/2026.

Hệ thống không nên mặc định luôn dùng văn bản mới nhất.

Cần kết hợp ít nhất:

- `reference_date`;
- `effective_from`;
- `effective_to`;
- `status`;
- `supersedes`;
- `superseded_by`.

Ví dụ chuỗi versioning trong Data Pack:

```text
LAW09 → LAW06 → LAW12
```

và:

```text
LAW07 + LAW08 → LAW11
```

---

## 8. Khuyến nghị pipeline kỹ thuật

Một pipeline tham khảo:

```text
Question
   ↓
Query preprocessing / rewriting
   ↓
Metadata filtering theo reference_date
   ↓
Retriever
   ↓
Top-k chunks
   ↓
Optional reranker
   ↓
Source-priority / version validation
   ↓
Answer generation
   ↓
Citation verification
   ↓
Confidence estimation
   ↓
ANSWER hoặc ABSTAIN
```

Các đội được phép thiết kế pipeline khác nếu đạt mục tiêu.

---

## 9. KPI/metric gợi ý

Các KPI phù hợp với Case 1 gồm:

| KPI | Ý nghĩa |
|---|---|
| Retrieval Recall@5 | Khả năng đưa tài liệu/chunk liên quan vào top-5 |
| Answer Accuracy / Correctness | Mức độ đúng của câu trả lời so với căn cứ trong Data Pack |
| Citation Accuracy | Citation có thực sự hỗ trợ cho nội dung trả lời hay không |
| Unsupported Answer Rate | Tỷ lệ câu trả lời chứa khẳng định không có căn cứ; càng thấp càng tốt |
| Abstention Quality | Khả năng trả lời khi đủ căn cứ và từ chối khi không đủ căn cứ |
| Versioning Accuracy | Khả năng chọn đúng văn bản theo `reference_date` |
| Latency | Thời gian xử lý câu hỏi |

Mục tiêu tham khảo trong đề thi:

```text
Recall@5 ≥ 0.80
Citation Accuracy ≥ 0.80
Thời gian phản hồi trung bình ≤ 10 giây
```

Các ngưỡng trên mang tính tham khảo. Đội thi cần mô tả rõ tập đánh giá, cách tính KPI và quy trình kiểm thử.

---

## 10. Một số lỗi thường gặp

Đội thi nên tránh:

1. Chỉ tìm đúng từ khóa nhưng không kiểm tra hiệu lực văn bản.
2. Dùng FAQ nội bộ thay cho văn bản pháp luật.
3. Trả lời đúng nhưng citation sai.
4. Dẫn một tài liệu có liên quan nhưng không chứa căn cứ thực sự cho câu trả lời.
5. Bịa thông tin khi corpus không có dữ liệu.
6. Luôn trả lời thay vì sử dụng `ABSTAIN`.
7. Luôn `ABSTAIN` để tránh sai.
8. Hard-code đáp án theo bộ câu hỏi public.
9. Không giữ thứ tự ranking trong `retrieved_chunk_ids`.
10. Thay đổi tên `question_id` hoặc schema submission.

---

## 11. Checklist trước khi nộp

Trước khi nộp kết quả, đội thi cần kiểm tra:

- [ ] Tệp là CSV UTF-8.
- [ ] Đúng tên và đủ các cột theo template.
- [ ] Không thiếu `question_id`.
- [ ] Không trùng `question_id`.
- [ ] `confidence` nằm trong `[0,1]`.
- [ ] `abstain` chỉ nhận `TRUE` hoặc `FALSE`.
- [ ] Các danh sách ID dùng dấu `;`.
- [ ] `retrieved_chunk_ids` giữ nguyên thứ tự ranking.
- [ ] Citation tồn tại trong `citation_map.csv`.
- [ ] Không sử dụng dữ liệu ngoài phạm vi được BTC cho phép.
- [ ] Hệ thống xử lý được câu hỏi ngoài phạm vi và câu hỏi versioning.

---

## 12. Quy định sử dụng tài liệu giả lập

Các tài liệu `SIM01`–`SIM08` thuộc Công ty Cổ phần Nova Việt là dữ liệu giả lập được tạo riêng cho cuộc thi.

Không được hiểu hoặc công bố các dữ liệu này là thông tin của một doanh nghiệp có thật.

Các số liệu như:

- hạn mức;
- workflow;
- vai trò;
- SLA;
- ma trận phê duyệt;
- KPI;
- quy định công tác phí;

chỉ có ý nghĩa trong phạm vi Case Study.

---

## 13. Phiên bản Data Pack

```text
Case: PolicyAssist AI
Festival: CRYSTARA – Festival Chuyển đổi số 2026
Corpus snapshot: 17/10/2026
Documents: 20
LAW documents: 12
SIM documents: 8
Corpus chunks: 374
Public questions: 90
Public answer samples: 30
```

BTC có thể cập nhật Data Pack trước khi phát hành chính thức. Nếu có cập nhật, cần tăng version và giữ lại `corpus_manifest.csv` để đối chiếu.

---

**HẾT README – BẢNG A / CASE 1: POLICYASSIST AI**
