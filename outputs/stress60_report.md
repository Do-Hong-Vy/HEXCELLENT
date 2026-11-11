# Stress-60 – PolicyAssist AI V1.0

- Thời điểm chạy: 02:08 12/11/2026 · corpus fingerprint 7357afec5ef0
- Bộ câu: 60 câu (14 kiểu stress) · ANSWER 52 · ABSTAIN 8 · nhãn: data/eval/stress60_labels.csv (trạng thái: Nháp – kế thừa nhãn từ seed 30, Đã đối chiếu chunk_text 22, Đã kiểm tra corpus không có dữ liệu 8).
- Recall@5: tỷ lệ chunk kỳ vọng nằm trong 5 chunk đầu (câu bị ABSTAIN tính 0). Citation Accuracy: tỷ lệ citation dẫn đúng nhãn/chunk kỳ vọng (như KPI 3). Versioning: văn bản LAW đầu tiên được dẫn còn hiệu lực tại mốc thuộc tập văn bản kỳ vọng. Phạm vi theo nguồn: chỉ trích LAW → LEGAL, chỉ SIM → INTERNAL, cả hai → MIXED, câu hiệu lực → VERSIONING, ABSTAIN → OUT_OF_SCOPE.
- Không dùng bộ này để tinh chỉnh ngưỡng.

## Kết quả

| hệ thống | số câu | quyết định đúng | F1 ABSTAIN | Recall@5 | căn cứ đúng top-5 | Citation Accuracy | citation [1] đúng | có citation đúng | đúng văn bản | Versioning | phạm vi nguồn đúng | κ phạm vi nguồn | citation hợp lệ | latency TB (ms) | latency p95 (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CHRONOS-LEDGER | 60 | 1.0 | 1.0 | 0.742 | 1.0 | 0.848 | 0.846 | 1.0 | 1.0 | 1.0 | 0.967 | 0.951 | 1.0 | 19.6 | 41.0 |
| B0 – BM25 thuần | 60 | 0.867 | 0.0 | 0.36 | 0.654 | 0.394 | 0.423 | 0.442 | 0.692 | 0.214 | 0.8 | 0.682 | 0.9 | 6.1 | 9.0 |

## Theo kiểu stress (CHRONOS-LEDGER)

| kiểu stress | số câu | quyết định đúng | Recall@5 | Citation Accuracy | citation [1] đúng | có citation đúng | Versioning |
|---|---|---|---|---|---|---|---|
| PARAPHRASE | 6 | 1.0 | 1.0 | 0.944 | 1.0 | 1.0 | — |
| NO_DIACRITIC | 4 | 1.0 | 0.75 | 0.875 | 1.0 | 1.0 | — |
| ABBREV_TYPO | 1 | 1.0 | 0.333 | 0.5 | 1.0 | 1.0 | — |
| ABBREV_CODEMIX | 5 | 1.0 | 0.893 | 1.0 | 1.0 | 1.0 | — |
| FALSE_PREMISE | 8 | 1.0 | 0.688 | 0.938 | 1.0 | 1.0 | 1.0 |
| OUTDATED_BAIT | 4 | 1.0 | 0.533 | 0.812 | 0.75 | 1.0 | 1.0 |
| TEMPORAL_BOUNDARY | 7 | 1.0 | 0.881 | 0.81 | 0.714 | 1.0 | 1.0 |
| TEMPORAL_IMPLICIT | 3 | 1.0 | 0.875 | 1.0 | 1.0 | 1.0 | 1.0 |
| INJECTION | 5 | 1.0 | 0.75 | 0.778 | 0.667 | 1.0 | — |
| NEAR_MISS_OOS | 5 | 1.0 | — | — | — | — | — |
| PARTIAL_OOS | 3 | 1.0 | 0.5 | 0.667 | 0.667 | 1.0 | — |
| MULTI_HOP | 4 | 1.0 | 0.567 | 0.625 | 0.75 | 1.0 | — |
| NUMERIC_TRAP | 4 | 1.0 | 0.675 | 0.792 | 0.5 | 1.0 | — |
| AMBIGUOUS | 1 | 1.0 | 0.5 | 1.0 | 1.0 | 1.0 | — |

## Theo trạng thái nhãn

| trạng thái nhãn | số câu | quyết định đúng | Recall@5 | Citation Accuracy | citation [1] đúng | có citation đúng | Versioning |
|---|---|---|---|---|---|---|---|
| Nháp – kế thừa nhãn từ seed | 30 | 1.0 | 0.764 | 0.858 | 0.9 | 1.0 | 1.0 |
| Đã kiểm tra corpus không có dữ liệu | 8 | 1.0 | — | — | — | — | — |
| Đã đối chiếu chunk_text | 22 | 1.0 | 0.711 | 0.833 | 0.773 | 1.0 | 1.0 |

## Ma trận phạm vi (hàng = nhãn, cột = phạm vi theo nguồn trích dẫn)

| nhãn phạm vi | INTERNAL | LEGAL | MIXED | OUT_OF_SCOPE | VERSIONING | Tổng |
|---|---|---|---|---|---|---|
| INTERNAL | 28 | 0 | 1 | 0 | 1 | 30 |
| LEGAL | 0 | 7 | 0 | 0 | 0 | 7 |
| MIXED | 0 | 0 | 1 | 0 | 0 | 1 |
| OUT_OF_SCOPE | 0 | 0 | 0 | 8 | 0 | 8 |
| VERSIONING | 0 | 0 | 0 | 0 | 14 | 14 |
| Tổng | 28 | 7 | 2 | 8 | 15 | 60 |

## Câu cần xem lại (0)

Sai quyết định, hoặc trả lời mà không có citation/chunk kỳ vọng nào.

Không có.
