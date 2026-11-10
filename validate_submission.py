"""validate_submission.py – kiểm tra file nộp submission.csv của PolicyAssist AI (Festival CĐS 2026 · Bảng A · Case 1).

Đối chiếu với README Data Pack (mục 5 định dạng đầu ra, mục 6 ABSTAIN, mục 11 checklist trước khi nộp) và checklist
14 quy định của đội (quy định 6 thứ tự ranking, 7 schema, 8 citation). Script ĐỘC LẬP với policyassist.py, chỉ dùng thư
viện chuẩn của Python, để kiểm chéo file do hệ thống sinh ra (không dùng chung mã với bên tạo file).

Cách dùng:
    python validate_submission.py                                   # kiểm outputs/submission.csv
    python validate_submission.py duong_dan/submission.csv
    python validate_submission.py submission.csv --datapack data/DataPack-CASE1_PolicyAssist

Mã thoát: 0 = đạt mọi kiểm tra bắt buộc (có thể còn cảnh báo) · 1 = có kiểm tra FAIL · 2 = không đọc được file.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
COLUMNS = ["question_id", "answer", "retrieved_document_ids", "retrieved_chunk_ids", "citations", "confidence",
           "abstain", "latency_ms"]
ABSTAIN_PREFIX = "Không đủ căn cứ trong Data Pack để xác định"
FILES = {   # đường dẫn trong Data Pack (README mục 3); file metadata có thể mang tên document_metadata_v3_checked.csv
    "chunks": ["03_metadata/legal_chunks.csv"],
    "documents": ["03_metadata/document_metadata.csv", "03_metadata/document_metadata_v3_checked.csv"],
    "citation_map": ["citation_map.csv", "03_metadata/citation_map.csv"],
    "questions": ["04_questions/questions_sample.csv"],
    "template": ["submission_output_template.csv", "06_output_template/submission_output_template.csv"],
}
CHUNK_RE = re.compile(r"^(?:LAW|SIM)\d{2}_C\d{3}$")
DOC_RE = re.compile(r"^(?:LAW|SIM)\d{2}$")


def read_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def find(root: Path, key: str) -> Path | None:
    return next((root / c for c in FILES[key] if (root / c).exists()), None)


def split_list(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(";") if x.strip()]


def to_date(s: str) -> date | None:
    try:
        return date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


class Report:
    def __init__(self):
        self.rows: list[tuple[str, str, str, str]] = []

    def add(self, code: str, check: str, ok: bool | None, detail: str = "", warn: bool = False):
        status = "PASS" if ok else ("WARN" if warn else "FAIL") if ok is not None else "INFO"
        self.rows.append((code, check, status, detail))

    def failed(self) -> int:
        return sum(r[2] == "FAIL" for r in self.rows)

    def print(self):
        w = max(len(r[1]) for r in self.rows)
        for code, check, status, detail in self.rows:
            mark = {"PASS": "✓", "FAIL": "✗", "WARN": "!", "INFO": "·"}[status]
            print(f"{mark} {code} {check:<{w}}  {status:<4}  {detail}")


def examples(items: list[str], n: int = 5) -> str:
    return ", ".join(items[:n]) + (f" … (+{len(items) - n})" if len(items) > n else "")


def validate(sub_path: Path, root: Path) -> Report:
    rep = Report()
    raw = sub_path.read_bytes()
    try:
        text = raw.decode("utf-8")
        rep.add("F01", "Mã hóa UTF-8", True, "có BOM như template" if text.startswith("﻿") else "không có BOM")
    except UnicodeDecodeError as exc:
        rep.add("F01", "Mã hóa UTF-8", False, str(exc))
        return rep
    text = text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text, newline=""))
    table = list(reader)
    if not table:
        rep.add("F02", "Tiêu đề 8 cột theo template", False, "file rỗng")
        return rep
    header, body = table[0], [r for r in table[1:] if any(c.strip() for c in r)]
    tpl = find(root, "template")
    tpl_cols = next(csv.reader(io.StringIO(tpl.read_text(encoding="utf-8-sig")))) if tpl else COLUMNS
    rep.add("F02", "Tiêu đề 8 cột đúng tên, đúng thứ tự template", header == tpl_cols,
            "" if header == tpl_cols else f"đang có {header}")
    bad_width = [str(i + 2) for i, r in enumerate(body) if len(r) != len(tpl_cols)]
    rep.add("F03", "Mỗi dòng đúng 8 ô", not bad_width, f"dòng sai số ô: {examples(bad_width)}" if bad_width else f"{len(body)} dòng")
    if header != tpl_cols or bad_width:
        return rep
    rows = [dict(zip(header, r)) for r in body]
    multiline = [r["question_id"] for r in rows if "\n" in r["answer"] or "\r" in r["answer"]]
    rep.add("F04", "Mỗi câu hỏi một dòng (answer không xuống dòng)", not multiline,
            f"{examples(multiline)}" if multiline else "", warn=True)

    # ---- question_id
    qs = {r["question_id"]: r for r in read_rows(find(root, "questions"))} if find(root, "questions") else {}
    tpl_ids = [r["question_id"] for r in read_rows(tpl)] if tpl else list(qs)
    ids = [r["question_id"] for r in rows]
    dup = sorted({q for q in ids if ids.count(q) > 1})
    rep.add("F05", "Không trùng question_id", not dup, examples(dup))
    missing, extra = [q for q in tpl_ids if q not in set(ids)], [q for q in ids if q not in set(tpl_ids)]
    rep.add("F06", "Đủ question_id của template, không thừa", not missing and not extra,
            (f"thiếu {examples(missing)} " if missing else "") + (f"thừa {examples(extra)}" if extra else "")
            or f"{len(ids)} câu")
    rep.add("F07", "Giữ thứ tự question_id như template", ids == [q for q in tpl_ids if q in set(ids)], "", warn=True)

    # ---- kiểu dữ liệu
    bad_conf = [r["question_id"] for r in rows if not re.fullmatch(r"(?:0(?:\.\d+)?|1(?:\.0+)?)", r["confidence"].strip())]
    rep.add("F08", "confidence là số thực trong [0, 1] (dấu chấm thập phân)", not bad_conf, examples(bad_conf))
    bad_abs = [r["question_id"] for r in rows if r["abstain"] not in ("TRUE", "FALSE")]
    rep.add("F09", "abstain chỉ nhận TRUE/FALSE", not bad_abs, examples(bad_abs))
    bad_lat = [r["question_id"] for r in rows if not re.fullmatch(r"[1-9]\d*", r["latency_ms"].strip())]
    rep.add("F10", "latency_ms là số nguyên dương (mili-giây)", not bad_lat, examples(bad_lat))

    # ---- ABSTAIN / ANSWER
    abst = [r for r in rows if r["abstain"] == "TRUE"]
    ans = [r for r in rows if r["abstain"] == "FALSE"]
    bad_text = [r["question_id"] for r in abst if not r["answer"].strip().startswith(ABSTAIN_PREFIX)]
    rep.add("F11", f'ABSTAIN: answer mở đầu "{ABSTAIN_PREFIX}…"', not bad_text, examples(bad_text))
    not_empty = [r["question_id"] for r in abst
                 if r["retrieved_document_ids"] or r["retrieved_chunk_ids"] or r["citations"]]
    rep.add("F12", "ABSTAIN: để trống retrieved_document_ids, retrieved_chunk_ids, citations", not not_empty,
            examples(not_empty))
    empty = [r["question_id"] for r in ans if not (r["answer"].strip() and r["retrieved_chunk_ids"] and r["citations"])]
    rep.add("F13", "ANSWER: có answer, retrieved_chunk_ids và citations", not empty, examples(empty))

    # ---- danh sách ID và citation
    sep = [r["question_id"] for r in rows for col in ("retrieved_document_ids", "retrieved_chunk_ids")
           if "," in r[col] or r[col].strip().startswith(";") or r[col].strip().endswith(";") or ";;" in r[col]]
    rep.add("F14", "Danh sách ID phân cách bằng ';' (không ',' và không phần tử rỗng)", not sep, examples(sorted(set(sep))))
    chunks = {r["chunk_id"]: r for r in read_rows(find(root, "chunks"))} if find(root, "chunks") else {}
    docs = {r["document_id"] for r in read_rows(find(root, "documents"))} if find(root, "documents") else set()
    cmap = read_rows(find(root, "citation_map")) if find(root, "citation_map") else []
    by_label: dict[str, list[dict]] = {}
    for c in cmap:
        by_label.setdefault(c["citation_label"], []).append(c)
    unknown_chunk, dup_chunk, unknown_doc, doc_mismatch, doc_order = [], [], [], [], []
    for r in rows:
        cs, ds = split_list(r["retrieved_chunk_ids"]), split_list(r["retrieved_document_ids"])
        unknown_chunk += [f'{r["question_id"]}:{c}' for c in cs if not CHUNK_RE.match(c) or (chunks and c not in chunks)]
        if len(set(cs)) < len(cs):
            dup_chunk.append(r["question_id"])
        unknown_doc += [f'{r["question_id"]}:{d}' for d in ds if not DOC_RE.match(d) or (docs and d not in docs)]
        chunk_docs = list(dict.fromkeys((chunks[c]["document_id"] if c in chunks else c[:5]) for c in cs))
        if set(chunk_docs) != set(ds):
            doc_mismatch.append(r["question_id"])
        elif chunk_docs != ds:
            doc_order.append(r["question_id"])
    rep.add("F15", "retrieved_chunk_ids tồn tại trong legal_chunks.csv", not unknown_chunk, examples(unknown_chunk))
    rep.add("F16", "Không lặp chunk trong một dòng", not dup_chunk, examples(dup_chunk))
    rep.add("F17", "retrieved_document_ids tồn tại trong document_metadata", not unknown_doc, examples(unknown_doc))
    rep.add("F18", "retrieved_document_ids khớp tài liệu của các chunk đã truy xuất", not doc_mismatch, examples(doc_mismatch))
    rep.add("F19", "Thứ tự tài liệu theo hạng chunk đầu tiên của mỗi tài liệu (quy định 6)", not doc_order,
            examples(doc_order), warn=True)
    unknown_cit, not_retrieved, out_of_date = [], [], []
    n_cit = 0
    for r in ans:
        cs = set(split_list(r["retrieved_chunk_ids"]))
        ref = to_date(qs.get(r["question_id"], {}).get("reference_date", "")) or date(2026, 10, 17)
        for lb in split_list(r["citations"]):
            n_cit += 1
            cands = by_label.get(lb)
            if not cands:
                unknown_cit.append(f'{r["question_id"]}:{lb}')
                continue
            hit = [c for c in cands if c["chunk_id"] in cs]
            if not hit:
                not_retrieved.append(f'{r["question_id"]}:{lb}')
                continue
            valid = any((to_date(c.get("effective_from", "")) or date.min) <= ref <= (to_date(c.get("effective_to", "")) or date.max)
                        for c in hit)
            if not valid:
                out_of_date.append(f'{r["question_id"]}:{lb}')
    rep.add("F20", "Citation có trong citation_map.csv (không tự tạo)", not unknown_cit, examples(unknown_cit) or f"{n_cit} citation")
    rep.add("F21", "Mỗi citation ứng với một chunk đã truy xuất (quy định 8)", not not_retrieved, examples(not_retrieved))
    rep.add("F22", "Citation còn hiệu lực tại reference_date", not out_of_date,
            (f"{len(out_of_date)} citation dẫn văn bản lịch sử – hợp lệ nếu là câu hỏi về phiên bản: "
             + examples(out_of_date)) if out_of_date else "", warn=True)
    lat = [int(r["latency_ms"]) for r in rows if r["latency_ms"].strip().isdigit()]
    if lat:
        s = sorted(lat)
        p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
        rep.add("F23", "Latency trung bình ≤ 10.000 ms (mục tiêu đề thi)", sum(lat) / len(lat) <= 10000,
                f"TB {sum(lat) / len(lat):.0f} ms · p95 {p95} ms · tối đa {max(lat)} ms", warn=True)
    rep.add("I01", "Tổng hợp", None, f"{len(rows)} câu · ANSWER {len(ans)} · ABSTAIN {len(abst)} · {n_cit} citation")
    return rep


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:                                          # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="Kiểm tra submission.csv theo README Data Pack và checklist 14 quy định.")
    ap.add_argument("submission", nargs="?", default=str(HERE / "outputs" / "submission.csv"))
    ap.add_argument("--datapack", default=str(HERE / "data" / "DataPack-CASE1_PolicyAssist"))
    a = ap.parse_args(argv)
    sub, root = Path(a.submission), Path(a.datapack)
    if not sub.exists():
        print(f"Không tìm thấy {sub}")
        return 2
    missing = [k for k in FILES if find(root, k) is None]
    if missing:
        print(f"Không tìm thấy file Data Pack: {', '.join(missing)} trong {root}")
        return 2
    rep = validate(sub, root)
    print(f"Kiểm tra {sub} · Data Pack {root}\n")
    rep.print()
    n_fail = rep.failed()
    n_warn = sum(r[2] == "WARN" for r in rep.rows)
    print(f"\n{'❌ KHÔNG ĐẠT' if n_fail else '✅ ĐẠT'}: {n_fail} lỗi · {n_warn} cảnh báo")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
