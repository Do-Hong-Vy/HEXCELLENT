# -*- coding: utf-8 -*-
"""
PolicyAssist AI – CHRONOS-LEDGER  (đội HEXCELLENT · Festival Chuyển đổi số 2026 · Bảng A · Case 1)

Trợ lý tra cứu chính sách tài chính – kế toán – thuế có dẫn nguồn, chỉ dựa trên Data Pack của BTC.
Không phải công cụ tư vấn pháp lý/thuế. SIM01–SIM08 là dữ liệu nội bộ GIẢ LẬP của "Công ty Cổ phần Nova Việt".

Pipeline của đội (mỗi câu hỏi):
  Question + reference_date
   → P0 Guard & P1 Query Planning
   → P2 Hybrid Retrieval (BM25 âm tiết + cụm 2 âm tiết  ⊕  TF-IDF ký tự)
   → P3 Version Resolution (CHRONOS: hiệu lực cấp chunk + đồ thị thay thế + thế chỗ bằng văn bản kế nhiệm)
   → P4 Authority-aware Reranking (luật còn hiệu lực → quy chế/quy trình → sổ tay/FAQ; truy nguồn gốc FAQ; cấu trúc Điều)
   → P5 Evidence Ledger & Answerability Gate
   → P6 Grounded Answer Composition (trích xuất, không bịa – mỗi ý gắn [n])
   → P7 Citation Audit (tồn tại, đã truy xuất, hỗ trợ nội dung, đúng thời điểm)
   → P8 Calibrated Confidence
   → ANSWER / ABSTAIN  (+ Audit Log JSONL)

Cách chạy (xem README.md):
  python policyassist.py                         # mở giao diện web
  python policyassist.py ask "Câu hỏi" --date 2026-10-17
  python policyassist.py batch                   # 90 câu public → outputs/submission.csv
  python policyassist.py eval                    # 7 KPI: baseline B0 vs CHRONOS-LEDGER + ablation
  python policyassist.py verify                  # kiểm tra toàn vẹn Data Pack (SHA-256 + cấu trúc)
"""
from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import html as _html
import json
import math
import re
import secrets
import subprocess
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field, fields, replace
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

# Giờ Việt Nam cho mọi mốc thời gian hiển thị / ghi nhật ký: máy chủ đám mây (Streamlit Cloud, Linux) chạy giờ UTC nên lịch sử,
# audit log, run_id sẽ lệch 7 tiếng. time.tzset() chỉ có trên Unix; Windows dùng giờ máy (đã là giờ Việt Nam) nên không đổi.
if hasattr(time, "tzset"):
    import os as _os
    _os.environ["TZ"] = "Asia/Ho_Chi_Minh"
    time.tzset()

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

# =============================================================================
# 0. ĐƯỜNG DẪN & HẰNG SỐ
# =============================================================================
APP_NAME = "PolicyAssist AI"
APP_VERSION = "V1.0"
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DATAPACK_DIR = DATA_DIR / "DataPack-CASE1_PolicyAssist"
MANIFEST_PATH = DATA_DIR / "corpus_manifest.csv"
MANIFEST_JSON = DATA_DIR / "corpus_manifest.json"
PROBE_PATH = DATA_DIR / "eval" / "probe_questions.csv"
EXT60_PATH = DATA_DIR / "eval" / "ext60_labels.csv"   # Ext-60: nhãn đội cho 60 câu public chưa có đáp án (2 người gán)
PARAPHRASE_PATH = DATA_DIR / "eval" / "paraphrase_questions.csv"   # câu diễn đạt lại / viết tắt / ngoài phạm vi
STRESS60_PATH = DATA_DIR / "eval" / "stress60_labels.csv"   # Stress-60: 60 câu kiểm thử chịu tải, 14 kiểu (đội soạn)
OUTPUT_DIR = ROOT / "outputs"
LOG_DIR = ROOT / "logs"
AUDIT_LOG = LOG_DIR / "audit_log.jsonl"
FEEDBACK_LOG = LOG_DIR / "feedback.jsonl"
HISTORY_DIR = LOG_DIR / "sessions"          # lịch sử tra cứu (mỗi phiên một file JSON)
DATAPACK_VERSION = "v1-snapshot-2026-10-17"

# Vị trí file theo Data Pack BTC phát hành; phương án thay thế theo cấu trúc gợi ý ở README mục 3
# (README gọi metadata là document_metadata_v3_checked.csv – trong Data Pack thực tế là document_metadata.csv).
FILE_CANDIDATES = {
    "chunks": ["03_metadata/legal_chunks.csv"],
    "documents": ["03_metadata/document_metadata.csv", "03_metadata/document_metadata_v3_checked.csv"],
    "citation_map": ["citation_map.csv", "03_metadata/citation_map.csv"],
    "questions": ["04_questions/questions_sample.csv"],
    "answer_key": ["05_answer_sample/answer_key_sample.csv"],
    "template": ["submission_output_template.csv", "06_output_template/submission_output_template.csv"],
}
REQUIRED_FILES = ("chunks", "documents", "citation_map", "questions", "template")
TEXT_DIR = "02_documents_text"
EXPECTED = {"documents": 20, "law": 12, "sim": 8, "chunks": 374, "questions": 90, "answers": 30}
SUBMISSION_COLUMNS = ["question_id", "answer", "retrieved_document_ids", "retrieved_chunk_ids",
                      "citations", "confidence", "abstain", "latency_ms"]

SNAPSHOT = date(2026, 10, 17)
ABSTAIN_TEXT = "Không đủ căn cứ trong Data Pack để xác định thông tin này."
ABSTAIN_ASK_RE = re.compile(
    r"\s+(?:là|bằng)\s+(?:bao nhiêu(?:\s+\S+)?|gì|ai|công ty nào|ngân hàng nào|đơn vị nào|bao lâu)\s*\??\s*$|"
    r"\s+ở đâu\s*\??\s*$"
)


def abstain_text(question: str, fact: bool) -> str:
    """Câu ABSTAIN: mở đầu đúng mẫu README ("Không đủ căn cứ trong Data Pack để xác định …"), nêu rõ điều không xác định được
    khi tách được từ câu hỏi ("Mã số thuế … là bao nhiêu?" → "mã số thuế …"; "X có … không?" → "X có … hay không"), nếu
    không thì "thông tin này"; câu hỏi đòi dữ liệu thực tế của doanh nghiệp giả lập → kèm lý do."""
    q = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(question or ""))).strip()
    obj = ""
    if m := ABSTAIN_ASK_RE.search(q):
        obj = q[:m.start()]
    elif m := re.match(r"(?i)ai là\s+(.+?)\s*\??$", q):
        obj = m.group(1)
    elif m := re.match(r"(?i)(.+?)\s+(?:hiện\s+)?(?:đang\s+)?có\s+bao nhiêu\s+(.+?)\s*\??$", q):
        obj = f"số lượng {m.group(2)} mà {m.group(1)} hiện có"
    elif m := re.match(
        r"(?i)(.+?)\s+((?:hiện\s+)?(?:đang\s+)?(?:dùng|sử dụng|ký|thuê|mở|áp dụng)[^?]*?)\s+"
        r"(?:những\s+|các\s+)?(.+?)\s+nào(?:\s+(.+?))?\s*\??$", q
    ):
        verb = re.sub(r"\s+(?:với|tại|ở|cho)$", "", m.group(2).strip())
        obj = f"{m.group(3)} mà {m.group(1)} {verb}" + (f" {m.group(4)}" if m.group(4) else "")
    elif m := re.match(r"(?i)(.+?)\s+có\s+(.+?)\s+(?:hay\s+)?không\s*\??$", q):
        obj = f"{m.group(1)} có {m.group(2)} hay không"
    if not obj or len(obj) > 150 or re.search(r"[?.;]|\b(?:nào|bao nhiêu|gì|ai|đâu)\b", norm(obj.replace("hay không", ""))):
        obj = "thông tin này"
    elif not (len(obj.split()) > 1 and obj.split()[1][:1].isupper()):      # giữ hoa danh từ riêng ("Nova Việt …")
        obj = obj[:1].lower() + obj[1:]
    text = f"Không đủ căn cứ trong Data Pack để xác định {obj}."
    if fact:
        text += (" Nova Việt là doanh nghiệp giả lập; Data Pack chỉ có văn bản pháp luật và quy chế, quy trình nội bộ giả lập, "
                 "không có dữ liệu thực tế này.")
    return text
DISCLAIMER = "Thông tin chỉ để tham khảo, không thay thế tư vấn pháp lý hoặc thuế. Vui lòng kiểm tra văn bản gốc."   # câu chuẩn của đội

# trạng thái hiệu lực của một chunk / văn bản tại reference_date
VALID, EXPIRED, NOT_YET, REF_ONLY, INTERNAL, INTERNAL_NOT_YET = (
    "VALID", "EXPIRED", "NOT_YET", "REFERENCE_ONLY", "INTERNAL", "INTERNAL_NOT_YET")
STATE_VI = {VALID: "Còn hiệu lực", EXPIRED: "Hết hiệu lực", NOT_YET: "Chưa có hiệu lực",
            REF_ONLY: "Chỉ tham khảo (hợp nhất)", INTERNAL: "Nội bộ (giả lập) – đang áp dụng",
            INTERNAL_NOT_YET: "Nội bộ – chưa ban hành"}
USABLE = {VALID, INTERNAL}

# thứ bậc thẩm quyền (README mục 2): pháp luật → quy chế/quy trình → sổ tay/FAQ
AUTHORITY = {"LAW": 9, "DECREE": 8, "CIRCULAR": 7, "CONSOLIDATED": 5,
             "POLICY": 4, "PROCEDURE": 4, "MATRIX_POLICY": 4, "HANDBOOK": 2, "FAQ": 1}
SECONDARY_TYPES = ("FAQ", "HANDBOOK")


def resolve_file(key: str, root: Path = DATAPACK_DIR) -> Path | None:
    for rel in FILE_CANDIDATES[key]:
        if (root / rel).exists():
            return root / rel
    return None


def read_csv(path) -> pd.DataFrame:
    """Mọi CSV đọc dạng chuỗi, ô trống là "" (không phải NaN), chấp nhận UTF-8 có/không BOM."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


# =============================================================================
# 1. XỬ LÝ VĂN BẢN TIẾNG VIỆT
# =============================================================================
STOPWORDS = {
    "và", "của", "là", "các", "những", "được", "có", "cho", "trong", "theo", "với", "khi", "thì",
    "này", "đó", "nào", "một", "hay", "hoặc", "như", "thế", "gì", "nếu", "tại", "để", "về", "từ",
    "đến", "bao", "nhiêu", "hãy", "nêu", "ra", "sao", "ai", "phải", "nên", "cần", "đã", "sẽ",
    "bị", "do", "mà", "thể", "vẫn", "đang", "còn", "không", "chỉ", "lại", "rằng", "nhưng", "vào", "mấy",
}
GENERIC = {"data", "pack", "quy", "định", "theo", "hiện", "hành", "trường", "hợp", "việc", "đơn", "vị",
           "doanh", "nghiệp", "công", "ty", "cổ", "phần", "nova", "việt", "hệ", "thống", "policyassist",
           "dụng", "áp", "người", "nội", "bộ"}
# từ dẫn dắt cách hỏi – không phải nội dung cần tìm trong bằng chứng
FRAMING = {"mô", "tả", "giữa", "quan", "giải", "thích", "trình", "bày", "vì", "biết", "cho", "trả", "lời",
           "câu", "hỏi", "xác", "cụ", "thể", "gồm", "những", "nhóm", "như", "thế", "nào", "loại", "hiểu", "nghĩa",
           "coi", "xem", "nhất", "phù", "nguồn", "ngày", "tháng", "năm", "phát", "sinh", "tình", "huống", "chủ", "yếu",
           "vậy", "điều", "kiện", "bước", "trình", "tự", "đâu", "lúc", "sau", "trước", "đủ", "ý", "dựa", "biết",
           "nói", "làm", "tôi", "mình", "bạn", "giúp", "xin", "vui", "lòng", "nhé", "ạ"}          # lời hỏi giao tiếp
# từ giao tiếp thường gặp khi gõ không dấu (ưu tiên hơn dạng có dấu phổ biến trong văn bản luật)
CONVERSATIONAL = ("tôi", "mình", "bạn", "biết", "giúp", "muốn", "hỏi", "xin", "của")
# âm tiết dẫn dắt chỉ bỏ khi tính độ phủ từ đơn (vẫn giữ trong cụm từ như "cơ quan", "bản sao", "đối chiếu")
FRAMING_UNI = {"so", "khiến", "bản", "cơ", "khác", "thay", "vẫn", "luôn", "nhau", "vừa", "trăm", "riêng", "cách", "đi", "cả", "đối"}
TOKEN_RE = re.compile(r"\d+(?:/[0-9a-zđ]+(?:-[0-9a-zđ]+)*)+|[a-zđ]+(?:_[a-zđ0-9]+)+|\d+|[^\W\d_]+",
                      re.UNICODE)
DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
DOCID_RE = re.compile(r"\b((?:LAW|SIM)\d{2})\b", re.I)
DOCRANGE_RE = re.compile(r"\b(LAW|SIM)(\d{2})\s*(?:–|-|—|đến)\s*(?:LAW|SIM)?(\d{2})\b", re.I)
NUMBER_RE = re.compile(r"\d+/(?:\d{4}/)?[A-ZĐ]+(?:-[A-ZĐ]+)*\d*")
CODE_RE = re.compile(r"\b[A-Z]{3,}(?:_[A-Z0-9]+)*\b")      # mã trạng thái: HOLD, RETURN_TO_REQUESTER...


# kiểu bỏ dấu cũ ("hoá", "khoá", "uỷ", "thuỷ") → kiểu mới dùng trong Data Pack ("hóa", "khóa", "ủy", "thủy")
_OLD_TONE = {"oá": "óa", "oà": "òa", "oả": "ỏa", "oã": "õa", "oạ": "ọa", "oé": "óe", "oè": "òe", "oẻ": "ỏe",
             "oẽ": "õe", "oẹ": "ọe", "uý": "úy", "uỳ": "ùy", "uỷ": "ủy", "uỹ": "ũy", "uỵ": "ụy"}
_OLD_TONE_RE = re.compile("(" + "|".join(_OLD_TONE) + r")(?![a-zđăâêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ])")


def norm(text) -> str:
    t = unicodedata.normalize("NFC", str(text or "")).lower()
    return _OLD_TONE_RE.sub(lambda m: _OLD_TONE[m.group(1)], t)


def _same_case(src: str, word: str) -> str:
    """Giữ kiểu viết hoa chữ cái đầu của từ người dùng gõ khi thay bằng từ có dấu."""
    return word[:1].upper() + word[1:] if src[:1].isupper() else word


def fold(text: str) -> str:
    """Bỏ dấu tiếng Việt (dùng để nhận diện câu hỏi gõ không dấu)."""
    t = unicodedata.normalize("NFD", norm(text)).replace("đ", "d")
    return unicodedata.normalize("NFC", "".join(ch for ch in t if unicodedata.category(ch) != "Mn"))


def tokenize(text: str, bigrams: bool = True) -> list[str]:
    """Âm tiết (bỏ hư từ) + cặp âm tiết liền nhau (nối bằng '~') + số hiệu văn bản + mã trạng thái."""
    t = DATE_RE.sub(" ", norm(text))
    raw = TOKEN_RE.findall(t)
    out: list[str] = []
    for tok in raw:
        if "/" in tok:
            out.append(tok)
            parts = tok.split("/")
            if len(parts) > 2:
                out.append("/".join(parts[:2]))          # 78/2021/tt-btc → 78/2021
        elif "_" in tok:
            out.append(tok)
            out.extend(p for p in tok.split("_") if p and p not in STOPWORDS)
        elif tok not in STOPWORDS:
            out.append(tok)
    if bigrams:
        words = [w for w in raw if not w[0].isdigit() and "_" not in w and "/" not in w]
        for a, b in zip(words, words[1:]):
            if not (a in STOPWORDS and b in STOPWORDS):
                out.append(f"{a}~{b}")
    return out


def content_terms(text: str) -> list[str]:
    skip = STOPWORDS | GENERIC | FRAMING | FRAMING_UNI
    return sorted({t for t in tokenize(text, bigrams=False)
                   if t not in skip and len(t) > 1 and not t.isdigit() and "/" not in t})


def content_bigrams(text: str) -> set[str]:
    skip = STOPWORDS | GENERIC | FRAMING
    return {b for b in tokenize(text) if "~" in b and not any(p in skip for p in b.split("~"))}


def fmt_date(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso or ""


def flat_text(text: str) -> str:
    """Gộp câu trả lời nhiều dòng thành MỘT dòng (bỏ gạch đầu dòng) để mỗi câu hỏi đúng một dòng trong submission.csv."""
    lines = [re.sub(r"^-\s+", "", ln.strip()) for ln in str(text or "").splitlines() if ln.strip()]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if s.lower() in ("none", "null", "nan", "?"):
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        m = DATE_RE.search(s)
        if m:
            d, mth, y = map(int, m.groups())
            return date(y, mth, d)
    return None


PII_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<email>"),
    (re.compile(r"(?<!\d)(?:\+?84|0)\d{9,10}(?!\d)"), "<số điện thoại>"),
    (re.compile(r"(?<![\d/])\d{12}(?![\d/])"), "<số định danh>"),
    (re.compile(r"(?<![\d/])\d{10}(?:-\d{3})?(?![\d/])"), "<mã số thuế>"),
    (re.compile(r"(?<![\d/])\d{13,19}(?![\d/])"), "<số tài khoản>"),
]


def mask_pii(text: str) -> str:
    for rx, repl in PII_PATTERNS:
        text = rx.sub(repl, text)
    return text


# =============================================================================
# 2. TOÀN VẸN DỮ LIỆU (corpus_manifest SHA-256 + kiểm tra cấu trúc)
# =============================================================================
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def scan_datapack(root: Path = DATAPACK_DIR) -> pd.DataFrame:
    rows = [{"relative_path": p.relative_to(root).as_posix(), "size_bytes": p.stat().st_size, "sha256": sha256_file(p)}
            for p in sorted(root.rglob("*")) if p.is_file()]
    return pd.DataFrame(rows, columns=["relative_path", "size_bytes", "sha256"])


def fingerprint(df: pd.DataFrame) -> str:
    joined = "\n".join(f"{r.relative_path}:{r.sha256}" for r in df.sort_values("relative_path").itertuples())
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def build_manifest(root: Path = DATAPACK_DIR) -> tuple[pd.DataFrame, str]:
    """Ghi corpus_manifest.csv (hash từng file) + corpus_manifest.json (phiên bản, fingerprint, số lượng)."""
    df = scan_datapack(root)
    df.to_csv(MANIFEST_PATH, index=False, encoding="utf-8", lineterminator="\n")
    fp = fingerprint(df)
    counts = {}
    try:
        dp = DataPack(root)
        counts = {"documents": len(dp.doc), "law": sum(d.startswith("LAW") for d in dp.doc),
                  "sim": sum(d.startswith("SIM") for d in dp.doc), "chunks": len(dp.chunks),
                  "questions": len(dp.questions), "answer_samples": len(dp.answer_key)}
    except Exception:                                          # noqa: BLE001
        pass
    MANIFEST_JSON.write_text(json.dumps({
        "datapack": root.name, "datapack_version": DATAPACK_VERSION, "corpus_snapshot": SNAPSHOT.isoformat(),
        "created_at": datetime.now().isoformat(timespec="seconds"), "corpus_fingerprint": fp,
        "n_files": len(df), "counts": counts}, ensure_ascii=False, indent=2), encoding="utf-8")
    return df, fp


def verify_integrity(root: Path = DATAPACK_DIR, manifest: Path = MANIFEST_PATH) -> tuple[pd.DataFrame, str]:
    """Trả về bảng kiểm tra (PASS/WARN/FAIL) và corpus fingerprint."""
    checks: list[dict] = []

    def add(cid, name, ok, detail, level="FAIL"):
        checks.append({"mã": cid, "kiểm tra": name, "kết quả": "PASS" if ok else level, "chi tiết": detail})

    if not root.exists():
        add("I00", "Thư mục Data Pack tồn tại", False, f"Không thấy {root}")
        return pd.DataFrame(checks), ""
    actual = scan_datapack(root)
    fp = fingerprint(actual)
    if manifest.exists():
        man = read_csv(manifest)
        a = dict(zip(actual.relative_path, actual.sha256))
        missing = [p for p in man.relative_path if p not in a]
        changed = [p for p, h in zip(man.relative_path, man.sha256) if p in a and a[p] != h]
        extra = [p for p in a if p not in set(man.relative_path)]
        add("I01", "Đủ mọi file trong corpus_manifest", not missing, f"{len(man) - len(missing)}/{len(man)} file"
            + (f"; thiếu: {', '.join(missing[:5])}" if missing else ""))
        add("I02", "SHA-256 khớp manifest (không bị sửa)", not changed,
            "Tất cả khớp" if not changed else f"{len(changed)} file bị thay đổi: {', '.join(changed[:5])}")
        add("I03", "Không có file lạ ngoài manifest", not extra,
            "Không có" if not extra else ", ".join(extra[:5]), level="WARN")
    else:
        add("I01", "Có corpus_manifest SHA-256", False,
            "Chưa có data/corpus_manifest.csv – chạy `python policyassist.py manifest`", "WARN")

    paths = {k: resolve_file(k, root) for k in FILE_CANDIDATES}
    for key in FILE_CANDIDATES:
        p = paths[key]
        add("I04", f"Có file {FILE_CANDIDATES[key][0].split('/')[-1]}", p is not None,
            p.relative_to(root).as_posix() if p else "không tìm thấy", level="FAIL" if key in REQUIRED_FILES else "WARN")
    if any(paths[k] is None for k in REQUIRED_FILES):
        return pd.DataFrame(checks), fp
    try:
        docs, chunks, cmap = read_csv(paths["documents"]), read_csv(paths["chunks"]), read_csv(paths["citation_map"])
        qs, tpl = read_csv(paths["questions"]), read_csv(paths["template"])
        ak = read_csv(paths["answer_key"]) if paths["answer_key"] else pd.DataFrame()
    except Exception as exc:                                   # noqa: BLE001
        add("I05", "Đọc được CSV (UTF-8)", False, str(exc))
        return pd.DataFrame(checks), fp
    n_law = int((docs.source_type == "LEGAL").sum())
    add("I05", "Số tài liệu 20 (12 LAW + 8 SIM)",
        len(docs) == EXPECTED["documents"] and n_law == EXPECTED["law"], f"{len(docs)} tài liệu, {n_law} LAW, {len(docs) - n_law} SIM")
    add("I06", "374 chunk, chunk_id duy nhất", len(chunks) == EXPECTED["chunks"] and chunks.chunk_id.is_unique,
        f"{len(chunks)} chunk, trùng {int(chunks.chunk_id.duplicated().sum())}")
    orphan = sorted(set(chunks.document_id) - set(docs.document_id))
    add("I07", "Mọi chunk thuộc tài liệu có metadata", not orphan, "OK" if not orphan else ", ".join(orphan))
    m = chunks.merge(cmap[["chunk_id", "citation_label"]], on="chunk_id", how="left", suffixes=("", "_map"))
    bad = m[m.citation_label_map.isna() | (m.citation_label != m.citation_label_map)]
    add("I08", "citation_map khớp 1-1 với chunk", bad.empty and len(cmap) == len(chunks),
        f"{len(cmap)} dòng citation_map; lệch {len(bad)}")
    bad_dates = [q for q, d in zip(qs.question_id, qs.reference_date) if parse_date(d) is None]
    add("I09", "90 câu hỏi, id duy nhất, reference_date hợp lệ",
        len(qs) == EXPECTED["questions"] and qs.question_id.is_unique and not bad_dates,
        f"{len(qs)} câu; ngày lỗi: {len(bad_dates)}")
    if not ak.empty:
        add("I10", "Đáp án mẫu 30 câu, thuộc bộ câu hỏi", len(ak) == EXPECTED["answers"]
            and set(ak.question_id) <= set(qs.question_id), f"{len(ak)} đáp án")
        # I15: mỗi đáp án mẫu nối đúng câu hỏi (nội dung, ngày) → chunk có thật → đúng citation_label và document
        qmap = qs.drop_duplicates("question_id").set_index("question_id")
        c_label, c_doc = dict(zip(chunks.chunk_id, chunks.citation_label)), dict(zip(chunks.chunk_id, chunks.document_id))
        bad = []
        for r in ak.to_dict("records"):
            qid = r["question_id"]
            if qid not in qmap.index:
                bad.append(f"{qid} không có trong bộ câu hỏi")
                continue
            q = qmap.loc[qid]
            if "question_text" in r and " ".join(norm(r["question_text"]).split()) != " ".join(norm(q.question_text).split()):
                bad.append(f"{qid} lệch nội dung câu hỏi")
            if "reference_date" in r and r["reference_date"] != q.reference_date:
                bad.append(f"{qid} lệch reference_date")
            ids, labels, rdocs = (_split(r.get(k, "")) for k in ("relevant_chunk_ids", "citation_labels", "relevant_document_ids"))
            if r.get("expected_behavior") == "ABSTAIN":
                if ids or labels:
                    bad.append(f"{qid} ABSTAIN nhưng có chunk/citation")
                continue
            if not ids or any(c not in c_label for c in ids):
                bad.append(f"{qid} chunk không tồn tại: {', '.join(c for c in ids if c not in c_label) or 'trống'}")
                continue
            if set(labels) != {c_label[c] for c in ids}:
                bad.append(f"{qid} citation_labels không khớp chunk")
            if rdocs and set(rdocs) != {c_doc[c] for c in ids}:
                bad.append(f"{qid} relevant_document_ids không khớp chunk")
        add("I15", "Đáp án mẫu nối đúng câu hỏi – chunk – citation", not bad,
            f"{len(ak)}/{len(ak)} đáp án khớp (nội dung, ngày, chunk, nhãn, tài liệu)" if not bad else "; ".join(bad[:4]))
    add("I11", "Template submission đúng cột và đủ question_id",
        list(tpl.columns) == SUBMISSION_COLUMNS and list(tpl.question_id) == list(qs.question_id),
        ", ".join(tpl.columns))
    inv = chunks[(chunks.effective_from != "") & (chunks.effective_to != "") & (chunks.effective_from > chunks.effective_to)]
    add("I12", "Hiệu lực chunk hợp lệ (from ≤ to)", inv.empty, f"lỗi {len(inv)}")
    refs = {x.upper() for v in docs.superseded_by.tolist() + docs.supersedes.tolist() for x in DOCID_RE.findall(v)}
    add("I13", "Cạnh thay thế trỏ tới tài liệu có thật", refs <= set(docs.document_id), ", ".join(sorted(refs)))
    # hiệu lực cấp chunk do hệ thống tự tính tại ngày chụp corpus phải khớp cờ is_current_as_of_2026_10_17 của BTC
    flag_col = next((c for c in cmap.columns if c.startswith("is_current_as_of")), None) if len(cmap) else None
    if flag_col:
        try:
            dpk = DataPack(root)
            pairs = [(c, str(v).strip().upper() == "TRUE") for c, v in zip(cmap.chunk_id, cmap[flag_col]) if c in dpk.idx]
            same = sum((dpk.chunk_state(dpk.idx[c], SNAPSHOT) in USABLE) == cur for c, cur in pairs)
            add("I16", f"Hiệu lực tính tại {SNAPSHOT:%d/%m/%Y} khớp cờ {flag_col}", same == len(pairs),
                f"{same}/{len(pairs)} chunk khớp")
        except Exception as exc:                                   # noqa: BLE001
            add("I16", f"Hiệu lực tính tại {SNAPSHOT:%d/%m/%Y} khớp cờ {flag_col}", False, f"không kiểm được: {exc}", "WARN")
    if MANIFEST_JSON.exists():
        meta = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
        add("I14", "Fingerprint khớp corpus_manifest.json", meta.get("corpus_fingerprint") == fp,
            f"{meta.get('datapack_version', '?')} · {str(meta.get('corpus_fingerprint', ''))[:12]}")
    return pd.DataFrame(checks), fp


# =============================================================================
# 3. DATA PACK + ĐỒ THỊ PHIÊN BẢN
# =============================================================================
class DataPack:
    def __init__(self, root: Path = DATAPACK_DIR):
        self.root = root
        missing = [k for k in REQUIRED_FILES if resolve_file(k, root) is None]
        if missing:
            raise FileNotFoundError(f"Data Pack thiếu file: {', '.join(missing)} (thư mục {root})")
        self.chunks_df = read_csv(resolve_file("chunks", root))
        self.docs_df = read_csv(resolve_file("documents", root))
        self.cmap_df = read_csv(resolve_file("citation_map", root))
        self.questions = read_csv(resolve_file("questions", root))
        self.template = read_csv(resolve_file("template", root))
        ak = resolve_file("answer_key", root)
        self.answer_key = read_csv(ak) if ak else pd.DataFrame()
        self.chunks: list[dict] = self.chunks_df.to_dict("records")
        self.idx = {c["chunk_id"]: i for i, c in enumerate(self.chunks)}
        self.doc = {r["document_id"]: r for r in self.docs_df.to_dict("records")}
        self.label = dict(zip(self.cmap_df.chunk_id, self.cmap_df.citation_label))
        self.doc_chunks: dict[str, list[int]] = {}
        for i, c in enumerate(self.chunks):
            self.doc_chunks.setdefault(c["document_id"], []).append(i)
        # số hiệu văn bản → document_id ("78/2021/tt-btc", "78/2021")
        self.number: dict[str, str] = {}
        self.alias: dict[str, str] = {}
        for d, m in self.doc.items():
            hit = NUMBER_RE.search(m["title"])
            if hit and d.startswith("LAW"):
                num = hit.group(0)
                self.number[d] = num
                self.alias[norm(num)] = d
                parts = norm(num).split("/")
                if len(parts) == 3:
                    self.alias["/".join(parts[:2])] = d
        # cạnh SUPERSEDES (cũ → mới) khai báo trong superseded_by / supersedes
        self.succ: dict[str, set[str]] = {d: set() for d in self.doc}
        self.pred: dict[str, set[str]] = {d: set() for d in self.doc}
        for d, m in self.doc.items():
            for new in DOCID_RE.findall(m["superseded_by"]):
                self._edge(d, new.upper())
            for old in DOCID_RE.findall(m["supersedes"]):
                self._edge(old.upper(), d)
        # quan hệ "sửa đổi, bổ sung" đọc từ tiêu đề (vd. LAW08 sửa đổi LAW07)
        self.amends: dict[str, str] = {}
        for d, m in self.doc.items():
            if "sửa đổi" in norm(m["title"]):
                for n in NUMBER_RE.findall(m["title"])[1:]:
                    target = self.alias.get(norm(n))
                    if target and target != d:
                        self.amends[d] = target
        # nhận diện câu hỏi mẫu của BTC (nhật ký phân biệt câu mẫu / câu ngoài bộ mẫu)
        self.sample_keys = {self.question_key(t): q for q, t in zip(self.questions.question_id, self.questions.question_text)}
        self.sample_fold = {fold(k): q for k, q in self.sample_keys.items()}

    @staticmethod
    def question_key(text: str) -> str:
        return " ".join(re.findall(r"[^\W_]+(?:/[^\W_]+)*", norm(text)))

    def match_sample(self, text: str) -> str:
        """question_id của câu hỏi mẫu trùng nội dung (bỏ qua hoa/thường, dấu câu, khoảng trắng, gõ thiếu dấu, sai
        chính tả rất nhẹ ≥ 97%); câu diễn đạt khác hoặc câu mới → "" (câu ngoài bộ mẫu)."""
        key = self.question_key(text)
        if not key:
            return ""
        if key in self.sample_keys:
            return self.sample_keys[key]
        if fold(key) in self.sample_fold:
            return self.sample_fold[fold(key)]
        near = difflib.get_close_matches(key, list(self.sample_keys), n=1, cutoff=0.97)
        return self.sample_keys[near[0]] if near else ""

    def _edge(self, old: str, new: str):
        if old in self.doc and new in self.doc and old != new:
            self.succ[old].add(new)
            self.pred[new].add(old)

    # ---- metadata tiện ích ----
    def short(self, d: str) -> str:
        t = self.doc[d]["title"]
        hit = NUMBER_RE.search(t)
        return t[:hit.end()] if hit and d.startswith("LAW") else t

    def start(self, d: str) -> str:
        return self.doc[d]["effective_date"]

    def end(self, d: str) -> str:
        return self.doc[d]["expiry_date"]

    def chain(self, d: str) -> tuple[str, ...]:
        seen, stack = {d}, [d]
        while stack:
            x = stack.pop()
            for y in self.succ[x] | self.pred[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        key = lambda x: (self.doc[x]["effective_date"] or self.doc[x]["issue_date"] or "9999", x)
        return tuple(sorted(seen, key=key))

    def chains(self) -> list[tuple[str, ...]]:
        out = []
        for d in self.doc:
            c = self.chain(d)
            if len(c) > 1 and c not in out:
                out.append(c)
        return out

    def successors_in_force(self, d: str, ref: date) -> list[str]:
        out, stack, seen = [], list(self.succ[d]), set()
        while stack:
            x = stack.pop(0)
            if x in seen:
                continue
            seen.add(x)
            if self.doc_state(x, ref) == VALID:
                out.append(x)
            else:
                stack.extend(self.succ[x])
        return sorted(out)

    def anchor(self, d: str) -> int | None:
        """Điều khoản đại diện cho cả văn bản khi trả lời về hiệu lực: điều khoản hiệu lực/thay thế,
        nếu không có thì điều khoản phạm vi điều chỉnh, nếu không có nữa thì điều khoản đầu tiên."""
        ids = self.doc_chunks.get(d, [])
        for rx in (DOC_EFFECT_RE, SCOPE_HEAD_RE):
            hit = [i for i in ids if rx.search(norm(self.chunks[i]["heading"]))]
            if hit:
                return hit[0]
        return ids[0] if ids else None

    # ---- CHRONOS: hiệu lực tại reference_date ----
    def doc_state(self, d: str, ref: date) -> str:
        m, iso = self.doc[d], ref.isoformat()
        if m["source_type"] != "LEGAL":
            return INTERNAL_NOT_YET if m["effective_date"] and iso < m["effective_date"] else INTERNAL
        if m["status"] == "HISTORICAL_REFERENCE" or m["document_type"] == "CONSOLIDATED":
            return REF_ONLY
        if m["effective_date"] and iso < m["effective_date"]:
            return NOT_YET
        if m["expiry_date"] and iso > m["expiry_date"]:
            return EXPIRED
        return VALID

    def chunk_state(self, i: int, ref: date) -> str:
        c, iso = self.chunks[i], ref.isoformat()
        m = self.doc[c["document_id"]]
        start = c["effective_from"] or m["effective_date"]
        if c["source_type"] != "LEGAL":
            return INTERNAL_NOT_YET if start and iso < start else INTERNAL
        if c["status"] == "HISTORICAL_REFERENCE" or c["document_type"] == "CONSOLIDATED":
            return REF_ONLY
        end = c["effective_to"] or m["expiry_date"]
        if start and iso < start:
            return NOT_YET
        if end and iso > end:
            return EXPIRED
        return VALID

    def mentioned_docs(self, text: str) -> list[str]:
        """Văn bản được nhắc: số hiệu (78/2021/TT-BTC, Nghị định 123/2020), mã LAWxx/SIMxx, dải LAW04–LAW06."""
        found: list[str] = []
        q = norm(text)

        def push(d):
            if d in self.doc and d not in found:
                found.append(d)

        for m in DOCRANGE_RE.finditer(text):
            p, a, b = m.group(1).upper(), int(m.group(2)), int(m.group(3))
            for n in range(min(a, b), max(a, b) + 1):
                push(f"{p}{n:02d}")
        for m in DOCID_RE.finditer(text):
            push(m.group(1).upper())
        for tok in re.findall(r"\d+/[0-9a-zđ]+(?:/[0-9a-zđ]+(?:-[0-9a-zđ]+)*|-[0-9a-zđ]+)?", q):
            d = self.alias.get(tok) or self.alias.get("/".join(tok.split("/")[:2]))
            if d:
                push(d)
        return found

    def doc_full_text(self, d: str) -> str:
        p = self.root / TEXT_DIR / f"{d}.txt"
        if p.exists():
            return p.read_text(encoding="utf-8-sig")
        parts = [f"{self.doc[d]['title']}\n(Tài liệu nội bộ giả lập – ghép từ legal_chunks.csv)\n"]
        for i in self.doc_chunks.get(d, []):
            c = self.chunks[i]
            parts.append(f"[{c['chunk_id']}] {c['heading']}\n{c['chunk_text']}\nCitation: {c['citation_label']}\n")
        return "\n".join(parts)


# =============================================================================
# 4. CẤU HÌNH & KẾT QUẢ
# =============================================================================
@dataclass
class Config:
    name: str = "CHRONOS-LEDGER"
    top_k: int = 5
    pool: int = 40
    w_bm25: float = 0.6
    w_tfidf: float = 0.4
    w_coverage: float = 0.3             # trọng số độ phủ từ khóa khi tính điểm liên quan
    secondary_factor: float = 0.5       # FAQ/sổ tay đứng sau quy chế/quy trình gốc (README mục 2)
    nav_factor: float = 0.6             # chunk điều hướng ("Căn cứ tham chiếu", "Mục đích") không phải quy định thực chất
    prf_chunks: int = 2                 # số điều khoản gốc lấy cho mỗi văn bản được FAQ/sổ tay dẫn chiếu
    prf_legal_internal: float = 0.5     # trọng số khi FAQ dẫn chiếu văn bản luật trong câu hỏi thuần nội bộ
    sibling_prior: float = 0.7          # tiền nghiệm cho các khoản cùng Điều với căn cứ pháp luật đứng đầu
    successor_min_cos: float = 0.25     # độ tương đồng tối thiểu để coi là điều khoản tương ứng ở văn bản kế nhiệm
    min_coverage: float = 0.58          # độ phủ từ khóa có trọng số IDF
    min_bigram_coverage: float = 0.25   # độ phủ cụm 2 âm tiết
    min_best_chunk_coverage: float = 0.40  # độ phủ (IDF) của chunk tốt nhất – bằng chứng không được rời rạc
    min_focus_coverage: float = 0.35    # G7: căn cứ được trích dẫn phải phủ phần câu hỏi ngoài thuật ngữ chủ đề
    min_confidence: float = 0.35        # dưới ngưỡng → ABSTAIN
    review_confidence: float = 0.60     # dưới ngưỡng → gắn cờ cần chuyên viên rà soát
    max_answer_chunks: int = 3
    adjacent_ratio: float = 0.6         # chunk kề/cùng Điều với căn cứ chính được dùng nếu điểm ≥ tỷ lệ này
    complement_ratio: float = 1.0       # chunk khác chỉ được dẫn thêm nếu tự liên quan không kém căn cứ chính …
    complement_gain: float = 0.2        # … và bổ sung ≥ 20% ý (trọng số IDF) của câu hỏi
    version_content_chunks: int = 0     # câu hỏi về hiệu lực văn bản: số đoạn nội dung kèm theo (0 = chỉ mệnh đề hiệu lực)
    adjacent_same_article: bool = True  # "phần tiếp nối" chỉ tính cho khoản/điểm cùng một Điều
    adjacent_gain: float = 0.1          # khoản cùng Điều phải bổ sung tối thiểu chừng này ý mới
    prf_weight: float = 1.0             # điểm thừa hưởng của điều khoản gốc so với FAQ/sổ tay đã dẫn tới nó
    primary_full_chars: int = 300       # đoạn ngắn hơn ngưỡng này (1–2 câu của một quy định) được trích nguyên văn
    primary_units: int = 3              # số câu/dòng tối đa trích từ căn cứ chính dài (các căn cứ khác: 2)
    unit_ratio: float = 0.5             # chỉ trích câu/dòng có điểm liên quan ≥ tỷ lệ này × câu tốt nhất của đoạn
    table_row_ratio: float = 0.8        # bảng: chỉ các dòng có điểm ≥ tỷ lệ này × dòng khớp nhất
    primary_tiebreak: float = 0.05      # hai ứng viên sát nút (chênh < 5%) → chọn chunk tự liên quan hơn làm căn cứ chính
    use_guard: bool = True
    use_chronos: bool = True
    use_rerank: bool = True
    use_prf: bool = True                # truy nguồn gốc từ FAQ/sổ tay
    use_structure: bool = True          # mở rộng theo cấu trúc Điều của văn bản luật
    table_rows: bool = True             # chấm điểm bảng theo dòng khớp nhất
    use_rewrite: bool = True            # khôi phục dấu + từ viết tắt + từ đồng nghĩa trước khi xử lý
    use_expansion: bool = True          # mở rộng truy vấn theo từ đồng nghĩa nghiệp vụ / từ khóa hiệu lực (P1)
    use_forced: bool = True             # kéo thêm chunk của văn bản được nêu tên và chunk chứa mã trạng thái được hỏi (P2)
    prf_guide: bool = False             # (thử nghiệm) truy nguồn FAQ chỉ dùng phần trả lời/hướng xử lý – tắt: kém hơn trên Dev
    tiebreak_negation_only: bool = True # chỉ phân xử lại căn cứ chính khi khớp nhờ phần phủ định
    complement_same_kind: bool = True   # chunk bổ sung cùng loại nguồn với căn cứ chính (trừ câu MIXED)
    compare_counterpart: bool = True    # câu so sánh: nêu đủ hai vế
    secondary_fallback: float = 1.35    # FAQ/sổ tay được dùng làm căn cứ khi tự liên quan hơn nguồn gốc ≥ 35%
    default_scope_fallback: bool = True # câu hỏi không nêu phạm vi, không đoạn luật nào tự bao quát câu hỏi (ngưỡng G5)
                                        # → quy trình nội bộ làm căn cứ chính (README mục 2: ưu tiên khi "cùng liên quan")
    hard_date_filter: bool = False      # chỉ cho ablation B2′: bỏ chunk không còn hiệu lực trước khi xếp hạng (pipeline tham khảo)
    log_retention_days: int = 30        # audit log và phản hồi giữ tối đa 30 ngày (proposal mục 8.3); 0 = không xoá
    use_gate: bool = True
    use_audit: bool = True
    write_log: bool = True


@dataclass
class Result:
    question_id: str
    question: str
    reference_date: str
    applied_date: str
    decision: str = "ABSTAIN"
    answer: str = ABSTAIN_TEXT
    citations: list[str] = field(default_factory=list)
    cited_chunks: list[str] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    latency_ms: int = 0
    intent: str = ""
    scope: str = ""
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    ledger: list[dict] = field(default_factory=list)
    audit: list[dict] = field(default_factory=list)
    gate: list[dict] = field(default_factory=list)
    features: dict = field(default_factory=dict)
    needs_review: bool = False
    claims: list[dict] = field(default_factory=list)    # các ý đã qua kiểm toán: {text, kind, refs:[số citation], units}
    key_point: dict = field(default_factory=dict)       # ý then chốt trích nguyên văn: {text, refs}
    question_source: str = ""                           # "sample" = câu hỏi mẫu của BTC · "external" = câu ngoài bộ mẫu
    date_source: str = ""                               # mốc áp dụng lấy từ: "question" | "reference_date" | "default"
    trace_id: str = ""                                  # mã truy vết trong audit log
    expansions: list[str] = field(default_factory=list) # viết tắt/thuật ngữ đã hiểu: "HĐ → hợp đồng"

    @property
    def abstain(self) -> bool:
        return self.decision == "ABSTAIN"

    def submission_row(self) -> dict:
        ans = not self.abstain
        return {
            "question_id": self.question_id,
            "answer": flat_text(self.answer),
            "retrieved_document_ids": ";".join(dict.fromkeys(r["document_id"] for r in self.retrieved)) if ans else "",
            "retrieved_chunk_ids": ";".join(r["chunk_id"] for r in self.retrieved) if ans else "",
            "citations": ";".join(self.citations) if ans else "",
            "confidence": round(float(self.confidence), 3),
            "abstain": "FALSE" if ans else "TRUE",
            "latency_ms": int(self.latency_ms),
        }


# =============================================================================
# 5. PIPELINE
# =============================================================================
# ---- P0 Guard ----
ENTITY_RE = re.compile(r"nova việt|công ty cổ phần nova|\bnova\b|nhân viên cụ thể|một nhân viên cụ thể|"
                       r"kế toán trưởng|tổng giám đốc|giám đốc|chủ tịch|người đại diện")
ASK_RE = re.compile(r"bao nhiêu|là gì|ở đâu|là ai|\bai\b|công ty nào|ngân hàng nào|phần mềm .{0,25}nào|"
                    r"cho (?:tôi|mình|em|tớ|chúng tôi)?\s*biết|cung cấp (?:cho|giúp)|tra giúp|"
                    r"hay không|có đang|mấy|\bnào\b|là số")
# câu hỏi về CÁCH XỬ LÝ (có nhắc dữ kiện trong tình huống) – không phải đòi dữ kiện thực tế
PROCEDURAL_RE = re.compile(r"xử lý|thế nào|ra sao|quy trình|có được|nên làm|cần làm|các bước|bước nào|"
                           r"kiểm tra (gì|những|các)|cách nào|căn cứ nào|nguồn nào|trình tự")
# chứng từ/giao dịch cụ thể ("hóa đơn số 0001234", "tài khoản 0123456789"): dữ liệu vận hành thật, Data Pack không có
RECORD_RE = re.compile(r"(?:hóa đơn|chứng từ|hồ sơ|đề nghị(?: thanh toán)?|hợp đồng|phiếu (?:chi|thu)|đơn hàng|tài khoản)\s+"
                       r"(?:số\s+|mã\s+)?[a-z]{0,4}[-/]?\d{3,}")
POSITION = r"(?:kế toán trưởng|giám đốc|tổng giám đốc|chủ tịch|trưởng phòng|người đại diện|thủ quỹ)"
FACT_TYPES = {
    "định danh doanh nghiệp": r"mã số thuế|mã số doanh nghiệp|địa chỉ (trụ sở|đăng ký|cụ thể)|trụ sở|"
                              r"người đại diện theo pháp luật|số điện thoại|hotline|tổng đài|email|website",
    "định danh cá nhân": r"\bai\b\s+(?:hiện\s+)?(?:đang\s+)?(?:làm|giữ chức|giữ vị trí|đảm nhiệm|là)\s+" + POSITION
                         + r"|" + POSITION + r"[^?]{0,40}\blà ai\b|" + POSITION + r"[^?]{0,40}\btên (?:là )?gì|(?:tên|họ tên)\s+(?:của\s+)?" + POSITION,
    "tài chính cụ thể": r"vốn điều lệ|doanh thu|lợi nhuận|\blãi\b(?!\s*suất)|\blỗ\b|số dư|số tài khoản|mở tài khoản|"
                        r"tài khoản .{0,30}(?:ngân hàng nào|là gì)|tỷ giá|giá cổ phiếu|tổng tài sản|nợ phải trả|"
                        r"(?:đã|thực tế) (?:chi|thu|thanh toán|tạm ứng|hoàn ứng|phát hành)[^?]{0,30}(?:tổng cộng|tổng số|bao nhiêu)|"
                        r"tổng (?:cộng|số tiền|giá trị)[^?]{0,30}(?:đã|thực tế) (?:chi|thu|thanh toán|tạm ứng)",
    "nhân sự, cá nhân": r"bao nhiêu nhân viên|số (lượng )?nhân viên|quy mô nhân sự|mức lương|tiền lương|thu nhập của|"
                        r"thuế (suất )?thu nhập cá nhân|căn cước|cccd|cmnd|ngày sinh",
    "dữ liệu vận hành thực tế": r"(?:công ty|đơn vị|hãng) kiểm toán (?:nào|là ai|tên gì)|ngân sách (?:năm \d{4} )?của (?:phòng|bộ phận|ban)|"
                               r"(?:gửi|gửi tới|gửi đến|gửi cho) (?:địa chỉ )?email nào|(đang )?sử dụng phần mềm|phần mềm kế toán|nhà cung cấp .{0,50}(cụ thể|công ty nào|đang ký)|"
                               r"(?:nhà cung cấp|đối tác) nào|đang ký hợp đồng|mã hs|đang nhập khẩu|"
                               r"thanh tra|khách hàng lớn nhất",
    "chứng từ, giao dịch cụ thể": RECORD_RE.pattern,
}
FACT_RE = {k: re.compile(v) for k, v in FACT_TYPES.items()}
ILLEGAL_RE = re.compile(r"hóa đơn khống|trốn thuế|né thuế|lách luật|làm giả|giả mạo|hợp thức hóa|mua bán hóa đơn|"
                        r"xóa dấu vết|tẩy xóa|khai khống|rửa tiền")
INJECTION_RE = re.compile(r"bỏ qua (mọi|tất cả|các|toàn bộ)? ?(quy tắc|hướng dẫn|chỉ dẫn|lệnh)|ignore (all|previous|the)|"
                          r"system prompt|jailbreak|đóng vai")
# mạo danh thẩm quyền để đổi quy tắc: "Tôi là Giám đốc tài chính, tôi cho phép bạn …"
AUTHORITY_RE = re.compile(r"(?:^|(?<=[.!?:]\s))tôi là [^,.;:]{2,40}[,;]\s*(?:nên\s+)?tôi (?:cho phép|yêu cầu|ra lệnh|chỉ đạo|đồng ý cho|ủy quyền cho) "
                          r"(?:bạn|hệ thống|em)\s*", re.I)
STATUTE_RE = re.compile(r"\b(Bộ luật|Luật)\s+([A-ZĐ][^\s,.;:?!()]*(?:\s+[^\s,.;:?!()]+){0,3})")


def _strip_marks(s: str) -> str:
    """Bỏ dấu tiếng Việt nhưng giữ chữ hoa/thường – dùng cho mẫu regex (\\b, \\s, \\d không bị đổi)."""
    t = unicodedata.normalize("NFD", s).replace("đ", "d").replace("Đ", "D")
    return unicodedata.normalize("NFC", "".join(ch for ch in t if unicodedata.category(ch) != "Mn"))


def _fold_rx(rx: re.Pattern) -> re.Pattern:
    return re.compile(_strip_marks(rx.pattern), rx.flags)


# bản không dấu của các mẫu Guard – dùng khi người dùng gõ không dấu (bước khôi phục dấu có thể chọn sai từ)
GUARD_FOLDED = {"injection": _fold_rx(INJECTION_RE), "illegal": _fold_rx(ILLEGAL_RE), "entity": _fold_rx(ENTITY_RE),
                "record": _fold_rx(RECORD_RE), "ask": _fold_rx(ASK_RE), "procedural": _fold_rx(PROCEDURAL_RE),
                "facts": {k: _fold_rx(v) for k, v in FACT_RE.items()}}
GUARD_ACCENTED = {"injection": INJECTION_RE, "illegal": ILLEGAL_RE, "entity": ENTITY_RE, "record": RECORD_RE, "ask": ASK_RE,
                  "procedural": PROCEDURAL_RE, "facts": FACT_RE}

# ---- P1 Planning ----
VERSION_RE = re.compile(r"chuỗi thay thế|versioning|phiên bản|văn bản hợp nhất|nguồn lịch sử|còn là|hết hiệu lực|"
                        r"thời điểm đó|phát sinh (tại )?ngày|nguồn nào phù hợp|nên ưu tiên .{0,80} hay ")
VERSION_DOC_RE = re.compile(r"hiệu lực|thay thế|hiện hành|áp dụng")     # chỉ tính khi câu hỏi nêu tên văn bản luật
INTERNAL_RE = re.compile(r"nova việt|nội bộ|quy trình|quy chế|ma trận|sổ tay|faq|hệ thống nên|policyassist|hồ sơ|"
                         r"nhân viên|bộ phận|tạm ứng|công tác phí|phê duyệt|trạng thái|máy chủ|sự cố|sao lưu|"
                         r"khôi phục|phục hồi|metadata|audit log|kho lưu trữ|cntt")   # CNTT chỉ có trong tài liệu nội bộ
LEGAL_RE = re.compile(r"pháp luật|\bluật\b|nghị định|thông tư|quy định kế toán|văn bản|hiện hành|data pack|cơ quan thuế")
MIXED_RE = re.compile(r"kết hợp|đồng thời|khác với|vừa liên quan|nguồn pháp luật và|pháp luật hiện hành với|"
                      r"căn cứ pháp luật|nguồn nên ưu tiên|dựa (?:vào|trên) (?:nguồn|căn cứ|văn bản) nào|"
                      r"(?:theo|căn cứ) (?:nguồn|văn bản) nào|phân biệt .{0,50} với .{0,50} nội bộ")
CURRENT_RE = re.compile(r"hiện hành|hiện nay|hiện tại|bây giờ|hôm nay|đang có hiệu lực")
DATE_IN_Q_RE = re.compile(r"(trước|từ|sau|tại|ngày)\s*(?:ngày\s*)?(\d{1,2}/\d{1,2}/\d{4})")
# ---- P3/P4 cấu trúc văn bản ----
EFFECT_HEAD_RE = re.compile(r"hiệu lực|(?:điều khoản|quy định) chuyển tiếp|thay thế (?:thông tư|nghị định|luật|văn bản)|phạm vi điều chỉnh")
DOC_EFFECT_RE = re.compile(r"hiệu lực|(?:điều khoản|quy định) chuyển tiếp|thay thế (?:thông tư|nghị định|luật|văn bản)")
SCOPE_HEAD_RE = re.compile(r"phạm vi")
NAV_HEAD_RE = re.compile(r"căn cứ tham chiếu|tài liệu tham chiếu|^mục đích$|^phạm vi (?:và đối tượng )?áp dụng$")
SOURCE_LINE_RE = re.compile(r"Nguồn (?:tra cứu )?ưu tiên:\s*([^\n]+)")
SECONDARY_Q_RE = re.compile(r"\bfaq\b|sổ tay|sim07|sim08")
DEFINITION_Q_RE = re.compile(r"là gì|được hiểu|khái niệm|định nghĩa|nghĩa là|ý nghĩa|được dùng (?:khi|trong)")
DEFINITION_HEAD_RE = re.compile(r"khái niệm|giải thích|thuật ngữ|định nghĩa")
# phạm vi phủ định: từ phủ định đến ranh giới mệnh đề gần nhất. "không được/phải/nên/cần" là câu cấm/bắt buộc
# (chính là nội dung trả lời) và "không vượt quá/không quá/không có mã/không có khoản…" là thuộc tính/hạn mức nên không tính;
# "trừ" chỉ tính khi là "trừ trường hợp/trừ khi" (tránh "khấu trừ").
NEGATED_SPAN_RE = re.compile(r"\b(?:không(?!\s+(?:được|phải|nên|cần|có quyền|vượt|quá\b|có mã|có khoản))|ngoại trừ|trừ (?:trường hợp|khi))\b"
                             r"[^.;:\n]*?(?=[.;:\n]|\bthì\b|\bnhưng\b|$)")
NEGATION_Q_RE = re.compile(r"\b(?:không|chưa|đúng)\b")     # câu hỏi có cực tính ("mã số thuế đúng" = "không sai")
# câu hỏi yêu cầu nêu quy trình/trình tự xử lý ("Hãy nêu quy trình xử lý…", "kiểm tra theo trình tự nào") và điều khoản
# là một quy trình (tiêu đề bắt đầu bằng "Quy trình …")
PROCEDURE_Q_RE = re.compile(r"(?:nêu|mô tả|trình bày|cho biết|hướng dẫn|liệt kê)\s+(?:\S+\s+){0,3}?(?:quy trình|trình tự|"
                            r"các bước|thủ tục)|theo (?:những |các )?(?:bước|trình tự) nào|gồm những bước|(?:các bước|trình tự) (?:xử lý|thực hiện)")
PROCEDURE_HEAD_RE = re.compile(r"^(?:quy trình|trình tự|các bước|thủ tục)")
COMPARE_RE = re.compile(r"khác (?:cơ bản |nhau )?(?:thế nào|ra sao|gì|nhau)|so với|so sánh|phân biệt|thay vì")
# P6 – dạng câu hỏi quyết định cách nêu KẾT LUẬN (luôn là câu nguyên văn của căn cứ đã dẫn, không sinh tự do)
YESNO_Q_RE = re.compile(r"\bcó\s+(?:(?P<modal>được phép|được|nên|cần|phải|thể|bắt buộc)\s+)?(?P<pred>[^?;,.]+?)\s+"
                        r"(?:hay\s+)?không\s*(?=[?,.;]|$|(?:và|hay|rồi|thì)\b)")      # "không" kết thúc vế hỏi (≠ "không có mã")
QUANTITY_Q_RE = re.compile(r"\bbao nhiêu\b|\bmấy\b|\bbao lâu\b|\btỷ lệ\b|\bphần trăm\b|\btối (?:đa|thiểu)\b|\bkhông vượt quá\b")
WHY_Q_RE = re.compile(r"\bvì sao\b|\btại sao\b|\blý do\b|\bđể làm gì\b|\bsao\b[^?]{0,25}không cho\b")
SITUATION_Q_RE = re.compile(r"xử lý (?:thế nào|ra sao|như thế nào|sao)|trạng thái (?:\S+\s+){0,3}?(?:nào|gì)|nên là gì|nên làm gì|"
                            r"cần làm gì|làm sao|kết quả (?:nào|gì)")
LIST_Q_RE = re.compile(r"\b(?:những|các)\s+(?:\S+\s+){0,6}?(?:nào|gì)\b|\bgồm (?:những )?(?:gì|nào)\b|\bliệt kê\b")
HOWTO_Q_RE = re.compile(r"\b(?:nêu|mô tả|trình bày|hướng dẫn|cho biết)\s+(?:\S+\s+){0,2}?(?:cách|quy trình|các bước|trình tự|"
                        r"phương án)\b|\btheo (?:những )?(?:bước|trình tự) nào\b")
LIST_ITEM_RE = re.compile(r"^\(?(?:\d{1,2}(?:\.\d{1,2})*|[a-zđ])[.)]\s")
# lập trường của câu căn cứ đối với điều được hỏi: phủ định / cho phép – bắt buộc / chỉ cho phép khi đủ điều kiện
NEG_CUE_RE = re.compile(r"\b(?:không|chưa|cấm)\b(?!\s+(?:chỉ|những|riêng))")
POS_CUE_RE = re.compile(r"\b(?:được|có thể|phải|cần|nên|bắt buộc|có quyền)\b")
ONLY_CUE_RE = re.compile(r"\bchỉ\b")
CLAUSE_BREAK_RE = re.compile(r"[.;:!?,]|\b(?:nhưng|tuy nhiên|nếu|khi|thì|trừ|ngoại trừ|mà)\b")
REASON_RE = re.compile(r"\b(?:nhằm|bảo đảm|đảm bảo|tránh|phòng ngừa|vì|mục đích|xung đột lợi ích|phân tách)\b")
RESULT_HEAD_RE = re.compile(r"kết quả|xử lý|mong đợi|tuyến|hướng")
REFERENCE_TABLE_RE = re.compile(r"thuật ngữ|vai trò|ma trận|phân công|căn cứ tham chiếu|tài liệu tham chiếu|bảng tra nhanh")
# chọn ý then chốt: dòng mở đầu phần hướng dẫn / dòng chỉ nhắc lại tình huống, câu hỏi, nguồn
GUIDE_HEAD_RE = re.compile(r"^(?:hướng xử lý|cách xử lý|xử lý|trả lời|kết luận)[^:]{0,40}:$", re.I)
SIGNS_HEAD_RE = re.compile(r"^(?:dấu hiệu|điểm cần kiểm tra)[^:]{0,40}:$", re.I)
RESTATE_UNIT_RE = re.compile(r"^(?:tình huống|câu hỏi|nguồn[^:]{0,30})\s*:", re.I)
# mở rộng truy vấn (chỉ thêm vào truy vấn tìm kiếm, không thành từ khóa bắt buộc của cổng đủ căn cứ)
EXPANSIONS = {
    "sai": "sai sót", "sửa": "điều chỉnh thay thế", "hoàn ứng": "quyết toán tạm ứng", "quyết toán": "hoàn ứng",
    "tự phê duyệt": "xung đột lợi ích phân tách nhiệm vụ", "tự duyệt": "tự phê duyệt xung đột lợi ích phân tách nhiệm vụ",
    "phê duyệt cuối": "xung đột lợi ích phân tách nhiệm vụ",
    "lưu": "lưu trữ bảo quản", "tiêu hủy": "hủy thời hạn lưu trữ",
    "mất": "mất hủy hoại sao chụp", "khẩn cấp": "khẩn hậu kiểm", "chia nhỏ": "tách nhỏ giao dịch",
    "chữ ký": "ký duyệt", "ủy quyền": "ủy quyền thời hạn", "trùng": "trùng lặp",
    "chặn": "khóa", "hạn chế": "khóa", "hình thức": "loại có mã không có mã",
    "khách sạn": "lưu trú", "tiền phòng": "lưu trú",
    "mâu thuẫn": "khác", "trả về": "return_to_requester", "ghi log": "audit log ghi nhận", "lưu vết": "audit log",
    "khôi phục": "phục hồi", "phục hồi": "khôi phục", "xây dựng": "thiết kế", "cấp trên": "quản lý trực tiếp",
    "quá hạn": "overdue_advance thời hạn hoàn ứng điều kiện và hạn mức tạm ứng khóa quyền",
    "nhóm thông tin": "nhóm kiểm tra nội dung kiểm tra hồ sơ checklist kiểm tra nhanh điểm kiểm tra",
    "thông thường": "phân quyền truy cập vai trò archived",
    "ngoài ngân sách": "chi ngoài ngân sách nguồn bù ma trận theo loại chi",
    "chưa nhận được": "delivery log gửi lại không lập hóa đơn mới",
}
# viết lại câu hỏi (thay thế): từ viết tắt và từ đồng nghĩa phổ biến → đúng từ vựng của Data Pack
REWRITES = [
    (r"\bMST\b", "mã số thuế"), (r"\bHĐĐT\b", "hóa đơn điện tử"), (r"\bGTGT\b", "giá trị gia tăng"),
    (r"\bTNCN\b", "thu nhập cá nhân"), (r"\bTNDN\b", "thu nhập doanh nghiệp"), (r"\bBCTC\b", "báo cáo tài chính"),
    (r"\bNĐ\b(?!-)", "Nghị định"), (r"\bTT\b(?=\s*\d)", "Thông tư"), (r"\bIT\b", "CNTT"),
    (r"thỏa mãn", "đáp ứng"), (r"chia sẻ", "cung cấp"), (r"phòng ban", "bộ phận"), (r"định mức", "hạn mức"),
    (r"chi trả", "thanh toán"), (r"người nhận tiền", "người thụ hưởng"), (r"tài khoản nhận tiền", "tài khoản người thụ hưởng"),
    (r"(?:tiền|phần) (?:dư|thừa)", "phần chênh lệch"), (r"\bđi công tác\b", "chuyến công tác"),
    (r"bao lâu", "thời hạn bao nhiêu"), (r"(?:trong )?bao nhiêu ngày", "thời hạn bao nhiêu ngày"), (r"ứng trước", "tạm ứng"), (r"(?<!đưa )(?<!nộp )\bnhầm\b", "sai"),
    (r"(?:trễ|muộn) hạn", "quá hạn"), (r"tối đa", "không vượt quá"), (r"kiểm duyệt", "phê duyệt"),
    (r"xuất hóa đơn", "lập hóa đơn"), (r"giấy tờ", "chứng từ"), (r"xây dựng (biểu mẫu|mẫu)", r"thiết kế \1"),
    (r"(?:nhân viên|người dùng) bình thường", "người dùng thông thường"),
    (r"(?<!điều )\bchỉnh (?:sửa )?(số tiền|thuế suất|nội dung|thông tin|hóa đơn)", r"sửa \1"),     # khẩu ngữ "chỉnh" = sửa
    (r"cất (?:giữ|trữ)", "lưu trữ"), (r"(?:thế nào|ra sao) (?:thì |mới )?(?:là )?(?:đúng|hợp) (?:quy định|luật)", "thế nào theo quy định"), (r"rà soát", "kiểm tra"), (r"không mã", "không có mã"), (r"có mã cơ quan thuế", "có mã của cơ quan thuế"),
    (r"hình thức (?=hóa đơn|cơ bản|chính)", "loại hóa đơn có mã không có mã "), (r"mâu thuẫn", "xung đột"),
]
REWRITES_RE = [(re.compile(p, 0 if p == r"\bIT\b" else re.I), r) for p, r in REWRITES]   # "it" tiếng Anh ≠ IT
SYNONYM_RE = [(rx, r) for (p, r), (rx, _) in zip(REWRITES, REWRITES_RE) if not re.fullmatch(r"\\b[A-ZĐ]{2,}\\b.*", p)]
ABBR_RE = [(rx, r) for (p, r), (rx, _) in zip(REWRITES, REWRITES_RE) if re.fullmatch(r"\\b[A-ZĐ]{2,}\\b.*", p)]


def _abbreviations() -> list[tuple[str, str]]:
    """(từ viết tắt, dạng đầy đủ) trong REWRITES: MST, HĐĐT, GTGT, TNCN, TNDN, BCTC, NĐ, TT, IT."""
    return [(hit.group(1), r) for p, r in REWRITES if (hit := re.fullmatch(r"\\b([A-ZĐ]{2,})\\b.*", p))]


ABBREVIATIONS = _abbreviations()
# thuật ngữ nhiều âm tiết có dạng viết tắt (giá trị gia tăng, thu nhập doanh nghiệp, hóa đơn điện tử, mã số thuế…): là MỘT
# khái niệm – một đoạn chỉ cần nhắc tới thuật ngữ là khớp cả 3–4 âm tiết, lấn át phần câu hỏi thực sự hỏi (cổng G7)
TERM_COMPOUNDS = sorted({norm(r) for _, r in ABBREVIATIONS if " " in r}, key=len, reverse=True)


# P1a – viết tắt quen dùng trong nghiệp vụ kế toán (chạy sau REWRITES nên "HĐĐT", "TT 78/2021" đã được mở trước) và thuật ngữ
# tiếng Anh → đúng từ vựng của Data Pack. Không đụng số hiệu văn bản (123/2020/NĐ-CP, 78/2021/TT-BTC) và mã trạng thái.
ABBREV_VI = [
    (r"đntt|dntt", "đề nghị thanh toán"), (r"bbnt", "biên bản nghiệm thu"), (r"bbgn", "biên bản giao nhận"), (r"bb", "biên bản"),
    (r"hđkt", "hợp đồng kinh tế"), (r"hđlđ", "hợp đồng lao động"), (r"ncc", "nhà cung cấp"),
    (r"cqt", "cơ quan thuế"), (r"nnt", "người nộp thuế"), (r"ktt", "kế toán trưởng"), (r"tgđ", "tổng giám đốc"),
    (r"gđtc", "giám đốc tài chính"), (r"gđ", "giám đốc"), (r"stk", "số tài khoản"), (r"tk", "tài khoản"),
    (r"dn", "doanh nghiệp"), (r"cty", "công ty"), (r"uq", "ủy quyền"), (r"unc", "ủy nhiệm chi"), (r"tscđ", "tài sản cố định"),
    (r"bhxh", "bảo hiểm xã hội"), (r"bhyt", "bảo hiểm y tế"), (r"qlt", "quản lý thuế"), (r"vbhn", "văn bản hợp nhất"),
    (r"vbpl", "văn bản pháp luật"), (r"nlđ", "người lao động"), (r"hkd", "hộ kinh doanh"), (r"xnk", "xuất nhập khẩu"),
    (r"(?<!mã )hs", "hồ sơ"), (r"đc|dc", "được"), (r"vs", "so với"), (r"ko", "không"),
]
# viết tắt nhiều nghĩa: (nghĩa, dấu hiệu ở từ đứng TRƯỚC, dấu hiệu ở từ đứng SAU) – theo cách dùng phổ biến trong nghiệp vụ kế
# toán; không có dấu hiệu thì chọn nghĩa đồng xuất hiện nhiều nhất với các từ còn lại của câu trong Data Pack; nghĩa đầu là mặc định
ABBREV_AMBIG = {
    "hđ": [("hóa đơn", r"xuất|lập|phát hành|nhận|gửi|hủy|xóa|điều chỉnh|thay thế|sửa|các|mỗi|số|in",
            r"điện tử|gtgt|giá trị gia tăng|đầu vào|đầu ra|gốc|sai|điều chỉnh|thay thế|bán hàng|đã phát hành|mới|có mã|"
            r"không có mã|qua email|bị|của nhà cung cấp"),
           ("hợp đồng", r"ký|thanh lý|phụ lục|điều khoản|giá trị|vi phạm|chấm dứt|theo",
            r"quy định|yêu cầu|mua bán|nguyên tắc|kinh tế|lao động|thuê|ghi|với|đã ký|milestone|đợt|hết hạn")],
    "tt": [("thanh toán", r"đề nghị|hồ sơ|chứng từ|lệnh|chi|khoản|kỳ|đợt|điều kiện|được|đã|chưa|chờ|khi|mới|chỉ|duyệt|để|phải",
            r"cho|qua|bằng|tiền|trước|sau|khẩn cấp|ngay|toàn bộ|được|xong"),
           ("Thông tư", r"theo|các|của|tại", r"hiện hành|số|này|đó|nào|hướng dẫn|cũ|mới|thay thế|hết hiệu lực|có hiệu lực|bộ tài chính")],
    "nv": [("nhân viên", r"cho|của|các|mỗi|một|từng", r"mất|nộp|đi|đề nghị|công tác|tạm ứng|xin|có|được|phải|bình thường"),
           ("nghiệp vụ", r"xử lý|hạch toán|phát sinh", r"kinh tế|phát sinh|tài chính")],
    "kt": [("kế toán", r"phòng|bộ phận|nhân viên|chứng từ|sổ|tài liệu|chế độ|luật|cần|để",
            r"viên|thuế|bán hàng|thanh toán|xác nhận|kiểm tra|ghi nhận|lập"),
           ("kiểm toán", r"đang|phục vụ|phạm vi|cuộc|đơn vị", r"nội bộ|độc lập|viên|nhà nước"),
           ("kiểm tra", r"phải|được|đã|chưa|cần phải", r"lại|định kỳ|trước khi")],
    "ct": [("chứng từ", r"các|bộ|lưu|ký|lập|sửa|mất", r"gốc|kế toán|điện tử|chi tiền|hợp lệ|thanh toán"),
           ("công tác", r"đi|chuyến|về", r"phí|về|xa|trong nước|nước ngoài"),
           ("công ty", r"của", r"cổ phần|nova")],
    "cp": [("chi phí", r"các|khoản|tính vào|hạch toán|hoàn trả", r"công tác|phát sinh|hợp lý|được trừ|lưu trú|vượt|đi lại"),
           ("Chính phủ", r"nghị định|của", r"ban hành|quy định"),
           ("cổ phần", r"công ty", r"nova")],
    "qđ": [("quyết định", r"ra|ký|ban hành", r"phê duyệt|bổ nhiệm|số|tiêu hủy|công tác|của giám đốc"),
           ("quy định", r"các|đúng|vi phạm|tuân thủ", r"hiện hành|về|pháp luật|nội bộ|của pháp luật")],
    "kh": [("khách hàng", r"cho|của|gửi|báo|với", r"báo|chưa|nhận|mua|thanh toán|yêu cầu"),
           ("kế hoạch", r"theo|lập", r"kinh doanh|năm|ngân sách")],
    "ck": [("chuyển khoản", r"bằng|qua|thanh toán|chi|nhận|hay", r"ngân hàng|cho"),
           ("chiết khấu", r"được|hưởng", r"thương mại|thanh toán")],
    "tm": [("tiền mặt", r"bằng|chi|thu|thanh toán|tạm ứng|hay", r"tại quỹ"),
           ("thương mại", r"chiết khấu|phần mềm|kế toán|hóa đơn", r"điện tử")],
}
ABBREV_AMBIG_RE = re.compile(rf"(?<![\w/-])(?:{'|'.join(ABBREV_AMBIG)})(?![\w/-])", re.I)
GLOSSARY_EN = [
    (r"payment requests?", "đề nghị thanh toán"), (r"urgent payments?", "thanh toán khẩn cấp"),
    (r"e-?invoices?|electronic invoices?", "hóa đơn điện tử"), (r"invoices?", "hóa đơn"),
    (r"tax authorit(?:y|ies)|tax offices?", "cơ quan thuế"), (r"tax (?:codes?|ids?)", "mã số thuế"),
    (r"segregation of duties|sod", "phân tách nhiệm vụ"), (r"conflicts? of interest", "xung đột lợi ích"),
    (r"final approvers?", "người phê duyệt cuối"), (r"approvers?", "người phê duyệt"), (r"approv(?:e|ed|al|ing)", "phê duyệt"),
    (r"request(?:er|or)s?", "người đề nghị"), (r"requests?", "đề nghị"), (r"reject(?:ed|ion)?", "từ chối"),
    (r"skip(?:ped|ping)?|bypass(?:ed|ing)?", "bỏ qua"), (r"handl(?:e|ed|ing)", "xử lý"), (r"systems?", "hệ thống"),
    (r"rout(?:e|ed|ing)", "định tuyến"), (r"conflicts?", "xung đột"), (r"formats?", "định dạng"), (r"data(?!\s+pack)", "dữ liệu"),
    (r"deadlines?", "thời hạn"), (r"(?:cash )?advances?", "tạm ứng"), (r"settle(?:ments?)?", "quyết toán"),
    (r"suppliers?|vendors?", "nhà cung cấp"), (r"contracts?", "hợp đồng"), (r"acceptance (?:minutes|records?)", "biên bản nghiệm thu"),
    (r"budgets?", "ngân sách"), (r"limits?", "hạn mức"), (r"archiv(?:e|ed|ing)", "lưu trữ"), (r"backups?", "sao lưu"),
    (r"restor(?:e|ed|ing)|recover(?:y|ed|ing)?", "khôi phục"), (r"beneficiar(?:y|ies)", "người thụ hưởng"),
    (r"bank accounts?", "tài khoản ngân hàng"), (r"duplicat(?:e|ed|es)", "trùng lặp"), (r"business trips?", "chuyến công tác"),
    (r"per diem|travel allowances?", "công tác phí"), (r"hotels?", "khách sạn"), (r"polic(?:y|ies)", "quy chế"),
    (r"procedures?|process(?:es)?|workflows?", "quy trình"), (r"regulations?", "quy định"), (r"decrees?", "nghị định"),
    (r"circulars?", "thông tư"), (r"chief accountants?", "kế toán trưởng"), (r"accountants?|accounting", "kế toán"),
    (r"cfo|finance directors?", "giám đốc tài chính"), (r"ceo|general directors?", "tổng giám đốc"),
    (r"audit(?:s|ed|ing)?(?!\s+log)", "kiểm toán"), (r"status(?:es)?", "trạng thái"),
    (r"vouchers?|accounting documents?", "chứng từ kế toán"), (r"instead of", "thay vì"), (r"mov(?:e|ed|ing) to", "chuyển sang"),
    (r"vat", "giá trị gia tăng"), (r"wrong|incorrect|mistakes?|errors?", "sai"), (r"edit(?:ed|ing)?|modif(?:y|ied|ication)", "sửa"),
    (r"delet(?:e|ed|ion)|remov(?:e|ed|al)", "xóa"), (r"issued", "đã phát hành"), (r"cancel(?:led|lation)?", "hủy"),
    (r"adjust(?:ed|ment)?", "điều chỉnh"), (r"replac(?:e|ed|ement)", "thay thế"), (r"allowed|permitted", "được phép"),
    (r"retention|storage", "lưu trữ"), (r"destr(?:oy|uction)|dispos(?:e|al)", "tiêu hủy"), (r"signatures?", "chữ ký"),
    (r"employees?|staff", "nhân viên"), (r"expenses?", "chi phí"), (r"reimburse(?:ment)?", "hoàn trả"),
    (r"original", "bản gốc"), (r"overdue", "quá hạn"), (r"exceptions?", "ngoại lệ"), (r"delegat(?:e|ed|ion)", "ủy quyền"),
    (r"expired?|expiry", "hết hạn"), (r"buyers?", "người mua"), (r"sellers?", "người bán"), (r"customers?", "khách hàng"),
    (r"notif(?:y|ication)", "thông báo"), (r"purchase orders?", "đơn đặt hàng"), (r"electronic", "điện tử"),
]
ABBREV_VI_RE = [(re.compile(rf"(?<![\w/-])(?:{p})(?![\w/-])", re.I), r) for p, r in ABBREV_VI]
GLOSSARY_EN_RE = [(re.compile(rf"(?<![\w-])(?:{p})(?![\w-])", re.I), r) for p, r in GLOSSARY_EN]
# từ chức năng tiếng Anh: không tính vào độ phủ; câu có từ 2 từ đánh dấu trở lên là câu tiếng Anh → không "khôi phục dấu"
ENGLISH_STOP = {"the", "of", "to", "be", "is", "are", "was", "were", "been", "being", "should", "would", "could", "must",
                "shall", "will", "does", "did", "when", "what", "which", "who", "whom", "why", "how", "where", "this", "that",
                "these", "those", "with", "from", "into", "than", "if", "or", "and", "for", "please", "about", "after",
                "before", "still", "also", "just", "only", "any", "all", "some", "our", "your", "their", "its", "we", "you",
                "they", "a"}
ENGLISH_MARKERS = ENGLISH_STOP - {"to", "be", "the", "a", "than", "all"}
# lời đệm khẩu ngữ, cụm hỏi "văn bản nào", mốc thời gian tương đối: không phải nội dung phải có trong bằng chứng
FILLER_RE = re.compile(
    r"\b(?:nói ngắn gọn|ngắn gọn|nói cách khác|cái gọi là|gọi là|cho (?:mình|tôi|em) hỏi|giúp (?:mình|tôi|em|với)|"
    r"tức là|xong rồi|cho nhanh|cho lẹ|(?:căn cứ (?:vào )?)?(?:những |các )?(?:văn bản|căn cứ) nào|"
    r"tại thời điểm (?:đó|này)|có vai trò gì|tương ứng|"
    r"hôm nay|hôm qua|ngày mai|bây giờ|hiện giờ|lúc này|năm (?:nay|ngoái|rồi|tới)|tháng (?:này|rồi|tới)|"
    r"hãy viết (?:ra )?(?:các |những )?bước|viết (?:ra )?các bước|"
    r"rồi|vậy|nhé|nha|nhỉ|ạ|ơi|chứ|hả|đấy|ấy|lỡ)\b")
# mốc ngầm: "năm ngoái", "tháng 3 năm ngoái", "tháng trước", "hôm qua"… – không phải khoảng thời gian ("05 năm trước khi")
REL_DATE_RE = re.compile(r"(?:tháng\s+(\d{1,2})\s+)?năm\s+(nay|ngoái|trước|rồi|sau|tới)\b|tháng\s+(này|trước|rồi|sau|tới)\b|"
                         r"hôm\s+(nay|qua)\b|ngày\s+mai\b|bây giờ|hiện giờ|lúc này")
_REL_STEP = {"nay": 0, "này": 0, "ngoái": -1, "trước": -1, "rồi": -1, "sau": 1, "tới": 1}
DURATION_BEFORE_RE = re.compile(r"(?:\d+|mấy|vài|nhiều|các|những|mỗi|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)\s*$")
ATTRIBUTIVE_BEFORE_RE = re.compile(r"\bcủa\s*$")      # "chứng từ của tháng trước": kỳ của sự vật, không phải lúc sự việc xảy ra


def strip_fillers(text: str) -> str:
    """Câu hỏi bỏ lời đệm khẩu ngữ và mốc thời gian tương đối (dùng khi tính từ khóa và khi tìm kiếm)."""
    return FILLER_RE.sub(" ", norm(text))


def relative_date(q: str, base: date) -> tuple[date | None, str]:
    """Mốc ngầm trong câu hỏi (chữ thường) → ngày cụ thể tính từ mốc tham chiếu; (None, "") nếu câu không có."""
    for m in REL_DATE_RE.finditer(q):
        if DURATION_BEFORE_RE.search(q[:m.start()]) or ATTRIBUTIVE_BEFORE_RE.search(q[:m.start()]):
            continue
        phrase = m.group(0)
        if m.group(2):
            y = base.year + _REL_STEP[m.group(2)]
            if m.group(1) and 1 <= int(m.group(1)) <= 12:
                return date(y, int(m.group(1)), 15), phrase
            return (date(y, 2, 28) if (base.month, base.day) == (2, 29) else base.replace(year=y)), phrase
        if m.group(3):
            k = base.year * 12 + base.month - 1 + _REL_STEP[m.group(3)]
            return (date(k // 12, k % 12 + 1, 15) if _REL_STEP[m.group(3)] else base), phrase
        if m.group(4) == "qua":
            return base - timedelta(days=1), phrase
        if phrase.startswith("ngày"):
            return base + timedelta(days=1), phrase
        return base, phrase
    return None, ""


def is_unaccented(text: str) -> bool:
    """Câu gõ không dấu: từ 8 chữ cái trở lên và không quá 3% chữ cái mang dấu tiếng Việt."""
    letters = [ch for ch in str(text) if ch.isalpha()]
    return len(letters) >= 8 and sum(fold(ch) != ch.lower() for ch in letters) / len(letters) <= 0.03


# âm tiết tiếng Việt viết không dấu: phụ âm đầu? + 1–3 nguyên âm + phụ âm cuối? ("is", "allowed", "invoice" không thỏa)
VN_SYLLABLE_RE = re.compile(r"(?:ngh|ng|nh|ch|gh|gi|kh|ph|th|tr|qu|[bcdghklmnprstvx])?[aeiouy]{1,3}(?:ng|nh|ch|[cmnpt])?")


def is_english(text: str) -> bool:
    """Câu tiếng Anh: ≥ 2 hư từ tiếng Anh, hoặc ≥ 2 từ (≥ 40% số từ) không thể là âm tiết tiếng Việt."""
    if sum(w.lower() in ENGLISH_MARKERS for w in re.findall(r"[A-Za-z]+", str(text))) >= 2:
        return True
    words = re.findall(r"[^\W\d_]+", str(text))
    foreign = [w for w in words if len(w) > 1 and not w.isupper() and fold(w) == w.lower()
               and not VN_SYLLABLE_RE.fullmatch(w.lower())]
    return len(foreign) >= 2 and len(foreign) >= 0.4 * len(words)


def question_terms(question: str) -> tuple[list[str], set[str]]:
    """Từ khóa và cụm 2 âm tiết mà bằng chứng phải phủ: bỏ lời đệm khẩu ngữ, mốc thời gian tương đối; câu tiếng Anh bỏ
    thêm hư từ tiếng Anh."""
    core, eng = strip_fillers(question), ENGLISH_STOP if is_english(question) else set()
    return ([t for t in content_terms(core) if t not in eng],
            {b for b in content_bigrams(core) if not any(p in eng for p in b.split("~"))})


class PolicyAssist:
    def __init__(self, dp: DataPack, cfg: Config | None = None):
        self.dp = dp
        self.cfg = cfg or Config()
        C = dp.chunks
        fields = [" ".join([c["document_title"], c["heading"], c["heading"], c["topic"], c["subtopic"],
                            c["article"], c["citation_label"], c["chunk_text"]]) for c in C]
        self.tokens = [tokenize(t) for t in fields]
        self.tokset = [set(t) for t in self.tokens]
        self.bm25 = BM25Okapi(self.tokens, k1=1.5, b=0.75)
        self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True,
                                     preprocessor=norm, min_df=1)
        self.X = self.tfidf.fit_transform([f"{c['heading']} {c['chunk_text']}" for c in C])
        n = len(C)
        df: dict[str, int] = {}
        for s in self.tokset:
            for t in s:
                df[t] = df.get(t, 0) + 1
        self.idf = {t: math.log((n + 1) / (v + 0.5)) for t, v in df.items()}
        self.idf_max = math.log((n + 1) / 0.5)
        self.codes = [set(CODE_RE.findall(c["chunk_text"] + " " + c["heading"])) for c in C]
        self.content_tok = [set(tokenize(c["heading"] + " " + c["chunk_text"], bigrams=False)) for c in C]
        self.corpus_codes = set().union(*self.codes)
        # điều khoản chỉ áp dụng trong phạm vi chính tài liệu của nó ("khác biệt giữa SIM05 với …", "giữa tài liệu này và …")
        self.self_scoped = {i for i, c in enumerate(C) if c["source_type"] != "LEGAL" and re.search(
            rf"khác(?: biệt)? giữa (?:{c['document_id'].lower()}|tài liệu này)\b", norm(c["chunk_text"]))}
        self.titles = " | ".join(norm(m["title"]) for m in dp.doc.values())
        self.affirmed = [set(tokenize(c["heading"] + " " + NEGATED_SPAN_RE.sub(" ", norm(c["chunk_text"])))) for c in C]
        # bảng: độ phủ tính theo DÒNG tốt nhất (kèm tiêu đề bảng + tiêu đề cột), không theo cả bảng
        self.rows = [[set(tokenize(c["heading"] + " " + c["chunk_text"].split("\n", 1)[0] + " " + u)) for u in self.units(c)]
                     if c["content_type"] == "SOURCE_TABLE_TEXT" else None for c in C]
        # luật được gọi bằng tên (không kèm số hiệu): "Luật Quản lý thuế" → các văn bản LAW cùng tên
        self.law_names: dict[str, list[str]] = {}
        for d, m in dp.doc.items():
            if m["document_type"] == "LAW":
                name = re.split(r"\s+số\s+|\s+\d", norm(m["title"]))[0].strip()
                self.law_names.setdefault(name, []).append(d)
        # từ vựng Data Pack để khôi phục dấu cho câu hỏi gõ không dấu
        from collections import Counter
        uni, bi = Counter(), Counter()
        texts = [c["heading"] + " " + c["chunk_text"] for c in C] + list(dp.docs_df.title) + list(dp.questions.question_text)
        texts.append(" ".join(STOPWORDS | GENERIC | FRAMING | FRAMING_UNI))
        for t in texts:
            ws = re.findall(r"[^\W\d_]+", norm(t))
            uni.update(ws)
            bi.update(f"{a} {b}" for a, b in zip(ws, ws[1:]))
        self.restore_uni: dict[str, str] = {}
        for w, n in uni.most_common():
            self.restore_uni.setdefault(fold(w), w)
        for w in CONVERSATIONAL:                     # câu hỏi đời thường: "toi" là "tôi" (không phải "tối")
            self.restore_uni[fold(w)] = w
        self.chunk_norm = [norm(c["heading"] + " " + c["chunk_text"]) for c in C]
        self.corpus_text = "\n".join(self.chunk_norm)
        self.term_chunks: dict[str, set[int]] = {}
        for i, toks in enumerate(self.tokset):
            for t in toks:
                self.term_chunks.setdefault(t, set()).add(i)
        self._phrase_cache: dict[str, set[int]] = {}
        self.restore_bi: dict[str, str] = {}
        self.bi_count: dict[str, int] = {}
        for w, n in bi.most_common():
            if n >= 2:
                k = fold(w)
                if k not in self.restore_bi:
                    self.restore_bi[k] = w
                    self.bi_count[k] = n

    def restore_diacritics(self, text: str) -> str:
        """Câu hỏi gõ không dấu ("chung tu ke toan la gi") → khôi phục dấu theo cụm từ/âm tiết phổ biến nhất trong Data Pack."""
        if not is_unaccented(text) or is_english(text):
            return text
        words = list(re.finditer(r"[^\W\d_]+", text))
        out, last, i = [], 0, 0
        while i < len(words):
            w = words[i]
            if w.group(0).isupper() and len(w.group(0)) > 1:          # mã/viết tắt (HOLD, LAW) giữ nguyên
                i += 1
                continue
            if i + 1 < len(words) and text[w.end():words[i + 1].start()].strip() == "":
                key = fold(w.group(0)) + " " + fold(words[i + 1].group(0))
                next_key = (fold(words[i + 1].group(0)) + " " + fold(words[i + 2].group(0))
                            if i + 2 < len(words) and text[words[i + 1].end():words[i + 2].start()].strip() == "" else "")
                if key in self.restore_bi and self.bi_count.get(key, 0) >= self.bi_count.get(next_key, 0):
                    a, b = self.restore_bi[key].split(" ", 1)
                    out += [text[last:w.start()], _same_case(w.group(0), a), text[w.end():words[i + 1].start()],
                            _same_case(words[i + 1].group(0), b)]
                    last, i = words[i + 1].end(), i + 2
                    continue
            rep = self.restore_uni.get(fold(w.group(0)))
            if rep:
                out += [text[last:w.start()], _same_case(w.group(0), rep)]
                last = w.end()
            i += 1
        out.append(text[last:])
        return "".join(out)

    def rewrite(self, question: str) -> str:
        return self.rewrite_ex(question)[0]

    def rewrite_ex(self, question: str) -> tuple[str, list[str]]:
        """Chuẩn hóa câu hỏi trước khi xử lý: khôi phục dấu (nếu gõ không dấu), từ đồng nghĩa (chỉ khi Data Pack không dùng
        đúng cụm đó), từ viết tắt (nhiều nghĩa → chọn theo ngữ cảnh), thuật ngữ tiếng Anh. Trả về câu đã chuẩn hóa và danh sách
        "viết tắt → cách hiểu" để người dùng kiểm tra."""
        q = self.restore_diacritics(unicodedata.normalize("NFC", question))
        q = _OLD_TONE_RE.sub(lambda m: _OLD_TONE[m.group(1)], q)
        seen: list[str] = []

        def note(src: str, dst: str) -> str:
            if norm(src) != norm(dst):
                item = f"{src} → {dst}"
                if item not in seen:
                    seen.append(item)
            return dst

        for rx, rep in SYNONYM_RE:
            if rep == "chứng từ" and "chứng từ" in norm(q):
                continue
            q = rx.sub(lambda m, rx=rx, rep=rep: m.group(0) if self.corpus_phrase(q, m) else m.expand(rep), q)
        for rx, rep in ABBR_RE + ABBREV_VI_RE:
            q = rx.sub(lambda m, rep=rep: note(m.group(0), m.expand(rep)), q)
        q = ABBREV_AMBIG_RE.sub(lambda m: note(m.group(0), self.resolve_abbrev(m)), q)
        for rx, rep in GLOSSARY_EN_RE:                  # mã trạng thái có trong Data Pack (REJECT, URGENT…) giữ nguyên
            q = rx.sub(lambda m, rep=rep: m.group(0) if m.group(0) in self.corpus_codes else note(m.group(0), rep), q)
        return re.sub(r"\s+", " ", q).strip(), seen

    def corpus_phrase(self, q: str, m: re.Match) -> bool:
        """Cụm từ người dùng gõ (kèm từ đứng sau) có nguyên văn trong Data Pack → giữ, không thay bằng từ đồng nghĩa."""
        nxt = re.match(r"\s*([^\W\d_]+)", q[m.end():])
        phrase = norm(m.group(0) + (" " + nxt.group(1) if nxt else ""))
        return bool(nxt) and phrase in self.corpus_text

    def resolve_abbrev(self, m: re.Match) -> str:
        """Nghĩa của viết tắt nhiều nghĩa: dấu hiệu ở từ đứng ngay trước/sau (2 điểm mỗi bên), rồi mức đồng xuất hiện với các
        từ còn lại của câu trong Data Pack; nghĩa trùng từ đứng cạnh ("KT kiểm tra") bị loại; hòa → nghĩa thường gặp nhất."""
        text, abbr = m.string, m.group(0)
        left, right = norm(text[:m.start()]).rstrip(), norm(text[m.end():]).lstrip(" ,")
        ctx = [t for t in content_terms(text[:m.start()] + " " + text[m.end():]) if t in self.term_chunks]
        best, best_score = None, None
        for rank, (cand, lc, rc) in enumerate(ABBREV_AMBIG[norm(abbr)]):
            score = 2.0 * bool(re.search(rf"(?:^|\s)(?:{lc})$", left)) + 2.0 * bool(re.match(rf"(?:{rc})\b", right))
            if right.startswith(norm(cand)) or left.endswith(norm(cand)):
                score -= 3.0
            docs = self.phrase_chunks(norm(cand))
            if docs and ctx:
                score += sum(len(docs & self.term_chunks[t]) / len(docs) for t in ctx) / len(ctx)
            score -= 0.01 * rank
            if best_score is None or score > best_score:
                best, best_score = cand, score
        return best if abbr.islower() or best[0].isupper() else best

    def phrase_chunks(self, phrase: str) -> set[int]:
        if phrase not in self._phrase_cache:
            rx = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)")
            self._phrase_cache[phrase] = {i for i, t in enumerate(self.chunk_norm) if rx.search(t)}
        return self._phrase_cache[phrase]

    def with_config(self, **kw) -> "PolicyAssist":
        clone = object.__new__(PolicyAssist)
        clone.__dict__ = dict(self.__dict__)
        clone.cfg = replace(self.cfg, **kw)
        return clone

    # ------------------------------------------------------------------ P0
    def guard(self, question: str, raw: str = "") -> tuple[bool, str]:
        q = norm(question)
        if why := self._guard_rules(q, GUARD_ACCENTED):
            return True, why
        for m in STATUTE_RE.finditer(question):
            words = norm(m.group(2)).split()[:2]
            if words and f"luật {' '.join(words)}" not in self.titles:
                return True, f"Câu hỏi dựa trên “{m.group(0).strip()}” – văn bản này không có trong Data Pack."
        # câu gõ không dấu: bước khôi phục dấu có thể chọn sai từ ("muc luong" → "mức lượng") nên dò lại trên câu gốc bỏ dấu
        if raw and is_unaccented(raw) and (why := self._guard_rules(fold(raw), GUARD_FOLDED)):
            return True, why
        return False, ""

    def split_scope(self, q: str) -> tuple[str, list[str]]:
        """Tách phần không được xử lý khỏi câu hỏi, trả về (phần còn lại, ghi chú hiển thị cho người dùng):
        – câu/vế chứa chỉ dẫn chèn vào (bỏ qua quy tắc, không cần trích dẫn…) hoặc mạo danh thẩm quyền ("tôi là Giám đốc …,
          tôi cho phép bạn") bị bỏ – hệ thống không làm theo, vẫn trả lời phần hỏi hợp lệ theo Data Pack và luôn dẫn nguồn;
          không còn gì để hỏi thì giữ nguyên câu để Guard từ chối;
        – câu hỏi ghép ("…, và …?") có vế đòi dữ liệu thực tế (Guard nhóm dữ kiện) → vế đó được nêu là không có dữ liệu, vế
          còn lại được trả lời. Câu chỉ có một vế giữ nguyên (Guard xử lý như trước)."""
        notes = []
        parts = re.split(r"(?<=[.!?:])\s+", q.strip())
        keep = [p for p in parts if not INJECTION_RE.search(norm(p))]
        if len(keep) < len(parts) and keep and content_terms(" ".join(keep)):
            notes.append("Đã bỏ qua chỉ dẫn chèn vào câu hỏi (yêu cầu bỏ quy tắc/không trích dẫn) – hệ thống luôn trả lời theo "
                         "Data Pack và luôn dẫn nguồn.")
            q = " ".join(keep)
        q2 = AUTHORITY_RE.sub("", q)
        if q2 != q and content_terms(q2):
            notes.append("Câu hỏi nêu thẩm quyền của người hỏi – thẩm quyền tự nêu không thay đổi quy định; hệ thống trả lời theo "
                         "quy trình trong Data Pack.")
            q = q2[:1].upper() + q2[1:]
        nq = norm(q)
        clauses = re.split(r",?\s+(?:và|còn)\s+(?=[^,.;?]*(?:\?|$))|;\s+", q)
        if len(clauses) >= 2 and (ENTITY_RE.search(nq) or RECORD_RE.search(nq)):
            oos, rest = [], []
            for c in clauses:
                nc = norm(c)
                hit = next((cat for cat, frx in FACT_RE.items() if frx.search(nc)), None) \
                    if ASK_RE.search(nc) and not PROCEDURAL_RE.search(nc) else None
                (oos if hit else rest).append((c, hit))
            if oos and rest and content_terms(" ".join(c for c, _ in rest)):
                for c, cat in oos:
                    notes.append(f"Phần “{c.strip(' ?.,;')}” đòi dữ liệu thực tế thuộc nhóm “{cat}” – Data Pack không có "
                                 "(Nova Việt là doanh nghiệp giả lập); hệ thống chỉ trả lời phần còn lại.")
                q = ", ".join(c.strip(" ,;") for c, _ in rest).rstrip(" ?") + "?"
        return q, notes

    @staticmethod
    def _guard_rules(q: str, rx: dict) -> str:
        if rx["injection"].search(q):
            return "Câu hỏi chứa chỉ dẫn yêu cầu bỏ qua quy tắc hệ thống (prompt injection)."
        if rx["illegal"].search(q):
            return "Yêu cầu hướng tới hành vi trái pháp luật – hệ thống không hỗ trợ."
        if (rx["entity"].search(q) or rx["record"].search(q)) and rx["ask"].search(q) and not rx["procedural"].search(q):
            for cat, frx in rx["facts"].items():
                if m := frx.search(q):
                    return (f"Câu hỏi đòi dữ liệu thực tế thuộc nhóm “{cat}” (“{m.group(0)}”) – Data Pack không có; "
                            "Nova Việt là doanh nghiệp giả lập.")
        return ""

    # ------------------------------------------------------------------ P1
    def plan(self, question: str, ref: date | None) -> dict:
        q = norm(question)
        warnings = []
        applied = ref or SNAPSHOT
        m = DATE_IN_Q_RE.search(q)
        rel, phrase = (None, "") if m else relative_date(q, applied)
        if m:
            qd = parse_date(m.group(2))
            if qd:
                if m.group(1) == "trước":
                    qd -= timedelta(days=1)
                if ref is not None and qd != ref:
                    warnings.append(f"Câu hỏi nêu mốc {qd:%d/%m/%Y}; hệ thống áp dụng mốc này thay cho reference_date.")
                applied = qd
        elif rel is not None and rel != applied:
            warnings.append(f"Câu hỏi nêu “{phrase}” – hệ thống hiểu là ngày {rel:%d/%m/%Y} (tính từ mốc {applied:%d/%m/%Y}); "
                            "muốn chính xác hãy nêu ngày cụ thể.")
            applied = rel
        date_source = "question" if m or rel is not None else "reference_date" if ref is not None else "default"
        date_unknown = ref is None and not m and rel is None and not CURRENT_RE.search(q)
        if ref is None and not m and rel is None:
            warnings.append(f"Không có reference_date – hệ thống giả định mốc corpus {SNAPSHOT:%d/%m/%Y}.")
        if applied > SNAPSHOT:
            warnings.append(f"Mốc {applied:%d/%m/%Y} sau ngày chụp corpus {SNAPSHOT:%d/%m/%Y}: văn bản mới hơn (nếu có) không nằm trong Data Pack.")
        mentioned = self.dp.mentioned_docs(question)
        law_mentioned = [d for d in mentioned if d.startswith("LAW")]
        # luật được gọi bằng tên → văn bản cùng tên còn hiệu lực tại mốc (không coi là câu hỏi về phiên bản)
        named_laws = [d for name, ds in self.law_names.items() if name in q for d in ds
                      if self.dp.doc_state(d, applied) == VALID and d not in mentioned]
        same_chain = any(sum(1 for x in law_mentioned if self.dp.chain(x) == self.dp.chain(d)) >= 2 for d in law_mentioned)
        codes = {c for c in CODE_RE.findall(question) if c not in {"LAW", "SIM", "FAQ", "BTC", "CNTT", "USD", "VND"}}
        is_internal = bool(INTERNAL_RE.search(q) or codes or any(d.startswith("SIM") for d in mentioned))
        is_legal = bool(LEGAL_RE.search(q) or law_mentioned)
        if re.search(r"có mã.*không (?:có )?mã|cơ quan thuế", q) and not re.search(r"nova việt|nội bộ|quy trình|quy chế|sổ tay|faq", q):
            is_internal, is_legal = False, True
        sims = [d for d in mentioned if d.startswith("SIM")]
        terms, bigrams = question_terms(question)
        doc_toks = set().union(*(set(tokenize(self.dp.doc[d]["title"] + " " + self.dp.number.get(d, ""), bigrams=False))
                                 for d in mentioned)) if mentioned else set()
        ver_meta_toks = {"hiệu", "lực", "thay", "thế", "hiện", "hành", "áp", "dụng", "còn", "hết", "độc", "lập",
                         "lịch", "sử", "hợp", "nhất", "pháp", "lý", "tra", "cứu", "versioning", "phiên", "bản",
                         "chuỗi", "quan", "hệ", "ưu", "tiên", "mới", "cũ", "sửa", "đổi", "bổ", "sung", "kế", "nhiệm",
                         "luật", "nghị", "định", "thông", "tư", "văn", "bản", "tài", "liệu", "chế", "độ", "doanh", "nghiệp",
                         "quốc", "hội", "chính", "phủ", "bộ", "chính", "hóa", "đơn", "điện", "tử", "chứng", "quản", "thuế",
                         "hướng", "dẫn", "chi", "tiết", "phát", "sinh", "nghiệp", "vụ", "nguồn", "tạo", "tính", "dùng"} | doc_toks
        subst_terms = [t for t in terms if t not in ver_meta_toks and not t.isdigit() and not re.fullmatch(r"(?:law|sim)\d*", t)]
        pure_version = (len(subst_terms) == 0 and not sims
                        and not re.search(r"quy định (?:như )?thế nào|nội dung (?:gì|nào)", q))
        version_q = bool(VERSION_RE.search(q) or same_chain
                         or (law_mentioned and (applied != SNAPSHOT or VERSION_DOC_RE.search(q)
                                                or any(self.dp.doc_state(d, applied) != VALID for d in law_mentioned)))
                         or (pure_version and re.search(r"(?:thông tư|nghị định|luật|văn bản)[^?]{0,35}nào|"
                                                        r"(?:áp dụng|ưu tiên) (?:thông tư|nghị định|luật|văn bản) nào", q)))
        inferred_laws: list[str] = []
        if pure_version and version_q and not law_mentioned:
            want_type = ("CIRCULAR" if "thông tư" in q or "hướng dẫn" in q else
                         "DECREE" if "nghị định" in q or "chi tiết" in q else
                         "LAW" if "luật" in q else "")
            if want_type:
                chain_docs = [d for d, m in self.dp.doc.items() if m["document_type"] == want_type and len(self.dp.chain(d)) > 1]
                inferred_laws = [d for d in chain_docs if self.dp.doc_state(d, applied) == VALID] or chain_docs
        only_sim_named = bool(mentioned) and all(d.startswith("SIM") for d in mentioned) and not re.search(
            r"\bluật\b|nghị định|thông tư|pháp luật", q)
        if version_q or (applied != SNAPSHOT and (not is_internal or is_legal)):
            intent = "VERSIONING"
        elif is_internal and not only_sim_named and (MIXED_RE.search(q) or re.search(r"\bluật\b|nghị định|thông tư|pháp luật", q)):
            intent = "MIXED"
        elif is_internal:
            intent = "INTERNAL"
        else:
            intent = "LEGAL"            # câu hỏi chung không nhắc nội bộ → ưu tiên pháp luật (README mục 2)
        scope = ("MIXED" if intent == "MIXED" or (is_internal and is_legal) else
                 "INTERNAL" if is_internal else "LEGAL")
        extra = [v for k, v in EXPANSIONS.items() if re.search(rf"\b{k}\b", q)] if self.cfg.use_expansion else []
        if version_q and (pure_version or sims) and self.cfg.use_expansion:
            extra.append("hiệu lực thay thế chuyển tiếp phạm vi")
        if sims and law_mentioned and self.cfg.use_expansion:
            extra.append("nguyên tắc sử dụng thứ tự ưu tiên nguồn thông tin chưa được cập nhật")
        core = strip_fillers(question) if self.cfg.use_rewrite else question   # bỏ lời đệm, mốc tương đối khi tìm kiếm
        expanded = f"{core} {' '.join(extra)}" if extra else core
        return {"question": question, "applied": applied, "date_unknown": date_unknown, "date_source": date_source,
                "mentioned": mentioned, "pure_version": pure_version, "subst_terms": subst_terms, "inferred_laws": inferred_laws,
                "law_mentioned": law_mentioned, "named_laws": named_laws, "codes": codes, "intent": intent, "scope": scope,
                "version_question": version_q, "expanded": expanded, "warnings": warnings,
                "scope_cue": is_internal or is_legal, "procedure": bool(PROCEDURE_Q_RE.search(norm(question))),
                "terms": terms, "bigrams": bigrams}

    # ------------------------------------------------------------------ P2
    def retrieve(self, P: dict) -> dict[int, dict]:
        qtok = tokenize(P["expanded"])
        bm = np.asarray(self.bm25.get_scores(qtok))
        tf = (self.X @ self.tfidf.transform([P["expanded"]]).T).toarray().ravel() if self.cfg.w_tfidf else np.zeros(len(bm))
        bmn = bm / bm.max() if bm.max() > 0 else bm
        tfn = tf / tf.max() if tf.max() > 0 else tf
        fused = self.cfg.w_bm25 * bmn + self.cfg.w_tfidf * tfn
        P["fused_all"] = fused                     # độ liên quan "gốc" của mọi chunk – dùng khi chọn citation
        order = list(np.argsort(-fused, kind="stable")[: self.cfg.pool])
        forced = set()
        if self.cfg.use_forced:
            for d in P["mentioned"]:                                 # chỉ mục cấu trúc: văn bản được nhắc tên
                if P["intent"] == "VERSIONING" and not P.get("pure_version", True) and self.dp.doc_state(d, P["applied"]) not in USABLE:
                    for nd in self.dp.successors_in_force(d, P["applied"]):
                        forced.update(sorted(self.dp.doc_chunks.get(nd, []), key=lambda i: -fused[i])[:3])
                    continue
                forced.update(sorted(self.dp.doc_chunks.get(d, []), key=lambda i: -fused[i])[:3])
            if P["codes"]:
                forced.update(i for i in np.argsort(-fused)[:120] if self.codes[i] & P["codes"])
        cands = {}
        for i in list(order) + sorted(forced - set(order)):
            cands[int(i)] = {"bm25": float(bm[i]), "tfidf": float(tf[i]), "fused": float(fused[i]),
                             "forced": i in forced}
        return cands

    def coverage(self, i: int, terms: list[str]) -> float:
        return sum(1 for t in terms if t in self.tokset[i]) / len(terms) if terms else 0.0

    def row_coverage(self, i: int, terms: list[str]) -> float:
        """Với bảng: độ phủ của DÒNG khớp nhất (kèm tiêu đề bảng); với văn bản thường: độ phủ cả chunk."""
        if not self.rows[i] or not terms:
            return self.coverage(i, terms)
        return max(sum(1 for t in terms if t in rs) / len(terms) for rs in self.rows[i])

    def table_factor(self, i: int, terms: list[str]) -> float:
        """Bảng TRA CỨU (thuật ngữ, vai trò, ma trận, phân công, căn cứ tham chiếu) chỉ thực sự liên quan khi có một
        dòng khớp câu hỏi; từ khóa rải rác ở nhiều dòng không được tính đủ. Bảng tình huống/trạng thái/checklist giữ nguyên."""
        if not self.cfg.table_rows or not self.rows[i] or not terms \
                or not REFERENCE_TABLE_RE.search(norm(self.dp.chunks[i]["heading"])):
            return 1.0
        whole = self.coverage(i, terms)
        return 0.5 + 0.5 * min(1.0, self.row_coverage(i, terms) / whole) if whole else 1.0

    @staticmethod
    def guide_text(c: dict) -> str:
        """Phần hướng dẫn của FAQ/sổ tay (bỏ câu hỏi/tình huống lặp lại và dòng "Nguồn ưu tiên")."""
        t = c["chunk_text"]
        m = (re.search(r"Trả lời:\s*(.*?)(?:\n\s*Nguồn ưu tiên:|$)", t, re.S) if c["document_type"] == "FAQ"
             else re.search(r"Dấu hiệu[^\n]*:\s*(.*?)(?:\n\s*Nguồn tra cứu ưu tiên:|$)", t, re.S))
        return m.group(1) if m else re.sub(r"Câu hỏi:[^\n]*\n?|Tình huống:[^\n]*\n?|Nguồn[^\n]*", " ", t)

    # ------------------------------------------------------------------ P3 + P4
    def resolve_and_rerank(self, P: dict, cands: dict[int, dict]) -> list[dict]:
        ref, cfg, dp = P["applied"], self.cfg, self.dp
        rows: list[dict] = []
        byi: dict[int, dict] = {}

        def add(i: int, fused: float, via: str = "") -> dict:
            r = byi.get(i)
            if r is not None:
                if fused > r["fused"]:
                    r["fused"], r["via"] = fused, via or r["via"]
                return r
            c, s = dp.chunks[i], cands.get(i, {})
            st = dp.chunk_state(i, ref) if cfg.use_chronos else (INTERNAL if c["source_type"] != "LEGAL" else VALID)
            r = {"i": i, "chunk_id": c["chunk_id"], "document_id": c["document_id"], "state": st,
                 "coverage": self.coverage(i, P["terms"]), "bm25": s.get("bm25", 0.0), "tfidf": s.get("tfidf", 0.0),
                 "fused": fused, "forced": s.get("forced", False), "via": via, "endorsed_by": ""}
            rows.append(r)
            byi[i] = r
            return r

        for i, s in cands.items():
            if cfg.hard_date_filter and dp.chunk_state(i, ref) in (EXPIRED, NOT_YET, INTERNAL_NOT_YET):
                continue                         # B2′: pipeline tham khảo lọc cứng theo ngày trước khi xếp hạng
            add(i, s["fused"])
        top_by_fused = lambda n: sorted(rows, key=lambda r: -r["fused"])[:n]

        # (1) CHRONOS – thế chỗ: chunk luật đã hết hiệu lực xếp cao → điều khoản tương ứng ở văn bản kế nhiệm
        if cfg.use_chronos and (P["intent"] != "VERSIONING" or not P.get("pure_version", True)):
            for r in top_by_fused(10):
                if r["state"] not in (EXPIRED, REF_ONLY):
                    continue
                for nd in dp.successors_in_force(r["document_id"], ref):
                    pool = [j for j in dp.doc_chunks[nd] if dp.chunk_state(j, ref) == VALID]
                    if not pool:
                        continue
                    sims = (self.X[pool] @ self.X[r["i"]].T).toarray().ravel()
                    b = int(np.argmax(sims))
                    if sims[b] >= cfg.successor_min_cos:
                        add(pool[b], r["fused"] * 0.9 * min(1.0, sims[b] / 0.5), f"kế nhiệm của {r['chunk_id']}")

        # (2) Truy nguồn gốc: FAQ/sổ tay là tài liệu thứ cấp, luôn ghi "Nguồn ưu tiên: ..." → văn bản gốc (đã quy về
        #     văn bản còn hiệu lực) được ưu tiên; phần trả lời của FAQ dùng làm truy vấn mở rộng tìm điều khoản gốc.
        endorsed: dict[str, str] = {}
        if cfg.use_rerank and cfg.use_prf:
            guides = [r for r in top_by_fused(5) if dp.chunks[r["i"]]["document_type"] in SECONDARY_TYPES][:2]
            if len(guides) > 1:
                guides = [g for g in guides if g is guides[0]
                          or (g["document_id"] != guides[0]["document_id"] and g["fused"] >= 0.75 * guides[0]["fused"])]
            P["guides"] = [g["i"] for g in guides]
            for g in guides:
                c = dp.chunks[g["i"]]
                m = SOURCE_LINE_RE.search(c["chunk_text"])
                if not m:
                    continue
                g_docs = []
                for d in dp.mentioned_docs(m.group(1)):
                    if dp.doc[d]["document_type"] in SECONDARY_TYPES:
                        continue
                    st = dp.doc_state(d, ref)
                    for x in (dp.successors_in_force(d, ref) if st in (EXPIRED, REF_ONLY) else [d]):
                        endorsed.setdefault(x, g["chunk_id"])
                        if x not in g_docs:
                            g_docs.append(x)
                if g_docs and cfg.prf_chunks:
                    if cfg.prf_guide:
                        text = self.guide_text(c)
                        # phần hướng dẫn của FAQ/sổ tay được nhấn mạnh (lặp 2 lần) so với câu hỏi gốc
                        sc = np.asarray(self.bm25.get_scores(tokenize(f"{text} {text} {P['expanded']}")))
                    else:
                        text = re.sub(r"Câu hỏi:[^\n]*\n?|Nguồn[^\n]*", " ", c["chunk_text"])
                        if not re.search(r"xung đột|tự (?:phê )?duyệt|tự duyệt", norm(P["question"])):
                            text = re.sub(r";?\s*(?:người (?:lập|tạo)|người có xung đột|trường hợp có xung đột).*?(?=[.;\n]|$)", " ", text)
                        sc = np.asarray(self.bm25.get_scores(tokenize(P["expanded"] + " " + text)))
                    for d in g_docs:
                        ids = [j for j in dp.doc_chunks.get(d, []) if dp.chunk_state(j, ref) in USABLE]
                        if not ids:
                            continue
                        mx = float(max(sc[j] for j in ids)) or 1.0
                        w = cfg.prf_weight * (cfg.prf_legal_internal if (P["scope"] == "INTERNAL" and d.startswith("LAW")) else 1.0)
                        for j in sorted(ids, key=lambda j: -sc[j])[: cfg.prf_chunks]:
                            add(j, g["fused"] * w * float(sc[j]) / mx, f"điều khoản gốc do {g['chunk_id']} dẫn chiếu")

        # (3) README mục 2: tài liệu nội bộ dẫn chiếu luật đã hết hiệu lực → kéo căn cứ pháp luật kế nhiệm còn hiệu lực
        if cfg.use_chronos and P["intent"] in ("INTERNAL", "MIXED"):
            for r in top_by_fused(6):
                c = dp.chunks[r["i"]]
                if c["source_type"] == "LEGAL":
                    continue
                for d in dp.mentioned_docs(c["chunk_text"]):
                    if not (d.startswith("LAW") and dp.doc_state(d, ref) in (EXPIRED, REF_ONLY)):
                        continue
                    for nd in dp.successors_in_force(d, ref):
                        pool = [j for j in dp.doc_chunks[nd] if dp.chunk_state(j, ref) == VALID]
                        if pool:
                            j = max(pool, key=lambda j: cands.get(j, {}).get("fused", 0.0) + 0.5 * self.coverage(j, P["terms"]))
                            add(j, r["fused"] * 0.9, f"thay {d} mà {r['chunk_id']} dẫn chiếu")

        # (4) Cấu trúc điều luật: các khoản/điểm cùng Điều với căn cứ pháp luật đứng đầu thường đi cùng nhau
        top_legal = None
        if cfg.use_rerank and cfg.use_structure:
            prov = sorted(rows, key=lambda r: -((1 - cfg.w_coverage) * r["fused"] + cfg.w_coverage * r["coverage"]))
            top_legal = next((r for r in prov[:8] if dp.chunks[r["i"]]["source_type"] == "LEGAL"
                              and r["state"] in USABLE and dp.chunks[r["i"]]["article"]), None)
            if top_legal is not None:
                art = dp.chunks[top_legal["i"]]["article"]
                sibs = [j for j in dp.doc_chunks[top_legal["document_id"]] if j != top_legal["i"]
                        and dp.chunks[j]["article"] == art and dp.chunk_state(j, ref) in USABLE]
                for j in sorted(sibs, key=lambda j: -self.coverage(j, P["terms"]))[:5]:
                    add(j, top_legal["fused"] * cfg.sibling_prior, f"cùng {art} với {top_legal['chunk_id']}")

        # (5) Câu hỏi về hiệu lực văn bản: luôn có điều khoản đại diện của văn bản được hỏi và văn bản kế nhiệm/tiền nhiệm
        v_laws = P["law_mentioned"] or P.get("inferred_laws", [])
        if cfg.use_rerank and P["intent"] == "VERSIONING" and v_laws and (P.get("pure_version", True) or any(d.startswith("SIM") for d in P["mentioned"])):
            for d in v_laws:
                a = dp.anchor(d)
                if a is not None:
                    add(a, 0.0, f"điều khoản đại diện của {d}")
                for sd in sorted(dp.succ[d] | dp.pred[d], key=lambda x: dp.start(x) or "9999"):
                    sa = dp.anchor(sd)
                    if sa is not None:
                        add(sa, 0.0, f"điều khoản liên quan của {d}")
        elif cfg.use_rerank and P["intent"] == "VERSIONING" and P["law_mentioned"] and not any(dp.doc_state(d, ref) == VALID for d in P["law_mentioned"]):
            for d in P["law_mentioned"]:
                for nd in dp.successors_in_force(d, ref):
                    sa = dp.anchor(nd)
                    if sa is not None:
                        add(sa, 0.0, f"điều khoản hiệu lực của {nd}")

        intent, scope = P["intent"], P["scope"]
        definition_q = bool(DEFINITION_Q_RE.search(norm(P["question"])))
        secondary_q = bool(SECONDARY_Q_RE.search(norm(P["question"])))
        tl_art = dp.chunks[top_legal["i"]]["article"] if top_legal is not None else None

        def is_sibling(r):
            return (top_legal is not None and r is not top_legal and r["document_id"] == top_legal["document_id"]
                    and dp.chunks[r["i"]]["article"] == tl_art)

        for r in rows:
            c = dp.chunks[r["i"]]
            rel = (1 - cfg.w_coverage) * r["fused"] + cfg.w_coverage * r["coverage"]
            f_state = 1.0
            if cfg.use_chronos:
                if intent == "VERSIONING" and P.get("pure_version", True):
                    f_state = {EXPIRED: 0.9, NOT_YET: 0.8, REF_ONLY: 0.85, INTERNAL_NOT_YET: 0.5}.get(r["state"], 1.0)
                else:
                    f_state = {EXPIRED: 0.3, NOT_YET: 0.3, REF_ONLY: 0.5, INTERNAL_NOT_YET: 0.3}.get(r["state"], 1.0)
            f_scope = f_auth = f_struct = 1.0
            if cfg.use_rerank:
                legal = c["source_type"] == "LEGAL"
                if scope == "INTERNAL":
                    f_scope = 0.9 if legal else 1.1
                elif scope == "LEGAL":
                    f_scope = 1.15 if legal else 0.75
                f_auth = 1 + AUTHORITY.get(c["document_type"], 1) / 100           # phân xử khi điểm gần bằng
                if c["document_type"] in SECONDARY_TYPES and not secondary_q:
                    f_auth *= cfg.secondary_factor + (0.05 if c["document_type"] == "HANDBOOK" else 0.0)
                # chunk điều hướng; bảng thuật ngữ khi không hỏi định nghĩa; hoặc điều khoản tự giới hạn trong tài liệu của nó
                if (NAV_HEAD_RE.search(norm(c["heading"]))
                        or (not definition_q and c["content_type"] == "SOURCE_TABLE_TEXT" and "thuật ngữ" in norm(c["heading"]))
                        or (r["i"] in self.self_scoped and r["document_id"] not in P["mentioned"])):
                    f_auth *= cfg.nav_factor
                elif "tình huống kiểm thử" in norm(c["heading"]):
                    f_auth *= 0.68
                if re.search(r"ngoài ngân sách|vượt ngân sách", norm(P["question"])) and "trong ngân sách" in norm(c["heading"]):
                    f_struct *= 0.8
                in_force_mentioned = [d for d in P["mentioned"] if dp.doc_state(d, ref) in USABLE]
                succ_mentioned = [nd for d in P["mentioned"] if dp.doc_state(d, ref) not in USABLE
                                  for nd in dp.successors_in_force(d, ref)]
                if r["document_id"] in P["mentioned"]:
                    subst = P.get("subst_terms", [])
                    if (intent != "VERSIONING" or P.get("pure_version", True)
                            or (r["state"] in USABLE and (not subst or any(t in self.tokset[r["i"]] for t in subst)
                                                          or r["i"] == dp.anchor(r["document_id"])))):
                        f_struct *= 1.25
                    if P["version_question"] and P.get("pure_version", True) and EFFECT_HEAD_RE.search(norm(c["heading"])):
                        f_struct *= 1.3
                elif not in_force_mentioned and r["document_id"] in succ_mentioned and r["state"] in USABLE:
                    f_struct *= 1.25
                elif r["document_id"] in P.get("named_laws", []):        # "Luật Quản lý thuế hiện hành" → LAW10
                    f_struct *= 1.25
                f_struct *= self.table_factor(r["i"], P["terms"])
                if P["codes"] and self.codes[r["i"]] & P["codes"]:
                    f_struct *= 1 + 0.10 + 0.15 * len(self.codes[r["i"]] & P["codes"]) / len(P["codes"])
                if definition_q and DEFINITION_HEAD_RE.search(norm(c["heading"])):
                    f_struct *= 1.2
                if WHY_Q_RE.search(norm(P["question"])) and REASON_RE.search(norm(c["heading"])):
                    f_struct *= 1.35
                if r["document_id"] in endorsed:
                    f_struct *= 1.2
                    r["endorsed_by"] = endorsed[r["document_id"]]
                if is_sibling(r):
                    f_struct *= 1.2
            r.update(rel=rel, f_state=f_state, f_scope=f_scope, f_auth=f_auth, f_struct=f_struct,
                     final=rel * f_state * f_scope * f_auth * f_struct)
        if top_legal is not None:                        # khoản cùng Điều không vượt căn cứ chính
            for r in rows:
                if is_sibling(r):
                    r["final"] = min(r["final"], top_legal["final"] * 0.98)
        rows.sort(key=lambda r: -r["final"])
        if cfg.use_rerank:
            rows = self._ensure_constraints(P, rows)
        for n, r in enumerate(rows, 1):
            r["rank"] = n
        return rows

    def _ensure_constraints(self, P: dict, rows: list[dict]) -> list[dict]:
        k, ref, dp = self.cfg.top_k, P["applied"], self.dp

        def promote(pred, slot=None):
            nonlocal rows
            target_slot = slot if slot is not None else k - 1
            if any(pred(r) for r in rows[: (target_slot + 1)]):
                return
            cand = next((r for r in rows if pred(r)), None)
            if cand is None:
                return
            rows.remove(cand)
            if target_slot == 0 and rows and cand["final"] <= rows[0]["final"]:
                cand["final"] = rows[0]["final"] + 1e-4
            rows.insert(target_slot, cand)

        sims = [d for d in P["mentioned"] if d.startswith("SIM")]
        v_laws = P["law_mentioned"] or P.get("inferred_laws", [])
        if P["intent"] == "VERSIONING" and v_laws and P.get("pure_version", True):
            # văn bản còn hiệu lực trước (ưu tiên văn bản có điều khoản hiệu lực trực tiếp), rồi văn bản lịch sử/chưa hiệu lực
            in_force = sorted([d for d in v_laws if dp.doc_state(d, ref) == VALID],
                              key=lambda d: not bool(DOC_EFFECT_RE.search(norm(dp.chunks[dp.anchor(d)]["heading"]))))
            picks = [dp.anchor(d) for d in in_force]
            for d in v_laws:
                if d not in in_force:
                    picks.append(dp.anchor(d))
                if dp.end(d):
                    direct = sorted(dp.succ[d], key=lambda x: dp.start(x) or "9999")
                    if direct and direct[0] not in v_laws:
                        picks.append(dp.anchor(direct[0]))
                if not P["law_mentioned"]:
                    for pd_id in sorted(dp.pred[d], key=lambda x: dp.start(x) or "9999", reverse=True):
                        picks.append(dp.anchor(pd_id))
            byi = {r["i"]: r for r in rows}
            picks = [j for j in dict.fromkeys(picks) if j is not None and j in byi][:k]
            chosen = set(picks)
            rows = [byi[j] for j in picks] + [r for r in rows if r["i"] not in chosen]
        elif P["intent"] == "VERSIONING" and sims and P["law_mentioned"]:
            in_force = [d for d in P["law_mentioned"] if dp.doc_state(d, ref) == VALID] or \
                       [nd for d in P["law_mentioned"] for nd in dp.successors_in_force(d, ref)]
            if not in_force:
                for d in sims:
                    best_sim = next((r["i"] for r in rows if r["document_id"] == d
                                     and not NAV_HEAD_RE.search(norm(dp.chunks[r["i"]]["heading"]))), None)
                    if best_sim is not None:
                        for md in dp.mentioned_docs(dp.chunks[best_sim]["chunk_text"]):
                            if md.startswith("LAW") and dp.doc_state(md, ref) == VALID and md not in in_force:
                                in_force.append(md)
            picks = [dp.anchor(d) for d in dict.fromkeys(in_force)]
            for d in sims:
                best_sim = next((r["i"] for r in rows if r["document_id"] == d
                                 and dp.chunks[r["i"]]["article"].startswith("Điều")
                                 and not NAV_HEAD_RE.search(norm(dp.chunks[r["i"]]["heading"]))), None) or \
                           next((r["i"] for r in rows if r["document_id"] == d), None)
                if best_sim is not None:
                    picks.append(best_sim)
            best_int = next((r["i"] for r in rows if r["state"] == INTERNAL
                             and dp.chunks[r["i"]]["document_type"] not in SECONDARY_TYPES
                             and not NAV_HEAD_RE.search(norm(dp.chunks[r["i"]]["heading"]))), None)
            if best_int is not None:
                picks.append(best_int)
            byi = {r["i"]: r for r in rows}
            picks = [j for j in dict.fromkeys(picks) if j is not None and j in byi][:k]
            chosen = set(picks)
            rows = [byi[j] for j in picks] + [r for r in rows if r["i"] not in chosen]
        elif P["intent"] == "VERSIONING" and P["law_mentioned"] and not P.get("pure_version", True):
            in_force = [d for d in P["law_mentioned"] if dp.doc_state(d, ref) == VALID]
            bait = not in_force
            if bait:
                in_force = [nd for d in P["law_mentioned"] for nd in dp.successors_in_force(d, ref)]
            subst = P.get("subst_terms", [])
            for slot, d in enumerate(dict.fromkeys(in_force)):
                if slot < 2:
                    promote(lambda r, d=d: r["document_id"] == d and r["state"] == VALID
                            and (not subst or any(t in self.tokset[r["i"]] for t in subst))
                            and not DOC_EFFECT_RE.search(norm(dp.chunks[r["i"]]["heading"]))
                            and not SCOPE_HEAD_RE.search(norm(dp.chunks[r["i"]]["heading"])), slot=slot)
            if bait:
                for d in dict.fromkeys(in_force):
                    anc = dp.anchor(d)
                    if anc is not None:
                        promote(lambda r, anc=anc: r["i"] == anc)
                    if len(dp.succ[d] | dp.pred[d]) > 0:
                        for pd_id in sorted(dp.pred[d], key=lambda x: dp.start(x) or "9999", reverse=True):
                            if dp.doc_state(pd_id, ref) != VALID and DOC_EFFECT_RE.search(norm(dp.chunks[dp.anchor(pd_id)]["heading"])):
                                promote(lambda r, a=dp.anchor(pd_id): r["i"] == a)
        if P["intent"] == "VERSIONING":
            for d in sims:
                promote(lambda r, d=d: r["document_id"] == d)
        if P["intent"] in ("VERSIONING", "MIXED"):
            promote(lambda r: dp.chunks[r["i"]]["source_type"] == "LEGAL" and r["state"] == VALID)
        if P["intent"] == "MIXED":
            promote(lambda r: r["state"] == INTERNAL)
        # câu hỏi quy trình mà căn cứ pháp luật trong top-k liên quan không kém quy trình nội bộ → kèm điều khoản pháp luật
        # tương ứng với bước quy trình (README mục 2: pháp luật còn hiệu lực trước, quy trình nội bộ sau)
        # README mục 2: sổ tay/FAQ đứng sau nguồn gốc nên hay bị đẩy khỏi top-k dù là đoạn DUY NHẤT mô tả đúng tình huống.
        # Đoạn sổ tay/FAQ khớp câu hỏi nhất (độ liên quan gốc cao nhất trong mọi ứng viên) thay chỗ đoạn ít tự liên quan nhất
        # từ hạng 3 trở đi; đoạn bị thay vẫn được cổng "đủ căn cứ" xét như FAQ dẫn đường (không làm thay đổi quyết định G1–G7)
        if (P["intent"] in ("INTERNAL", "MIXED") or (P["intent"] == "LEGAL" and not P["scope_cue"])) and len(rows) > k:
            best = max(rows, key=lambda r: r["rel"])
            if dp.chunks[best["i"]]["document_type"] in SECONDARY_TYPES and best not in rows[:k]:
                weakest = min(rows[2:k], key=lambda r: self.own_relevance(P, r["i"]))
                j, jb = rows.index(weakest), rows.index(best)
                rows[j], rows[jb] = best, weakest
                P["guides"] = list(P.get("guides", [])) + [weakest["i"]]
        P.pop("counterpart", None)
        if P.get("procedure") and P["intent"] in ("INTERNAL", "MIXED") and self.cfg.use_chronos:
            top = rows[:k]
            proc = next((r for r in top if dp.chunks[r["i"]]["source_type"] != "LEGAL" and r["state"] == INTERNAL
                         and PROCEDURE_HEAD_RE.search(norm(dp.chunks[r["i"]]["heading"]))), None)
            legal = [r for r in top if dp.chunks[r["i"]]["source_type"] == "LEGAL" and r["state"] == VALID]
            if proc is not None and legal and max(self.own_relevance(P, r["i"]) for r in legal) >= \
                    self.cfg.complement_ratio * self.own_relevance(P, proc["i"]):
                cp = self.legal_counterpart(P, proc["i"])
                if cp is not None and any(r["i"] == cp for r in rows):
                    promote(lambda r: r["i"] == cp)
                    P["counterpart"] = (proc["i"], cp)
        return rows

    def legal_counterpart(self, P: dict, i: int) -> int | None:
        """Điều khoản pháp luật còn hiệu lực tại mốc gần nhất (TF-IDF ký tự) với một bước quy trình nội bộ – căn cứ pháp
        luật của bước đó; None nếu chưa đủ tương đồng (cùng ngưỡng điều khoản tương ứng ở văn bản kế nhiệm)."""
        dp = self.dp
        pool = [j for j, c in enumerate(dp.chunks) if c["source_type"] == "LEGAL" and dp.chunk_state(j, P["applied"]) == VALID]
        if not pool:
            return None
        sims = (self.X[pool] @ self.X[i].T).toarray().ravel()
        b = int(np.argmax(sims))
        return pool[b] if sims[b] >= self.cfg.successor_min_cos else None

    # ------------------------------------------------------------------ P5
    def weighted_coverage(self, terms: list[str], idxs: list[int]) -> tuple[float, list[str]]:
        if not terms:
            return 1.0, []
        ev = set().union(*(self.tokset[i] for i in idxs)) if idxs else set()
        w = {t: self.idf.get(t, self.idf_max) for t in terms}
        missing = [t for t in terms if t not in ev]
        return 1 - sum(w[t] for t in missing) / sum(w.values()), missing

    def build_ledger(self, P: dict, ranked: list[dict]) -> list[dict]:
        dp, ref = self.dp, P["applied"]
        out = []
        for r in ranked[: self.cfg.top_k]:
            c = dp.chunks[r["i"]]
            role = ("Căn cứ pháp luật" if r["state"] == VALID else
                    "Quy chế/quy trình nội bộ" if r["state"] == INTERNAL and c["document_type"] not in SECONDARY_TYPES else
                    "Sổ tay/FAQ nội bộ" if r["state"] == INTERNAL else
                    "Lịch sử (hết hiệu lực)" if r["state"] == EXPIRED else
                    "Tham khảo (hợp nhất)" if r["state"] == REF_ONLY else "Chưa có hiệu lực")
            stale = []
            if c["source_type"] != "LEGAL" and self.cfg.use_chronos:
                for d in dp.mentioned_docs(c["chunk_text"]):
                    if d.startswith("LAW") and dp.doc_state(d, ref) in (EXPIRED, REF_ONLY):
                        stale.append(f"{d}→{','.join(dp.successors_in_force(d, ref)) or '?'}")
            succ = dp.successors_in_force(c["document_id"], ref) if r["state"] in (EXPIRED, REF_ONLY) else []
            out.append({"rank": r["rank"], "chunk_id": c["chunk_id"], "document_id": c["document_id"],
                        "citation": dp.label.get(c["chunk_id"], c["citation_label"]), "heading": c["heading"],
                        "state": r["state"], "role": role, "authority": c["document_type"],
                        "score": round(r["final"], 4), "bm25": round(r["bm25"], 2), "tfidf": round(r["tfidf"], 3),
                        "coverage": round(r["coverage"], 2),
                        "terms_hit": ", ".join(t for t in P["terms"] if t in self.tokset[r["i"]]),
                        "successor_in_force": ";".join(succ), "stale_refs": "; ".join(stale), "via": r["via"],
                        "endorsed_by": r.get("endorsed_by", ""), "i": r["i"]})
        return out

    def gate(self, P: dict, ledger: list[dict]) -> tuple[bool, str, list[dict], dict]:
        dp = self.dp
        # bằng chứng xét "đủ căn cứ" = top-k + FAQ/sổ tay đã dẫn đường (thuộc Data Pack dù không được dẫn làm citation)
        idxs = [e["i"] for e in ledger] + [i for i in P.get("guides", []) if i not in {e["i"] for e in ledger}]
        wcov, missing = self.weighted_coverage(P["terms"], idxs)
        ev_bi = set().union(*(content_bigrams(dp.chunks[i]["heading"] + " " + dp.chunks[i]["chunk_text"]) for i in idxs)) if idxs else set()
        qb = P["bigrams"]
        bcov = len(qb & ev_bi) / len(qb) if qb else 1.0
        has_usable = any(e["state"] in USABLE for e in ledger)
        top_bm = max((float(e["bm25"]) if not e["via"] else 1.0 for e in ledger), default=0.0)
        best = max((self.weighted_coverage(P["terms"], [i])[0] for i in idxs), default=0.0)
        named = bool(P["mentioned"])
        # câu hỏi về hiệu lực của văn bản được nêu tên: căn cứ chính là metadata hiệu lực → nới ngưỡng độ phủ
        meta_q = P["version_question"] and (P["law_mentioned"] or P.get("pure_version", False))
        min_cov = 0.2 if meta_q else self.cfg.min_coverage
        min_best = 0.2 if meta_q else self.cfg.min_best_chunk_coverage
        # README mục 6: thiếu thời điểm và văn bản liên quan có nhiều phiên bản → không suy luận an toàn được
        versioned = [e["document_id"] for e in ledger[:3]
                     if e["document_id"].startswith("LAW") and len(dp.chain(e["document_id"])) > 1]
        g6 = not (P["date_unknown"] and versioned)
        cmp = lambda v, t: f"{v:.2f} {'≥' if v >= t else '<'} {t}"
        checks = [
            {"cổng": "G1 Có bằng chứng", "giá trị": f"BM25 đầu = {top_bm:.2f}", "đạt": bool(ledger) and top_bm > 0},
            {"cổng": "G2 Độ phủ từ khóa (trọng số IDF)", "giá trị": cmp(wcov, min_cov)
                + (f" · thiếu: {', '.join(missing[:6])}" if missing else ""), "đạt": wcov >= min_cov},
            {"cổng": "G3 Độ phủ cụm từ", "giá trị": cmp(bcov, self.cfg.min_bigram_coverage)
                + (" (bỏ qua: câu nêu tên văn bản)" if named else ""), "đạt": named or bcov >= self.cfg.min_bigram_coverage},
            {"cổng": "G4 Có căn cứ còn hiệu lực tại mốc", "giá trị": f"{sum(e['state'] in USABLE for e in ledger)} chunk",
             "đạt": has_usable},
            {"cổng": "G5 Một chunk đủ bao quát câu hỏi", "giá trị": cmp(best, min_best), "đạt": best >= min_best},
            {"cổng": "G6 Xác định được thời điểm áp dụng",
             "giá trị": (f"thiếu reference_date, bằng chứng thuộc chuỗi phiên bản ({', '.join(dict.fromkeys(versioned))})"
                         if not g6 else "có mốc thời gian" if not P["date_unknown"] else "thiếu mốc nhưng văn bản không đổi phiên bản"),
             "đạt": g6},
        ]
        passed = all(c["đạt"] for c in checks)
        reason = "" if passed else next(c["cổng"] for c in checks if not c["đạt"])
        return passed, reason, checks, {"wcov": wcov, "bcov": bcov, "best": best, "missing": missing}

    @staticmethod
    def topic_split(P: dict) -> tuple[list[str], list[str]]:
        """Tách từ khóa câu hỏi thành thuật ngữ chủ đề nhiều âm tiết (TERM_COMPOUNDS; "thuế" đứng ngay trước cơ sở tính thuế
        thuộc tên sắc thuế: thuế giá trị gia tăng) và phần còn lại – điều câu hỏi thực sự hỏi về chủ đề đó."""
        q, terms = norm(P["question"]), set(P["terms"])
        topics, inside = [], set()
        for ph in TERM_COMPOUNDS:
            pat = rf"(?<!\w)(?:thuế\s+)?{re.escape(ph)}(?!\w)"
            for hit in re.finditer(pat, q):
                topics.append(hit.group(0))
                inside.update(t for t in hit.group(0).split() if t in terms)
            q = re.sub(pat, " | ", q)
        outside = set(content_terms(q))
        return topics, [t for t in P["terms"] if t not in inside or t in outside]

    def focus_gate(self, P: dict, cited: list[int]) -> dict | None:
        """G7 – khớp chủ đề chưa phải là trả lời: với câu hỏi có thuật ngữ chủ đề nhiều âm tiết, các đoạn được trích dẫn phải
        phủ (trọng số IDF) đủ phần còn lại của câu hỏi. Không áp dụng cho câu hỏi hiệu lực của văn bản được nêu tên (căn cứ
        là metadata phiên bản) và câu trả lời chỉ dựng từ metadata."""
        topics, rest = self.topic_split(P)
        if not topics or not rest or not cited or (P["version_question"] and (P["law_mentioned"] or P.get("pure_version", False))):
            return None
        cov, missing = self.weighted_coverage(rest, cited)
        thr = self.cfg.min_focus_coverage
        return {"cổng": "G7 Căn cứ trả lời đúng điều được hỏi",
                "giá trị": f"ngoài chủ đề “{'; '.join(dict.fromkeys(topics))}”: {cov:.2f} {'≥' if cov >= thr else '<'} {thr}"
                           + (f" · thiếu: {', '.join(missing[:6])}" if missing else ""), "đạt": cov >= thr}

    # ------------------------------------------------------------------ P6
    @staticmethod
    def units(c: dict) -> list[str]:
        raw = c["chunk_text"]
        if c["document_type"] in SECONDARY_TYPES:      # FAQ/sổ tay: bỏ câu hỏi lặp lại và mọi phần từ dòng "Nguồn ưu tiên"
            raw = re.split(r"\n\s*Nguồn (?:tra cứu )?ưu tiên\s*:", raw)[0]
        lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
        if c["document_type"] in SECONDARY_TYPES:
            lines = [re.sub(r"^Trả lời:\s*", "", ln) for ln in lines
                     if not re.match(r"(?:Câu hỏi|Nguồn ưu tiên|Nguồn tra cứu ưu tiên)\s*:", ln)]
        if c["content_type"] == "SOURCE_TABLE_TEXT" and len(lines) > 1:
            head = [h.strip() for h in lines[0].split("|")]
            out = []
            for ln in lines[1:]:
                cells = [x.strip() for x in ln.split("|")]
                if len(cells) == 2 and len(head) == 2:
                    out.append(f"{cells[0]}: {cells[1]}")
                else:
                    out.append(" – ".join(x for x in cells if x))
            return out
        out = []
        for ln in lines:
            if LIST_ITEM_RE.match(ln) or re.match(r"bước \d", norm(ln)):    # một mục của danh sách là một quy định trọn vẹn
                out.append(ln)
                continue
            for s in re.split(r"(?<=[.;!?])\s+(?=[A-ZĐÀ-Ỹ0-9(])", ln):
                s = s.strip()
                if s and out and re.fullmatch(r"\(?(?:\d{1,2}|[a-zđ])[.)]", out[-1]):
                    out[-1] = f"{out[-1]} {s}"          # số thứ tự "1." đi liền nội dung của mục
                elif s:
                    out.append(s)
        return out

    def question_form(self, P: dict) -> dict:
        """Dạng câu hỏi: có/không (kèm vị ngữ được hỏi và phần tình huống đứng trước), con số, vì sao, tình huống/trạng thái,
        liệt kê/quy trình, định nghĩa – quyết định câu nào làm KẾT LUẬN và trích bao nhiêu câu của mỗi căn cứ."""
        if "form" in P:
            return P["form"]
        q = norm(P["question"])
        f = {"quantity": bool(QUANTITY_Q_RE.search(q)) and not LIST_Q_RE.search(q), "why": bool(WHY_Q_RE.search(q)),
             "situation": bool(SITUATION_Q_RE.search(q)),
             "list": bool(LIST_Q_RE.search(q) or HOWTO_Q_RE.search(q)) or bool(P.get("procedure")),
             "definition": bool(DEFINITION_Q_RE.search(q)), "yesno": None}
        m = YESNO_Q_RE.search(q)
        if m and not (P["version_question"] and P["law_mentioned"] and P.get("pure_version", True)):
            skip = STOPWORDS | GENERIC | set(CONVERSATIONAL)
            terms = list(dict.fromkeys(t for t in tokenize(m.group("pred"), bigrams=False) if t not in skip and len(t) > 1))
            if terms:
                f["yesno"] = {"terms": terms, "situation_text": q[:m.start()].strip() or q}
        P["form"] = f
        return f

    def unit_rel(self, u: str, P: dict, w: dict, total: float) -> float:
        """Điểm liên quan của một câu/dòng: độ phủ từ khóa câu hỏi (trọng số IDF) + cụm 2 âm tiết + mã trạng thái được hỏi;
        dòng quá ngắn kém thông tin."""
        tk = set(tokenize(u))
        rel = sum(v for t, v in w.items() if t in tk) / total if total else 0.0
        if P["bigrams"]:
            rel += 0.5 * len(P["bigrams"] & tk) / len(P["bigrams"])
        if P["codes"] & set(CODE_RE.findall(u)):
            rel += 0.3
        return rel * min(1.0, len(u) / 40)

    @staticmethod
    def list_groups(us: list[str]) -> dict[int, list[int]]:
        """Nhóm danh sách trong một đoạn: dòng tiêu đề ("… các trường sau:", hoặc dòng ngắn không dấu câu như "Bộ phận CNTT"
        đứng trước các mục kết thúc bằng ";") → chỉ số các mục của nó (tới mục kết thúc bằng ".")."""
        heads = []
        for n, u in enumerate(us):
            t = u.rstrip()
            if t.endswith(":") or (len(t) < 60 and not re.search(r"[.;!?]$", t) and not LIST_ITEM_RE.match(t)
                                   and n + 1 < len(us) and us[n + 1].rstrip().endswith((";", "."))):
                heads.append(n)
        groups = {}
        for h in heads:
            items, j = [], h + 1
            while j < len(us) and j not in heads and j - h <= 12 and not LIST_ITEM_RE.match(us[j]):
                items.append(j)
                if not us[j].rstrip().endswith(";"):
                    break
                j += 1
            groups[h] = items
        return groups

    def pick_units(self, c: dict, P: dict, max_units: int = 3, full_chars: int = 300, whole: bool = False) -> list[str]:
        """Chỉ trích các câu/dòng trả lời đúng điều được hỏi, không trích cả đoạn. Giữ trọn: đoạn ngắn (≤ full_chars hoặc ≤ 3
        câu – một quy định), quy trình (các bước), câu trả lời/hướng xử lý soạn sẵn của FAQ/sổ tay (bỏ dòng nhắc lại tình
        huống), danh sách đúng chủ đề câu hỏi liệt kê/quy trình. Còn lại (danh sách dài, bảng): câu/dòng có điểm ≥ unit_ratio
        (bảng: table_row_ratio) × câu tốt nhất, tối đa max_units, kèm tiêu đề và trọn nhóm mục chứa câu được chọn."""
        us = self.units(c)
        if not us:
            return []
        table = c["content_type"] == "SOURCE_TABLE_TEXT"
        if c["document_type"] in SECONDARY_TYPES:
            out, restate = [], False          # bỏ dòng nhắc lại tình huống/câu hỏi (kể cả phần sau dấu chấm phẩy của nó)
            for u in us:
                st = u.strip()
                if RESTATE_UNIT_RE.match(st):
                    restate = True
                    continue
                if GUIDE_HEAD_RE.match(st) or SIGNS_HEAD_RE.match(st):
                    restate = False
                if not restate:
                    out.append(u)
            return out or us
        proc = bool(PROCEDURE_HEAD_RE.search(norm(c["heading"]))) or sum(bool(re.match(r"bước \d", norm(u))) for u in us) >= 2
        f = self.question_form(P)
        closed = bool(f["yesno"] or f["quantity"] or f["definition"] or f["why"])   # câu hỏi đóng: chỉ cần đúng câu trả lời
        if whole or proc or len(us) == 1 or (not table and (len(us) <= 3 or len(c["chunk_text"]) <= full_chars
                                                             or (len(us) <= 5 and not closed))):
            return us
        w = {t: self.idf.get(t, self.idf_max) for t in P["terms"]}
        total = sum(w.values()) or 1.0
        head = set(tokenize(c["heading"], bigrams=False))
        if self.question_form(P)["list"] and sum(v for t, v in w.items() if t in head) / total >= 0.2:
            return us[:12]
        groups = self.list_groups(us)
        scored = [0.0 if n in groups and not us[n].rstrip().endswith(":") else self.unit_rel(u, P, w, total)
                  for n, u in enumerate(us)]
        top = max(scored)
        if top <= 0:
            return us[:2]
        ratio = self.cfg.table_row_ratio if table else self.cfg.unit_ratio
        keep = set(sorted((n for n, v in enumerate(scored) if v >= ratio * top), key=lambda n: (-scored[n], n))[:max_units])
        for h, items in groups.items():              # tiêu đề được chọn hoặc có mục được chọn → trọn nhóm
            if h in keep or (keep & set(items) and len(items) <= 6):
                keep |= {h, *items}
            elif keep & set(items):
                keep.add(h)
        return [us[n] for n in sorted(keep)]

    def stance(self, u: str, terms: list[str]) -> str:
        """Lập trường của câu căn cứ đối với động từ chính của vị ngữ được hỏi (terms): COND – "chỉ được … khi …" (trong cùng
        vế câu), NEG – "không được xóa", POS – "được thiết kế" (từ phủ định/cho phép đứng sát trước, trong 4 từ); "" nếu câu
        không nói rõ."""
        t = norm(u)
        found = ""
        for term in terms:
            for m in re.finditer(rf"(?<!\w){re.escape(term)}(?!\w)", t):
                head = CLAUSE_BREAK_RE.split(t[:m.start()])[-1]
                win = " ".join(head.split()[-4:])
                if ONLY_CUE_RE.search(head) and POS_CUE_RE.search(head):
                    return "COND"
                if NEG_CUE_RE.search(win):
                    return "NEG"
                if POS_CUE_RE.search(win):
                    found = found or "POS"
        return found

    def cond_violated(self, u: str, situation_text: str) -> bool:
        """Câu "chỉ được … khi/nếu: A; không B; …" mà tình huống được hỏi rơi đúng vào một điều kiện phủ định (B) → không được.
        So khớp theo âm tiết và cụm 2 âm tiết (trọng số IDF) để "kiểm toán" không bị nhầm với "kế toán"; điều kiện liệt kê
        nhiều phương án ("không liên quan đến hồ sơ đang kiểm tra, tranh chấp hoặc kiểm toán") bị vi phạm khi tình huống
        trùng một phương án."""
        t = norm(u)
        m = re.search(r"\b(?:khi|nếu)\b", t)
        sit = set(content_terms(situation_text)) | content_bigrams(situation_text)
        if not m or not sit:
            return False
        idf = lambda x: self.idf.get(x, self.idf_max)
        share = lambda xs: sum(idf(x) for x in xs & sit) / (sum(idf(x) for x in xs) or 1.0)
        for part in re.split(r";|:\s*", t[m.end():]):
            part = part.strip(" .")
            if not re.match(r"(?:không|chưa)\b", part):
                continue
            if share(set(content_terms(part)) | content_bigrams(part)) >= 0.3:
                return True
            for alt in re.split(r",|\bhoặc\b", part):
                bi = content_bigrams(alt)
                if bi and share(set(content_terms(alt)) | bi) >= 0.6:
                    return True
        return False

    def unit_display(self, c: dict, u: str) -> str:
        """Dòng của bảng tình huống ("Mã | Tình huống | Kết quả mong đợi") → "tình huống → kết quả"; bỏ số thứ tự mục."""
        if c["content_type"] == "SOURCE_TABLE_TEXT":
            head = [h.strip() for h in c["chunk_text"].split("\n")[0].split("|")]
            cells = u.split(" – ")
            if len(head) >= 3 and len(cells) == len(head) and RESULT_HEAD_RE.search(norm(head[-1])):
                if re.fullmatch(r"(?:[a-z]{0,3}\d{1,3}|nhóm [a-z])", norm(cells[0])):
                    cells = cells[1:]
                u = " – ".join(cells[:-1]) + " → " + cells[-1]
        return re.sub(r"^\(?(?:\d{1,2}(?:\.\d{1,2})*|[a-zđ])[.)]\s+", "", u)

    def conclusion(self, P: dict, kept: list[dict]) -> dict:
        """KẾT LUẬN nêu trước câu trả lời – luôn là một câu/dòng NGUYÊN VĂN của căn cứ đã qua kiểm toán (không diễn giải):
        mệnh đề hiệu lực (câu hỏi phiên bản); câu nói rõ được/không được làm điều được hỏi (câu có/không → kèm "Có."/"Không.");
        câu có con số (bao nhiêu, mấy, tối đa); câu nêu lý do (vì sao); dòng tình huống khớp nhất (xử lý thế nào, trạng thái
        nào); còn lại là câu khớp câu hỏi nhất – ưu tiên căn cứ chính do pipeline chọn. Trả về {k, unit, text, polarity}."""
        # câu hỏi phiên bản: mệnh đề hiệu lực (CHRONOS) là kết luận, không lấy câu của tài liệu nội bộ đi kèm
        lead = next((k for k, cl in enumerate(kept) if cl["kind"] == "version"), None)
        if lead is None:
            lead = next((k for k, cl in enumerate(kept) if cl["refs"] and cl.get("primary")), None)
        if lead is None:
            lead = next((k for k, cl in enumerate(kept) if cl["refs"] and cl["kind"] != "chain"), None)
        if lead is None:
            return {}
        if kept[lead]["kind"] == "version":
            return {"k": lead, "unit": None, "text": kept[lead]["text"], "polarity": ""}
        form = self.question_form(P)
        w = {t: self.idf.get(t, self.idf_max) for t in P["terms"]}
        total = sum(w.values()) or 1.0
        yn = form["yesno"]
        pw = {t: self.idf.get(t, self.idf_max) for t in yn["terms"]} if yn else {}
        best = None
        for k, cl in enumerate(kept):
            if cl["kind"] not in ("legal", "internal") or not cl["refs"]:
                continue
            allu = cl.get("all_units") or cl.get("units") or [cl["text"]]
            # mục của danh sách đi kèm dòng tiêu đề của nó ("Bộ phận CNTT: Không được tự ý sửa …") – không đứng một mình
            groups = {h: items for h, items in self.list_groups(allu).items()
                      if not (GUIDE_HEAD_RE.match(allu[h].strip()) or SIGNS_HEAD_RE.match(allu[h].strip()))}
            head_of = {allu[i]: allu[h] for h, items in groups.items() for i in items}
            heads = {allu[h] for h in groups}
            cands, section, guide = [], "", []
            secondary_chunk = self.dp.chunks[self.dp.idx[cl["refs"][0]["chunk_id"]]]["document_type"] in SECONDARY_TYPES
            for u in allu:
                s = u.strip()
                if GUIDE_HEAD_RE.match(s) or SIGNS_HEAD_RE.match(s):
                    section = "guide" if GUIDE_HEAD_RE.match(s) else "signs"
                    continue
                # dòng "Tình huống: …" (kể cả phần sau dấu chấm phẩy) chỉ nhắc lại tình huống, không phải kết luận
                if secondary_chunk and re.match(r"^tình huống\s*:", s, re.I):
                    section = "restate"
                    continue
                if section == "restate":
                    continue
                if RESTATE_UNIT_RE.match(s) or (s.endswith(":") and len(s) < 60) or u in heads:
                    continue
                if u in head_of and form["list"]:      # câu hỏi liệt kê: kết luận là trọn danh sách (tiêu đề + mọi mục)
                    h = next(h for h, items in groups.items() if allu.index(u) in items)
                    cands.append(([allu[h]] + [allu[i] for i in groups[h]], section))
                else:
                    cands.append(([head_of[u], u] if u in head_of else [u], section))
                if section == "guide":
                    guide.append(s)
            if 1 < len(guide) <= 4:                  # mục "Hướng xử lý" của sổ tay/FAQ: trọn mục là một kết luận
                cands.append((guide, "guide"))
            for units, sec in cands:
                s = " ".join(units)
                low = norm(s)
                score = self.unit_rel(s, P, w, total) + {"guide": 0.3, "signs": -0.15}.get(sec, 0.0)
                score += 0.05 if sec == "guide" and len(units) > 1 else 0.0       # hòa điểm → trọn mục "Hướng xử lý"
                # câu hỏi thời hạn ("trong bao nhiêu ngày") → câu nêu thời hạn phải làm ("trong vòng 05 ngày") hơn câu nêu hệ quả
                if form["quantity"] and re.search(r"thời hạn", norm(P["question"])) and \
                        re.search(r"trong vòng|trong thời hạn|chậm nhất|không quá|tối đa", low):
                    score += 0.15
                if form["quantity"] and re.search(r"\d", s):
                    score += 0.3
                if form["why"] and REASON_RE.search(low):
                    score += 0.25
                if form["situation"] and (CODE_RE.search(s) or " – " in s):
                    score += 0.1
                if form["definition"] and re.match(r"^[^:]{2,60}:\s", s):
                    score += 0.15
                pol = ""
                if yn and pw:
                    tk = set(tokenize(s, bigrams=False))
                    pcov = sum(v for t, v in pw.items() if t in tk) / sum(pw.values())
                    # động từ chính của vị ngữ (bỏ trạng từ "tự", "tự ý") phải có trong câu căn cứ – lập trường xét ngay trước nó
                    verb = next((t for t in yn["terms"] if t not in ("tự", "ý", "quyền")), "")     # "có quyền sửa" → sửa
                    if pcov >= 0.3 and verb in tk:
                        st = self.stance(s, [verb])
                        pol = ("Không" if st == "NEG" or (st == "COND" and self.cond_violated(s, yn["situation_text"])) else
                               "Có" if st == "POS" and pcov >= 0.5 else "")
                        score += 0.5 if pol else 0.0
                score *= 1.0 if k == lead else 0.8           # căn cứ chính do pipeline chọn được ưu tiên
                if best is None or score > best[0] + 1e-9:
                    best = (score, k, units, pol)
        if best is None:
            return {"k": lead, "unit": None, "text": kept[lead]["text"], "polarity": ""}
        _, k, units, pol = best
        c = self.dp.chunks[self.dp.idx[kept[k]["refs"][0]["chunk_id"]]]
        shown = [self.unit_display(c, u) for u in units]
        text = " ".join(shown)
        if len(units) == 2 and not units[0].rstrip().endswith((":", ".", ";")):     # tiêu đề nhóm không dấu: "Bộ phận CNTT: …"
            text = f"{shown[0]}: {shown[1]}"
        return {"k": k, "unit": units[-1], "units": units, "text": text, "polarity": pol}

    def affirmed_coverage(self, i: int, terms: list[str]) -> float:
        """Độ phủ chỉ tính phần khẳng định của chunk: bỏ các cụm nằm sau từ phủ định ("không sai mã số thuế, …")."""
        toks = self.affirmed[i]
        return sum(1 for t in terms if t in toks) / len(terms) if terms else 0.0

    def own_relevance(self, P: dict, i: int) -> float:
        """Độ liên quan của chính chunk với câu hỏi (trước mọi cộng điểm cấu trúc/thẩm quyền). Nếu câu hỏi không
        mang phủ định, từ khóa chỉ xuất hiện trong phạm vi phủ định của chunk không được tính là khớp."""
        fused = P.get("fused_all")
        f = float(fused[i]) if fused is not None else 0.0
        cov = self.coverage(i, P["terms"])
        if not NEGATION_Q_RE.search(norm(P["question"])):
            cov = min(cov, self.affirmed_coverage(i, P["terms"]))
            f *= 0.5 + 0.5 * (self.affirmed_coverage(i, P["terms"]) / cov if cov else 1.0)
        tf = self.table_factor(i, P["terms"])
        if tf < 1.0:                                              # bảng tra cứu: xét theo dòng khớp nhất
            f *= tf
            cov = 0.5 * (cov + self.row_coverage(i, P["terms"]))
        return (1 - self.cfg.w_coverage) * f + self.cfg.w_coverage * cov

    def _select_evidence(self, P: dict, usable: list[dict]) -> list[dict]:
        """Căn cứ chính + chỉ những chunk vừa đủ liên quan vừa bổ sung ý mới (kể cả con số được hỏi) – tránh dẫn thừa."""
        dp, cfg = self.dp, self.cfg
        primary = usable[0]
        p_cov = self.coverage(primary["i"], P["terms"])
        # chỉ phân xử lại khi căn cứ đứng đầu khớp câu hỏi nhờ phần PHỦ ĐỊNH ("… nhưng không sai mã số thuế")
        negated_match = bool(p_cov) and not NEGATION_Q_RE.search(norm(P["question"])) \
            and self.affirmed_coverage(primary["i"], P["terms"]) < p_cov
        if cfg.primary_tiebreak and (negated_match or not cfg.tiebreak_negation_only):
            close = [r for r in usable[:3] if r["final"] >= (1 - cfg.primary_tiebreak) * primary["final"]]
            primary = max(close, key=lambda r: self.own_relevance(P, r["i"]))
            usable = [primary] + [r for r in usable if r is not primary]
        pc = dp.chunks[primary["i"]]
        compare = bool(COMPARE_RE.search(norm(P["question"])))
        chosen = [primary]
        nums = {t for t in tokenize(P["question"], bigrams=False) if t.isdigit()}
        keys = set(P["terms"]) | nums
        w = {t: self.idf.get(t, self.idf_max) for t in keys}
        w_total = sum(w.values()) or 1.0
        # con số được hỏi ("5 năm", "80%") phải nằm trong nội dung đoạn, không tính số trong nhãn citation ("khoản 5")
        has = lambda t, i: t in (self.content_tok[i] if t.isdigit() else self.tokset[i])
        covered = {t for t in keys if has(t, primary["i"])}
        base = self.own_relevance(P, primary["i"]) or 1e-9
        want_mixed = P["intent"] == "MIXED"
        for r in usable[1:]:
            if len(chosen) >= cfg.max_answer_chunks:
                break
            c = dp.chunks[r["i"]]
            new = {t for t in keys if has(t, r["i"])} - covered
            gain = sum(w[t] for t in new) / w_total
            own = self.own_relevance(P, r["i"]) / base
            kinds = {dp.chunks[x["i"]]["source_type"] for x in chosen}
            fills_mix = want_mixed and c["source_type"] not in kinds and r["final"] >= 0.5 * primary["final"]
            same_doc = r["document_id"] == primary["document_id"]
            same_article = same_doc and bool(pc["article"]) and c["article"] == pc["article"]
            # khoản kề nhau / cùng Điều là phần tiếp nối của cùng quy định – vẫn phải tự liên quan và thêm ý
            near = same_article if cfg.adjacent_same_article else (abs(r["i"] - primary["i"]) <= 2 or same_article)
            # câu hỏi pháp luật không chèn thêm nội dung nội bộ; câu hỏi nội bộ chỉ nêu tên SIM không tự chèn thêm LAW
            only_sim_named = P["intent"] == "INTERNAL" and bool(P["mentioned"]) and all(d.startswith("SIM") for d in P["mentioned"])
            same_kind = (c["source_type"] != "LEGAL") if only_sim_named else not (
                P["intent"] == "LEGAL" and pc["source_type"] == "LEGAL" and c["source_type"] != "LEGAL")
            adjacent = same_doc and near and own >= cfg.adjacent_ratio and gain >= cfg.adjacent_gain
            in_budget_mismatch = re.search(r"ngoài ngân sách|vượt ngân sách", norm(P["question"])) and "trong ngân sách" in norm(c["heading"])
            complements = not in_budget_mismatch and (same_kind or not cfg.complement_same_kind) and own >= cfg.complement_ratio \
                and gain >= cfg.complement_gain
            # câu hỏi so sánh ("khác … so với …"): nêu đủ hai vế từ cùng văn bản
            counterpart = cfg.compare_counterpart and compare and same_doc and len(chosen) == 1 and own >= 0.6
            if fills_mix or adjacent or complements or counterpart:
                chosen.append(r)
                covered |= new
        if len(P["mentioned"]) >= 2 and not P["version_question"]:
            for d in P["mentioned"]:
                if not any(x["document_id"] == d for x in chosen) and len(chosen) < cfg.max_answer_chunks:
                    cand = next((r for r in usable if r["document_id"] == d), None)
                    if cand is not None:
                        chosen.append(cand)
        return chosen

    def compose(self, P: dict, ranked: list[dict], ledger: list[dict]) -> tuple[list[dict], list[str]]:
        """Trả về các 'claims' {text, kind, refs[{chunk_id,i,doc}]} và cảnh báo. Mọi claim gắn với chunk đã truy xuất."""
        dp, ref, cfg = self.dp, P["applied"], self.cfg
        top = ranked[: cfg.top_k]
        claims, warns = [], []
        sims = [d for d in P["mentioned"] if d.startswith("SIM")]
        bait_version = (bool(P["law_mentioned"]) and not any(dp.doc_state(d, ref) == VALID for d in P["law_mentioned"])
                        and not sims and not P.get("pure_version", True))
        meta_version = (cfg.use_chronos and P["intent"] == "VERSIONING" and P["version_question"]
                        and P.get("pure_version", True))
        # (a) Câu hỏi phiên bản: dẫn dắt bằng metadata hiệu lực (CHRONOS)
        if cfg.use_chronos and P["intent"] == "VERSIONING":
            vc = self._version_claims(P, ranked)
            if meta_version or sims or bait_version:
                claims += [c for c in vc if c["kind"] != "meta"]
                warns += [f"Theo document_metadata.csv: {c['text']}" for c in vc if c["kind"] == "meta"]
            else:
                warns += [f"Theo document_metadata.csv: {c['text']}" for c in vc if c["kind"] in ("version", "meta")]
        # (b) Nội dung: chỉ trích từ chunk còn hiệu lực/nội bộ tại mốc
        usable = [r for r in top if r["state"] in USABLE] if cfg.use_chronos else list(top)
        if usable:
            sec_fallback = None
            if cfg.use_rerank:
                # README mục 2: sổ tay/FAQ đứng sau quy chế/quy trình → nguồn gốc đủ liên quan làm căn cứ chính
                secondary = lambda r: dp.chunks[r["i"]]["document_type"] in SECONDARY_TYPES
                lead = usable[0]["final"]
                usable = sorted(usable, key=lambda r: (secondary(r) or r["final"] < 0.6 * lead, -r["final"]))
                # … nhưng nếu nguồn gốc không bao quát câu hỏi (vd. "khách chưa nhận hóa đơn" chỉ có trong sổ tay/FAQ)
                # thì dùng FAQ/sổ tay làm căn cứ và ghi rõ đó là nguồn thứ cấp
                sec = [r for r in usable if secondary(r)]
                prim = [r for r in usable if not secondary(r)]
                # … trừ khi đã có điều khoản pháp luật còn hiệu lực tự bao quát câu hỏi (pháp luật đứng trước mọi tài liệu nội bộ)
                law_covers = any(dp.chunks[r["i"]]["source_type"] == "LEGAL" and r["state"] == VALID
                                 and not DOC_EFFECT_RE.search(norm(dp.chunks[r["i"]]["heading"]))
                                 and not SCOPE_HEAD_RE.search(norm(dp.chunks[r["i"]]["heading"]))
                                 and self.weighted_coverage(P["terms"], [r["i"]])[0] >= cfg.min_best_chunk_coverage for r in prim)
                if sec and cfg.secondary_fallback and not law_covers:
                    best_sec = max(sec, key=lambda r: self.own_relevance(P, r["i"]))
                    best_prim = max((self.own_relevance(P, r["i"]) for r in prim), default=0.0)
                    # sổ tay/FAQ chỉ nêu các phương án ("HOLD hoặc RETURN_TO_REQUESTER") mà điều khoản quy trình gốc trong top-k
                    # (không tính bảng tình huống kiểm thử) đã định nghĩa → quy trình gốc quyết định, giữ làm căn cứ chính
                    g = re.split(r"(?im)^\s*hướng xử lý[^:\n]{0,40}:", dp.chunks[best_sec["i"]]["chunk_text"])
                    codes = (set(CODE_RE.findall(g[1])) if len(g) > 1 else set()) - {"SIM", "LAW", "FAQ", "CNTT"}
                    defined = len(codes) >= 2 and any(codes <= set(CODE_RE.findall(dp.chunks[r["i"]]["chunk_text"])) for r in prim
                                                  if not norm(dp.chunks[r["i"]]["heading"]).startswith("tình huống"))
                    if not defined and self.own_relevance(P, best_sec["i"]) >= cfg.secondary_fallback * best_prim:
                        usable = [best_sec] + [r for r in usable if r is not best_sec]
                        sec_fallback = best_sec
                # README mục 2 xếp pháp luật trước nội bộ "khi nhiều nguồn cùng liên quan". Câu hỏi không nêu phạm vi chỉ
                # được ưu tiên pháp luật theo mặc định; nếu không đoạn pháp luật nào tự bao quát câu hỏi (ngưỡng G5) mà
                # quy chế/quy trình nội bộ thì có, quy trình nội bộ làm căn cứ chính.
                legal = lambda r: dp.chunks[r["i"]]["source_type"] == "LEGAL"
                covers = lambda r: self.weighted_coverage(P["terms"], [r["i"]])[0] >= cfg.min_best_chunk_coverage
                if (cfg.default_scope_fallback and P["intent"] == "LEGAL" and not P["scope_cue"] and legal(usable[0])
                        and not any(covers(r) for r in usable if legal(r))):
                    own = [r for r in usable if not legal(r) and not secondary(r) and covers(r)]
                    if own:
                        best_own = max(own, key=lambda r: self.own_relevance(P, r["i"]))
                        usable = [best_own] + [r for r in usable if r is not best_own]
                        warns.append("Câu hỏi không nêu phạm vi; văn bản pháp luật trong Data Pack không nêu trực tiếp "
                                     "tình huống này nên nội dung chính lấy từ quy trình nội bộ.")
            chosen = self._select_evidence(P, usable)
            if sec_fallback is not None and sec_fallback in chosen:
                warns.append("Nội dung chính lấy từ sổ tay/FAQ nội bộ (tài liệu thứ cấp) vì quy chế/quy trình "
                             "gốc không nêu trực tiếp tình huống này; cần đối chiếu nguồn gốc khi áp dụng.")
            cp = P.get("counterpart")
            proc = next((r for r in usable if cp and r["i"] == cp[0]), None)
            if proc is not None and not meta_version:
                base = self.own_relevance(P, proc["i"])
                legal = [r for r in usable if dp.chunks[r["i"]]["source_type"] == "LEGAL" and r["state"] == VALID
                         and r["i"] != cp[1] and self.own_relevance(P, r["i"]) >= cfg.complement_ratio * base]
                pair = next((r for r in usable if r["i"] == cp[1]), None)
                chosen = ([proc] + legal[: max(cfg.max_answer_chunks - 2, 0)] + ([pair] if pair is not None else []))
                chosen = chosen[: cfg.max_answer_chunks]
            if meta_version:
                used = {rf["chunk_id"] for cl in claims for rf in cl["refs"]}
                chosen = [r for r in chosen if r["chunk_id"] not in used][: cfg.version_content_chunks]
            elif sims and P["intent"] == "VERSIONING":
                used = {rf["chunk_id"] for cl in claims for rf in cl["refs"]}
                chosen = [r for r in usable if r["state"] == INTERNAL and r["chunk_id"] not in used][:2]
            elif bait_version:
                used = {rf["chunk_id"] for cl in claims for rf in cl["refs"]}
                chosen = [r for r in chosen if r["chunk_id"] not in used
                          and not DOC_EFFECT_RE.search(norm(dp.chunks[r["i"]]["heading"]))][:1]
            elif cfg.use_chronos:
                # README mục 2: tài liệu nội bộ dẫn chiếu luật đã hết hiệu lực → nêu căn cứ pháp luật kế nhiệm còn hiệu lực
                stale: set[str] = set()
                for r in chosen:
                    c = dp.chunks[r["i"]]
                    if c["source_type"] != "LEGAL":
                        for d in dp.mentioned_docs(c["chunk_text"]):
                            if d.startswith("LAW") and dp.doc_state(d, ref) in (EXPIRED, REF_ONLY):
                                stale |= set(dp.successors_in_force(d, ref))
                if stale and not any(dp.chunks[r["i"]]["source_type"] == "LEGAL" for r in chosen):
                    leg = next((r for r in top if r["document_id"] in stale and r["state"] == VALID), None)
                    if leg is not None:
                        chosen.append(leg)
            # README mục 2: sổ tay/FAQ làm căn cứ chính → dẫn kèm quy chế/quy trình (hoặc văn bản pháp luật) mà chính nó ghi là
            # "Nguồn (tra cứu) ưu tiên" nếu đã có trong top-k; nguồn gốc được trình bày trước sổ tay/FAQ
            is_sec = lambda r: dp.chunks[r["i"]]["document_type"] in SECONDARY_TYPES
            if chosen and not meta_version and all(is_sec(r) for r in chosen):
                src = SOURCE_LINE_RE.search(dp.chunks[chosen[0]["i"]]["chunk_text"])
                docs: set[str] = set()
                for d in (dp.mentioned_docs(src.group(1)) if src else []):
                    docs |= set(dp.successors_in_force(d, ref)) if dp.doc_state(d, ref) in (EXPIRED, REF_ONLY) else {d}
                cand = [r for r in usable if r["document_id"] in docs and not is_sec(r)]
                if cand:
                    chosen.append(max(cand, key=lambda r: self.own_relevance(P, r["i"])))
            both = len({dp.chunks[r["i"]]["source_type"] for r in chosen}) > 1
            order = sorted(chosen, key=lambda r: (dp.chunks[r["i"]]["source_type"] != "LEGAL", is_sec(r),
                                                  r["rank"] if both else 0))
            for r in order:
                c = dp.chunks[r["i"]]
                main = r is chosen[0]            # căn cứ chính: được trích nhiều câu hơn
                whole_proc = r["i"] == (P.get("counterpart") or (None,))[0]     # câu hỏi quy trình: trích trọn quy trình
                picked = self.pick_units(c, P, max_units=cfg.primary_units if main else 2,
                                         full_chars=cfg.primary_full_chars, whole=whole_proc)
                claims.append({"text": " ".join(picked),
                               "kind": "legal" if c["source_type"] == "LEGAL" else "internal",
                               "refs": [{"chunk_id": c["chunk_id"], "i": r["i"], "doc": c["document_id"]}],
                               # câu/dòng đã trích (hiển thị), toàn bộ câu của đoạn (để chọn KẾT LUẬN), căn cứ chính
                               "units": picked, "all_units": self.units(c), "primary": main})
        cited = {rf["chunk_id"] for cl in claims for rf in cl["refs"]}
        if any(dp.chunks[dp.idx[c]]["content_type"] == "NORMALIZED_SUMMARY" for c in cited):
            warns.append("Nội dung văn bản pháp luật trích từ bản tóm tắt chuẩn hóa của Data Pack (NORMALIZED_SUMMARY), sát "
                         "nguồn nhưng không phải nguyên văn văn bản.")
        for e in ledger:
            if e["stale_refs"] and e["chunk_id"] in cited:
                warns.append(f"{e['citation']} dẫn chiếu văn bản không còn hiệu lực tại {ref:%d/%m/%Y} ({e['stale_refs']}); "
                             "hệ thống ưu tiên văn bản pháp luật đang có hiệu lực.")
        kinds = {cl["kind"] for cl in claims}
        if "internal" in kinds:
            warns.append("Phần nội bộ trích từ tài liệu GIẢ LẬP của Nova Việt, chỉ có ý nghĩa trong Case Study.")
        if {"legal", "internal"} <= kinds:
            warns.append("Thứ tự ưu tiên: pháp luật đang có hiệu lực → quy chế/quy trình nội bộ → sổ tay/FAQ; "
                         "nếu nội bộ khác pháp luật, áp dụng pháp luật và báo cáo cập nhật tài liệu nội bộ.")
        return claims, warns

    def _version_claims(self, P: dict, ranked: list[dict]) -> list[dict]:
        dp, ref = self.dp, P["applied"]
        top = ranked[: self.cfg.top_k]
        in_top = {r["i"] for r in top}
        sims = [d for d in P["mentioned"] if d.startswith("SIM")]
        pure = P.get("pure_version", True)
        targets = list(P["law_mentioned"]) or list(P.get("inferred_laws", []))
        if not targets:
            for r in top:
                d = r["document_id"]
                if d.startswith("LAW") and len(dp.chain(d)) > 1 and d not in targets:
                    targets.append(d)
            targets = targets[:2]
        if not targets:
            return []
        mk = lambda i, d: {"chunk_id": dp.chunks[i]["chunk_id"], "i": i, "doc": d}

        def refs_for(d: str) -> list[dict]:
            """Chunk chứng minh mệnh đề hiệu lực của d (đã truy xuất): (1) điều khoản hiệu lực/thay thế của chính d;
            (2) nếu d đang hiệu lực: điều khoản phạm vi điều chỉnh của d; (3) điều khoản của văn bản kế nhiệm có nêu
            số hiệu của d; (4) điều khoản đại diện của d; (5) chunk bất kỳ của d trong top-k."""
            own = [r for r in top if r["document_id"] == d]
            eff = [r for r in own if DOC_EFFECT_RE.search(norm(dp.chunks[r["i"]]["heading"]))]
            if eff:
                return [mk(eff[0]["i"], d)]
            if dp.doc_state(d, ref) == VALID:
                sc = [r for r in own if SCOPE_HEAD_RE.search(norm(dp.chunks[r["i"]]["heading"]))]
                if sc:
                    return [mk(sc[0]["i"], d)]
            succ_refs = []
            if d in dp.number:
                short_num = "/".join(norm(dp.number[d]).split("/")[:2])
                for r in top:
                    if r["document_id"] in dp.succ[d] and short_num in norm(dp.chunks[r["i"]]["chunk_text"]):
                        succ_refs = [mk(r["i"], d)]
                        break
            if dp.doc_state(d, ref) == VALID and own:
                return [mk(own[0]["i"], d)] + succ_refs
            if succ_refs:
                return succ_refs
            if not pure and dp.doc_state(d, ref) != VALID:
                return []
            a = dp.anchor(d)
            if a in in_top:
                return [mk(a, d)]
            return [mk(own[0]["i"], d)] if own else []

        chains = list(dict.fromkeys(dp.chain(d) for d in targets))
        in_force = [d for d in targets if dp.doc_state(d, ref) == VALID] or \
                   [d for ch in chains for d in ch if dp.doc_state(d, ref) == VALID]
        if sims:
            for r in top:
                if r["document_id"] in sims:
                    for md in dp.mentioned_docs(dp.chunks[r["i"]]["chunk_text"]):
                        # chỉ văn bản cùng chuỗi phiên bản với văn bản được hỏi (FAQ còn nhắc LAW01–03 không liên quan)
                        if md.startswith("LAW") and dp.doc_state(md, ref) == VALID and md not in in_force \
                                and dp.chain(md) in chains:
                            in_force.append(md)
        day = f"{ref:%d/%m/%Y}"
        q = norm(P["question"])
        prefix = ""
        if re.search(r"hay không|có nên|có còn|còn là|còn hiệu lực|còn được", q) and P["law_mentioned"]:
            prefix = "Có. " if all(dp.doc_state(d, ref) == VALID for d in P["law_mentioned"]) else "Không. "
        claims = []
        if in_force:
            parts, refs = [], []
            for d in in_force:
                extra = f", sửa đổi, bổ sung {dp.short(dp.amends[d])} ({dp.amends[d]})" if d in dp.amends else ""
                parts.append(f"{dp.short(d)} ({d}, hiệu lực từ {fmt_date(dp.start(d))}{extra})")
                refs += refs_for(d)
            claims.append({"text": f"{prefix}Tại ngày {day}, nguồn cần ưu tiên áp dụng là " + "; ".join(parts) + ".",
                           "kind": "version" if refs else "meta", "refs": refs})
            # trích nguyên văn điều khoản hiệu lực đã dẫn của văn bản đang áp dụng (không phát sinh citation mới)
            if pure:
                for rf in refs:
                    c = dp.chunks[rf["i"]]
                    claims.append({"text": f"{dp.label[c['chunk_id']]}: {c['chunk_text']}", "kind": "legal", "refs": [rf]})
        else:
            claims.append({"text": f"{prefix}Tại ngày {day}, không có văn bản nào trong chuỗi liên quan đang có hiệu lực trong Data Pack.",
                           "kind": "version", "refs": []})
        not_yet = []
        for d in targets:
            if d in in_force:
                continue
            st = dp.doc_state(d, ref)
            if st == EXPIRED:
                end = date.fromisoformat(dp.end(d)) + timedelta(days=1) if dp.end(d) else None
                direct = sorted(dp.succ[d], key=lambda x: dp.start(x) or "9999")
                now = dp.successors_in_force(d, ref)
                txt = f"{dp.short(d)} ({d}) đã hết hiệu lực" + (f" từ {end:%d/%m/%Y}" if end else "")
                if direct:
                    txt += f", được thay thế bởi {dp.short(direct[0])} ({direct[0]})"
                later = [x for x in now if not direct or x != direct[0]]
                if later:
                    txt += "; văn bản đang có hiệu lực tại mốc này: " + ", ".join(f"{dp.short(x)} ({x})" for x in later)
                txt += "."
            elif st == REF_ONLY:
                succ = dp.successors_in_force(d, ref)
                txt = (f"{dp.short(d)} ({d}) là văn bản hợp nhất phục vụ tra cứu/versioning, không phải nguồn tạo hiệu lực "
                       f"pháp lý độc lập" + (f"; nên dựa vào {', '.join(f'{dp.short(s)} ({s})' for s in succ)}" if succ else "") + ".")
            else:
                not_yet.append(d)
                continue
            refs = [] if sims else refs_for(d)
            # không có chunk nào đã truy xuất làm căn cứ → chỉ nêu như lưu ý từ metadata, không thành khẳng định
            claims.append({"text": txt, "kind": "version" if refs else "meta", "refs": refs})
        if not_yet:
            groups: dict[str, list[str]] = {}
            for d in not_yet:
                groups.setdefault(dp.start(d), []).append(d)
            txt = "Chưa áp dụng tại mốc này: " + "; ".join(
                f"{', '.join(f'{dp.short(d)} ({d})' for d in ds)} – hiệu lực từ {fmt_date(s)}" for s, ds in groups.items()) + "."
            refs = [] if sims else [x for d in not_yet for x in refs_for(d)]
            claims.append({"text": txt, "kind": "version" if refs else "meta", "refs": refs})
        for ch in chains:
            if len(ch) >= 2 and (len([d for d in targets if d in ch]) >= 2 or re.search(r"chuỗi|quan hệ|versioning", q)):
                seq = " → ".join(
                    f"{d} ({dp.number.get(d, '')}, " + ("hợp nhất – tham khảo" if dp.doc_state(d, ref) == REF_ONLY else
                    f"{fmt_date(dp.start(d))}–{fmt_date(dp.end(d)) or 'nay'}") + ")" for d in ch)
                claims.append({"text": f"Chuỗi phiên bản theo metadata: {seq}.", "kind": "chain", "refs": []})
        return claims

    # ------------------------------------------------------------------ P7
    def audit_citations(self, P: dict, claims: list[dict], ranked: list[dict]) -> tuple[list[dict], list[dict]]:
        dp, ref = self.dp, P["applied"]
        retrieved = {r["chunk_id"] for r in ranked[: self.cfg.top_k]}
        kept, rows = [], []
        for cl in claims:
            original = bool(cl["refs"])
            good = []
            for rf in cl["refs"]:
                cid, i = rf["chunk_id"], rf["i"]
                label = dp.label.get(cid, "")
                c1, c2 = bool(label), cid in retrieved
                if cl["kind"] in ("version", "chain"):
                    owner, d = dp.chunks[i]["document_id"], rf["doc"]
                    c3 = owner == d or owner in dp.succ.get(d, set())
                    note = "metadata hiệu lực của chính văn bản" if owner == d else f"điều khoản hiệu lực của văn bản kế nhiệm {owner}"
                else:
                    raw_text = cl["text"]
                    if label and raw_text.startswith(f"{label}: "):
                        raw_text = raw_text[len(label) + 2:]
                    ctoks, atoks = set(tokenize(dp.chunks[i]["chunk_text"])), set(tokenize(raw_text))
                    ratio = len(atoks & ctoks) / len(atoks) if atoks else 0.0
                    c3, note = ratio >= 0.9, f"trùng {ratio:.0%} token với chunk"
                state = dp.chunk_state(i, ref)
                c4 = state in USABLE or cl["kind"] in ("version", "chain")
                ok = c1 and c2 and c3 and (c4 or not self.cfg.use_chronos)
                rows.append({"citation": label or cid, "chunk_id": cid, "C1 có trong citation_map": c1,
                             "C2 nằm trong top-k đã truy xuất": c2, "C3 hỗ trợ nội dung": c3, "ghi chú C3": note,
                             "C4 phù hợp thời điểm": c4, "trạng thái": STATE_VI.get(state, state),
                             "kết quả": "GIỮ" if ok else "LOẠI"})
                if ok and cid not in {g["chunk_id"] for g in good}:
                    good.append(rf)
            cl["refs"] = good
            # mệnh đề có nguồn nhưng mọi nguồn bị loại → bỏ; mệnh đề chỉ dựa metadata hiệu lực → giữ kèm câu trả lời
            if good or (not original and cl["kind"] in ("version", "chain")):
                kept.append(cl)
        if not any(cl["refs"] for cl in kept):
            kept = []
        return kept, rows

    # ------------------------------------------------------------------ P8
    @staticmethod
    def confidence(feat: dict) -> float:
        z = (-3.2 + 2.6 * feat["wcov"] + 1.0 * feat["bcov"] + 1.4 * feat["top_cov"] + 1.0 * feat["audit_ratio"]
             + 0.5 * feat["usable_primary"] + 1.2 * feat["separation"])
        return 1 / (1 + math.exp(-z))

    # ------------------------------------------------------------------ RUN
    def answer(self, question: str, reference_date=None, question_id: str = "") -> Result:
        t0 = time.perf_counter()
        cfg = self.cfg
        ref = parse_date(reference_date)
        sample = self.dp.match_sample(question or "")
        if not question_id:              # hỏi tự do (giao diện/CLI): câu mẫu giữ mã của BTC, câu ngoài được cấp mã EXT-xxxx
            question_id = sample or (next_external_id() if cfg.write_log else "EXT")
        res = Result(question_id=question_id, question=question, reference_date=ref.isoformat() if ref else "",
                     applied_date=(ref or SNAPSHOT).isoformat(), question_source="sample" if sample else "external",
                     date_source="reference_date" if ref else "default",
                     trace_id=f"T{datetime.now():%Y%m%d-%H%M%S}-{secrets.token_hex(3)}")
        lap = [time.perf_counter()]

        def mark(stage, detail):
            now = time.perf_counter()
            res.trace.append({"bước": stage, "ms": round((now - lap[0]) * 1000, 2), "chi tiết": detail})
            lap[0] = now

        q = (question or "").strip()
        if len(content_terms(q)) == 0:
            res.reason = "Câu hỏi trống hoặc không có nội dung tra cứu."
            mark("P0 Guard", res.reason)
            return self._finish(res, t0, 0.02)
        if cfg.use_rewrite:
            q, res.expansions = self.rewrite_ex(q)    # khôi phục dấu, viết tắt theo ngữ cảnh, từ đồng nghĩa → từ vựng Data Pack
        if q != question.strip():
            mark("P1a Chuẩn hóa câu hỏi", q)
        scope_notes: list[str] = []
        if cfg.use_guard:
            q, notes = self.split_scope(q)
            scope_notes = notes                       # nêu trong câu trả lời: vế không có dữ liệu, chỉ dẫn chèn vào bị bỏ qua
            res.warnings += notes
            if notes:
                mark("P0 Tách câu", " · ".join(notes))
            blocked, why = self.guard(q, raw=question)
            mark("P0 Guard", why or "Qua – không đòi dữ liệu thực tế/ngoài phạm vi")
            if blocked:
                res.reason, res.intent = why, "OUT_OF_SCOPE"
                return self._finish(res, t0, 0.05)
        P = self.plan(q, ref)
        res.applied_date, res.intent, res.scope = P["applied"].isoformat(), P["intent"], P["scope"]
        res.date_source = P["date_source"]
        res.warnings += P["warnings"]
        mark("P1 Query Planning", f"intent={P['intent']} · scope={P['scope']} · mốc={P['applied']:%d/%m/%Y} · "
             f"văn bản nhắc tới={','.join(P['mentioned']) or '—'} · từ khóa={', '.join(P['terms'][:10])}")
        cands = self.retrieve(P)
        mark("P2 Hybrid Retrieval", f"{len(cands)} ứng viên (BM25 ⊕ TF-IDF ký tự, pool={cfg.pool})")
        ranked = self.resolve_and_rerank(P, cands)
        n_exp = sum(r["state"] in (EXPIRED, NOT_YET, REF_ONLY) for r in ranked[:20])
        n_sub = sum(r["via"].startswith(("kế nhiệm", "thay ")) for r in ranked)
        mark("P3 Version Resolution (CHRONOS)", f"{n_exp}/20 ứng viên đầu không còn hiệu lực tại mốc; "
             f"{n_sub} điều khoản kế nhiệm/còn hiệu lực được kéo vào" if cfg.use_chronos else "Tắt")
        mark("P4 Authority-aware Rerank", " > ".join(r["chunk_id"] for r in ranked[: cfg.top_k]))
        ledger = self.build_ledger(P, ranked)
        res.ledger = [{k: v for k, v in e.items() if k != "i"} for e in ledger]
        res.retrieved = [{"chunk_id": e["chunk_id"], "document_id": e["document_id"], "citation": e["citation"],
                          "state": e["state"], "score": e["score"]} for e in ledger]
        passed, why, gate_rows, gfeat = self.gate(P, ledger)
        res.gate = gate_rows
        mark("P5 Evidence Ledger & Gate", "ĐẠT" if passed else f"KHÔNG ĐẠT – {why}")

        def gate_abstain(reason: str) -> Result:
            res.reason = reason
            res.features = {"wcov": round(gfeat["wcov"], 3), "bcov": round(gfeat["bcov"], 3)}
            conf = 0.5 * self.confidence({"wcov": gfeat["wcov"], "bcov": gfeat["bcov"], "top_cov": 0, "audit_ratio": 0,
                                          "usable_primary": 0, "separation": 0})
            return self._finish(res, t0, conf)

        if cfg.use_gate and not passed:
            detail = next((g["giá trị"] for g in gate_rows if g["cổng"] == why), "")
            hint = (" Hãy cung cấp ngày tham chiếu (reference_date) để xác định đúng phiên bản văn bản."
                    if why.startswith("G6") else "")
            return gate_abstain(f"Không qua cổng đủ căn cứ: {why} ({detail}).{hint}")
        claims, warns = self.compose(P, ranked, ledger)
        n_src = len({rf["chunk_id"] for cl in claims for rf in cl["refs"]})
        mark("P6 Grounded Composition", f"{len(claims)} ý, trích xuất/dẫn từ {n_src} chunk")
        if cfg.use_audit:
            kept, audit_rows = self.audit_citations(P, claims, ranked)
        else:
            kept, audit_rows = [cl for cl in claims if cl["refs"] or cl["kind"] in ("version", "chain")], []
        res.audit = audit_rows
        g7 = self.focus_gate(P, [self.dp.idx[rf["chunk_id"]] for cl in kept for rf in cl["refs"]]) if cfg.use_gate else None
        if g7:
            res.gate.append(g7)
        mark("P7 Citation Audit", f"giữ {sum(r['kết quả'] == 'GIỮ' for r in audit_rows)}/{len(audit_rows)} citation"
             + (f" · {g7['cổng']}: {'ĐẠT' if g7['đạt'] else 'KHÔNG ĐẠT'}" if g7 else ""))
        if not kept:
            res.reason = "Không còn citation hợp lệ sau kiểm toán."
            return self._finish(res, t0, 0.15)
        if g7 and not g7["đạt"]:
            return gate_abstain(f"Không qua cổng đủ căn cứ: {g7['cổng']} ({g7['giá trị']}).")
        finals = [r["final"] for r in ranked[:10]]
        top_f = max(finals) if finals else 0.0
        sep = min(1.0, max(0.0, (top_f - float(np.mean(finals))) / top_f)) if top_f > 0 else 0.0
        feat = {"wcov": gfeat["wcov"], "bcov": gfeat["bcov"], "top_cov": gfeat["best"],
                "audit_ratio": (sum(r["kết quả"] == "GIỮ" for r in audit_rows) / len(audit_rows)) if audit_rows else 1.0,
                "usable_primary": float(ledger[0]["state"] in USABLE), "separation": sep}
        conf = self.confidence(feat)
        res.features = {k: round(float(v), 3) for k, v in feat.items()}
        mark("P8 Calibrated Confidence", f"{conf:.2f} (ngưỡng ABSTAIN {cfg.min_confidence}, rà soát {cfg.review_confidence})")
        if conf < cfg.min_confidence and cfg.use_gate:
            res.reason = f"Độ tin cậy {conf:.2f} thấp hơn ngưỡng {cfg.min_confidence}."
            return self._finish(res, t0, conf)
        # ---- soạn văn bản cuối: KẾT LUẬN trước, rồi phần căn cứ; mỗi ý gắn [n] của các chunk đã qua kiểm toán ----
        order: list[str] = []
        for cl in kept:
            for rf in cl["refs"]:
                if rf["chunk_id"] not in order:
                    order.append(rf["chunk_id"])
        num = {cid: n for n, cid in enumerate(order, 1)}
        tags = lambda cl: "".join(f"[{num[rf['chunk_id']]}]" for rf in cl["refs"])
        concl = self.conclusion(P, kept)
        cunits = set(concl.get("units") or [])
        if cunits:                                    # câu kết luận chưa nằm trong phần đã trích → thêm đúng vị trí trong đoạn
            cl = kept[concl["k"]]
            if not cunits <= set(cl["units"]):
                pos = {u: n for n, u in enumerate(cl.get("all_units") or cl["units"])}
                cl["units"] = sorted(set(cl["units"]) | cunits, key=lambda u: pos.get(u, 0))
                cl["text"] = " ".join(cl["units"])
        lines = []
        if concl:
            pol = f"{concl['polarity']}. " if concl["polarity"] else ""
            lines.append(f"Kết luận: {pol}{concl['text']} {tags(kept[concl['k']])}".rstrip())
        mixed = {cl["kind"] for cl in kept} >= {"legal", "internal"}
        section = None
        for k, cl in enumerate(kept):
            units = cl.get("units") or [cl["text"]]
            if concl and k == concl["k"]:              # câu đã nêu ở KẾT LUẬN không lặp lại
                units = [] if not cunits else [u for u in units if u not in cunits]
            # tiêu đề mục ("Hướng xử lý nội bộ:") không còn nội dung đi kèm (đã nêu ở KẾT LUẬN) → không trích tiêu đề trơ
            is_head = lambda u: bool(GUIDE_HEAD_RE.match(u.strip()) or SIGNS_HEAD_RE.match(u.strip()))
            units = [u for n, u in enumerate(units) if not (is_head(u) and (n == len(units) - 1 or is_head(units[n + 1])))]
            if not units:
                continue
            if mixed and cl["kind"] in ("legal", "internal") and section != cl["kind"]:
                section = cl["kind"]
                lines.append("Căn cứ pháp luật:" if section == "legal" else "Quy trình nội bộ (Nova Việt – giả lập):")
            bullet = "- " if mixed and cl["kind"] in ("legal", "internal") else ""
            if len(cl.get("units") or []) < len(cl.get("all_units") or []):       # trích một phần → bỏ số thứ tự mục
                units = [re.sub(r"^\(?(?:\d{1,2}(?:\.\d{1,2})*|[a-zđ])[.)]\s+", "", u) for u in units]
            tag = tags(cl)
            lines.append(f"{bullet}{' '.join(units)}{' ' + tag if tag else ''}")
        res.cited_chunks = order
        res.citations = [self.dp.label[cid] for cid in order]
        res.claims = [{"text": cl["text"], "kind": cl["kind"], "refs": [num[rf["chunk_id"]] for rf in cl["refs"]],
                       "units": cl.get("units") or [cl["text"]]} for cl in kept]
        res.key_point = ({"text": concl["text"], "polarity": concl["polarity"],
                          "refs": [num[rf["chunk_id"]] for rf in kept[concl["k"]]["refs"]],
                          "items": list(concl.get("units") or [concl["text"]])} if concl else {})
        res.warnings += warns
        res.needs_review = conf < cfg.review_confidence
        if res.needs_review:
            res.warnings.append("Độ tin cậy trung bình – nên chuyển chuyên viên kế toán rà soát (human-in-the-loop).")
        src = "; ".join(f"[{n}] {self.dp.label[cid]}" for cid, n in num.items())
        res.answer = ("\n".join(lines) + f"\nNguồn: {src}." + "".join(f"\nLưu ý: {w}" for w in scope_notes + warns)
                      + f"\n{DISCLAIMER}")
        res.decision = "ANSWER"
        res.reason = "Đủ căn cứ, citation đã kiểm toán."
        return self._finish(res, t0, conf)

    def _finish(self, res: Result, t0: float, conf: float) -> Result:
        res.confidence = float(min(max(conf, 0.0), 1.0))
        if res.decision == "ABSTAIN":
            # câu chuẩn README mục 5–6, nêu rõ điều không xác định được; lý do chi tiết lưu ở res.reason + audit log
            res.answer = abstain_text(res.question, res.intent == "OUT_OF_SCOPE" and "dữ liệu thực tế" in res.reason)
            res.citations, res.cited_chunks, res.claims, res.key_point = [], [], [], {}
        res.latency_ms = max(1, int(round((time.perf_counter() - t0) * 1000)))
        if self.cfg.write_log:
            write_audit_log(res, self.cfg)
        return res


# =============================================================================
# 6. AUDIT LOG
# =============================================================================
_FINGERPRINT = {"value": ""}
RUN = {"id": ""}                     # mã lần chạy (batch/eval) – ghi vào audit log để đối chiếu số liệu với từng câu
_PRUNED = {"done": False}


def prune_logs(days: int):
    """Giới hạn lưu trữ (proposal mục 8.3): bỏ các dòng audit log/phản hồi cũ hơn `days` ngày – một lần mỗi tiến trình."""
    if _PRUNED["done"] or days <= 0:
        return
    _PRUNED["done"] = True
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    for path in (AUDIT_LOG, FEEDBACK_LOG):
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        keep = [ln for ln in lines if (m := re.search(r'"timestamp": "([^"]+)"', ln)) is None or m.group(1) >= cutoff]
        if len(keep) < len(lines):
            path.write_text("".join(ln + "\n" for ln in keep), encoding="utf-8")


def write_audit_log(res: Result, cfg: Config):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    prune_logs(cfg.log_retention_days)
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"), "trace_id": res.trace_id, "run_id": RUN["id"],
        "system": f"{APP_VERSION} / {cfg.name}",
        "corpus_fingerprint": _FINGERPRINT["value"][:12], "question_id": res.question_id,
        "question_source": res.question_source,
        "question": mask_pii(res.question), "reference_date": res.reference_date, "applied_date": res.applied_date,
        "intent": res.intent, "decision": res.decision, "confidence": round(res.confidence, 3),
        "latency_ms": res.latency_ms, "reason": res.reason, "citations": res.citations,
        "retrieved": [r["chunk_id"] for r in res.retrieved], "gate": res.gate, "audit": res.audit,
        "features": res.features, "warnings": res.warnings, "needs_review": res.needs_review,
        "trace": [{"bước": t["bước"], "ms": t["ms"]} for t in res.trace],
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_jsonl(path: Path, last: int = 200) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines()[-last:]:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def next_external_id() -> str:
    """Mã cho câu hỏi ngoài bộ mẫu của BTC: EXT-0001, EXT-0002… (đánh số tiếp theo audit log)."""
    n = 0
    if AUDIT_LOG.exists():
        n = max((int(x) for x in re.findall(r'"question_id": "EXT-(\d+)"', AUDIT_LOG.read_text(encoding="utf-8"))),
                default=0)
    return f"EXT-{n + 1:04d}"


# ---- lịch sử tra cứu: mỗi phiên (một lần "Tra cứu mới") gồm nhiều câu hỏi, lưu logs/sessions/<id>.json ----
def new_session() -> dict:
    now = datetime.now()
    return {"id": f"S{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}", "created": now.isoformat(timespec="seconds"),
            "title": "", "turns": []}


def result_from_dict(d: dict) -> Result:
    names = {f.name for f in fields(Result)}
    return Result(**{k: v for k, v in d.items() if k in names})


def history_save(sess: dict) -> None:
    """Ghi phiên tra cứu (câu hỏi đã che thông tin cá nhân như audit log)."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    turns = []
    for t in sess["turns"]:
        r = asdict(t["res"])
        r["question"] = mask_pii(r["question"])
        turns.append({"time": t["time"], "feedback": t.get("feedback", ""), "date_mode": t.get("date_mode", ""), "result": r})
    data = {k: v for k, v in sess.items() if k != "turns"} | {"updated": datetime.now().isoformat(timespec="seconds"),
                                                               "turns": turns}
    (HISTORY_DIR / f"{sess['id']}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def history_load(sid: str) -> dict | None:
    p = HISTORY_DIR / f"{sid}.json"
    if not re.fullmatch(r"S[\w-]+", sid) or not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    data["turns"] = [{"time": t["time"], "feedback": t.get("feedback", ""), "date_mode": t.get("date_mode", ""),
                      "res": result_from_dict(t["result"])} for t in data.get("turns", [])]
    return data


_HISTORY_CACHE: dict[str, tuple[float, dict]] = {}


@lru_cache(maxsize=8192)
def _fold_char(ch: str) -> str:
    return (fold(ch) or ch)[:1]


@lru_cache(maxsize=8192)
def _lower_char(ch: str) -> str:
    return (ch.lower() or ch)[:1]


def fold_aligned(text: str) -> str:
    """Như fold() nhưng giữ nguyên độ dài (ký tự thứ i ↔ ký tự thứ i) để tô sáng đúng chỗ khớp trong văn bản gốc."""
    return "".join(map(_fold_char, text))


def norm_aligned(text: str) -> str:
    """Như norm() (chữ thường, thống nhất vị trí dấu thanh hoà/hòa) nhưng giữ nguyên độ dài."""
    return _OLD_TONE_RE.sub(lambda m: _OLD_TONE[m.group(1)], "".join(map(_lower_char, text)))


def search_field(text: str) -> tuple[str, str, str]:
    """(văn bản gốc, bản bỏ dấu, bản chữ thường) cùng độ dài – để tìm kiếm rồi tô sáng đúng vị trí."""
    t = re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(text or ""))).strip()
    return t, fold_aligned(t), norm_aligned(t)


def _history_index() -> list[dict]:
    """Tóm tắt + nội dung tìm kiếm (tên phiên, câu hỏi, câu trả lời) của mọi phiên đã lưu; chỉ đọc lại file đã thay đổi."""
    out = []
    for p in HISTORY_DIR.glob("S*.json"):
        mtime = p.stat().st_mtime
        hit = _HISTORY_CACHE.get(p.name)
        if hit is None or hit[0] != mtime:
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            turns = d.get("turns", [])
            title = search_field(d.get("title") or "Phiên tra cứu")
            texts = [(i, kind, search_field(t["result"].get(key))) for i, t in enumerate(turns)
                     for kind, key in (("Hỏi", "question"), ("Đáp", "answer"))]
            hit = (mtime, {"id": d["id"], "created": d.get("created", ""), "updated": d.get("updated", d.get("created", "")),
                           "title": title[0], "n": len(turns), "pinned": bool(d.get("pinned")),
                           "n_abstain": sum(t["result"].get("decision") == "ABSTAIN" for t in turns),
                           "title_x": title, "texts": [x for x in texts if x[2][0]]})
            _HISTORY_CACHE[p.name] = hit
        out.append(hit[1])
    return out


def history_list(limit: int = 60) -> list[dict]:
    """Các phiên cho cột LỊCH SỬ TRA CỨU: phiên được ghim trước, còn lại theo lần hỏi gần nhất."""
    return sorted(_history_index(), key=lambda h: (h["pinned"], h["updated"]), reverse=True)[:limit]


# từ viết tắt trong REWRITES (MST, HĐĐT, GTGT…): ô tìm kiếm lịch sử hiểu cả dạng viết tắt lẫn dạng đầy đủ
SEARCH_ABBR = {fold(a): fold(r) for a, r in ABBREVIATIONS}


def search_patterns(query: str) -> list[list[tuple[re.Pattern, int]]]:
    """Các cách hiểu truy vấn: nguyên văn và (nếu có) thay từ viết tắt bằng dạng đầy đủ. Mỗi từ khoá → (regex, 1 = so trên
    bản bỏ dấu khi người dùng gõ không dấu | 2 = so có dấu khi người dùng gõ có dấu). Từ khoá khớp trọn âm tiết, riêng từ
    cuối khớp phần đầu vì người dùng có thể đang gõ dở."""
    words = list(dict.fromkeys(norm_aligned(re.sub(r"\s+", " ", query)).split()))
    variants = [words] if words else []
    alt = " ".join(SEARCH_ABBR.get(fold(w), w) for w in words).split()
    if words and alt != words:
        variants.append(alt)
    return [[(re.compile(rf"(?<!\w){re.escape(w)}" + ("" if i == len(v) - 1 else r"(?!\w)")), 1 if fold(w) == w else 2)
             for i, w in enumerate(v)] for v in variants]


def history_search(query: str, limit: int = 30) -> tuple[list[tuple[re.Pattern, int]], list[dict]]:
    """Tìm phiên theo tên phiên, câu hỏi và câu trả lời (mọi từ khoá phải có trong phiên). Mỗi kết quả kèm "hit" =
    (lượt, "Hỏi"/"Đáp", trường) khớp nhiều từ khoá nhất để trích đoạn – không kèm khi tên phiên đã chứa đủ từ khoá. Khớp ở
    tên phiên/câu hỏi xếp trước khớp ở câu trả lời, rồi đến phiên mới hơn. Trả về cả các mẫu đã khớp để tô sáng."""
    variants = search_patterns(query)
    found, used = [], {}
    for h in _history_index() if variants else []:
        fields_ = [h["title_x"], *(x[2] for x in h["texts"])]
        ok = [v for v in variants if all(any(rx.search(f[k]) for f in fields_) for rx, k in v)]
        if not ok:
            continue
        pats = [p for v in ok for p in v]
        used.update(((rx.pattern, k), (rx, k)) for rx, k in pats)

        def count(f, pats=pats):
            return sum(bool(rx.search(f[k])) for rx, k in pats)

        hit = max(h["texts"], key=lambda x: (count(x[2]), x[1] == "Hỏi", -x[0]), default=None)
        in_title = any(all(rx.search(h["title_x"][k]) for rx, k in v) for v in ok)
        if in_title or (hit and not count(hit[2])):
            hit = None
        strong = in_title or bool(hit and hit[1] == "Hỏi" and any(all(rx.search(hit[2][k]) for rx, k in v) for v in ok))
        found.append(h | {"hit": hit, "strong": strong})
    found.sort(key=lambda h: (h["strong"], h["updated"]), reverse=True)
    return list(used.values()), found[:limit]


_MD_SPECIAL_RE = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>$~:])")


def md_escape(text: str) -> str:
    """Thoát ký tự Markdown để văn bản người dùng hiện đúng nguyên văn trong nhãn nút."""
    return _MD_SPECIAL_RE.sub(r"\\\1", text)


def md_highlight(field_: tuple[str, str, str], pats: list[tuple[re.Pattern, int]], width: int | None = None) -> str:
    """Markdown của trường (hoặc đoạn ~width ký tự quanh chỗ khớp đầu tiên) với các từ khoá được tô nền vàng."""
    text = field_[0]
    start, end = 0, len(text)
    if width and len(text) > width:
        pos = min((m.start() for rx, k in pats if (m := rx.search(field_[k]))), default=0)
        start = max(0, pos - width // 3)
        if start:
            sp = text.find(" ", start, pos)
            start = sp + 1 if sp >= 0 else start
        end = min(len(text), start + width)
        if end < len(text):
            sp = text.rfind(" ", pos + 1, end)
            end = sp if sp > 0 else end
    spans: list[list[int]] = []
    for a, b in sorted(m.span() for rx, k in pats for m in rx.finditer(field_[k], start, end) if m.end() > m.start()):
        if spans and a <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], b)
        else:
            spans.append([a, b])
    out, cur = [], start
    for a, b in spans:
        out += [md_escape(text[cur:a]), f':color[{md_escape(text[a:b])}]{{background="#F2B544"}}']
        cur = b
    out.append(md_escape(text[cur:end]))
    return ("…" if start else "") + "".join(out) + ("…" if end < len(text) else "")


def history_update(sid: str, **changes) -> None:
    """Đổi tên / ghim một phiên đã lưu (giữ nguyên thời điểm cập nhật để không đổi thứ tự lịch sử)."""
    p = HISTORY_DIR / f"{sid}.json"
    if re.fullmatch(r"S[\w-]+", sid) and p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
        data.update(changes)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def history_delete(sid: str) -> None:
    p = HISTORY_DIR / f"{sid}.json"
    if re.fullmatch(r"S[\w-]+", sid) and p.exists():
        p.unlink()


# =============================================================================
# 7. BATCH / SUBMISSION / ĐÁNH GIÁ 7 KPI
# =============================================================================
def run_batch(pa: PolicyAssist, questions: pd.DataFrame, progress=None) -> tuple[pd.DataFrame, list[Result]]:
    results = []
    for n, r in enumerate(questions.itertuples(index=False), 1):
        results.append(pa.answer(r.question_text, getattr(r, "reference_date", ""), r.question_id))
        if progress:
            progress(n, len(questions), r.question_id)
    sub = pd.DataFrame([x.submission_row() for x in results], columns=SUBMISSION_COLUMNS)
    return sub, results


SUBMISSION_QUOTED = ("answer", "retrieved_document_ids", "retrieved_chunk_ids", "citations")   # như ví dụ README mục 5


def _submission_cell(col: str, v) -> str:
    """Giá trị một ô của submission (một dòng, không ký tự điều khiển)."""
    s = "" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v)
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", s)).strip()


def submission_bytes(sub: pd.DataFrame) -> bytes:
    """Nội dung submission.csv ĐÚNG submission_output_template.csv – file dành cho máy chấm của BTC:
    UTF-8 có BOM, phân cách bằng dấu phẩy, đúng 8 cột theo thứ tự, MỖI CÂU HỎI MỘT DÒNG (CRLF như template),
    số thập phân dùng dấu chấm (0.93), danh sách phân cách ';'. Giống hệt ví dụ README mục 5:
      Q001,"Chứng từ kế toán là ...","LAW01","LAW01_C001","LAW01 – Điều 3",0.93,FALSE,842
      Q077,"Không đủ căn cứ trong Data Pack để xác định thông tin này.",,,,0.18,TRUE,615
    – 4 cột văn bản/danh sách đặt trong ngoặc kép (dấu phẩy trong câu trả lời vì thế không tách cột), số và TRUE/FALSE
    không có ngoặc kép, ô trống để trống; ngoặc kép bên trong nội dung viết thành "" (chuẩn CSV RFC 4180)."""
    def cell(col: str, v) -> str:
        s = _submission_cell(col, v)
        quote = bool(s) and (col in SUBMISSION_QUOTED or bool(re.search(r'[",]', s)))
        return '"' + s.replace('"', '""') + '"' if quote else s
    lines = [",".join(SUBMISSION_COLUMNS)]
    lines += [",".join(cell(c, v) for c, v in zip(SUBMISSION_COLUMNS, row))
              for row in sub[SUBMISSION_COLUMNS].itertuples(index=False)]
    return ("﻿" + "\r\n".join(lines) + "\r\n").encode("utf-8")


def submission_xlsx_bytes(sub: pd.DataFrame) -> bytes:
    """Bản Excel (.xlsx) của submission để MỞ BẰNG EXCEL: đúng 8 cột, đúng tên cột như template, mọi ô giữ nguyên giá trị.
    Cần bản này vì Excel đọc CSV theo thiết lập vùng của Windows: máy đặt định dạng Việt Nam (dấu thập phân ',') thì Excel
    tách cột CSV bằng ';' – trùng dấu ';' trong retrieved_chunk_ids nên các cột bị lệch, dù file CSV đúng chuẩn BTC.
    Viết trực tiếp định dạng Office Open XML tối thiểu (không cần thư viện ngoài)."""
    import io
    import zipfile
    from xml.sax.saxutils import escape

    def ref(c: int, r: int) -> str:
        return f"{chr(65 + c)}{r}"                        # 8 cột: A–H

    def text(c: int, r: int, v: str, style: int) -> str:
        return f'<c r="{ref(c, r)}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(v)}</t></is></c>'

    rows = ['<row r="1">' + "".join(text(c, 1, h, 1) for c, h in enumerate(SUBMISSION_COLUMNS)) + "</row>"]
    for r, rec in enumerate(sub[SUBMISSION_COLUMNS].itertuples(index=False), start=2):
        cells = []
        for c, (col, v) in enumerate(zip(SUBMISSION_COLUMNS, rec)):
            s = _submission_cell(col, v)
            num = None
            try:
                num = float(s) if col == "confidence" and s else int(float(s)) if col == "latency_ms" and s else None
            except ValueError:
                num = None
            if num is not None:                           # số thật trong Excel (hiển thị theo dấu thập phân của máy)
                cells.append(f'<c r="{ref(c, r)}" s="{2 if col == "confidence" else 3}"><v>{num!r}</v></c>')
            else:                                         # văn bản giữ nguyên (TRUE/FALSE, mã chunk, câu trả lời…)
                cells.append(text(c, r, s, 0))
        rows.append(f'<row r="{r}">' + "".join(cells) + "</row>")
    last = ref(len(SUBMISSION_COLUMNS) - 1, len(sub) + 1)
    widths = {"question_id": 12, "answer": 100, "retrieved_document_ids": 24, "retrieved_chunk_ids": 46, "citations": 44,
              "confidence": 12, "abstain": 9, "latency_ms": 11}
    cols = "".join(f'<col min="{c + 1}" max="{c + 1}" width="{widths[n]}" customWidth="1"/>'
                   for c, n in enumerate(SUBMISSION_COLUMNS))
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    ns_r = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    parts = {
        "[Content_Types].xml": head + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>",
        "_rels/.rels": head + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": head + f'<workbook {ns} {ns_r}><sheets><sheet name="submission" sheetId="1" r:id="rId1"/></sheets>'
        f'<definedNames><definedName name="_xlnm._FilterDatabase" localSheetId="0" hidden="1">submission!$A$1:${last[0]}${last[1:]}'
        "</definedName></definedNames></workbook>",
        "xl/_rels/workbook.xml.rels": head + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{rel}/worksheet" Target="worksheets/sheet1.xml"/>'
        f'<Relationship Id="rId2" Type="{rel}/styles" Target="styles.xml"/></Relationships>',
        "xl/styles.xml": head + f'<styleSheet {ns}><numFmts count="1"><numFmt numFmtId="164" formatCode="0.000"/></numFmts>'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>'
        '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1E3A6E"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="4">'
        '<xf numFmtId="49" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>'
        '<xf numFmtId="49" fontId="1" fillId="2" borderId="0" xfId="0" applyNumberFormat="1" applyFont="1" applyFill="1"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>'
        '<xf numFmtId="1" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="top"/></xf>'
        '</cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        "xl/worksheets/sheet1.xml": head + f'<worksheet {ns}><dimension ref="A1:{last}"/><sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'<cols>{cols}</cols><sheetData>{"".join(rows)}</sheetData><autoFilter ref="A1:{last}"/></worksheet>',
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, xml in parts.items():
            z.writestr(zipfile.ZipInfo(name, date_time=(2026, 10, 17, 0, 0, 0)), xml.encode("utf-8"), zipfile.ZIP_DEFLATED)
    return buf.getvalue()


_QUOTED_FIELD = r'"(?:[^"]|"")*"'
README_ROW_RE = re.compile(rf'^[^",]+,{_QUOTED_FIELD},(?:{_QUOTED_FIELD})?,(?:{_QUOTED_FIELD})?,(?:{_QUOTED_FIELD})?,'
                           r'(?:0(?:\.\d+)?|1(?:\.0+)?),(?:TRUE|FALSE),\d+$')


def check_submission_file(data: bytes | Path, sub: pd.DataFrame, template: Path | None = None) -> list[str]:
    """Đọc lại file submission ĐÚNG NHƯ MÁY CHẤM (bộ đọc CSV chuẩn, phân cách ',') và so TỪNG Ô với bảng kết quả.
    Trả về danh sách lỗi (rỗng = file chuẩn)."""
    import csv
    import io
    raw = Path(data).read_bytes() if isinstance(data, Path) else data
    problems = []
    if not raw.startswith(b"\xef\xbb\xbf"):
        problems.append("thiếu BOM UTF-8 như template")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return problems + ["không phải UTF-8"]
    template = template or resolve_file("template")
    if template is not None and template.exists():
        tpl = template.read_bytes().decode("utf-8-sig")
        if text.split("\r\n", 1)[0] != tpl.splitlines()[0]:
            problems.append("dòng tiêu đề khác submission_output_template.csv")
    if "\n" in text.replace("\r\n", "") or "\r" in text.replace("\r\n", ""):
        problems.append("có xuống dòng nằm trong một ô")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    bad = [i for i, r in enumerate(rows) if len(r) != len(SUBMISSION_COLUMNS)]
    if bad:
        problems.append(f"{len(bad)} dòng không đủ 8 ô (dòng {', '.join(str(i + 1) for i in bad[:5])})")
    if rows and rows[0] != SUBMISSION_COLUMNS:
        problems.append("tên/thứ tự cột sai")
    if len(rows) - 1 != len(sub):
        problems.append(f"số dòng dữ liệu {len(rows) - 1} ≠ {len(sub)}")
    # mỗi dòng dữ liệu đúng mẫu ví dụ README mục 5: id,"câu trả lời","…","…","…",số,TRUE|FALSE,số nguyên
    off = [ln.split(",", 1)[0] for ln in text.split("\r\n")[1:] if ln and not README_ROW_RE.match(ln)]
    if off:
        problems.append(f"{len(off)} dòng khác mẫu ví dụ README mục 5 ({', '.join(off[:5])})")
    diff = 0
    for r, rec in zip(rows[1:], sub[SUBMISSION_COLUMNS].itertuples(index=False)):
        if len(r) == len(SUBMISSION_COLUMNS):
            diff += sum(a != _submission_cell(c, b) for a, b, c in zip(r, rec, SUBMISSION_COLUMNS))
    if diff:
        problems.append(f"{diff} ô đọc lại khác bảng kết quả")
    for r in rows[1:]:
        if len(r) == len(SUBMISSION_COLUMNS):
            try:
                ok = 0 <= float(r[5]) <= 1 and r[6] in ("TRUE", "FALSE") and int(r[7]) > 0
            except ValueError:
                ok = False
            if not ok:
                problems.append(f"{r[0]}: confidence/abstain/latency_ms sai kiểu")
                break
    return problems


def save_submission(sub: pd.DataFrame, path: Path) -> Path:
    """Ghi submission.csv (file nộp BTC) + bản .xlsx cùng tên để xem bằng Excel; tự đọc lại để chắc chắn file chuẩn."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = submission_bytes(sub)
    problems = check_submission_file(data, sub)
    if problems:
        raise ValueError("submission.csv không đạt định dạng: " + "; ".join(problems))
    for target, content in ((path, data), (path.with_suffix(".xlsx"), submission_xlsx_bytes(sub))):
        try:
            target.write_bytes(content)
        except PermissionError as exc:
            raise PermissionError(f"Không ghi được {target.name}: file đang mở trong chương trình khác (thường là Excel). "
                                  "Đóng file rồi chạy lại.") from exc
    return path


def validate_submission(sub: pd.DataFrame, dp: DataPack, path: Path | None = None) -> pd.DataFrame:
    """Checklist README mục 11 (+ đọc lại file như máy chấm, so từng ô)."""
    labels = set(dp.cmap_df.citation_label)
    cits = [c for v in sub.citations for c in str(v).split(";") if c]
    conf = pd.to_numeric(sub.confidence, errors="coerce")
    chunk_ok = all(c in dp.idx for v in sub.retrieved_chunk_ids for c in str(v).split(";") if c)
    problems = check_submission_file(Path(path), sub) if path is not None and Path(path).exists() else []
    expected_ids = list(dp.template.question_id)
    full_set = list(sub.question_id) == expected_ids
    rows = [
        ("Tệp là CSV UTF-8 (có BOM như template)", not any("UTF-8" in p for p in problems)),
        ("Đúng tên và thứ tự cột theo template", list(sub.columns) == SUBMISSION_COLUMNS
         and not any("tiêu đề" in p or "tên/thứ tự" in p for p in problems)),
        ("Mỗi câu hỏi đúng một dòng, đủ 8 ô", not any(k in p for p in problems for k in ("8 ô", "xuống dòng", "số dòng"))),
        ('Mỗi dòng đúng mẫu ví dụ README mục 5 (Q001,"…","…","…","…",0.93,FALSE,842)',
         not any("mẫu ví dụ README" in p for p in problems)),
        ("Đọc lại file như máy chấm: khớp từng ô với bảng", not problems),
        ("Không thiếu question_id (so với template)", full_set or set(sub.question_id) <= set(expected_ids)),
        ("Không trùng question_id", bool(sub.question_id.is_unique)),
        ("confidence nằm trong [0,1]", bool(conf.between(0, 1).all())),
        ("abstain chỉ nhận TRUE/FALSE", set(sub.abstain) <= {"TRUE", "FALSE"}),
        ("Danh sách ID phân cách bằng ';'", not any("," in str(v) for v in sub.retrieved_chunk_ids)),
        ("retrieved_chunk_ids tồn tại và giữ thứ tự ranking", chunk_ok),
        ("Citation tồn tại trong citation_map.csv", all(c in labels for c in cits)),
        ("ABSTAIN không kèm citation", bool(((sub.abstain == "TRUE") <= (sub.citations == "")).all())),
        ("latency_ms là số nguyên dương", bool((pd.to_numeric(sub.latency_ms, errors="coerce") > 0).all())),
    ]
    out = pd.DataFrame([{"kiểm tra": k, "kết quả": "PASS" if v else "FAIL"} for k, v in rows])
    if not full_set:
        out.loc[5, "kết quả"] = "PASS" if set(sub.question_id) <= set(expected_ids) else "FAIL"
        out.loc[5, "kiểm tra"] += " – bộ câu hỏi tùy chỉnh"
    return out


def _split(v) -> list[str]:
    return [x.strip() for x in str(v or "").split(";") if x.strip()]


def _toks(s: str) -> list[str]:
    return TOKEN_RE.findall(norm(s))


def _lcs(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if x == y else max(prev[j], cur[-1]))
        prev = cur
    return prev[-1]


def _answer_body(ans: str) -> str:
    return "\n".join(ln for ln in ans.split("\n") if not ln.startswith(("Nguồn:", "Lưu ý:")) and ln != DISCLAIMER)


TAG_RE = re.compile(r"\[(\d+)\]")
VERSION_LINE_RE = re.compile(r"^(?:(?:Có|Không)\. )?(?:Tại ngày|Chưa áp dụng)|\(LAW\d{2}\)[^.]*(?:hiệu lực|thay thế|hợp nhất)")


def _support_lines(r: Result, dp: DataPack) -> list[tuple[list[int], list[str]]]:
    """Từng câu (dòng) của câu trả lời: các số citation gắn kèm và lỗi kiểm chứng của câu đó (rỗng = được xác nhận)."""
    out = []
    cited = r.cited_chunks
    ref = parse_date(r.applied_date) or SNAPSHOT
    for ln in _answer_body(r.answer).split("\n"):
        s = ln.strip()
        if not s or (s.endswith(":") and len(s) < 60):                    # tiêu đề nhóm
            continue
        tags = [int(x) for x in TAG_RE.findall(s)]
        body = re.sub(r"^Kết luận:\s*", "", TAG_RE.sub("", s).strip(" -"))
        chunks = [cited[t - 1] for t in tags if 0 < t <= len(cited)]
        problems: list[str] = []
        out.append((tags, problems))
        if body.startswith("Chuỗi phiên bản"):
            if not all(d.upper() in dp.doc for d in DOCID_RE.findall(body)):
                problems.append(f"chuỗi phiên bản nêu văn bản không có trong metadata: {body[:60]}")
            continue
        if VERSION_LINE_RE.search(body):
            docs = [d.upper() for d in DOCID_RE.findall(body)]
            allowed = {ref.isoformat()}
            for d in docs:
                if d in dp.doc:
                    for v in (dp.start(d), dp.end(d)):
                        if v:
                            allowed.add(v)
                    if dp.end(d):
                        allowed.add((date.fromisoformat(dp.end(d)) + timedelta(days=1)).isoformat())
            for dd, mm, yy in DATE_RE.findall(body):
                if f"{int(yy):04d}-{int(mm):02d}-{int(dd):02d}" not in allowed:
                    problems.append(f"ngày {dd}/{mm}/{yy} không khớp metadata: {body[:60]}")
            if not chunks and "không có văn bản" not in body:
                problems.append(f"mệnh đề hiệu lực thiếu nguồn: {body[:60]}")
            continue
        if not chunks:
            problems.append(f"câu thiếu nguồn: {body[:60]}")
            continue
        text = re.sub(r"^(?:LAW|SIM)\d{2} – [^:]{1,80}: ", "", body)        # bỏ nhãn citation đứng đầu trích dẫn
        text = re.sub(r"^(?:Có|Không)\.\s+", "", text)                     # từ trả lời câu có/không của KẾT LUẬN
        ctoks = set().union(*(set(tokenize(dp.chunks[dp.idx[c]]["heading"] + " " + dp.chunks[dp.idx[c]]["chunk_text"],
                                           bigrams=False)) for c in chunks if c in dp.idx))
        atoks = set(tokenize(text, bigrams=False))
        ratio = len(atoks & ctoks) / len(atoks) if atoks else 1.0
        if ratio < 0.9:
            problems.append(f"chỉ {ratio:.0%} nội dung khớp nguồn: {body[:60]}")
    return out


def verify_support(r: Result, dp: DataPack) -> tuple[bool, list[str]]:
    """Kiểm chứng ĐỘC LẬP với pipeline: mọi câu của câu trả lời phải được xác nhận bởi chính chunk mà nó dẫn
    (≥ 90% từ của câu có trong chunk), mệnh đề hiệu lực phải khớp ngày trong document_metadata, không có câu
    khẳng định nào thiếu nguồn. Trả về (đạt?, danh sách lỗi)."""
    if r.abstain:
        return True, []
    problems = [x for _, probs in _support_lines(r, dp) for x in probs]
    return not problems, problems


def _versioning_ok(r: Result, expected_docs: set[str], dp: DataPack) -> float:
    """Đúng khi văn bản LAW đầu tiên được dẫn mà còn hiệu lực tại mốc áp dụng thuộc tập văn bản đúng."""
    if r.abstain:
        return 0.0
    ref = parse_date(r.applied_date) or SNAPSHOT
    first = next((c.split(" – ")[0] for c in r.citations
                  if c.startswith("LAW") and dp.doc_state(c.split(" – ")[0], ref) == VALID), "")
    return float(first in expected_docs)


# 7 KPI của README mục 9 – mục tiêu: đề thi (Recall@5, Citation Accuracy, Latency) và đội đề xuất (còn lại)
KPI_SPECS = [
    ("recall_at_5", "1. Retrieval Recall@5", ">=", 0.80, "đề thi"),
    ("answer_accuracy", "2. Answer Accuracy / Correctness (độ phủ ý chính)", ">=", 0.70, "đội đề xuất"),
    ("citation_accuracy", "3. Citation Accuracy", ">=", 0.80, "đề thi"),
    ("unsupported_rate", "4. Unsupported Answer Rate", "<=", 0.10, "đội đề xuất"),
    ("abstention_f1", "5. Abstention Quality (F1)", ">=", 0.90, "đội đề xuất"),
    ("versioning_accuracy", "6. Versioning Accuracy", ">=", 0.90, "đội đề xuất"),
    ("latency_ms_avg", "7. Latency trung bình (ms)", "<=", 10000, "đề thi"),
]
KPI_DEFINITIONS = {
    "recall_at_5": "|chunk đáp án ∩ 5 chunk đầu của retrieved_chunk_ids| / |chunk đáp án|, trung bình trên 26 câu ANSWER của "
                   "answer_key (câu bị ABSTAIN tính 0, đúng như file nộp).",
    "answer_correctness": "Thang 0 / 0,5 / 1 của báo cáo mục 5, chấm tự động: 1 khi độ phủ ý chính ≥ 0,70 (đủ ý), 0,5 khi "
                          "0,40–0,70 (thiếu ý), 0 khi < 0,40 hoặc ABSTAIN nhầm; trung bình trên câu ANSWER. Là chỉ số kèm – "
                          "điểm chính thức theo grading_note cần chấm tay.",
    "answer_accuracy": "Tỷ lệ từ khóa nội dung (bỏ hư từ) của reference_answer xuất hiện trong câu trả lời, trung bình trên 26 câu "
                       "ANSWER (ABSTAIN tính 0). Kèm ROUGE-L tham khảo; không thay chấm tay.",
    "citation_accuracy": "Trong các câu đã trả lời: |citation dẫn ∩ citation_labels đáp án| / |citation dẫn| (chặt, theo nhãn). "
                         "Kèm tỷ lệ citation hợp lệ về thời gian trên 90 câu public.",
    "unsupported_rate": "Theo đề/README: câu đã trả lời mà lẽ ra phải ABSTAIN, hoặc có câu khẳng định không được chính nguồn nó "
                        "dẫn xác nhận (kiểm chứng độc lập: ≥ 90% từ có trong chunk, ngày hiệu lực khớp metadata) / tổng câu đã trả "
                        "lời (Dev-30 + Probe-25). Kèm 'evidence_mismatch_rate' = câu Dev không có citation nào trùng nhãn đáp án.",
    "abstention_f1": "F1 của lớp ABSTAIN trên 30 câu Dev + 25 câu probe (kèm precision, recall, accuracy quyết định).",
    "versioning_accuracy": "Câu VERSIONING (4 Dev + 6 probe có expected_documents): văn bản LAW đầu tiên được dẫn còn hiệu lực "
                           "tại mốc áp dụng phải thuộc tập văn bản đúng.",
    "latency_ms_avg": "Thời gian xử lý trung bình mỗi câu (ms) trên Dev + probe + 90 câu public, đo trong tiến trình.",
}


def kpi_status(key: str, value: float) -> bool:
    spec = next(s for s in KPI_SPECS if s[0] == key)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    return value >= spec[3] if spec[2] == ">=" else value <= spec[3]


def evaluate_system(dev_res: list[Result], probe_res: list[Result], dp: DataPack,
                    probe: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    key = dp.answer_key
    by = {r.question_id: r for r in dev_res}
    rows = []
    for k in key.itertuples(index=False):
        r = by.get(k.question_id)
        if r is None:
            continue
        exp_abs, answered = k.expected_behavior == "ABSTAIN", not r.abstain
        row = {"tập": "Dev-30", "question_id": k.question_id, "scope": k.answer_scope, "expected": k.expected_behavior,
               "predicted": r.decision, "decision_correct": float(answered != exp_abs), "confidence": r.confidence,
               "latency_ms": r.latency_ms, "citations": "; ".join(r.citations)}
        if not exp_abs:
            gold_c, gold_l, gold_d = _split(k.relevant_chunk_ids), _split(k.citation_labels), set(_split(k.relevant_document_ids))
            pred_c = [x["chunk_id"] for x in r.retrieved][:5] if answered else []
            row["recall_at_5"] = len(set(gold_c) & set(pred_c)) / len(gold_c) if gold_c else np.nan
            body = _answer_body(r.answer) if answered else ""
            ref_terms, ans_terms = set(content_terms(k.reference_answer)), set(content_terms(body))
            row["answer_accuracy"] = len(ref_terms & ans_terms) / len(ref_terms) if ref_terms else np.nan
            row["answer_correctness"] = answer_correctness(row["answer_accuracy"], not answered)
            b, t = _toks(body), _toks(k.reference_answer)
            m = _lcs(b, t)
            row["rouge_l"] = (2 * m / (len(b) + len(t))) if m else 0.0
            if answered:
                inter = set(r.citations) & set(gold_l)
                row["citation_accuracy"] = len(inter) / len(r.citations) if r.citations else 0.0
                row["citation_recall"] = len(inter) / len(gold_l) if gold_l else 0.0
                row["evidence_mismatch"] = float(not inter)
                ok, probs = verify_support(r, dp)
                row["unsupported"] = float(not ok)
                row["support_problems"] = "; ".join(probs)
            if k.answer_scope == "VERSIONING":
                row["versioning_correct"] = _versioning_ok(r, gold_d, dp)
            # nhãn hiệu chỉnh: confidence = xác suất "nên trả lời và câu trả lời có căn cứ đúng"
            row["calib_label"] = 1.0 - row["evidence_mismatch"] if answered else 1.0
        else:
            if answered:
                row["unsupported"] = 1.0
                row["support_problems"] = "lẽ ra phải ABSTAIN"
            row["calib_label"] = 0.0
        rows.append(row)
    for p, r in zip(probe.itertuples(index=False), probe_res):
        exp_abs, answered = p.expected_behavior == "ABSTAIN", not r.abstain
        row = {"tập": "Probe", "question_id": p.question_id, "scope": "", "expected": p.expected_behavior,
               "predicted": r.decision, "decision_correct": float(answered != exp_abs), "confidence": r.confidence,
               "latency_ms": r.latency_ms, "citations": "; ".join(r.citations), "calib_label": 0.0 if exp_abs else 1.0}
        if answered:
            ok, probs = verify_support(r, dp)
            row["unsupported"] = 1.0 if exp_abs else float(not ok)
            row["support_problems"] = "lẽ ra phải ABSTAIN" if exp_abs else "; ".join(probs)
        exp_docs = set(_split(getattr(p, "expected_documents", "")))
        if exp_docs:
            row["scope"] = "VERSIONING"
            row["versioning_correct"] = _versioning_ok(r, exp_docs, dp)
        rows.append(row)
    df = pd.DataFrame(rows)

    def mean(col, mask=None):
        if col not in df:
            return np.nan
        s = pd.to_numeric(df[col] if mask is None else df[col][mask], errors="coerce").dropna()
        return round(float(s.mean()), 3) if len(s) else np.nan

    dev = df["tập"] == "Dev-30"
    dev_ans = dev & (df.expected == "ANSWER")
    answered = df.predicted == "ANSWER"
    exp_ab, pred_ab = df.expected == "ABSTAIN", df.predicted == "ABSTAIN"
    tp = int((exp_ab & pred_ab).sum())
    prec = tp / int(pred_ab.sum()) if pred_ab.sum() else 0.0
    rec = tp / int(exp_ab.sum()) if exp_ab.sum() else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    conf, ok = df.confidence.astype(float), df.calib_label.astype(float)
    bins = np.clip((conf * 5).astype(int), 0, 4)
    ece = float(sum(abs(conf[bins == b].mean() - ok[bins == b].mean()) * (bins == b).sum() for b in range(5)
                    if (bins == b).any()) / len(df)) if len(df) else np.nan
    summary = {
        "recall_at_5": mean("recall_at_5", dev_ans),
        "answer_accuracy": mean("answer_accuracy", dev_ans),
        "answer_correctness": mean("answer_correctness", dev_ans),
        "citation_accuracy": mean("citation_accuracy", dev_ans & answered),
        "unsupported_rate": mean("unsupported", answered),
        "abstention_f1": round(f1, 3),
        "versioning_accuracy": mean("versioning_correct"),
        "latency_ms_avg": round(float(df.latency_ms.mean()), 1),
        "citation_recall": mean("citation_recall", dev_ans & answered),
        "evidence_mismatch_rate": mean("evidence_mismatch", dev_ans & answered),
        "rouge_l": mean("rouge_l", dev_ans),
        "abstain_precision": round(prec, 3), "abstain_recall": round(rec, 3),
        "decision_accuracy": mean("decision_correct"),
        "false_abstain": int((dev_ans & pred_ab).sum()), "missed_abstain": int((exp_ab & answered).sum()),
        "n_versioning": int(df["versioning_correct"].notna().sum()) if "versioning_correct" in df else 0,
        "versioning_ok": int(pd.to_numeric(df["versioning_correct"], errors="coerce").fillna(0).sum())
        if "versioning_correct" in df else 0,
        "n_answered": int(answered.sum()),
        "n_unsupported": int(pd.to_numeric(df.get("unsupported"), errors="coerce").fillna(0)[answered].sum())
        if "unsupported" in df else 0,
        "abstain_tp": tp, "abstain_fp": int((pred_ab & ~exp_ab).sum()), "abstain_fn": int((exp_ab & ~pred_ab).sum()),
        "brier": round(float(np.mean((conf - ok) ** 2)), 3), "ece": round(ece, 3),
        "latency_ms_p95": round(float(df.latency_ms.quantile(0.95)), 1),
        "n_labeled": len(df),
    }
    return df, summary


SYSTEMS = {
    # B0 = BM25 thuần đúng nghĩa: câu hỏi nguyên văn (không chuẩn hóa/mở rộng/kéo chunk theo tên văn bản), top-5 theo BM25,
    # trả lời bằng đoạn trích của chunk đứng đầu, luôn trả lời (không Guard/Gate), không xét hiệu lực/thẩm quyền/kiểm toán.
    "B0 – BM25 thuần (baseline)": dict(name="B0", w_tfidf=0.0, use_guard=False, use_chronos=False, use_rerank=False,
                                      use_prf=False, use_structure=False, use_gate=False, use_audit=False,
                                      use_rewrite=False, use_expansion=False, use_forced=False, w_coverage=0.0,
                                      max_answer_chunks=1),
    "CHRONOS-LEDGER (đầy đủ)": dict(name="FULL"),
    "– bỏ CHRONOS (versioning)": dict(name="NO_CHRONOS", use_chronos=False),
    "– bỏ Authority rerank": dict(name="NO_RERANK", use_rerank=False),
    "– bỏ truy nguồn FAQ (PRF)": dict(name="NO_PRF", use_prf=False),
    "– bỏ cấu trúc Điều": dict(name="NO_STRUCTURE", use_structure=False),
    "– bỏ Guard & Gate": dict(name="NO_GATE", use_guard=False, use_gate=False),
    "– bỏ TF-IDF (chỉ BM25)": dict(name="NO_TFIDF", w_tfidf=0.0),
}
FULL_SYSTEM = "CHRONOS-LEDGER (đầy đủ)"


def load_probe() -> pd.DataFrame:
    if not PROBE_PATH.exists():
        return pd.DataFrame(columns=["question_id", "question_text", "reference_date", "expected_behavior", "expected_documents"])
    p = read_csv(PROBE_PATH)
    if "expected_documents" not in p:
        p["expected_documents"] = ""
    return p


def cohen_kappa(a: list, b: list) -> float:
    from collections import Counter
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def run_stress(pa: PolicyAssist, progress=None) -> dict:
    """Stress-60 (data/eval/stress60_labels.csv): bộ kiểm thử chịu tải của đội – 60 biến thể của câu Ext-60 thuộc 14 kiểu
    (diễn đạt lại, không dấu, viết tắt/tiếng Anh, tiền đề sai, mồi văn bản hết hiệu lực, mốc chuyển giao hiệu lực, mốc ngầm,
    chèn lệnh, gần phạm vi nhưng không có dữ liệu, một phần ngoài phạm vi, nhiều bước, bẫy số, câu mơ hồ). Chấm quyết định
    ANSWER/ABSTAIN, Recall@5 theo chunk kỳ vọng, Citation Accuracy theo nhãn (như KPI), đúng văn bản, Versioning (câu
    VERSIONING), phạm vi trả lời; baseline B0 để đối chiếu. Không dùng để tinh chỉnh ngưỡng."""
    dp = pa.dp
    lab = read_csv(STRESS60_PATH)
    runs = [("CHRONOS-LEDGER", pa.with_config(write_log=False)),
            ("B0 – BM25 thuần", pa.with_config(write_log=False, **SYSTEMS["B0 – BM25 thuần (baseline)"]))]
    rows = []
    for n_sys, (sys_name, sysm) in enumerate(runs):
        for k, r in enumerate(lab.to_dict("records"), 1):
            res = sysm.answer(r["question_text"], r["reference_date"], r["question_id"])
            exp_abs = r["expected_behavior"] == "ABSTAIN"
            exp_chunks, exp_cits, exp_docs = (set(_split(r.get(c, ""))) for c in
                                              ("expected_chunk_ids", "expected_citations", "expected_document_ids"))
            # phạm vi của câu trả lời theo nguồn đã trích dẫn: chỉ LAW → LEGAL, chỉ SIM → INTERNAL, cả hai → MIXED
            kinds = {c[:3] for c in res.cited_chunks}
            src_scope = ("OUT_OF_SCOPE" if res.abstain else "VERSIONING" if res.intent == "VERSIONING" or not kinds else
                         "MIXED" if kinds >= {"LAW", "SIM"} else "LEGAL" if "LAW" in kinds else "INTERNAL")
            route = "OUT_OF_SCOPE" if res.abstain else res.intent
            ref = parse_date(res.applied_date) or SNAPSHOT
            valid = all(c in dp.label and (dp.chunk_state(dp.idx[c], ref) in USABLE or res.intent == "VERSIONING")
                        for c in res.cited_chunks)
            row = {"hệ thống": sys_name, "question_id": r["question_id"], "kiểu stress": r["stress_type"],
                   "seed": r.get("seed_id", ""), "trạng thái nhãn": r.get("trang_thai", ""), "câu hỏi": r["question_text"],
                   "reference_date": r["reference_date"], "nhãn phạm vi": r["answer_scope"], "phạm vi theo nguồn": src_scope,
                   "phạm vi định tuyến": route, "nhãn hành vi": r["expected_behavior"], "quyết định": res.decision,
                   "quyết định đúng": float(res.abstain == exp_abs), "phạm vi nguồn đúng": float(src_scope == r["answer_scope"]),
                   "định tuyến đúng": float(route == r["answer_scope"]), "citations": "; ".join(res.citations),
                   "citation kỳ vọng": r.get("expected_citations", ""), "citation hợp lệ": float(valid),
                   "độ tin cậy": round(res.confidence, 3), "latency_ms": res.latency_ms, "lý do": res.reason}
            if not exp_abs and exp_chunks:
                top5 = {x["chunk_id"] for x in res.retrieved[:5]}
                row["Recall@5"] = 0.0 if res.abstain else len(exp_chunks & top5) / len(exp_chunks)
                row["căn cứ đúng top-5"] = 0.0 if res.abstain else float(bool(exp_chunks & top5))
                if not res.abstain:
                    hits = [c in exp_chunks or lb in exp_cits for c, lb in zip(res.cited_chunks, res.citations)]
                    row["Citation Accuracy"] = sum(hits) / len(hits) if hits else 0.0
                    row["citation [1] đúng"] = float(bool(hits) and hits[0])
                    row["có citation đúng"] = float(any(hits))
                    if exp_docs:
                        row["đúng văn bản"] = float(bool({c.split("_")[0] for c in res.cited_chunks} & exp_docs))
                if r["answer_scope"] == "VERSIONING" and exp_docs:
                    row["Versioning"] = _versioning_ok(res, exp_docs, dp)
            rows.append(row)
            if progress:
                progress(n_sys * len(lab) + k, len(runs) * len(lab), f"{sys_name} · {r['question_id']}")
    df = pd.DataFrame(rows)

    def mean(g, c):
        return round(float(g[c].mean()), 3) if c in g and g[c].notna().any() else np.nan

    def summarize(g: pd.DataFrame) -> dict:
        exp, got = g["nhãn hành vi"] == "ABSTAIN", g["quyết định"] == "ABSTAIN"
        tp, fp, fn = int((exp & got).sum()), int((~exp & got).sum()), int((exp & ~got).sum())
        p, rc = (tp / (tp + fp) if tp + fp else 0.0), (tp / (tp + fn) if tp + fn else 0.0)
        ans = g["quyết định"] == "ANSWER"
        return {"số câu": len(g), "quyết định đúng": mean(g, "quyết định đúng"),
                "F1 ABSTAIN": (round(2 * p * rc / (p + rc), 3) if p + rc else 0.0) if tp + fp + fn else np.nan,
                "Recall@5": mean(g, "Recall@5"), "căn cứ đúng top-5": mean(g, "căn cứ đúng top-5"),
                "Citation Accuracy": mean(g, "Citation Accuracy"), "citation [1] đúng": mean(g, "citation [1] đúng"),
                "có citation đúng": mean(g, "có citation đúng"), "đúng văn bản": mean(g, "đúng văn bản"),
                "Versioning": mean(g, "Versioning"), "phạm vi nguồn đúng": mean(g, "phạm vi nguồn đúng"),
                "κ phạm vi nguồn": round(cohen_kappa(list(g["nhãn phạm vi"]), list(g["phạm vi theo nguồn"])), 3),
                "citation hợp lệ": round(float(g.loc[ans, "citation hợp lệ"].mean()), 3) if ans.any() else np.nan,
                "latency TB (ms)": round(float(g["latency_ms"].mean()), 1),
                "latency p95 (ms)": round(float(np.percentile(g["latency_ms"], 95)), 1)}

    summary = pd.DataFrame([{"hệ thống": s, **summarize(g)} for s, g in df.groupby("hệ thống", sort=False)])
    main = df[df["hệ thống"] == "CHRONOS-LEDGER"]
    keep = ("số câu", "quyết định đúng", "Recall@5", "Citation Accuracy", "citation [1] đúng", "có citation đúng", "Versioning")
    order = list(dict.fromkeys(lab["stress_type"]))
    by_type = pd.DataFrame([{"kiểu stress": t, **{c: v for c, v in summarize(main[main["kiểu stress"] == t]).items() if c in keep}}
                            for t in order])
    by_status = pd.DataFrame([{"trạng thái nhãn": s, **{c: v for c, v in summarize(g).items() if c in keep}}
                              for s, g in main.groupby("trạng thái nhãn")])
    confusion = pd.crosstab(main["nhãn phạm vi"], main["phạm vi theo nguồn"], margins=True, margins_name="Tổng")
    misses = main[(main["quyết định đúng"] < 1) | (main.get("có citation đúng", pd.Series(1.0, index=main.index)) == 0)
                  | (main.get("Recall@5", pd.Series(1.0, index=main.index)) == 0)]
    return {"rows": df, "summary": summary, "by_type": by_type, "by_status": by_status, "confusion": confusion,
            "misses": misses, "labels": lab}


def write_stress_report(st: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    st["rows"].to_csv(OUTPUT_DIR / "stress60_results.csv", index=False, encoding="utf-8-sig")
    st["summary"].to_csv(OUTPUT_DIR / "stress60_summary.csv", index=False, encoding="utf-8-sig")
    lab = st["labels"]

    def md(df: pd.DataFrame, index: bool = False) -> str:
        d = df.reset_index() if index else df
        cols = [str(c) for c in d.columns]
        out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for r in d.itertuples(index=False):
            out.append("| " + " | ".join("—" if isinstance(v, float) and np.isnan(v) else str(v).replace("|", "/")
                                         for v in r) + " |")
        return "\n".join(out)

    beh = lab["expected_behavior"].value_counts()
    miss = st["misses"][["question_id", "kiểu stress", "nhãn hành vi", "quyết định", "citations", "citation kỳ vọng", "câu hỏi"]]
    text = [f"# Stress-60 – {APP_NAME} {APP_VERSION}", "",
            f"- Thời điểm chạy: {datetime.now():%H:%M %d/%m/%Y} · corpus fingerprint {_FINGERPRINT['value'][:12] or '—'}",
            f"- Bộ câu: {len(lab)} câu ({lab['stress_type'].nunique()} kiểu stress) · ANSWER {beh.get('ANSWER', 0)} · "
            f"ABSTAIN {beh.get('ABSTAIN', 0)} · nhãn: data/eval/stress60_labels.csv (trạng thái: "
            + ", ".join(f"{k} {v}" for k, v in lab["trang_thai"].value_counts().items()) + ").",
            "- Recall@5: tỷ lệ chunk kỳ vọng nằm trong 5 chunk đầu (câu bị ABSTAIN tính 0). Citation Accuracy: tỷ lệ citation dẫn "
            "đúng nhãn/chunk kỳ vọng (như KPI 3). Versioning: văn bản LAW đầu tiên được dẫn còn hiệu lực tại mốc thuộc tập văn "
            "bản kỳ vọng. Phạm vi theo nguồn: chỉ trích LAW → LEGAL, chỉ SIM → INTERNAL, cả hai → MIXED, câu hiệu lực → "
            "VERSIONING, ABSTAIN → OUT_OF_SCOPE.", "- Không dùng bộ này để tinh chỉnh ngưỡng.", "",
            "## Kết quả", "", md(st["summary"]), "", "## Theo kiểu stress (CHRONOS-LEDGER)", "", md(st["by_type"]), "",
            "## Theo trạng thái nhãn", "", md(st["by_status"]), "",
            "## Ma trận phạm vi (hàng = nhãn, cột = phạm vi theo nguồn trích dẫn)", "", md(st["confusion"], index=True), "",
            f"## Câu cần xem lại ({len(miss)})", "", "Sai quyết định, hoặc trả lời mà không có citation/chunk kỳ vọng nào.", "",
            md(miss) if len(miss) else "Không có.", ""]
    path = OUTPUT_DIR / "stress60_report.md"
    path.write_text("\n".join(text), encoding="utf-8")
    return path


# ---- Đánh giá đầy đủ (báo cáo mục 5 của đội) -------------------------------------------------------------------------
# Mọi tập có nhãn · đủ 7 KPI (Recall@5 · Answer Correctness · Citation Accuracy · Unsupported · Abstention · Versioning ·
# Latency TB/p95) + chỉ số phụ (MRR@5, Recall@5 theo văn bản, Precision/Recall ABSTAIN, citation đủ 4 điều kiện, Source
# Priority) · số câu đúng/tổng · khoảng tin cậy 95% (bootstrap) · tách theo answer_scope · kiểm định ghép cặp với B0.
EVAL_SETS = {
    "Dev-30": "30 câu có đáp án mẫu của BTC (answer_key_sample.csv)",
    "Ext-60": "60 câu public còn lại – nhãn của đội: 2 người gán độc lập, hội chẩn câu bất đồng (data/eval/ext60_labels.csv)",
    "Public-90": "Dev-30 + Ext-60: toàn bộ 90 câu public",
    "Stress-60": "60 câu kiểm thử chịu tải do đội viết; đã dùng để phân tích lỗi (24/10 và 10/11/2026) nên không còn hoàn toàn độc lập (data/eval/stress60_labels.csv)",
    "Probe-25": "25 câu thăm dò: ngoài phạm vi, diễn đạt lại, versioning mốc mới (data/eval/probe_questions.csv)",
    "Paraphrase-52": "52 câu diễn đạt lại câu mẫu, viết tắt, gõ không dấu + câu phải ABSTAIN (data/eval/paraphrase_questions.csv)",
}
LABEL_COLUMNS = ["question_id", "question_text", "reference_date", "expected_behavior", "answer_scope", "gold_chunks",
                 "ok_chunks", "gold_labels", "gold_docs", "ver_docs", "reference_answer", "grading_note", "trap_chunks",
                 "stress_type", "seed_id"]
# kiểu Stress-60 giữ nguyên đáp án của câu gốc (seed_id) → Answer Correctness chấm theo đáp án câu gốc; kiểu khác cần chấm tay
SAME_ANSWER_STRESS = {"PARAPHRASE", "NO_DIACRITIC", "ABBREV_TYPO", "ABBREV_CODEMIX", "INJECTION"}
# Answer Correctness theo thang 0 / 0,5 / 1 của báo cáo mục 5: độ phủ ý chính ≥ 0,70 (= mục tiêu đội của độ phủ) → 1 (đủ ý);
# ≥ 0,40 → 0,5 (thiếu ý); thấp hơn, hoặc ABSTAIN câu cần trả lời → 0. Chấm tự động – không thay chấm tay theo grading_note.
CORRECT_FULL, CORRECT_PART = 0.70, 0.40
BOOT_N, BOOT_SEED = 2000, 2026
_OFF = dict(use_guard=False, use_chronos=False, use_rerank=False, use_prf=False, use_structure=False, use_gate=False,
            use_audit=False, max_answer_chunks=1, min_confidence=0.0)
# Ablation thêm dần (báo cáo mục 5.3): bật lần lượt từng khối của pipeline từ B0 đến hệ thống đầy đủ B6; B2′ thay CHRONOS
# bằng cách của pipeline tham khảo (lọc cứng theo ngày trước khi xếp hạng) để so hai cách xử lý phiên bản.
ABLATION_STEPS = {
    "B0 – BM25 thuần (baseline)": dict(name="B0", **{k: v for k, v in SYSTEMS["B0 – BM25 thuần (baseline)"].items()
                                                     if k != "name"}),
    "B1 – + truy hồi lai, chuẩn hóa truy vấn": dict(name="B1", **_OFF),
    "B2 – + CHRONOS (chuyển hướng phiên bản)": dict(name="B2", **{**_OFF, "use_chronos": True}),
    "B2′ – B1 + lọc cứng theo ngày": dict(name="B2p", hard_date_filter=True, **_OFF),
    "B3 – + xếp hạng thẩm quyền, cấu trúc Điều, truy nguồn FAQ": dict(name="B3", **{**_OFF, "use_chronos": True,
                                                                                   "use_rerank": True, "use_prf": True,
                                                                                   "use_structure": True}),
    "B4 – + Guard, cổng đủ căn cứ": dict(name="B4", **{**_OFF, "use_chronos": True, "use_rerank": True, "use_prf": True,
                                                       "use_structure": True, "use_guard": True, "use_gate": True}),
    "B5 – + soạn nhiều căn cứ, kiểm toán citation": dict(name="B5", min_confidence=0.0),
    "B6 – + ngưỡng độ tin cậy (= hệ thống đầy đủ)": dict(name="FULL"),
}
DEMO_CASES = [   # kịch bản demo của đội (Demo Script v0, sheet "Câu hỏi & Kỳ vọng")
    ("A – một nguồn", "Q001", "", "2026-10-17", "ANSWER", "LAW01_C001"),
    ("B1 – nhiều nguồn", "Q042", "", "2026-10-17", "ANSWER", "LAW12_C009;LAW12_C011;SIM02_C006"),
    ("B2 – versioning", "", "Hướng dẫn về hóa đơn điện tử nên áp dụng theo Thông tư nào?", "2025-05-15", "ANSWER", "LAW09"),
    ("B2 – versioning", "", "Hướng dẫn về hóa đơn điện tử nên áp dụng theo Thông tư nào?", "2025-06-15", "ANSWER", "LAW06"),
    ("B2 – versioning", "", "Hướng dẫn về hóa đơn điện tử nên áp dụng theo Thông tư nào?", "2026-08-15", "ANSWER", "LAW12"),
    ("C – ABSTAIN", "Q077", "", "2026-10-17", "ABSTAIN", ""),
]


def load_eval_sets(dp: DataPack) -> dict[str, pd.DataFrame]:
    """Các tập có nhãn quy về một lược đồ chung (LABEL_COLUMNS). gold_chunks: chunk chính tính Recall@5/MRR;
    ok_chunks + gold_labels: citation chấp nhận được; ver_docs: văn bản đúng của câu VERSIONING."""
    key = dp.answer_key
    blank = dict.fromkeys(LABEL_COLUMNS, "")

    def row(**kw):
        return {**blank, **{k: "" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v) for k, v in kw.items()}}

    def ans(r, text):
        return text if r.expected_behavior == "ANSWER" else ""

    sets = {"Dev-30": [row(question_id=r.question_id, question_text=r.question_text, reference_date=r.reference_date,
                           expected_behavior=r.expected_behavior, answer_scope=r.answer_scope,
                           gold_chunks=r.relevant_chunk_ids, ok_chunks=r.relevant_chunk_ids, gold_labels=r.citation_labels,
                           gold_docs=r.relevant_document_ids, ver_docs=r.relevant_document_ids,
                           reference_answer=ans(r, r.reference_answer), grading_note=r.grading_note)
                       for r in key.itertuples(index=False)]}
    refs = {r["question_id"]: r["reference_answer"] for r in sets["Dev-30"] if r["reference_answer"]}
    if EXT60_PATH.exists():
        sets["Ext-60"] = [row(question_id=r.question_id, question_text=r.question_text, reference_date=r.reference_date,
                              expected_behavior=r.expected_behavior, answer_scope=r.answer_scope,
                              gold_chunks=r.relevant_chunk_ids,
                              ok_chunks=";".join(_split(r.relevant_chunk_ids) + _split(r.supporting_chunk_ids)),
                              gold_labels=r.citation_labels, gold_docs=r.relevant_document_ids,
                              ver_docs=r.expected_document_ids or r.relevant_document_ids,
                              reference_answer=ans(r, r.reference_answer), grading_note=r.grading_note,
                              trap_chunks=r.trap_chunk_ids) for r in read_csv(EXT60_PATH).itertuples(index=False)]
        refs.update({r["question_id"]: r["reference_answer"] for r in sets["Ext-60"] if r["reference_answer"]})
        sets["Public-90"] = sets["Dev-30"] + sets["Ext-60"]
    if STRESS60_PATH.exists():
        sets["Stress-60"] = [row(question_id=r.question_id, question_text=r.question_text, reference_date=r.reference_date,
                                 expected_behavior=r.expected_behavior, answer_scope=r.answer_scope,
                                 gold_chunks=r.expected_chunk_ids, ok_chunks=r.expected_chunk_ids,
                                 gold_labels=r.expected_citations, gold_docs=r.expected_document_ids,
                                 ver_docs=r.expected_document_ids,
                                 reference_answer=refs.get(r.seed_id, "") if r.stress_type in SAME_ANSWER_STRESS
                                 and r.expected_behavior == "ANSWER" else "",
                                 grading_note=r.ghi_chu, stress_type=r.stress_type, seed_id=r.seed_id)
                             for r in read_csv(STRESS60_PATH).itertuples(index=False)]
    sets["Probe-25"] = [row(question_id=r.question_id, question_text=r.question_text, reference_date=r.reference_date,
                            expected_behavior=r.expected_behavior,
                            answer_scope="VERSIONING" if r.expected_documents else
                            "OUT_OF_SCOPE" if r.expected_behavior == "ABSTAIN" else "",
                            ver_docs=r.expected_documents) for r in load_probe().itertuples(index=False)]
    if PARAPHRASE_PATH.exists():
        src, rows = key.set_index("question_id"), []
        # phạm vi của câu diễn đạt lại = phạm vi câu gốc, kể cả câu gốc thuộc Ext-60 (trước đây chỉ tra answer_key Dev-30
        # nên câu diễn đạt lại của Q060, Q062 – câu phiên bản – bị để trống phạm vi và không được tính Versioning)
        ext_scope = {r["question_id"]: r["answer_scope"] for r in sets.get("Ext-60", [])}
        for r in read_csv(PARAPHRASE_PATH).itertuples(index=False):
            s = src.loc[r.source_id] if r.source_id in src.index and r.expected_behavior == "ANSWER" else None
            acc = _split(r.acceptable_chunk_ids)
            gold = _split(s.relevant_chunk_ids) if s is not None else acc
            ok = list(dict.fromkeys(gold + acc))
            rows.append(row(question_id=r.question_id, question_text=r.question_text, reference_date=r.reference_date,
                            expected_behavior=r.expected_behavior,
                            answer_scope=s.answer_scope if s is not None else
                            "OUT_OF_SCOPE" if r.expected_behavior == "ABSTAIN" else ext_scope.get(r.source_id, ""),
                            gold_chunks=";".join(gold), ok_chunks=";".join(ok),
                            gold_labels=";".join(dict.fromkeys(dp.label[c] for c in ok if c in dp.label)),
                            gold_docs=";".join(dict.fromkeys(c.split("_")[0] for c in gold)),
                            ver_docs=r.expected_documents or (s.relevant_document_ids if s is not None else ""),
                            reference_answer=s.reference_answer if s is not None else "", grading_note=r.note,
                            seed_id=r.source_id))
        sets["Paraphrase-52"] = rows
    return {k: pd.DataFrame(v, columns=LABEL_COLUMNS) for k, v in sets.items()}


def citation_checks(res: Result, dp: DataPack) -> list[dict]:
    """Bốn điều kiện của một citation đúng (báo cáo mục 5.2 của đội): (a) có trong citation_map.csv; (b) ứng với chunk đã
    truy xuất; (c) chunk chứa căn cứ cho mọi câu gắn citation đó (≥ 90% từ của câu có trong chunk, mệnh đề hiệu lực khớp
    metadata – như verify_support); (d) phù hợp reference_date (chunk còn hiệu lực/nội bộ tại mốc áp dụng, hoặc được dẫn
    như văn bản lịch sử trong câu hỏi về phiên bản)."""
    if res.abstain:
        return []
    ref = parse_date(res.applied_date) or SNAPSHOT
    retrieved = {x["chunk_id"] for x in res.retrieved}
    labels = set(dp.cmap_df.citation_label)
    lines = _support_lines(res, dp)
    out = []
    for n, (lb, c) in enumerate(zip(res.citations, res.cited_chunks), 1):
        tagged = [p for tags, p in lines if n in tags]
        ok = {"a": lb in labels, "b": c in retrieved, "c": bool(tagged) and not any(tagged),
              "d": c in dp.idx and (dp.chunk_state(dp.idx[c], ref) in USABLE or res.intent == "VERSIONING")}
        out.append({"citation": lb, "chunk_id": c, **ok, "đạt": all(ok.values())})
    return out


def source_priority_ok(res: Result, dp: DataPack) -> float:
    """Source Priority (chỉ số phụ, câu MIXED): có căn cứ pháp luật còn hiệu lực tại mốc; căn cứ pháp luật đứng trước tài
    liệu nội bộ; không dùng văn bản pháp luật hết hiệu lực/chưa hiệu lực/hợp nhất làm căn cứ (trừ câu hỏi về phiên bản);
    tài liệu nội bộ dẫn chiếu luật đã hết hiệu lực thì phải dẫn văn bản kế nhiệm hoặc cảnh báo dẫn chiếu lỗi thời."""
    if res.abstain or not res.cited_chunks:
        return 0.0
    ref = parse_date(res.applied_date) or SNAPSHOT
    cs = [dp.chunks[dp.idx[c]] for c in res.cited_chunks if c in dp.idx]
    state = lambda c: dp.chunk_state(dp.idx[c["chunk_id"]], ref)
    legal = [c["source_type"] == "LEGAL" for c in cs]
    if not any(lg and state(c) == VALID for lg, c in zip(legal, cs)):
        return 0.0
    if any(legal[k] for k in range(next((k for k, lg in enumerate(legal) if not lg), len(cs)), len(cs))):
        return 0.0
    if res.intent != "VERSIONING" and any(lg and state(c) not in USABLE for lg, c in zip(legal, cs)):
        return 0.0
    cited_docs = {c["document_id"] for c in cs}
    for c in cs:
        if c["source_type"] == "LEGAL":
            continue
        for d in dp.mentioned_docs(c["chunk_text"]):
            if d.startswith("LAW") and dp.doc_state(d, ref) in (EXPIRED, REF_ONLY):
                succ = set(dp.successors_in_force(d, ref))
                if succ and not succ & cited_docs and not any(d in w for w in res.warnings):
                    return 0.0
    return 1.0


def answer_coverage(reference: str, res: Result) -> float:
    """Độ phủ ý chính: tỷ lệ từ khóa nội dung của đáp án tham chiếu có trong phần trả lời (ABSTAIN → 0)."""
    ref_terms = set(content_terms(reference))
    if not ref_terms:
        return float("nan")
    body = "" if res.abstain else _answer_body(res.answer)
    return len(ref_terms & set(content_terms(body))) / len(ref_terms)


def answer_correctness(cov: float, abstained: bool) -> float:
    if isinstance(cov, float) and math.isnan(cov):
        return float("nan")
    return 0.0 if abstained else 1.0 if cov >= CORRECT_FULL else 0.5 if cov >= CORRECT_PART else 0.0


def error_type(row: dict) -> str:
    """Phân loại lỗi để lập bảng lỗi (retrieval / citation / abstain / versioning / unsupported / generation)."""
    exp, pred = row["expected"], row["predicted"]
    if exp == "ABSTAIN":
        return "ABSTAIN – trả lời câu lẽ ra phải từ chối" if pred == "ANSWER" else ""
    if pred == "ABSTAIN":
        return "ABSTAIN – từ chối nhầm câu đủ căn cứ"
    if row.get("hit_at_5") == 0:
        return "RETRIEVAL – chunk chính không có trong top-5"
    if row.get("citation_any") == 0:
        return "CITATION – không citation nào đúng nhãn"
    if row.get("versioning_correct") == 0:
        return "VERSIONING – văn bản không đúng mốc"
    if row.get("unsupported") == 1:
        return "UNSUPPORTED – nội dung không khớp nguồn"
    if row.get("answer_correctness") == 0:
        return "GENERATION – thiếu ý chính"
    return ""


def score_result(res: Result, lab: dict, dp: DataPack) -> dict:
    exp_abs, answered = lab["expected_behavior"] == "ABSTAIN", not res.abstain
    row = {"question_id": lab["question_id"], "scope": lab["answer_scope"], "stress_type": lab["stress_type"],
           "expected": lab["expected_behavior"], "predicted": res.decision, "decision_correct": float(answered != exp_abs),
           "confidence": round(res.confidence, 3), "latency_ms": res.latency_ms, "intent": res.intent,
           "applied_date": res.applied_date, "citations": "; ".join(res.citations),
           "retrieved": ";".join(x["chunk_id"] for x in res.retrieved) if answered else "", "reason": res.reason,
           "trace_id": res.trace_id, "answer": flat_text(res.answer)}
    if answered:
        ok, probs = verify_support(res, dp)
        row["unsupported"] = 1.0 if exp_abs else float(not ok)
        row["support_problems"] = "lẽ ra phải ABSTAIN" if exp_abs else "; ".join(probs)
        checks = citation_checks(res, dp)
        row["n_citations"] = len(checks)
        row["citation_valid_4"] = sum(c["đạt"] for c in checks) / len(checks) if checks else 0.0
    if not exp_abs:
        retrieved = [x["chunk_id"] for x in res.retrieved] if answered else []
        top5 = set(retrieved[:5])
        gold = set(_split(lab["gold_chunks"]))
        if gold:
            row["recall_at_5"] = len(gold & top5) / len(gold)
            row["hit_at_5"] = float(bool(gold & top5))
            row["rr"] = next((1.0 / k for k, c in enumerate(retrieved, 1) if c in gold), 0.0)
        gdocs = set(_split(lab["gold_docs"]))
        if gdocs:
            row["doc_recall_at_5"] = len(gdocs & {c.split("_")[0] for c in top5}) / len(gdocs)
        if lab["reference_answer"]:
            cov = answer_coverage(lab["reference_answer"], res)
            if not math.isnan(cov):
                row["answer_accuracy"] = cov
                row["answer_correctness"] = answer_correctness(cov, res.abstain)
        ok_c, labels = set(_split(lab["ok_chunks"])), set(_split(lab["gold_labels"]))
        if answered and (ok_c or labels):
            hits = [c in ok_c or lb in labels for c, lb in zip(res.cited_chunks, res.citations)]
            row["citation_accuracy"] = sum(hits) / len(hits) if hits else 0.0
            row["citation_first"] = float(bool(hits) and hits[0])
            row["citation_any"] = float(any(hits))
            must = {dp.label[c] for c in gold if c in dp.label}             # nhãn của chunk chính phải được dẫn
            row["citation_match"] = ("không khớp" if not any(hits) else "một phần" if not all(hits) else
                                     "khớp đủ" if must <= set(res.citations) else "đúng nhưng thiếu")
            traps = set(_split(lab["trap_chunks"]))
            if traps:
                row["trap_cited"] = float(bool(traps & set(res.cited_chunks)))
        vdocs = set(_split(lab["ver_docs"]))
        if lab["answer_scope"] == "VERSIONING" and vdocs:
            row["versioning_correct"] = _versioning_ok(res, vdocs, dp)
        if lab["answer_scope"] == "MIXED":
            row["source_priority"] = source_priority_ok(res, dp)
    if "citation_match" not in row:
        row["citation_match"] = (("ABSTAIN đúng" if res.abstain else "trả lời câu lẽ ra phải từ chối") if exp_abs else
                                 "từ chối nhầm" if res.abstain else "")
    row["gold_citations"] = lab["gold_labels"]
    row["error"] = error_type(row)
    return row


def evaluate_labeled(sysm: PolicyAssist, labels: pd.DataFrame, progress=None) -> tuple[pd.DataFrame, list[Result]]:
    rows, results = [], []
    for n, lab in enumerate(labels.to_dict("records"), 1):
        res = sysm.answer(lab["question_text"], lab["reference_date"], lab["question_id"])
        results.append(res)
        rows.append(score_result(res, lab, sysm.dp))
        if progress:
            progress(n, len(labels), lab["question_id"])
    return pd.DataFrame(rows), results


def _num(df: pd.DataFrame, col: str, mask=None) -> np.ndarray:
    if col not in df:
        return np.array([], dtype=float)
    s = pd.to_numeric(df[col] if mask is None else df[col][mask], errors="coerce").dropna()
    return s.to_numpy(dtype=float)


def _boot_ci(values: np.ndarray, stat=np.mean) -> tuple[float, float]:
    """Khoảng tin cậy 95% bootstrap (lấy mẫu lại câu hỏi, 2000 lần, hạt giống cố định → tái lập được)."""
    if len(values) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(values), size=(BOOT_N, len(values)))
    m = np.apply_along_axis(stat, 1, values[idx]) if stat is not np.mean else values[idx].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def _abstain_counts(exp_ab: np.ndarray, pred_ab: np.ndarray) -> dict:
    tp, fp = int((exp_ab & pred_ab).sum()), int((~exp_ab & pred_ab).sum())
    fn, tn = int((exp_ab & ~pred_ab).sum()), int((~exp_ab & ~pred_ab).sum())
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")            # tập không có câu ABSTAIN → recall không xác định ("—")
    f1 = 2 * p * r / (p + r) if not (math.isnan(p) or math.isnan(r)) and p + r else (0.0 if tp + fn else float("nan"))
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": p, "recall": r, "f1": f1}


def summarize_eval(df: pd.DataFrame) -> dict:
    """Tổng hợp một (tập, hệ thống): giá trị, số câu đúng/tổng, khoảng tin cậy 95%."""
    exp_ab, pred_ab = (df.expected == "ABSTAIN").to_numpy(), (df.predicted == "ABSTAIN").to_numpy()
    lab_ans, answered = df.expected == "ANSWER", df.predicted == "ANSWER"
    out = {"số câu": len(df), "nhãn ANSWER": int(lab_ans.sum()), "nhãn ABSTAIN": int(exp_ab.sum()),
           "đã trả lời": int(answered.sum())}

    def put(key, col, mask=None, ci=False):
        v = _num(df, col, mask)
        out[key] = round(float(v.mean()), 3) if len(v) else np.nan
        out[key + "_n"] = len(v)
        out[key + "_sum"] = round(float(v.sum()), 2) if len(v) else 0
        if ci:
            lo, hi = _boot_ci(v)
            out[key + "_ci"] = "" if math.isnan(lo) else f"{lo:.3f}–{hi:.3f}"

    put("quyết định đúng", "decision_correct", ci=True)
    put("recall_at_5", "recall_at_5", lab_ans, ci=True)
    put("hit_at_5", "hit_at_5", lab_ans)
    put("mrr", "rr", lab_ans)
    put("doc_recall_at_5", "doc_recall_at_5", lab_ans)
    put("answer_accuracy", "answer_accuracy", lab_ans, ci=True)
    put("answer_correctness", "answer_correctness", lab_ans)
    put("citation_accuracy", "citation_accuracy", lab_ans & answered, ci=True)
    put("citation_first", "citation_first", lab_ans & answered)
    put("citation_any", "citation_any", lab_ans & answered)
    put("trap_cited", "trap_cited", lab_ans & answered)
    put("citation_valid_4", "citation_valid_4", answered)
    put("unsupported_rate", "unsupported", answered, ci=True)
    put("versioning_accuracy", "versioning_correct", ci=True)
    put("source_priority", "source_priority")
    ab = _abstain_counts(exp_ab, pred_ab)
    out.update({"abstain_tp": ab["tp"], "abstain_fp": ab["fp"], "abstain_fn": ab["fn"], "abstain_tn": ab["tn"],
                "abstention_precision": round(ab["precision"], 3) if not math.isnan(ab["precision"]) else np.nan,
                "abstention_recall": round(ab["recall"], 3) if not math.isnan(ab["recall"]) else np.nan,
                "abstention_f1": round(ab["f1"], 3) if not math.isnan(ab["f1"]) else np.nan})
    if ab["tp"] + ab["fn"] and len(df) > 1:
        rng = np.random.default_rng(BOOT_SEED)
        f1s = []
        for _ in range(BOOT_N):
            i = rng.integers(0, len(df), len(df))
            f = _abstain_counts(exp_ab[i], pred_ab[i])["f1"]
            if not math.isnan(f):
                f1s.append(f)
        out["abstention_f1_ci"] = f"{np.percentile(f1s, 2.5):.3f}–{np.percentile(f1s, 97.5):.3f}" if f1s else ""
    lat = _num(df, "latency_ms")
    out.update({"latency_ms_avg": round(float(lat.mean()), 1) if len(lat) else np.nan,
                "latency_ms_p95": round(float(np.percentile(lat, 95)), 1) if len(lat) else np.nan,
                "latency_ms_max": int(lat.max()) if len(lat) else 0})
    return out


def scope_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Mọi KPI tách theo answer_scope để thấy hệ thống yếu ở loại câu nào."""
    rows = []
    for sc, g in df.groupby(df["scope"].replace("", "(không nhãn)"), sort=False):
        s = summarize_eval(g)
        rows.append({"phạm vi": sc, "số câu": s["số câu"], "quyết định đúng": s["quyết định đúng"],
                     "Recall@5": s["recall_at_5"], "MRR@5": s["mrr"], "Answer Correctness": s["answer_accuracy"],
                     "Citation Accuracy": s["citation_accuracy"], "Unsupported": s["unsupported_rate"],
                     "Versioning": s["versioning_accuracy"], "Source Priority": s["source_priority"],
                     "latency TB (ms)": s["latency_ms_avg"]})
    return pd.DataFrame(rows)


def paired_tests(full: pd.DataFrame, b0: pd.DataFrame) -> dict:
    """So sánh ghép cặp từng câu (báo cáo mục 5.2): McNemar chính xác cho quyết định đúng/sai; bootstrap ghép cặp cho chênh
    lệch Recall@5, Answer Correctness, Citation Accuracy (chỉ trên câu cả hai hệ thống đều có giá trị)."""
    j = full.set_index("question_id").join(b0.set_index("question_id"), rsuffix="_b0", how="inner")
    out = {}
    b = int(((j.decision_correct == 1) & (j.decision_correct_b0 == 0)).sum())
    c = int(((j.decision_correct == 0) & (j.decision_correct_b0 == 1)).sum())
    p = min(1.0, 2 * sum(math.comb(b + c, k) for k in range(min(b, c) + 1)) / 2 ** (b + c)) if b + c else 1.0
    out["quyết định đúng"] = f"+{b} / −{c} câu · McNemar p = {p:.3g}"
    rng = np.random.default_rng(BOOT_SEED)
    for col, name in (("recall_at_5", "Recall@5"), ("answer_accuracy", "Answer Correctness"),
                      ("citation_accuracy", "Citation Accuracy")):
        if col not in j or col + "_b0" not in j:
            continue
        d = (pd.to_numeric(j[col], errors="coerce") - pd.to_numeric(j[col + "_b0"], errors="coerce")).dropna().to_numpy()
        if len(d) < 2:
            continue
        m = d[rng.integers(0, len(d), size=(BOOT_N, len(d)))].mean(axis=1)
        out[name] = f"Δ = {d.mean():+.3f} (95%: {np.percentile(m, 2.5):+.3f} … {np.percentile(m, 97.5):+.3f}; {len(d)} câu)"
    return out


def core_fingerprint(root: Path = DATAPACK_DIR) -> str:
    """Dấu vân tay corpus theo cách tính trong báo cáo ngày 1 của đội: SHA-256 của chuỗi nối mã SHA-256 của 6 file đầu vào
    (legal_chunks, document_metadata, citation_map, questions_sample, answer_key_sample, template), xếp theo đường dẫn."""
    files = [p for p in (resolve_file(k, root) for k in ("chunks", "documents", "citation_map", "questions", "answer_key",
                                                          "template")) if p is not None]
    rel = sorted((p.relative_to(root).as_posix(), p) for p in files)
    return hashlib.sha256("".join(hashlib.sha256(p.read_bytes()).hexdigest() for _, p in rel).encode()).hexdigest()


def run_manifest(pa: PolicyAssist, sets: dict[str, pd.DataFrame]) -> dict:
    """Hồ sơ lần chạy (báo cáo rà soát claim: mọi số liệu đi ngược được về lần chạy): run_id, mã nguồn, Data Pack, nhãn, cấu
    hình, môi trường."""
    import os
    import platform

    import sklearn
    import streamlit
    code = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    label_files = {"Dev-30": resolve_file("answer_key"), "Ext-60": EXT60_PATH, "Stress-60": STRESS60_PATH,
                   "Probe-25": PROBE_PATH, "Paraphrase-52": PARAPHRASE_PATH}
    return {
        "run_id": RUN["id"], "thời điểm": datetime.now().isoformat(timespec="seconds"), "phiên bản": APP_VERSION,
        "mã nguồn": {"file": Path(__file__).name, "sha256_12": code[:12]},
        "data_pack": {"phiên bản": DATAPACK_VERSION, "corpus_fingerprint (toàn bộ Data Pack, corpus_manifest)":
                      _FINGERPRINT["value"][:12], "corpus_fingerprint_core (6 file CSV, cách tính của đội)": core_fingerprint()[:12]},
        "nhãn": {k: {"file": str(p.relative_to(ROOT)) if p is not None and p.is_relative_to(ROOT) else str(p),
                     "sha256_12": hashlib.sha256(p.read_bytes()).hexdigest()[:12] if p is not None and p.exists() else "",
                     "số câu": len(sets.get(k, []))} for k, p in label_files.items()},
        "cấu hình": {k: v for k, v in asdict(pa.cfg).items() if k != "write_log"},
        "mô hình ngôn ngữ": "không dùng (BM25 + TF-IDF ký tự, trích xuất; pipeline tất định)",
        "môi trường": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
                       "scikit-learn": sklearn.__version__, "streamlit": streamlit.__version__,
                       "máy": platform.platform(), "cpu": os.cpu_count()},
    }


def run_demo_cases(pa: PolicyAssist) -> pd.DataFrame:
    """Kịch bản demo của đội: output thật (citation, độ tin cậy, latency, trace_id) để thay cột kỳ vọng khi rehearsal."""
    qs = pa.dp.questions.set_index("question_id")
    rows = []
    for case, qid, text, ref, exp, want in DEMO_CASES:
        q = qs.loc[qid, "question_text"] if qid else text
        res = pa.answer(q, ref, qid)
        got = set(res.cited_chunks) | {c.split("_")[0] for c in res.cited_chunks}
        lead = next((c.split(" – ")[0] for c in res.citations if c.startswith("LAW")), "")
        ok = res.decision == exp and (not want or (lead in _split(want) if case.startswith("B2") else
                                                   bool(set(_split(want)) & got)))
        rows.append({"case": case, "mã": qid or "tự đặt", "reference_date": ref, "câu hỏi": q, "hành vi kỳ vọng": exp,
                     "kỳ vọng": want, "quyết định": res.decision, "citations": "; ".join(res.citations),
                     "chunk được dẫn": ";".join(res.cited_chunks), "độ tin cậy": round(res.confidence, 3),
                     "latency_ms": res.latency_ms, "trace_id": res.trace_id, "khớp kỳ vọng": "Có" if ok else "Chưa"})
    return pd.DataFrame(rows)


def run_full_evaluation(pa: PolicyAssist, progress=None) -> dict:
    """Chạy hệ thống đầy đủ và B0 trên mọi tập có nhãn, ablation B0→B6 (+B2′) trên Public-90, kịch bản demo."""
    dp = pa.dp
    sets = load_eval_sets(dp)
    full, b0 = pa.with_config(write_log=False), pa.with_config(write_log=False, **SYSTEMS["B0 – BM25 thuần (baseline)"])
    runs = [k for k in sets if k != "Public-90"]
    total = 2 * sum(len(sets[k]) for k in runs) + (len(ABLATION_STEPS) - 2) * len(sets.get("Public-90", []))
    done = [0]

    def tick(label):
        done[0] += 1
        if progress and done[0] % 10 == 0:
            progress(done[0], total, label)

    per, res = {}, {}
    for name in runs:
        for tag, sysm in (("FULL", full), ("B0", b0)):
            per[(name, tag)], res[(name, tag)] = evaluate_labeled(sysm, sets[name], lambda n, t, q: tick(f"{name} · {tag}"))
    if "Public-90" in sets:
        for tag in ("FULL", "B0"):
            per[("Public-90", tag)] = pd.concat([per[("Dev-30", tag)], per[("Ext-60", tag)]], ignore_index=True)
    sysname = {"FULL": "CHRONOS-LEDGER", "B0": "B0 – BM25 thuần"}
    summary = pd.DataFrame([{"tập": name, "hệ thống": sysname[tag], **summarize_eval(per[(name, tag)])}
                            for name in EVAL_SETS for tag in ("FULL", "B0") if (name, tag) in per])
    by_scope = pd.concat([scope_breakdown(per[(name, "FULL")]).assign(tập=name) for name in EVAL_SETS
                          if (name, "FULL") in per], ignore_index=True)
    by_scope = by_scope[["tập"] + [c for c in by_scope.columns if c != "tập"]]
    tests = {name: paired_tests(per[(name, "FULL")], per[(name, "B0")]) for name in EVAL_SETS if (name, "FULL") in per}
    abl = []
    if "Public-90" in sets:
        for label, kw in ABLATION_STEPS.items():
            if kw["name"] in ("FULL", "B0"):
                df = per[("Public-90", "FULL" if kw["name"] == "FULL" else "B0")]
            else:
                sysm = pa.with_config(write_log=False, **kw)
                df = evaluate_labeled(sysm, sets["Public-90"], lambda n, t, q: tick(label))[0]
            s = summarize_eval(df)
            abl.append({"cấu hình": label, "Recall@5": s["recall_at_5"], "MRR@5": s["mrr"],
                        "Answer Correctness": s["answer_accuracy"], "Citation Accuracy": s["citation_accuracy"],
                        "Unsupported": s["unsupported_rate"], "Abstention P": s["abstention_precision"],
                        "Abstention R": s["abstention_recall"], "Abstention F1": s["abstention_f1"],
                        "Versioning": s["versioning_accuracy"], "Source Priority": s["source_priority"],
                        "quyết định đúng": s["quyết định đúng"], "latency TB (ms)": s["latency_ms_avg"]})
    rows = []
    for (name, tag), df in per.items():
        if tag != "FULL" or name == "Public-90":            # Public-90 = Dev-30 + Ext-60 (không lặp dòng)
            continue
        lab = sets[name].set_index("question_id")
        for r in df.to_dict("records"):
            q = lab.loc[r["question_id"]]
            rows.append({"tập": name, **r, "câu hỏi": q["question_text"], "đáp án tham chiếu": q["reference_answer"],
                         "grading_note": q["grading_note"]})
    results = pd.DataFrame(rows)
    errors = results[results["error"] != ""][
        ["tập", "question_id", "scope", "stress_type", "expected", "predicted", "error", "citations", "reason", "câu hỏi"]]
    return {"sets": sets, "per": per, "summary": summary, "by_scope": by_scope, "tests": tests,
            "ablation": pd.DataFrame(abl), "results": results, "errors": errors, "demo": run_demo_cases(full),
            "manifest": run_manifest(pa, sets)}


FULL_KPI_ROWS = [   # bảng KPI đầy đủ: (khóa trong summarize_eval, tên, hướng, mục tiêu, nguồn mục tiêu)
    ("recall_at_5", "1. Retrieval Recall@5", ">=", 0.80, "đề thi"),
    ("mrr", "   · MRR@5", "", None, ""),
    ("doc_recall_at_5", "   · Recall@5 theo văn bản", "", None, ""),
    ("answer_accuracy", "2. Answer Accuracy / Correctness (độ phủ ý chính)", ">=", 0.70, "đội"),
    ("answer_correctness", "   · thang 0 / 0,5 / 1 (tự động)", "", None, ""),
    ("citation_accuracy", "3. Citation Accuracy (đúng nhãn)", ">=", 0.80, "đề thi"),
    ("citation_valid_4", "   · citation đủ 4 điều kiện", "", None, ""),
    ("unsupported_rate", "4. Unsupported Answer Rate", "<=", 0.10, "đội"),
    ("abstention_f1", "5. Abstention Quality (F1)", ">=", 0.90, "đội"),
    ("abstention_precision", "   · Precision ABSTAIN", "", None, ""),
    ("abstention_recall", "   · Recall ABSTAIN", "", None, ""),
    ("versioning_accuracy", "6. Versioning Accuracy", ">=", 0.90, "đội"),
    ("latency_ms_avg", "7. Latency trung bình (ms)", "<=", 10000, "đề thi"),
    ("latency_ms_p95", "   · Latency p95 (ms)", "", None, ""),
    ("source_priority", "Chỉ số phụ: Source Priority (câu MIXED)", ">=", 0.85, "đội"),
    ("quyết định đúng", "Quyết định ANSWER/ABSTAIN đúng", "", None, ""),
]


def kpi_count(s: dict, key: str) -> str:
    """Số câu đúng / tổng cạnh tỷ lệ (vd. 10/12) – với chỉ số có điểm lẻ ghi tổng điểm / số câu."""
    if key == "abstention_f1":
        return f"TP {s['abstain_tp']} · FP {s['abstain_fp']} · FN {s['abstain_fn']}"
    if key in ("abstention_precision", "abstention_recall", "latency_ms_avg", "latency_ms_p95"):
        return f"{s['số câu']} câu" if key.startswith("latency") else ""
    n, tot = s.get(key + "_n", 0), s.get(key + "_sum", 0)
    if not n:
        return ""
    return f"{tot:g}/{n}"


def full_kpi_table(fe: dict) -> pd.DataFrame:
    """Bảng KPI dạng dài: mỗi (chỉ số, tập) một dòng – giá trị hệ thống, số câu, khoảng tin cậy 95%, B0, mục tiêu, đạt."""
    summ = fe["summary"]
    rows = []
    for key, name, op, target, src in FULL_KPI_ROWS:
        for set_name in EVAL_SETS:
            g = summ[summ["tập"] == set_name]
            if g.empty:
                continue
            s = g[g["hệ thống"] == "CHRONOS-LEDGER"].iloc[0].to_dict()
            b = g[g["hệ thống"] == "B0 – BM25 thuần"].iloc[0].to_dict()
            v = s.get(key, np.nan)
            v = np.nan if v is None or (isinstance(v, str) and not v) else float(v)
            met = "" if target is None or math.isnan(v) else ("Đạt" if (v >= target if op == ">=" else v <= target) else "Chưa đạt")
            rows.append({"chỉ số": name.strip(" ·"), "khóa": key, "tập": set_name, "giá trị": v,
                         "số câu": kpi_count(s, key), "CI 95%": s.get(key + "_ci", "") or "",
                         "B0": b.get(key, np.nan), "mục tiêu": "" if target is None else f"{'≥' if op == '>=' else '≤'} {target:g}",
                         "nguồn mục tiêu": src, "đánh giá": met})
    return pd.DataFrame(rows)


ROBUST_DESC = {"Ext-60": "60 câu public còn lại (nhãn đội)", "Paraphrase-52": "diễn đạt lại, viết tắt, ngoài phạm vi",
               "Probe-25": "thăm dò ngoài phạm vi, versioning mốc mới", "Stress-60": "kiểm thử chịu tải (đội viết; đã dùng phân tích lỗi từ 10/11/2026)"}


def public90_audit(fe: dict) -> pd.DataFrame:
    """Bảng đối chiếu 90 câu public (Dev-30 theo đáp án BTC, Ext-60 theo nhãn đội): quyết định, citation, mức khớp, độ phủ
    ý chính, kiểm chứng nguồn, câu trả lời và đáp án tham chiếu – dùng cho QA độc lập."""
    r = fe["results"]
    r = r[r["tập"].isin(["Dev-30", "Ext-60"])]
    cols = {"tập": "tập", "question_id": "question_id", "scope": "phạm vi", "expected": "hành vi kỳ vọng",
            "predicted": "quyết định", "citation_match": "đối chiếu citation", "citations": "citation hệ thống",
            "gold_citations": "citation đáp án/nhãn", "answer_accuracy": "độ phủ ý chính", "unsupported": "thiếu căn cứ",
            "versioning_correct": "đúng phiên bản", "error": "loại lỗi", "trace_id": "trace_id", "câu hỏi": "câu hỏi",
            "answer": "câu trả lời", "đáp án tham chiếu": "đáp án tham chiếu"}
    return r[[c for c in cols if c in r]].rename(columns=cols).reset_index(drop=True)


def robust_table(fe: dict) -> pd.DataFrame:
    """Độ bền ngoài đáp án mẫu của BTC (hệ thống đầy đủ): Ext-60, Paraphrase-52, Probe-25, Stress-60."""
    s = fe["summary"]
    rows = []
    for name, desc in ROBUST_DESC.items():
        g = s[(s["tập"] == name) & (s["hệ thống"] == "CHRONOS-LEDGER")]
        if g.empty:
            continue
        r = g.iloc[0]
        rows.append({"tập": f"{name} – {desc}", "số câu": int(r["số câu"]), "quyết định đúng": r["quyết định đúng"],
                     "căn cứ đúng trong top-5": r["hit_at_5"], "citation [1] đúng": r["citation_first"],
                     "có citation đúng": r["citation_any"], "độ chính xác citation": r["citation_accuracy"],
                     "versioning": r["versioning_accuracy"]})
    return pd.DataFrame(rows)


def _fmt3(v) -> str:
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{float(v):.3f}"


def run_evaluation(pa: PolicyAssist, progress=None) -> dict:
    dp = pa.dp
    RUN["id"] = f"RUN-{datetime.now():%Y%m%d-%H%M%S}-{hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:6]}"
    key, probe = dp.answer_key, load_probe()
    dev_q = dp.questions[dp.questions.question_id.isin(key.question_id)]
    summaries, per_q = [], {}
    steps = len(SYSTEMS) + 2
    for n, (label, kw) in enumerate(SYSTEMS.items(), 1):
        sysm = pa.with_config(write_log=False, **kw)
        _, dev_res = run_batch(sysm, dev_q)
        _, probe_res = run_batch(sysm, probe)
        df, s = evaluate_system(dev_res, probe_res, dp, probe)
        summaries.append({"hệ thống": label, **s})
        per_q[label] = df
        if progress:
            progress(n, steps, label)
    # toàn bộ 90 câu public (không cần đáp án): hiệu lực citation, latency, số câu ABSTAIN
    full = pa.with_config(write_log=False)
    sub, all_res = run_batch(full, dp.questions)
    cits = [(c, x) for x in all_res for c in x.cited_chunks]
    # citation hợp lệ về thời gian: chunk còn hiệu lực tại mốc, hoặc dẫn như văn bản lịch sử trong câu VERSIONING
    valid_time = [dp.chunk_state(dp.idx[c], parse_date(x.applied_date)) in USABLE or x.intent == "VERSIONING" for c, x in cits]
    lat = [x.latency_ms for x in all_res]
    public = {"n_questions": len(all_res), "answered": sum(not x.abstain for x in all_res),
              "abstained": sum(x.abstain for x in all_res),
              "abstained_ids": ", ".join(x.question_id for x in all_res if x.abstain),
              "citation_in_citation_map": round(float(np.mean([c in dp.label for c, _ in cits])), 3) if cits else np.nan,
              "citation_valid_at_reference_date": round(float(np.mean(valid_time)), 3) if cits else np.nan,
              "latency_ms_avg": round(float(np.mean(lat)), 1), "latency_ms_p95": round(float(np.percentile(lat, 95)), 1),
              "latency_ms_max": int(max(lat))}
    if progress:
        progress(len(SYSTEMS) + 1, steps, "90 câu public")
    fe = run_full_evaluation(pa, (lambda n, t, lab: progress(len(SYSTEMS) + 1 + n / t, steps, lab)) if progress else None)
    robust = robust_table(fe)
    if progress:
        progress(steps, steps, "Dev-30 · Ext-60 · Stress-60 · Probe-25 · Paraphrase-52 · ablation B0→B6")
    summary = pd.DataFrame(summaries)
    fs = summary.set_index("hệ thống").loc[FULL_SYSTEM]
    all_lat = list(per_q[FULL_SYSTEM].latency_ms) + lat
    fsum = fe["summary"]
    dev = fsum[(fsum["tập"] == "Dev-30") & (fsum["hệ thống"] == "CHRONOS-LEDGER")].iloc[0].to_dict()
    n_ans = int(fs["n_answered"])
    extra = {   # chỉ số kèm hiển thị dưới mỗi ô KPI – cùng tập Dev-30 + Probe-25 với giá trị chính
        "recall_at_5": f"MRR@5 {_fmt3(dev['mrr'])} (1 = đoạn đúng luôn đứng đầu) · Recall@5 theo văn bản {_fmt3(dev['doc_recall_at_5'])}",
        "answer_accuracy": f"Thang 0 / 0,5 / 1: {_fmt3(fs['answer_correctness'])} (26 câu ANSWER, chấm tự động)",
        "citation_accuracy": f"{float(dev['citation_valid_4']):.0%} citation đạt đủ 4 điều kiện kiểm tra",
        "unsupported_rate": f"{int(fs['n_unsupported'])}/{n_ans} câu trả lời có nội dung thiếu căn cứ",
        "abstention_f1": f"Từ chối đúng {int(fs['abstain_tp'])}/{int(fs['abstain_tp']) + int(fs['abstain_fn'])} câu cần từ chối · "
                         f"từ chối nhầm {int(fs['abstain_fp'])} (P {_fmt3(fs['abstain_precision'])} · R {_fmt3(fs['abstain_recall'])})",
        "versioning_accuracy": f"Đúng {int(fs['versioning_ok'])}/{int(fs['n_versioning'])} câu hỏi phiên bản",
        "latency_ms_avg": f"p95 {np.percentile(all_lat, 95):.0f} ms · {len(all_lat)} lượt đo",
    }
    kpis = []
    for k, name, op, target, src in KPI_SPECS:
        v = round(float(np.mean(all_lat)), 1) if k == "latency_ms_avg" else fs[k]
        b0 = summary.set_index("hệ thống").loc["B0 – BM25 thuần (baseline)"][k]
        kpis.append({"KPI": name, "giá trị": v, "mục tiêu": f"{op} {target}", "nguồn mục tiêu": src,
                     "đạt": "✅ Đạt" if kpi_status(k, v) else "⚠️ Chưa đạt", "baseline B0": b0, "cách đo": KPI_DEFINITIONS[k],
                     "chỉ số kèm": extra.get(k, "")})
    return {"summary": summary, "per_question": per_q, "public": public, "kpis": pd.DataFrame(kpis), "submission": sub,
            "robust": robust, "full": fe, "run_id": RUN["id"]}


def md_table(df: pd.DataFrame, index: bool = False) -> list[str]:
    d = df.reset_index() if index else df

    def cell(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return "—"
        if isinstance(v, float):
            return f"{v:.3f}"
        return str(v).replace("|", "/").replace("\n", " ")
    out = ["| " + " | ".join(str(c) for c in d.columns) + " |", "|" + "---|" * len(d.columns)]
    return out + ["| " + " | ".join(cell(v) for v in r) + " |" for r in d.itertuples(index=False)]


def kpi_wide(fe: dict, system: str = "CHRONOS-LEDGER", counts: bool = True) -> pd.DataFrame:
    """Bảng KPI: hàng = chỉ số, cột = tập đánh giá; ô = giá trị (số câu đúng/tổng)."""
    t = full_kpi_table(fe) if system == "CHRONOS-LEDGER" else None
    summ = fe["summary"]
    sets = [s for s in EVAL_SETS if s in set(summ["tập"])]
    rows = []
    for key, name, op, target, src in FULL_KPI_ROWS:
        row = {"Chỉ số": name.strip()}
        for s in sets:
            g = summ[(summ["tập"] == s) & (summ["hệ thống"] == system)]
            v = g.iloc[0].get(key, np.nan) if len(g) else np.nan
            v = np.nan if v is None or (isinstance(v, str) and not v) else float(v)
            txt = "—" if math.isnan(v) else (f"{v:,.0f}".replace(",", ".") if key.startswith("latency") else f"{v:.3f}")
            if counts and t is not None and not math.isnan(v):
                c = t[(t["khóa"] == key) & (t["tập"] == s)]["số câu"]
                if len(c) and c.iloc[0] and not key.startswith(("latency", "abstention_f1")):
                    txt += f" ({c.iloc[0]})"
            row[s] = txt
        row["Mục tiêu"] = "" if target is None else f"{'≥' if op == '>=' else '≤'} {target:g} ({src})"
        rows.append(row)
    return pd.DataFrame(rows)


def write_eval_report(ev: dict, fp: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ev["summary"].to_csv(OUTPUT_DIR / "eval_summary.csv", index=False, encoding="utf-8-sig")
    ev["kpis"].to_csv(OUTPUT_DIR / "kpi_7.csv", index=False, encoding="utf-8-sig")
    ev["per_question"][FULL_SYSTEM].to_csv(OUTPUT_DIR / "eval_per_question.csv", index=False, encoding="utf-8-sig")
    if len(ev.get("robust", [])):
        ev["robust"].to_csv(OUTPUT_DIR / "robustness.csv", index=False, encoding="utf-8-sig")
    fe = ev.get("full")
    if fe:
        kt = full_kpi_table(fe)
        kt.to_csv(OUTPUT_DIR / "kpi_table.csv", index=False, encoding="utf-8-sig")
        fe["summary"].to_csv(OUTPUT_DIR / "eval_by_set.csv", index=False, encoding="utf-8-sig")
        fe["by_scope"].to_csv(OUTPUT_DIR / "eval_by_scope.csv", index=False, encoding="utf-8-sig")
        fe["results"].to_csv(OUTPUT_DIR / "eval_results_all.csv", index=False, encoding="utf-8-sig")
        fe["errors"].to_csv(OUTPUT_DIR / "error_table.csv", index=False, encoding="utf-8-sig")
        fe["ablation"].to_csv(OUTPUT_DIR / "ablation_B0_B6.csv", index=False, encoding="utf-8-sig")
        fe["demo"].to_csv(OUTPUT_DIR / "demo_cases.csv", index=False, encoding="utf-8-sig")
        public90_audit(fe).to_csv(OUTPUT_DIR / "public90_audit.csv", index=False, encoding="utf-8-sig")
        (OUTPUT_DIR / "run_manifest.json").write_text(json.dumps(fe["manifest"], ensure_ascii=False, indent=2), encoding="utf-8")

    def fmt(v):
        return "" if (isinstance(v, float) and math.isnan(v)) else str(v)

    man = fe["manifest"] if fe else {}
    lines = [f"# Báo cáo đánh giá – {APP_NAME} ({APP_VERSION})", "",
             f"- Mã lần chạy (run_id): `{ev.get('run_id', '')}` · thời điểm {datetime.now():%d/%m/%Y %H:%M}",
             f"- Data Pack: {DATAPACK_VERSION} · corpus fingerprint `{fp[:12]}` (toàn bộ Data Pack, corpus_manifest) · "
             f"`{man.get('data_pack', {}).get('corpus_fingerprint_core (6 file CSV, cách tính của đội)', '')}` "
             "(6 file CSV, cách tính trong báo cáo ngày 1 của đội) – cùng một bộ dữ liệu.",
             f"- Mã nguồn `{Path(__file__).name}` sha256 `{man.get('mã nguồn', {}).get('sha256_12', '')}` · không dùng mô hình "
             "ngôn ngữ (pipeline tất định: chạy lại cho cùng kết quả, trừ latency) · hồ sơ đầy đủ: `outputs/run_manifest.json`.",
             "- Đo trên bộ câu hỏi mẫu của BTC và bộ câu do đội gán nhãn/tự viết, không phải người dùng thật.", ""]
    if fe:
        lines += ["## 1. Tập đánh giá", ""] + [f"- **{k}** ({len(fe['sets'][k])} câu): {v}" for k, v in EVAL_SETS.items()
                                               if k in fe["sets"]]
        lines += ["", "## 2. Bảng KPI theo tập – hệ thống CHRONOS-LEDGER", "",
                  "Ô = giá trị (tổng điểm hoặc số câu đúng / số câu được tính). Recall@5, Answer Correctness: câu nhãn ANSWER "
                  "(câu bị ABSTAIN tính 0). Citation: câu nhãn ANSWER đã trả lời. Unsupported: mọi câu đã trả lời. Abstention: "
                  "toàn bộ tập (ABSTAIN là lớp dương). Versioning: câu VERSIONING. Source Priority: câu MIXED.", ""]
        lines += md_table(kpi_wide(fe)) + [""]
        lines += ["### Cách đo", ""] + [f"- **{n.split('. ', 1)[-1]}**: {KPI_DEFINITIONS[k]}" for k, n, *_ in KPI_SPECS]
        lines += [f"- **MRR@5**: trung bình 1/hạng của chunk chính đầu tiên trong retrieved_chunk_ids (không có → 0). "
                  "**Recall@5 theo văn bản**: |văn bản đáp án ∩ văn bản của 5 chunk đầu| / |văn bản đáp án|.",
                  "- **Citation đủ 4 điều kiện**: (a) có trong citation_map.csv; (b) ứng với chunk đã truy xuất; (c) chunk "
                  "chứa căn cứ cho mọi câu gắn citation (≥ 90% từ); (d) còn hiệu lực tại reference_date (hoặc dẫn như văn bản "
                  "lịch sử trong câu hỏi phiên bản) – kiểm tự động trên 100% citation.",
                  "- **Source Priority** (chỉ số phụ, câu MIXED): có căn cứ pháp luật còn hiệu lực; pháp luật đứng trước nội "
                  "bộ; không dùng văn bản hết hiệu lực/hợp nhất làm căn cứ; nội bộ dẫn luật cũ thì phải dẫn văn bản kế nhiệm "
                  "hoặc cảnh báo.",
                  f"- **Answer Correctness** (độ phủ ý chính và thang 0 / 0,5 / 1) trên Stress-60 chỉ chấm tự động các kiểu "
                  f"giữ nguyên đáp án câu gốc ({', '.join(sorted(SAME_ANSWER_STRESS))}); các kiểu còn lại cần chấm tay theo "
                  "ghi_chu (cột grading_note trong outputs/eval_results_all.csv).", ""]
        lines += ["## 3. Baseline B0 (BM25 thuần) trên cùng các tập", ""]
        lines += md_table(kpi_wide(fe, "B0 – BM25 thuần", counts=False)) + [""]
        lines += ["### Kiểm định ghép cặp CHRONOS-LEDGER so với B0", "",
                  "McNemar chính xác cho quyết định đúng/sai từng câu (+ = câu chỉ hệ thống đúng, − = câu chỉ B0 đúng); "
                  "bootstrap ghép cặp 2000 lần cho chênh lệch các chỉ số có điểm lẻ.", ""]
        tst = pd.DataFrame([{"tập": k, **v} for k, v in fe["tests"].items()])
        lines += md_table(tst) + [""]
        ci_keys = [("quyết định đúng", "Quyết định đúng"), ("recall_at_5", "Recall@5"),
                   ("answer_accuracy", "Answer Correctness"), ("citation_accuracy", "Citation Accuracy"),
                   ("unsupported_rate", "Unsupported"), ("abstention_f1", "Abstention F1"),
                   ("versioning_accuracy", "Versioning")]
        fs_ = fe["summary"][fe["summary"]["hệ thống"] == "CHRONOS-LEDGER"]
        ci = pd.DataFrame([{"tập": r["tập"], **{lab: (f"{_fmt3(r[k])} [{r.get(k + '_ci', '')}]" if r.get(k + "_ci") else _fmt3(r[k]))
                                                for k, lab in ci_keys}} for r in fs_.to_dict("records")])
        lines += ["## 4. Khoảng tin cậy 95% (bootstrap theo câu hỏi)", "",
                  "Với 60 câu, mỗi câu ≈ 1,7 điểm phần trăm; nhóm 6–14 câu VERSIONING mỗi câu 7–17 điểm – nên đọc kèm số câu.", ""]
        lines += md_table(ci) + [""]
        lines += ["## 5. Ablation thêm dần B0 → B6 (Public-90 = Dev-30 + Ext-60)", "",
                  "Mỗi dòng bật thêm một khối của pipeline so với dòng trước; B2′ thay CHRONOS bằng cách của pipeline tham "
                  "khảo (lọc cứng chunk không còn hiệu lực tại reference_date trước khi xếp hạng) để so hai cách xử lý phiên "
                  "bản. B6 là hệ thống nộp bài.", ""]
        lines += md_table(fe["ablation"]) + [""]
    cols = ["hệ thống"] + [k for k, *_ in KPI_SPECS] + ["citation_recall", "evidence_mismatch_rate", "decision_accuracy", "brier", "ece"]
    lines += ["## 6. Ablation bỏ từng thành phần (Dev-30 + Probe-25)", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in ev["summary"][cols].itertuples(index=False):
        lines.append("| " + " | ".join(fmt(v) for v in r) + " |")
    lines += ["", "## 7. KPI chính trên giao diện (Dev-30 – đáp án BTC + Probe-25)", "",
              "| KPI | Giá trị | Mục tiêu | Nguồn mục tiêu | Trạng thái | Baseline B0 | Chỉ số kèm |", "|---|---|---|---|---|---|---|"]
    for r in ev["kpis"].itertuples(index=False):
        lines.append(f"| {r.KPI} | {fmt(r[1])} | {r[2]} | {r[3]} | {r[4]} | {fmt(r[5])} | {r[7]} |")
    if fe:
        lines += ["", "## 8. KPI tách theo answer_scope (hệ thống đầy đủ)", ""] + md_table(fe["by_scope"]) + [""]
        err = fe["errors"]
        lines += ["## 9. Bảng lỗi (retrieval / citation / abstain / versioning / generation)", "",
                  f"Chi tiết từng câu: `outputs/error_table.csv` ({len(err)} dòng) và `outputs/eval_results_all.csv`.", ""]
        if len(err):
            cnt = pd.crosstab(err["error"], err["tập"], margins=True, margins_name="Tổng")
            lines += md_table(cnt, index=True) + [""]
        au = public90_audit(fe)
        if len(au):
            lines += ["## 9b. Đối chiếu 90 câu public với đáp án", "",
                      "Dev-30 so với `answer_key_sample.csv` của BTC; Ext-60 so với nhãn đội. **khớp đủ** = mọi citation đúng và "
                      "có đủ citation của chunk chính; **đúng nhưng thiếu** = mọi citation đúng nhưng chưa đủ; **một phần** = có "
                      "citation đúng lẫn sai; **không khớp** = không citation nào đúng. Chi tiết từng câu (câu trả lời, đáp án "
                      "tham chiếu, trace_id): `outputs/public90_audit.csv`.", ""]
            lines += md_table(pd.crosstab(au["đối chiếu citation"], au["tập"], margins=True, margins_name="Tổng"), index=True)
            lines += [""]
        lines += ["## 10. Kịch bản demo – output thật", "",
                  "Dùng để thay cột kỳ vọng của demo script (ghi trace_id từng case).", ""]
        lines += md_table(fe["demo"].drop(columns=["câu hỏi"])) + [""]
    lines += ["## 11. Toàn bộ 90 câu public", ""] + [f"- {k}: {v}" for k, v in ev["public"].items()]
    rob = ev.get("robust")
    if rob is not None and len(rob):
        lines += ["", "## 12. Độ bền với câu hỏi ngoài đáp án mẫu (không dùng để tinh chỉnh)", ""] + md_table(rob)
    p = OUTPUT_DIR / "eval_report.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


# =============================================================================
# 8. GIAO DIỆN WEB (Streamlit) – xanh navy · hỏi đáp kiểu chat · lịch sử tra cứu theo ngày · panel nguồn trích dẫn
# =============================================================================
DOC_TYPE_VI = {"LAW": "Luật", "DECREE": "Nghị định", "CIRCULAR": "Thông tư", "CONSOLIDATED": "Văn bản hợp nhất",
               "POLICY": "Quy chế nội bộ", "PROCEDURE": "Quy trình nội bộ", "MATRIX_POLICY": "Ma trận phân quyền",
               "HANDBOOK": "Sổ tay nghiệp vụ", "FAQ": "FAQ nội bộ"}
DOC_ABBR = {"LAW": "Luật", "DECREE": "NĐ", "CIRCULAR": "TT", "CONSOLIDATED": "VBHN"}
PRIORITY_VI = {"1": "Luật", "2": "Nghị định", "3": "Thông tư", "4": "Quy chế, quy trình nội bộ", "5": "Sổ tay, FAQ nội bộ"}
WEEKDAY_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
STEP_LABELS = [("P0", "Kiểm tra"), ("P1", "Lập kế hoạch"), ("P2", "Tìm kiếm"), ("P3", "Phiên bản"), ("P4", "Xếp hạng"),
               ("P5", "Bằng chứng"), ("P6", "Soạn"), ("P7", "Kiểm citation"), ("P8", "Độ tin cậy")]
FEATURED_SAMPLES = ("Q042", "Q059", "Q028", "Q077")      # lối tắt "Thử nhanh" (chỉ chọn câu mẫu, không cố định đáp án)
# logo: biểu tượng cán cân (chính sách – pháp luật), nét theo bộ icon Lucide "scale" (giấy phép ISC). Đưa vào CSS dạng
# ảnh nền vì st.html lọc bỏ thẻ <svg>.
LOGO_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#14284B" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>'
            '<path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>')
LOGO_CSS = ("<style>.pa-brand .logo{background:#fff url('data:image/svg+xml;base64,"
            + base64.b64encode(LOGO_SVG.encode("utf-8")).decode("ascii") + "') center/26px 26px no-repeat;}</style>")
NOT_CODES = {"LAW", "SIM", "FAQ", "BTC", "CNTT", "USD", "VND", "XML", "PDF", "MST", "GTGT", "TNCN", "TNDN", "BCTC",
             "VBHN", "CASE", "ABSTAIN", "ANSWER", "RAG", "ID"}
# tô đậm thông tin quan trọng trong câu trả lời
EMPH_RE = re.compile(
    r"(?P<doc>\b\d{1,4}/\d{4}/[A-ZĐ]{2,}(?:-[A-ZĐ]+)*\b|\b(?:LAW|SIM)\d{2}\b)"
    r"|(?P<date>\b\d{1,2}/\d{1,2}/\d{4}\b)"
    r"|(?P<num>\b\d+(?:[.,]\d+)*\s*(?:%|phần trăm|ngày làm việc|ngày|tháng|năm|giờ|triệu đồng|đồng(?:/[^\s,.;:]+)*|lần)(?!\w))"
    r"|(?P<code>\b[A-Z]{3,}(?:_[A-Z0-9]+)*\b)"
    r"|(?P<must>\b(?:không được phép|không được|nghiêm cấm|chậm nhất|không vượt quá|tối đa|tối thiểu|"
    r"không cho phép)\b)")

# Ô tìm kiếm lịch sử (component v2 của Streamlit): gửi từ khóa sau MỖI lần gõ, kể cả khi bộ gõ tiếng Việt đang ghép chữ
# (st.text_input đợi bộ gõ ghép xong cả từ mới gửi); trễ 90 ms để không gửi dồn. Hàm JS được gọi lại mỗi lần vẽ lại nên giữ
# nguyên ô nhập (không mất con trỏ) và không huỷ lần gửi đang chờ.
SEARCH_BOX_HTML = ('<label class="pa-search"><span class="pa-ic" aria-hidden="true">search</span>'
                   '<input type="text" placeholder="Tìm phiên, câu hỏi, câu trả lời…" aria-label="Tìm trong lịch sử tra cứu" '
                   'autocomplete="off" spellcheck="false"><button class="clr pa-ic" type="button" aria-label="Xoá từ khóa" '
                   'title="Xoá từ khóa" hidden>close</button></label>')
SEARCH_BOX_JS = """
export default function (component) {
  const { parentElement, setStateValue, data } = component;
  const input = parentElement.querySelector("input");
  const clear = parentElement.querySelector(".clr");
  input._paSet = setStateValue;
  if (input._paSent === undefined) {          // ô vừa được tạo (lần đầu hoặc sidebar mở lại): khôi phục từ khóa đang tìm
    input._paSent = (data && data.query) || "";
    if (!input.value) input.value = input._paSent;
  }
  const send = (delay) => {
    clearTimeout(input._paTimer);
    input._paTimer = setTimeout(() => {
      if (input.value !== input._paSent) { input._paSent = input.value; input._paSet("query", input.value); }
    }, delay);
  };
  const sync = () => { clear.hidden = !input.value; send(90); };
  const onKey = (e) => { if (e.key === "Escape" && input.value) { input.value = ""; sync(); } };
  const onClear = () => { input.value = ""; sync(); input.focus(); };
  input.addEventListener("input", sync);
  input.addEventListener("keydown", onKey);
  clear.addEventListener("click", onClear);
  clear.hidden = !input.value;
  if (input.value !== input._paSent) send(0);
  return () => {
    input.removeEventListener("input", sync);
    input.removeEventListener("keydown", onKey);
    clear.removeEventListener("click", onClear);
  };
}
"""

UI_CSS = """<style>
:root{--pa-navy:#14284B;--pa-navy2:#1E3A6E;--pa-ink:#14213D;--pa-muted:#5B6578;--pa-line:#DCE3EE;--pa-soft:#F3F6FB;
--pa-legal:#1F4FA3;--pa-legal-bg:#EEF3FC;--pa-legal-line:#C9D7F1;--pa-int:#5B3E92;--pa-int-bg:#F6F2FC;--pa-int-line:#DED2F1;
--pa-ok:#17663F;--pa-ok-bg:#E2F4EA;--pa-warn:#8A4205;--pa-warn-bg:#FFF5E5;--pa-warn-line:#F1CF96;
--pa-bad:#A3300F;--pa-bad-bg:#FFF3EE;--pa-bad-line:#F4B39E;--pa-gold:#F2B544;--pa-mark:#FFE7A0;}
html,body,[data-testid="stApp"]{color:var(--pa-ink);}
[data-testid="stMainBlockContainer"]{padding:4.3rem 1.5rem .5rem;max-width:1720px;}
[data-testid="stHeader"]{background:#FFFFFFF2;border-bottom:1px solid var(--pa-line);}
h1,h2,h3{color:var(--pa-navy);}
/* ---------- sidebar ---------- */
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0E1F44 0%,#14284B 100%);}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{padding-top:.4rem;}
.pa-brand{display:flex;align-items:center;gap:12px;padding:2px 2px 10px;}
.pa-brand .logo{width:44px;height:44px;border-radius:12px;background:#fff;color:var(--pa-navy);display:flex;align-items:center;
 justify-content:center;flex:none;box-shadow:0 0 0 3px #F2B54466;}
.pa-brand .logo svg{width:26px;height:26px;}
/* lịch sử: mỗi phiên một hàng = nút mở phiên + menu ⋮ (Ghim / Đổi tên / Xoá) hiện khi rê chuột, như Gemini */
[class*="st-key-hrow-"]{background:#FFFFFF10;border:1px solid #FFFFFF14;border-radius:10px;padding-right:3px;}
[class*="st-key-hrow-"]:hover{background:#FFFFFF22;border-color:#FFFFFF30;}
[class*="st-key-hrow-"]:has([data-testid="stBaseButton-primary"]){background:#fff;border-color:#fff;}
[class*="st-key-hmenu-"] button{background:transparent!important;border:none!important;min-height:30px!important;
 width:30px;padding:0!important;border-radius:8px;opacity:0;}
[class*="st-key-hrow-"]:hover [class*="st-key-hmenu-"] button,[class*="st-key-hmenu-"] button:focus-visible,
[class*="st-key-hrow-"]:has([data-testid="stBaseButton-primary"]) [class*="st-key-hmenu-"] button{opacity:1;}
@media (hover:none){[class*="st-key-hmenu-"] button{opacity:1;}}
[class*="st-key-hmenu-"] button:hover{background:#FFFFFF24!important;}
[class*="st-key-hmenu-"] button p{font-size:19px;font-weight:700;color:#DCE5F7!important;line-height:1;}
[class*="st-key-hrow-"]:has([data-testid="stBaseButton-primary"]) [class*="st-key-hmenu-"] button:hover{background:#E8EEF8!important;}
[class*="st-key-hrow-"]:has([data-testid="stBaseButton-primary"]) [class*="st-key-hmenu-"] button p{color:var(--pa-navy)!important;}
[class*="st-key-hmenu-"] button [data-testid="stIconMaterial"]{display:none;}
[data-testid="stPopoverBody"]:has([class*="st-key-hm-"]){background:#fff!important;width:200px!important;min-width:200px;
 padding:6px!important;}
[data-testid="stPopoverBody"]:has([class*="st-key-hm-"]) [data-testid="stVerticalBlock"]{gap:2px;}
[class*="st-key-hm-"] button{justify-content:flex-start!important;padding:7px 10px!important;border-radius:8px;}
[class*="st-key-hm-"] button>div{justify-content:flex-start!important;}
[class*="st-key-hm-"] button:hover{background:#EEF2F8!important;}
[class*="st-key-hm-"] button p,[class*="st-key-hm-"] button [data-testid="stIconMaterial"]{color:#14213D!important;font-size:14px;}
[class*="st-key-hm-delete-"] button p,[class*="st-key-hm-delete-"] button [data-testid="stIconMaterial"]{color:#B42318!important;}
/* icon Material Symbols trong phần HTML (hàm ic) */
.pa-ic{font-family:"Material Symbols Rounded";font-weight:normal;font-style:normal;font-size:1.15em;line-height:1;
 letter-spacing:normal;text-transform:none;display:inline-block;white-space:nowrap;direction:ltr;vertical-align:-.2em;
 margin-right:4px;-webkit-font-feature-settings:"liga";font-feature-settings:"liga";-webkit-font-smoothing:antialiased;}
.pa-pill .pa-ic{font-size:15px;margin-right:0;}
.pa-alert .ico .pa-ic{font-size:24px;margin:0;}
/* ô tìm kiếm lịch sử (component: tìm theo từng ký tự gõ) */
.pa-search{display:flex;align-items:center;gap:8px;min-height:42px;padding:0 6px 0 11px;border:1px solid #FFFFFF33;
 border-radius:10px;background:#FFFFFF14;cursor:text;}
.pa-search:focus-within{border-color:#F2B544;background:#FFFFFF1C;}
.pa-search .pa-ic{font-size:20px;color:#B5C4E6;margin:0;}
.pa-search input{flex:1;min-width:0;border:0;outline:0;background:transparent;color:#F3F6FB;font:inherit;font-size:14px;
 padding:9px 0;}
.pa-search input::placeholder{color:#B5C4E6;opacity:1;}
.pa-search .clr{border:0;background:transparent;cursor:pointer;padding:3px;border-radius:6px;}
.pa-search .clr:hover{background:#FFFFFF1F;color:#fff;}
.pa-search .clr[hidden]{display:none;}
[class*="st-key-hist-"] .stMarkdownColoredBackground{background:#F2B544!important;color:#14213D!important;padding:0 2px;
 border-radius:3px;}
[class*="st-key-hist-"] button p:nth-of-type(2):not(:last-of-type){font-size:12.5px;opacity:.92;line-height:1.4;}
.pa-dlg-text{font-size:14.5px;line-height:1.55;color:var(--pa-ink);}
.st-key-del-ok button{background:#B42318!important;border-color:#B42318!important;color:#fff!important;}
.st-key-del-ok button:hover{background:#912018!important;border-color:#912018!important;}
.pa-brand b{display:block;color:#fff;font-size:17px;letter-spacing:.01em;}
.pa-brand span{display:block;color:#BFD0F2;font-size:12px;}
.pa-side-label{color:#BFD0F2;font-size:11.5px;font-weight:700;letter-spacing:.09em;margin:14px 2px 2px;}
.pa-day{color:#9FB4E2;font-size:12px;margin:10px 2px 0;}
.pa-side-empty{color:#BFD0F2;font-size:13px;line-height:1.5;padding:8px 10px;border:1px dashed #3B5590;border-radius:10px;}
.st-key-new_sess button{background:var(--pa-gold)!important;color:#14213D!important;border:none!important;font-weight:700;
 min-height:46px;border-radius:12px;font-size:15px;}
.st-key-new_sess button:hover{background:#FFC95E!important;}
[class*="st-key-hist-"] button{justify-content:flex-start;text-align:left;background:transparent!important;border:none!important;
 color:#E8EEFA!important;padding:7px 4px 7px 11px!important;min-height:0;border-radius:10px;}
[class*="st-key-hist-"] button [data-testid="stMarkdownContainer"]{text-align:left;width:100%;}
[class*="st-key-hist-"] button p{display:block;margin:0;font-size:13.5px;font-weight:600;line-height:1.35;white-space:normal;}
[class*="st-key-hist-"] button p + p{font-size:12px;font-weight:400;opacity:.78;margin-top:2px;}
[class*="st-key-hist-"] button[data-testid="stBaseButton-primary"]{color:var(--pa-navy)!important;}
/* ---------- tiêu đề trang ---------- */
.pa-h1{font-size:25px;font-weight:800;color:var(--pa-navy);line-height:1.2;}
.pa-h1-sub{font-size:13.5px;color:var(--pa-muted);margin-top:2px;}
.pa-chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:flex-end;}
.pa-chip{padding:6px 11px;border-radius:999px;font-size:12.5px;font-weight:600;background:#E8EEF8;color:var(--pa-navy2);white-space:nowrap;}
.pa-chip.gold{background:#FFF1D2;color:#7A4B00;}
.pa-chip.ok{background:var(--pa-ok-bg);color:var(--pa-ok);}
.pa-chip.bad{background:#FDE7E3;color:#A3300F;}
/* ---------- vùng hội thoại ---------- */
[data-testid="stLayoutWrapper"]:has(> .st-key-chatlog){flex:0 0 auto!important;height:max(320px,calc(100vh - 300px))!important;}
[data-testid="stLayoutWrapper"]:has(> .st-key-srcpanel){flex:0 0 auto!important;height:max(480px,calc(100vh - 150px))!important;}
.st-key-chatlog,.st-key-srcpanel{height:100%!important;}
.st-key-chatlog{background:var(--pa-soft);border:1px solid var(--pa-line)!important;border-radius:16px!important;padding:4px 6px!important;}
.st-key-srcpanel{background:#fff;border:1px solid var(--pa-line)!important;border-radius:16px!important;}
.pa-meta{display:flex;flex-wrap:wrap;align-items:center;gap:8px;font-size:12.5px;color:var(--pa-muted);margin:6px 2px 0;}
.pa-meta b{color:var(--pa-ink);}
.pa-meta .from-q{color:var(--pa-warn);font-weight:600;}
.pa-pill{display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:999px;font-size:11.5px;font-weight:700;white-space:nowrap;}
.pa-pill.ok{background:var(--pa-ok-bg);color:var(--pa-ok);}
.pa-pill.warn{background:#FDE7E3;color:#B42318;}
.pa-pill.amber{background:var(--pa-warn-bg);color:var(--pa-warn);}
.pa-pill.abs{background:#FFE6DD;color:var(--pa-bad);}
.pa-pill.sample{background:#E3EAF8;color:var(--pa-navy2);}
.pa-pill.ext{background:#ECEEF3;color:#4A5466;}
.pa-qwrap{display:flex;flex-direction:column;align-items:flex-end;gap:4px;margin:2px 0 0;}
.pa-bubble{max-width:88%;background:var(--pa-navy);color:#fff;padding:11px 15px;border-radius:16px 16px 4px 16px;font-size:15px;
 line-height:1.55;white-space:pre-wrap;box-shadow:0 2px 6px #14284B26;}
.pa-rewrite{font-size:12px;color:var(--pa-muted);max-width:88%;text-align:right;}
.pa-rewrite .pa-abbr{display:block;margin-top:2px;font-size:11.5px;}
[class*="st-key-card-"]{background:#fff;border:1px solid var(--pa-line);border-radius:16px;padding:14px 16px 12px;
 box-shadow:0 1px 3px #14284B12;gap:.65rem!important;}
[class*="st-key-card-"].abs,[class*="st-key-cardx-"]{border:2px dashed var(--pa-bad-line);}
[class*="st-key-cardx-"]{background:#fff;border-radius:16px;padding:14px 16px 12px;gap:.65rem!important;}
.pa-steps{display:flex;flex-wrap:wrap;align-items:center;gap:3px;}
.pa-steps-lbl{font-size:10.5px;font-weight:700;letter-spacing:.06em;color:#8A93A5;text-transform:uppercase;margin-right:4px;}
.pa-steps .stp{padding:1px 6px;border-radius:5px;font-size:10.5px;font-weight:700;cursor:help;line-height:1.6;}
.stp.done{background:var(--pa-ok-bg);color:var(--pa-ok);}
.stp.stop{background:#FF7A55;color:#fff;}
.stp.skip{background:#EEF0F5;color:#A0A8B8;}
.pa-lbl{font-size:11.5px;font-weight:800;letter-spacing:.07em;color:#45506A;}
.pa-concl{background:#F6F8FC;border:1px solid #E2E8F2;border-radius:12px;padding:10px 14px;}
.pa-concl p{margin:4px 0 0;font-size:17px;line-height:1.55;font-weight:700;color:var(--pa-ink);}
.pa-concl ol{margin:4px 0 0;padding-left:20px;font-size:16px;line-height:1.55;font-weight:700;}
.pa-ref{display:inline-block;margin-left:3px;padding:0 5px;border-radius:5px;background:#E3EAF8;color:var(--pa-navy2);
 font-size:11.5px;font-weight:700;vertical-align:2px;font-family:ui-monospace,Consolas,monospace;}
[class*="st-key-blkL-"],[class*="st-key-blkI-"],[class*="st-key-blkV-"]{border-radius:12px;padding:11px 14px 10px;gap:.45rem!important;}
[class*="st-key-blkL-"],[class*="st-key-blkV-"]{background:var(--pa-legal-bg);border:1px solid var(--pa-legal-line);}
[class*="st-key-blkI-"]{background:var(--pa-int-bg);border:1px solid var(--pa-int-line);}
.pa-bhead{display:flex;flex-wrap:wrap;align-items:center;gap:8px;}
.pa-bhead .pa-lbl.law{color:var(--pa-legal);}
.pa-bhead .pa-lbl.int{color:var(--pa-int);}
.pa-sim-tag{padding:2px 8px;border-radius:6px;background:#E7DCF6;color:#4A2F7A;font-size:11.5px;font-weight:600;}
.pa-claim{margin:4px 0 0;font-size:14.8px;line-height:1.62;}
.pa-claim .ln{padding:1px 0 1px 0;}
.pa-claim .ln.item{padding-left:2px;}
mark.pa-key{background:var(--pa-mark);color:inherit;padding:1px 3px;border-radius:4px;box-decoration-break:clone;-webkit-box-decoration-break:clone;}
.hl-doc{font-weight:700;color:var(--pa-navy2);}
.hl-date{font-weight:700;color:#7A3E00;}
.hl-num{font-weight:800;color:#0F4C8A;background:#E5EEFC;padding:0 3px;border-radius:4px;}
.hl-code{font-family:ui-monospace,Consolas,monospace;font-size:.88em;font-weight:700;background:#EEF0F6;color:#2A3550;padding:1px 5px;border-radius:5px;}
.hl-must{font-weight:800;color:#9B1C1C;}
.pa-note{border-radius:12px;padding:11px 14px;font-size:14px;line-height:1.6;}
.pa-note.amber{background:var(--pa-warn-bg);border:1px solid var(--pa-warn-line);color:#3D2A10;}
.pa-note.amber .pa-lbl{color:var(--pa-warn);}
.pa-note.info{background:#F4F6FA;border:1px solid #E1E6EF;color:#3B4656;font-size:13px;}
.pa-note ul{margin:4px 0 0;padding-left:18px;}
.pa-alert{display:flex;gap:12px;background:#B42318;color:#fff;border-radius:12px;padding:12px 15px;}
.pa-alert b{display:block;font-size:15px;font-weight:800;}
.pa-alert span{font-size:14px;line-height:1.55;}
.pa-alert .ico{font-size:20px;line-height:1.2;}
.pa-alert .hl-doc,.pa-alert .hl-date,.pa-alert .hl-num,.pa-alert .hl-must{color:#FFE8A3;background:none;font-weight:800;}
.pa-tl .row{display:flex;gap:4px;margin-top:8px;}
.pa-tl .seg{flex:1 1 0;min-width:0;display:flex;flex-direction:column;gap:4px;font-size:12px;}
.pa-tl .seg .pin{height:20px;font-size:11.5px;font-weight:700;color:#B42318;white-space:nowrap;}
.pa-tl .seg .bar{height:10px;background:#C7D2E6;}
.pa-tl .seg:first-child .bar{border-radius:6px 0 0 6px;} .pa-tl .seg:last-child .bar{border-radius:0 6px 6px 0;}
.pa-tl .seg.on .bar{background:var(--pa-navy2);} .pa-tl .seg.ref .bar{background:repeating-linear-gradient(45deg,#E2C79A,#E2C79A 4px,#F5E6CB 4px,#F5E6CB 8px);}
.pa-tl .seg b{font-family:ui-monospace,Consolas,monospace;font-size:12.5px;color:var(--pa-ink);}
.pa-tl .seg span{color:#45506A;} .pa-tl .seg em{font-style:normal;color:var(--pa-muted);}
.pa-tl .seg.on em{color:var(--pa-navy2);font-weight:700;}
.pa-foot{display:flex;flex-wrap:wrap;align-items:center;gap:14px;font-size:13px;color:var(--pa-muted);}
.pa-foot b{color:var(--pa-ink);} .pa-foot .c-hi{color:var(--pa-ok);} .pa-foot .c-mid{color:var(--pa-warn);} .pa-foot .c-lo{color:#B42318;}
[class*="st-key-cL-"] button,[class*="st-key-cI-"] button,[class*="st-key-cV-"] button{min-height:32px;padding:2px 10px;border-radius:8px;
 font-family:ui-monospace,Consolas,monospace;}
[class*="st-key-cL-"] button p,[class*="st-key-cI-"] button p,[class*="st-key-cV-"] button p{font-size:12.5px;font-weight:600;}
[class*="st-key-cL-"] button[data-testid="stBaseButton-secondary"],[class*="st-key-cV-"] button[data-testid="stBaseButton-secondary"]
 {background:#fff;color:var(--pa-legal);border:1.5px solid #9DB5E4;}
[class*="st-key-cI-"] button[data-testid="stBaseButton-secondary"]{background:#fff;color:var(--pa-int);border:1.5px solid #C4B0EA;}
[class*="st-key-cL-"] button[data-testid="stBaseButton-primary"],[class*="st-key-cV-"] button[data-testid="stBaseButton-primary"]
 {background:var(--pa-legal);color:#fff;border:1.5px solid var(--pa-legal);}
[class*="st-key-cI-"] button[data-testid="stBaseButton-primary"]{background:#6A45B0;color:#fff;border:1.5px solid #6A45B0;}
[class*="st-key-fb-"] button{min-height:32px;padding:2px 12px;border-radius:9px;}
[class*="st-key-fb-"] button p{font-size:13px;}
[class*="st-key-sug-"] button,[class*="st-key-try-"] button{justify-content:flex-start;text-align:left;background:#EEF3FC;
 border:1px solid #CCD9F2;color:#183A75;border-radius:10px;padding:8px 12px;}
[class*="st-key-sug-"] button p,[class*="st-key-try-"] button p{font-size:14px;text-align:left;white-space:normal;}
[class*="st-key-sug-"] button>div,[class*="st-key-try-"] button>div,[class*="st-key-hist-"] button>div{justify-content:flex-start;width:100%;}
[class*="st-key-sug-"] button [data-testid="stMarkdownContainer"],[class*="st-key-try-"] button [data-testid="stMarkdownContainer"]
 {text-align:left;width:100%;}
[class*="st-key-sug-"] button:hover,[class*="st-key-try-"] button:hover{background:#E1EAFA;border-color:#9DB5E4;}
.pa-abs-title{font-size:19px;font-weight:800;line-height:1.45;margin:0;}
.pa-abs-sub{font-size:14.5px;line-height:1.6;color:#2E3555;margin:2px 0 0;}
.pa-abs-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px 14px;background:var(--pa-bad-bg);
 border-radius:12px;padding:11px 14px;margin:0;}
.pa-abs-grid dt{font-size:11.5px;font-weight:800;letter-spacing:.06em;color:var(--pa-bad);}
.pa-abs-grid dd{margin:3px 0 0;font-size:13.5px;line-height:1.5;}
.pa-welcome{background:#fff;border:1px solid var(--pa-line);border-radius:16px;padding:18px 20px;margin-top:6px;}
.pa-welcome h3{margin:0 0 6px;font-size:19px;}
.pa-welcome p{margin:0;color:#3B4656;font-size:14.5px;line-height:1.6;}
.pa-wgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-top:14px;}
.pa-wgrid div{background:var(--pa-soft);border-radius:12px;padding:10px 12px;font-size:13px;line-height:1.5;color:#3B4656;}
.pa-wgrid b{display:block;color:var(--pa-navy);font-size:14px;margin-bottom:2px;}
/* ---------- ô soạn câu hỏi ---------- */
.st-key-composer{background:#fff;border:1px solid #DCE2EC;border-radius:16px;padding:10px 12px 8px;gap:.35rem!important;
 box-shadow:0 2px 10px #14284B0F;}
.st-key-composer [data-testid="stForm"]{border:none;padding:0;}
.st-key-composer [data-baseweb="textarea"]{background:#F6F8FB!important;border:1px solid #E3E8F0!important;border-radius:12px!important;}
.st-key-composer textarea{font-size:15.5px;line-height:1.5;background:transparent!important;}
.st-key-send button{height:68px;min-width:96px;border-radius:12px;font-weight:700;font-size:15px;}
.st-key-daterow{padding:0 2px!important;}
.pa-dlab{font-size:13px;font-weight:700;color:#3B4656;white-space:nowrap;}
.pa-hint{font-size:12.5px;color:#6B7486;line-height:1.4;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.st-key-daterow [data-testid="stElementContainer"]:has(.pa-hint){min-width:0;flex:1 1 auto;}
.st-key-daterow [data-testid="stCheckbox"] label{white-space:nowrap;}
.pa-hint b{color:#3B4656;}
.st-key-daterow [data-testid="stDateInput"] input{font-weight:700;}
.st-key-daterow [data-testid="stCheckbox"] p{font-size:13.5px;font-weight:600;color:#3B4656;}
.st-key-samplepop button{min-height:34px;padding:2px 12px;background:#fff!important;border:1px solid #DCE2EC!important;border-radius:9px;}
.st-key-samplepop button p{color:#3B4656!important;font-weight:600;font-size:13px;}
[data-testid="stPopoverBody"]:has(.st-key-pick){width:min(720px,92vw)!important;max-width:min(720px,92vw)!important;}
/* ---------- panel nguồn ---------- */
.pa-src-h{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:2px 2px 8px;border-bottom:1px solid var(--pa-line);}
.pa-src-h b{font-size:15.5px;color:var(--pa-navy);}
.pa-src{display:flex;flex-direction:column;gap:12px;padding-top:10px;}
.pa-src .pills{display:flex;flex-wrap:wrap;gap:6px;}
.pa-src .pill{padding:3px 9px;border-radius:6px;font-size:11.5px;font-weight:700;}
.pill.law{background:#E3EAF8;color:var(--pa-legal);} .pill.sim{background:#E7DCF6;color:#4A2F7A;}
.pill.ok{background:var(--pa-ok-bg);color:var(--pa-ok);} .pill.warn{background:#FDE7E3;color:#B42318;}
.pill.muted{background:#EEF0F5;color:#4A5466;} .pill.amber{background:var(--pa-warn-bg);color:var(--pa-warn);}
.pa-src .lab{font-family:ui-monospace,Consolas,monospace;font-size:14px;font-weight:700;color:var(--pa-ink);}
.pa-src .hd{font-size:14px;font-weight:700;margin-top:2px;}
.pa-src .dt{font-size:12.5px;color:var(--pa-muted);line-height:1.5;}
.pa-src dl{margin:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px 10px;font-size:12.5px;background:var(--pa-soft);
 border-radius:10px;padding:9px 11px;}
.pa-src dt{color:var(--pa-muted);} .pa-src dd{margin:2px 0 0;font-weight:600;word-break:break-word;}
.pa-src dd.mono{font-family:ui-monospace,Consolas,monospace;font-weight:500;}
.pa-src .orig{border:1.5px solid var(--pa-line);border-radius:10px;padding:10px 11px;font-size:13.5px;line-height:1.62;color:#2E3A50;
 max-height:340px;overflow:auto;white-space:normal;}
.pa-src mark.used{background:#FFF2C8;color:inherit;padding:1px 2px;border-radius:3px;}
.pa-src mark.key{background:var(--pa-mark);color:inherit;padding:1px 2px;border-radius:3px;font-weight:600;}
.pa-src ol.chain{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:6px;font-size:13px;}
.pa-src ol.chain li{display:flex;justify-content:space-between;gap:8px;padding:7px 10px;border-radius:8px;background:var(--pa-soft);color:#4A5466;}
.pa-src ol.chain li.on{background:#E3EAF8;color:var(--pa-legal);font-weight:700;}
.pa-src .refs{display:flex;flex-wrap:wrap;gap:6px;font-family:ui-monospace,Consolas,monospace;font-size:12px;}
.pa-src .refs span{padding:3px 8px;border-radius:6px;}
.pa-src .prio{margin:0;padding-left:18px;font-size:13px;line-height:1.7;color:#3B4656;}
.pa-src .empty{padding:24px 6px;font-size:14px;line-height:1.6;color:var(--pa-muted);}
.pa-src .empty b{display:block;font-size:15px;color:var(--pa-ink);margin-bottom:4px;}
.st-key-srcclose button{min-height:30px;padding:0 9px;border-radius:8px;}
/* ---------- các trang khác ---------- */
.pa-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:4px 0 8px;}
.pa-stat{background:#fff;border:1px solid var(--pa-line);border-radius:14px;padding:12px 14px;}
.pa-stat b{display:block;font-size:24px;font-weight:800;color:var(--pa-navy);line-height:1.2;}
.pa-stat span{font-size:12.5px;color:var(--pa-muted);}
.pa-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:8px 0 14px;}
@media (max-width:1100px){.pa-kpis{grid-template-columns:repeat(2,minmax(0,1fr));}}
.pa-kpi{background:#fff;border:1px solid var(--pa-line);border-radius:14px;padding:14px 16px 13px;display:flex;flex-direction:column;gap:8px;}
.pa-kpi .top{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;}
.pa-kpi .n{font-size:13.5px;font-weight:700;color:#3B4656;line-height:1.35;}
.pa-kpi .badge{flex:none;padding:2px 8px;border-radius:999px;font-size:11.5px;font-weight:700;white-space:nowrap;}
.pa-kpi .badge.ok{background:var(--pa-ok-bg);color:var(--pa-ok);} .pa-kpi .badge.bad{background:#FDE7E3;color:#B42318;}
.pa-kpi .v{font-size:30px;font-weight:700;color:var(--pa-ink);line-height:1.1;}
.pa-kpi .v small{font-size:15px;font-weight:600;color:var(--pa-muted);margin-left:2px;}
.pa-kpi .foot{display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 10px;font-size:12.5px;color:var(--pa-muted);
 border-top:1px solid #EEF1F6;padding-top:8px;margin-top:auto;}
.pa-kpi .d-good{color:var(--pa-ok);font-weight:700;} .pa-kpi .d-bad{color:#B42318;font-weight:700;}
.pa-kpi .d-neutral{color:#45506A;font-weight:600;}
.pa-legend{display:flex;flex-wrap:wrap;align-items:center;gap:6px 18px;font-size:13px;color:#45506A;}
.pa-legend .sw{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;vertical-align:-1px;}
.pa-legend .sw.sys{background:#2F64C0;} .pa-legend .sw.b0{background:#858FA0;} .pa-legend .sw.abs{background:#EB6834;}
.pa-legend .sw.set1{background:#1F4FA3;} .pa-legend .sw.set2{background:#5E93E0;} .pa-legend .sw.set3{background:#C2410C;}
.pa-heat td.g1,.pa-legend .sq.g1{background:#E3ECFA;} .pa-heat td.g2,.pa-legend .sq.g2{background:#BCD0F2;}
.pa-heat td.g3,.pa-legend .sq.g3{background:#7FA3E3;} .pa-heat td.g4,.pa-legend .sq.g4{background:#2F64C0;}
.pa-heat td.g4,.pa-heat td.g4 small{color:#fff;opacity:1;}
.pa-heat tr.alt th,.pa-heat tr.alt td{font-style:italic;} .pa-heat tr.alt th{color:#45506A;}
.pa-kpi-note{font-size:13px;color:#5B6578;margin:-4px 2px 6px;line-height:1.5;}
.pa-m-h{font-weight:700;color:#14213D;font-size:15px;margin-bottom:4px;} .pa-m-t{font-size:13.5px;color:#14213D;line-height:1.55;}
.pa-m-f{font-size:12px;font-weight:600;color:#5B6578;text-transform:uppercase;letter-spacing:.04em;margin-top:8px;}
.pa-m-r li{font-size:13px;} .katex-display{overflow-x:auto;overflow-y:hidden;padding:2px 0;}
.pa-legend .tk{display:inline-block;width:2px;height:14px;background:#14213D;margin-right:7px;vertical-align:-2px;}
.pa-legend .note{color:var(--pa-muted);font-size:12.5px;}
/* thẻ biểu đồ so sánh */
[class*="st-key-chart-"]{background:#fff;border:1px solid var(--pa-line);border-radius:14px;padding:14px 16px 10px;}
.pa-card-h{font-size:15.5px;font-weight:700;color:var(--pa-navy);line-height:1.3;}
.pa-card-s{font-size:13px;color:var(--pa-muted);margin-top:2px;}
.pa-card-k{font-size:13.5px;color:#22304D;margin-top:8px;line-height:1.45;}
.pa-card-k b{color:var(--pa-navy);}
.pa-card-lg{margin-top:8px;}
.pa-heat-wrap{overflow-x:auto;margin-top:10px;}
.pa-heat{width:100%;min-width:720px;border-collapse:separate;border-spacing:3px;font-size:13px;}
.pa-heat thead th{font-size:12.5px;font-weight:600;color:#45506A;text-align:center;padding:4px 6px 6px;line-height:1.25;}
.pa-heat thead th:first-child{text-align:left;}
.pa-heat tbody th{text-align:left;font-weight:600;color:var(--pa-ink);white-space:nowrap;padding:6px 10px 6px 4px;}
.pa-heat td{text-align:center;padding:6px 6px 5px;border-radius:8px;color:var(--pa-ink);font-variant-numeric:tabular-nums;}
.pa-heat td b{display:block;font-size:14px;font-weight:700;line-height:1.2;}
.pa-heat td small{display:block;font-size:11.5px;font-weight:600;opacity:.8;line-height:1.2;}
.pa-heat tr.ref td{background:#EAF0FA;} .pa-heat tr.ref th{color:var(--pa-navy);}
.pa-heat tr.b0 th,.pa-heat tr.b0 td{border-top:1px solid transparent;}
.pa-heat tr.b0 th{color:#45506A;}
.pa-heat td.z,.pa-legend .sq.z{background:#F4F6FA;}
.pa-heat td.w1,.pa-legend .sq.w1{background:#FDE8E4;} .pa-heat td.w2,.pa-legend .sq.w2{background:#F8C6BC;}
.pa-heat td.w3,.pa-legend .sq.w3{background:#EE9584;} .pa-heat td.w4,.pa-legend .sq.w4{background:#C53A2D;}
.pa-heat td.w4{color:#fff;} .pa-heat td.b1,.pa-legend .sq.b1{background:#DCE8FA;}
.pa-legend .sq{display:inline-block;width:14px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px;}
.pa-heat-lg{margin-top:8px;gap:6px 14px;}
.pa-sum{display:flex;flex-wrap:wrap;gap:8px;}
.pa-sum span{padding:5px 11px;border-radius:999px;font-size:13px;font-weight:600;background:#EEF2F8;color:#2A3550;}
.pa-sum span.ok{background:var(--pa-ok-bg);color:var(--pa-ok);}
.pa-sec{font-size:15.5px;font-weight:800;color:var(--pa-navy);margin:14px 0 4px;}
.pa-desc{font-size:14px;color:#3B4656;line-height:1.6;margin:0 0 6px;}
.pa-tlbox{background:#fff;border:1px solid var(--pa-line);border-radius:14px;padding:12px 14px;margin-bottom:10px;}
</style>"""


def ic(name: str) -> str:
    """Icon Material Symbols (bộ icon Streamlit dùng sẵn) cho phần giao diện viết bằng HTML; trình đọc màn hình bỏ qua."""
    return f'<span class="pa-ic" aria-hidden="true">{name}</span>'


def _esc(s) -> str:
    return _html.escape(str(s if s is not None else ""), quote=True)


def emphasize(text: str) -> str:
    """Escape HTML rồi tô đậm số hiệu văn bản, ngày, con số/thời hạn, mã trạng thái và từ cấm/bắt buộc."""
    def rep(m):
        s = m.group(0)
        if m.lastgroup == "code" and s in NOT_CODES:
            return s
        return f'<span class="hl-{m.lastgroup}">{s}</span>'
    return EMPH_RE.sub(rep, _esc(text))


def _fmt_ts(ts: str) -> str:
    try:
        return datetime.fromisoformat(ts).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return str(ts or "")


def day_label(d: date, today: date) -> str:
    if d == today:
        return f"Hôm nay · {d:%d/%m/%Y}"
    if d == today - timedelta(days=1):
        return f"Hôm qua · {d:%d/%m/%Y}"
    return f"{WEEKDAY_VI[d.weekday()]} · {d:%d/%m/%Y}"


def short_title(q: str, n: int = 62) -> str:
    q = re.sub(r"\s+", " ", str(q or "")).strip()
    first = re.split(r"(?<=[?.!])\s", q)[0]
    t = first if len(first) >= 20 else q
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def split_questions(text: str) -> list[str]:
    """Hỏi nhiều câu cùng lúc: mỗi dòng một câu hỏi (dòng quá ngắn được nối vào câu trước; bỏ số thứ tự/gạch đầu dòng)."""
    out: list[str] = []
    for ln in str(text or "").splitlines():
        s = re.sub(r"^\s*(?:\d{1,2}[.)]|[-•*])\s+", "", ln).strip()
        if not s:
            continue
        if out and len(content_terms(s)) < 2:
            out[-1] += " " + s
        else:
            out.append(s)
    return out


def doc_short_name(dp: DataPack, d: str) -> str:
    """'LAW09 · TT 78/2021'"""
    num = dp.number.get(d, "")
    abbr = DOC_ABBR.get(dp.doc[d]["document_type"], "")
    return f"{d} · {abbr} {'/'.join(num.split('/')[:2])}" if num else d


def state_pills(dp: DataPack, d: str, ref: date) -> list[tuple[str, str]]:
    """Nhãn hiệu lực của văn bản tại ngày ref (kèm cảnh báo nếu đã bị thay thế tại ngày dữ liệu)."""
    st, day = dp.doc_state(d, ref), f"{ref:%d/%m/%Y}"
    if st == VALID:
        out = [(f"Đang hiệu lực tại {day}", "ok")]
        if ref < SNAPSHOT and dp.doc_state(d, SNAPSHOT) != VALID and dp.end(d):
            nxt = date.fromisoformat(dp.end(d)) + timedelta(days=1)
            out.append((f"Đã bị thay thế từ {nxt:%d/%m/%Y}", "warn"))
        return out
    if st == INTERNAL:
        return [(f"Đang áp dụng nội bộ tại {day}", "ok")]
    if st in (NOT_YET, INTERNAL_NOT_YET):
        return [(f"Chưa có hiệu lực tại {day}", "muted")]
    if st == EXPIRED:
        return [(f"Hết hiệu lực tại {day}", "warn")]
    return [("Văn bản hợp nhất – chỉ tham khảo", "amber")]


def version_view(dp: DataPack, res: Result) -> dict:
    """Cảnh báo phiên bản (trả lời theo ngày cũ, văn bản đã bị thay thế) và chuỗi văn bản cần vẽ dòng thời gian."""
    ref = parse_date(res.applied_date) or SNAPSHOT
    laws = [d for d in dict.fromkeys(c.split("_")[0] for c in res.cited_chunks) if d.startswith("LAW")]
    old = [d for d in laws if ref < SNAPSHOT and dp.doc_state(d, ref) == VALID and dp.doc_state(d, SNAPSHOT) != VALID]
    alert = None
    if old:
        parts, now = [], []
        for d in old:
            nxt = date.fromisoformat(dp.end(d)) + timedelta(days=1) if dp.end(d) else None
            parts.append(f"{d} ({dp.short(d)}) đã được thay thế" + (f" từ {nxt:%d/%m/%Y}" if nxt else ""))
            now += [x for x in dp.successors_in_force(d, SNAPSHOT) if x not in now]
        alert = {"title": f"Cảnh báo phiên bản: trả lời theo ngày {ref:%d/%m/%Y}, không theo văn bản mới nhất",
                 "text": "; ".join(parts) + "." + (f" Tại ngày dữ liệu {SNAPSHOT:%d/%m/%Y}, văn bản hiện hành về nội dung này là "
                                                   + ", ".join(f"{x} – {dp.short(x)}" for x in now) + "." if now else "")}
    chains = []
    if res.intent == "VERSIONING":
        for d in laws:
            ch = dp.chain(d)
            if len(ch) > 1 and ch not in chains:
                chains.append(ch)
    return {"alert": alert, "chains": chains[:2], "ref": ref}


def timeline_html(dp: DataPack, chain: tuple[str, ...], ref: date, at: str = "ngày được hỏi") -> str:
    segs = []
    for d in chain:
        st = dp.doc_state(d, ref)
        start, end = fmt_date(dp.start(d)), fmt_date(dp.end(d))
        rng = "không có hiệu lực riêng" if st == REF_ONLY else (f"{start} – {end}" if end else f"từ {start}")
        tag, cls = {VALID: (f"Có hiệu lực tại {at}", "on"), NOT_YET: (f"Chưa có hiệu lực tại {at}", "next"),
                    EXPIRED: (f"Đã hết hiệu lực tại {at}", "past")}.get(st, ("Hợp nhất – chỉ tham khảo", "ref"))
        if st != VALID and dp.doc_state(d, SNAPSHOT) == VALID:
            tag += f" · hiện hành tại {SNAPSHOT:%d/%m/%Y}"
        pin = f"{ic('arrow_drop_down')}{ref:%d/%m/%Y}" if st == VALID else ""
        segs.append(f'<div class="seg {cls}"><div class="pin">{pin}</div><div class="bar"></div>'
                    f'<b>{_esc(doc_short_name(dp, d))}</b><span>{rng}</span><em>{_esc(tag)}</em></div>')
    topic = dp.doc[chain[-1]]["topic"]
    return (f'<div class="pa-tl"><div class="pa-lbl">DÒNG THỜI GIAN HIỆU LỰC · {_esc(topic.upper())}</div>'
            f'<div class="row">{"".join(segs)}</div></div>')


def steps_html(res: Result) -> str:
    """Dải P0–P8 của pipeline: bước đã chạy (xanh), bước dừng → ABSTAIN (cam), bước không chạy (xám); rê chuột xem chi tiết."""
    codes = [t["bước"].split()[0] for t in res.trace]
    detail = {t["bước"].split()[0]: f"{t['bước']} · {t['ms']} ms · {t['chi tiết']}" for t in res.trace}
    order = [c for c, _ in STEP_LABELS]
    stop = order.index(codes[-1]) if res.abstain and codes and codes[-1] in order else None
    chips = []
    for k, (code, label) in enumerate(STEP_LABELS):
        if stop is not None and k == stop:
            cls, lab = "stop", f"{code} {label} → ABSTAIN"
        elif code in codes and (stop is None or k < stop):
            cls, lab = "done", code
        else:
            cls, lab = "skip", code
        tip = f"{code} {label} · " + detail.get(code, "không chạy")
        chips.append(f'<span class="stp {cls}" title="{_esc(tip)}">{_esc(lab)}</span>')
    return f'<div class="pa-steps"><span class="pa-steps-lbl">Pipeline</span>{"".join(chips)}</div>'


def split_notes(res: Result) -> tuple[list[str], list[str]]:
    """Lưu ý hiệu lực (CHRONOS) và lưu ý về nguồn; bỏ các lưu ý đã thể hiện bằng nhãn trên thẻ."""
    version, other = [], []
    for w in res.warnings:
        if w.startswith(("Phần nội bộ trích từ tài liệu GIẢ LẬP", "Độ tin cậy trung bình")):
            continue
        if "sau ngày chụp corpus" in w:          # hỏi theo ngày hôm nay (sau 17/10/2026): nhắc ngắn gọn, không báo động
            other.append(f"Data Pack cập nhật đến {SNAPSHOT:%d/%m/%Y}; văn bản ban hành sau ngày này (nếu có) chưa có trong "
                         "Data Pack.")
            continue
        if w.startswith("Thứ tự ưu tiên") or not re.search(r"hiệu lực|mốc|reference_date|document_metadata|phiên bản", w):
            other.append(w)
        else:
            version.append(w)
    return version, other


def chronos_note(dp: DataPack, res: Result) -> str:
    """Ghi chú CHRONOS cho câu không hỏi về phiên bản: căn cứ pháp luật được chọn đúng văn bản đang có hiệu lực."""
    ref = parse_date(res.applied_date) or SNAPSHOT
    parts = []
    for d in dict.fromkeys(c.split("_")[0] for c in res.cited_chunks):
        direct = sorted(x for x in dp.pred[d] if not any(x in dp.pred[y] for y in dp.pred[d]))   # bỏ quan hệ bắc cầu
        if d.startswith("LAW") and direct and dp.doc_state(d, ref) == VALID:
            parts.append(f"{d} ({dp.short(d)}) có hiệu lực từ {fmt_date(dp.start(d))}, thay thế {', '.join(direct)}")
    return f"Căn cứ được chọn theo ngày {ref:%d/%m/%Y}: " + "; ".join(parts) + "." if parts else ""


def claim_html(cl: dict, key_items: set[str], as_lines: bool, skip: bool = False) -> str:
    units = [u for u in (cl.get("units") or [cl["text"]]) if u.strip()]
    refs = "".join(f'<span class="pa-ref">[{n}]</span>' for n in cl["refs"])
    parts = []
    for u in units:
        h = emphasize(u)
        if u.strip() in key_items:
            h = f'<mark class="pa-key">{h}</mark>'
        parts.append(h)
    if as_lines and len(parts) > 1:
        body = "".join(f'<div class="ln">{p}</div>' for p in parts[:-1]) + f'<div class="ln">{parts[-1]} {refs}</div>'
        return f'<div class="pa-claim">{body}</div>'
    return f'<p class="pa-claim">{" ".join(parts)} {refs}</p>'


def source_html(dp: DataPack, res: Result, n: int, cid: str) -> str:
    """Nội dung panel nguồn: nhãn loại/hiệu lực, metadata, đoạn gốc tô sáng phần được trích, chuỗi phiên bản, dẫn chiếu."""
    i = dp.idx[cid]
    c, ref = dp.chunks[i], parse_date(res.applied_date) or SNAPSHOT
    d = c["document_id"]
    m = dp.doc[d]
    law = c["source_type"] == "LEGAL"
    pills = [(("Văn bản pháp luật · " if law else "Nội bộ giả lập · ") + DOC_TYPE_VI.get(c["document_type"], c["document_type"]),
              "law" if law else "sim")] + state_pills(dp, d, ref)
    pill_html = "".join(f'<span class="pill {k}">{_esc(t)}</span>' for t, k in pills)
    eff_from = fmt_date(c["effective_from"] or m["effective_date"]) or "Không ghi"
    eff_to = fmt_date(c["effective_to"] or m["expiry_date"]) or "Không ghi"
    prio = f"{c['priority_level']} · {PRIORITY_VI.get(c['priority_level'], '')}".strip(" ·")
    # đoạn gốc: tô sáng câu/dòng đã trích vào câu trả lời (đậm hơn: ý then chốt)
    key = {u.strip() for u in (res.key_point.get("items") or [res.key_point.get("text", "")]) if u.strip()} \
        if n in res.key_point.get("refs", []) else set()
    used = [u.strip() for cl in res.claims if n in cl["refs"] for u in (cl.get("units") or [cl["text"]]) if u.strip()]
    text = _esc(c["chunk_text"])
    for u in sorted(set(used), key=len, reverse=True):
        for cand in (u, u.replace(": ", " | ", 1), u.replace(" – ", " | ")):
            e = _esc(cand)
            if e and e in text and f">{e}<" not in text:
                text = text.replace(e, f'<mark class="{"key" if u in key else "used"}">{e}</mark>', 1)
                break
    if "<mark" not in text and any(n in cl["refs"] and cl["kind"] in ("version", "chain") for cl in res.claims):
        text = f'<mark class="{"key" if key else "used"}">{text}</mark>'       # căn cứ của mệnh đề hiệu lực: cả đoạn
    text = text.replace("\n", "<br>")
    parts = [f'<div class="pills">{pill_html}</div>',
             f'<div><div class="lab">[{n}] {_esc(dp.label[cid])}</div><div class="hd">{_esc(c["heading"])}</div>'
             f'<div class="dt">{_esc(m["title"])}</div></div>',
             f'<dl><div><dt>chunk_id</dt><dd class="mono">{cid}</dd></div><div><dt>Mức ưu tiên</dt><dd>{_esc(prio)}</dd></div>'
             f'<div><dt>Hiệu lực từ</dt><dd>{eff_from}</dd></div><div><dt>Hiệu lực đến</dt><dd>{eff_to}</dd></div>'
             f'<div><dt>Trạng thái</dt><dd class="mono">{_esc(m["status"])}</dd></div>'
             f'<div><dt>Vị trí</dt><dd>{_esc(c["source_locator"] or c["article"])}</dd></div></dl>',
             f'<div><div class="pa-lbl">ĐOẠN GỐC</div><div class="orig">{text}</div></div>']
    if law and len(dp.chain(d)) > 1:
        rows = []
        for x in dp.chain(d):
            stx = dp.doc_state(x, ref)
            rng = "hợp nhất – tham khảo" if stx == REF_ONLY else (
                f"{fmt_date(dp.start(x))} – {fmt_date(dp.end(x))}" if dp.end(x) else f"từ {fmt_date(dp.start(x))}")
            tag = (" · dùng cho ngày hỏi" if ref != SNAPSHOT else " · đang dùng") if stx == VALID else (
                " · hiện hành" if dp.doc_state(x, SNAPSHOT) == VALID else "")
            rows.append(f'<li class="{"on" if x == d else ""}"><span>{_esc(doc_short_name(dp, x))}{tag}</span><span>{rng}</span></li>')
        parts.append(f'<div><div class="pa-lbl">CHUỖI PHIÊN BẢN · {_esc(m["topic"].upper())}</div>'
                     f'<ol class="chain" style="margin-top:6px">{"".join(rows)}</ol></div>')
    if not law and m["reference_documents"]:
        tags = []
        for x in _split(m["reference_documents"]):
            if x not in dp.doc:
                continue
            stx = dp.doc_state(x, ref)
            lab, cls = ({VALID: ("hiện hành", "background:#E2F4EA;color:#17663F"),
                         INTERNAL: ("nội bộ", "background:#EEF0F5;color:#4A5466"),
                         EXPIRED: (f"hết hiệu lực {fmt_date(dp.end(x))}", "background:#FDE7E3;color:#B42318"),
                         REF_ONLY: ("tham chiếu lịch sử", "background:#FFF1DC;color:#8A4205")}
                        .get(stx, ("chưa hiệu lực", "background:#EEF0F5;color:#4A5466")))
            tags.append(f'<span style="{cls}">{x} · {lab}</span>')
        parts.append(f'<div><div class="pa-lbl">DẪN CHIẾU TRONG METADATA</div><div class="refs" style="margin-top:6px">'
                     f'{"".join(tags)}</div><div class="dt" style="margin-top:6px">Tài liệu nội bộ giả lập; dẫn chiếu tới văn '
                     f'bản đã hết hiệu lực được chuyển sang văn bản đang có hiệu lực khi trả lời.</div></div>')
    return f'<div class="pa-src">{"".join(parts)}</div>'


PRIORITY_HTML = ('<div class="pa-src" style="padding-top:4px"><div><div class="pa-lbl">THỨ TỰ ƯU TIÊN NGUỒN</div>'
                 '<ol class="prio"><li>Luật: LAW01, LAW04, LAW10</li><li>Nghị định: LAW02, LAW07, LAW08, LAW11 (LAW05 hợp nhất)</li>'
                 '<li>Thông tư: LAW03, LAW06, LAW09, LAW12</li><li>Quy chế, quy trình nội bộ: SIM01–SIM06</li>'
                 '<li>Sổ tay, FAQ: SIM07–SIM08</li></ol><div class="dt">Chỉ dùng văn bản có hiệu lực tại ngày tham chiếu.</div>'
                 '</div></div>')


def doc_iframe_html(dp: DataPack, d: str, cid: str | None = None) -> str:
    """Toàn văn tài liệu trong Data Pack (đã escape), đoạn được trích tô sáng và tự cuộn tới."""
    blocks = [b for b in re.split(r"\n\s*\n", dp.doc_full_text(d)) if b.strip()]
    parts = []
    for b in blocks:
        lines = b.strip().split("\n")
        mm = re.match(r"\[((?:LAW|SIM)\d{2}_C\d{3})\]\s*(.*)", lines[0])
        if not mm:
            parts.append(f'<div class="head">{"<br>".join(_esc(x) for x in lines)}</div>')
            continue
        bid, hl = mm.group(1), mm.group(1) == cid
        body = "".join(f'<p class="meta">{_esc(x)}</p>' if re.match(r"(?:Nguồn định vị|Citation)\s*:", x) else f"<p>{_esc(x)}</p>"
                       for x in lines[1:])
        tag = '<span class="tag">Đoạn được trích dẫn</span>' if hl else ""
        parts.append(f'<section id="{"hl" if hl else bid}" class="{"hl" if hl else ""}"><h4><code>{bid}</code> '
                     f'{_esc(mm.group(2))}{tag}</h4>{body}</section>')
    css = ("body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:#14213D;margin:0;padding:14px 16px;background:#fff;"
           "font-size:14.5px;line-height:1.6}.head{background:#F3F6FB;border:1px solid #DCE3EE;border-radius:10px;padding:10px 12px;"
           "font-size:13px;color:#3B4656;margin-bottom:12px}section{border:1px solid transparent;padding:6px 12px;margin:0 0 6px;"
           "border-radius:8px}section h4{margin:0 0 2px;font-size:14.5px;color:#14284B}code{font-family:Consolas,monospace;"
           "font-size:12px;background:#E8EEF8;color:#1E3A6E;padding:1px 6px;border-radius:5px}p{margin:2px 0}p.meta{font-size:12px;"
           "color:#5B6578}section.hl{background:#FFF6D6;border-color:#EBCB6B}.tag{margin-left:8px;font-size:11px;"
           "font-weight:700;background:#14284B;color:#fff;padding:2px 7px;border-radius:999px;vertical-align:2px}")
    js = ("<script>const e=document.getElementById('hl');if(e){const t=e.getBoundingClientRect().top+window.scrollY-90;"
          "window.scrollTo(0,Math.max(0,t));}</script>")
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(parts)}{js}</body></html>"


KPI_SHORT = {"recall_at_5": "Retrieval Recall@5", "answer_accuracy": "Answer Correctness", "citation_accuracy": "Citation Accuracy",
             "unsupported_rate": "Unsupported Answer Rate", "abstention_f1": "Abstention Quality (F1)",
             "versioning_accuracy": "Versioning Accuracy", "latency_ms_avg": "Latency trung bình"}


# Cách tính 7 KPI + chỉ số phụ (bám Phần 4 tài liệu ôn tập của đội; khớp đúng cách tính trong evaluate_labeled/evaluate_system)
KPI_METHOD = [
    {"k": "recall_at_5", "title": "Độ bao phủ trong 5 đoạn trích đầu tiên (Retrieval Recall@5)", "target": "≥ 0,80 (đề thi)",
     "meaning": "Trong 5 đoạn hệ thống tìm được, có bao nhiêu đoạn là đoạn đáp án chuẩn của câu hỏi.",
     "formulas": [r"\text{Recall@5}_{\,q} = \dfrac{\left|\,\text{đoạn đáp án} \cap \text{Top-5 tìm được}\,\right|}{\left|\,\text{đoạn đáp án}\,\right|}",
                  r"\text{Recall@5} = \dfrac{1}{N}\sum_{q=1}^{N} \text{Recall@5}_{\,q} \qquad (N = \text{số câu có nhãn ANSWER})"],
     "rules": ["Chỉ tính trên câu có đáp án (nhãn ANSWER); câu có đáp án mà hệ thống từ chối nhầm tính 0 điểm.",
               "Chỉ số kèm: MRR@5 = trung bình của 1 / (hạng của đoạn đáp án đầu tiên trong Top-5); Recall@5 theo văn bản = "
               "cùng công thức nhưng so ở mức mã văn bản."]},
    {"k": "answer_accuracy", "title": "Độ chính xác câu trả lời / độ phủ ý chính (Answer Correctness)", "target": "≥ 0,70 (đội đề xuất)",
     "meaning": "Câu trả lời có nêu đủ các ý cốt lõi của đáp án tham chiếu hay không.",
     "formulas": [r"\text{Độ phủ ý chính}_{\,q} = \dfrac{\text{số từ khóa nội dung của đáp án mẫu có trong câu trả lời}}{\text{tổng số từ khóa nội dung của đáp án mẫu}}",
                  r"\text{Thang tự động}_{\,q} = \begin{cases} 1 & \text{độ phủ} \ge 0{,}70 \;(\text{đủ ý}) \\ 0{,}5 & 0{,}40 \le \text{độ phủ} < 0{,}70 \;(\text{thiếu ý}) \\ 0 & \text{độ phủ} < 0{,}40 \text{ hoặc từ chối nhầm} \end{cases}"],
     "rules": ["Từ khóa nội dung = từ của đáp án mẫu sau khi bỏ hư từ; giá trị chính là trung bình độ phủ trên các câu ANSWER, "
               "thang 0 / 0,5 / 1 là chỉ số kèm.",
               "Đây là chấm tự động theo từ khóa; điểm chính thức theo grading_note vẫn cần chấm tay. Trên Stress-60 chỉ chấm "
               "tự động các kiểu câu giữ nguyên đáp án của câu gốc."]},
    {"k": "citation_accuracy", "title": "Độ chính xác của nguồn trích dẫn (Citation Accuracy)", "target": "≥ 0,80 (đề thi)",
     "meaning": "Các nguồn hệ thống dẫn có đúng là nguồn của đáp án hay không – dẫn thừa hoặc dẫn sai đều bị trừ.",
     "formulas": [r"\text{Citation}_{\,q} = \dfrac{\text{số nguồn dẫn trùng nguồn của đáp án}}{\text{tổng số nguồn hệ thống đã dẫn}}",
                  r"\text{Citation Accuracy} = \dfrac{1}{M}\sum_{q=1}^{M} \text{Citation}_{\,q} \qquad (M = \text{số câu đã trả lời có nhãn})"],
     "rules": ["Quy tắc phạt dẫn thừa: câu chỉ cần 1 điều khoản mà hệ thống dẫn 3 (1 đúng, 2 thừa) thì được 1/3 ≈ 0,33.",
               "Chỉ số kèm – 4 điều kiện kiểm toán mỗi citation: (1) có trong citation_map; (2) ứng với đoạn nằm trong Top tìm "
               "kiếm; (3) đoạn chứa ≥ 90% từ của ý được khẳng định; (4) văn bản còn hiệu lực tại ngày tham chiếu."]},
    {"k": "unsupported_rate", "title": "Tỷ lệ câu trả lời không có căn cứ (Unsupported Answer Rate)", "target": "≤ 0,10 (đội đề xuất) – càng thấp càng tốt",
     "meaning": "Tỷ lệ 'ảo giác': câu trả lời khẳng định điều mà tài liệu không chứng minh được.",
     "formulas": [r"\text{Unsupported} = \dfrac{\text{số câu trả lời không có căn cứ}}{\text{tổng số câu hệ thống đã trả lời}}"],
     "rules": ["Một câu bị tính 'không có căn cứ' khi: câu lẽ ra phải từ chối (ngoài phạm vi) mà hệ thống vẫn trả lời; hoặc có "
               "ý khẳng định mà bộ kiểm chứng độc lập thấy < 90% từ có trong đoạn được dẫn, hoặc ngày hiệu lực không khớp metadata."]},
    {"k": "abstention_f1", "title": "Chất lượng từ chối trả lời (Abstention F1)", "target": "≥ 0,90 (đội đề xuất)",
     "meaning": "Khả năng nhận ra câu hỏi ngoài phạm vi / không đủ căn cứ để từ chối, mà không từ chối nhầm câu trả lời được.",
     "formulas": [r"P = \dfrac{TP}{TP + FP} \qquad R = \dfrac{TP}{TP + FN} \qquad F_1 = \dfrac{2\,P\,R}{P + R}"],
     "rules": ["TP – câu cần từ chối và hệ thống từ chối đúng; FP – câu có đủ căn cứ nhưng hệ thống từ chối nhầm; "
               "FN – câu cần từ chối nhưng hệ thống vẫn trả lời."]},
    {"k": "versioning_accuracy", "title": "Độ chính xác phiên bản hiệu lực (Versioning Accuracy)", "target": "≥ 0,90 (đội đề xuất)",
     "meaning": "Dẫn đúng văn bản còn hiệu lực tại mốc thời gian của câu hỏi (đúng thông tư, nghị định theo từng giai đoạn).",
     "formulas": [r"\text{Versioning} = \dfrac{\text{số câu phiên bản dẫn đúng văn bản}}{\text{tổng số câu hỏi phiên bản}}"],
     "rules": ["Một câu được tính đúng khi văn bản pháp luật (LAW) đầu tiên được dẫn còn hiệu lực tại mốc áp dụng và thuộc tập "
               "văn bản đúng của nhãn."]},
    {"k": "latency_ms_avg", "title": "Thời gian phản hồi trung bình và p95 (Latency)", "target": "Trung bình ≤ 10.000 ms (đề thi)",
     "meaning": "Tốc độ và độ ổn định khi trả lời.",
     "formulas": [r"\bar{t} = \dfrac{1}{n}\sum_{i=1}^{n} t_i \qquad t_{p95} = \text{mức thời gian mà 95\% số câu xử lý nhanh hơn}"],
     "rules": ["Đo trong tiến trình cho từng câu (ms). Latency dao động theo tải máy – muốn so hai phiên bản phải đo cặp xen kẽ."]},
]
KPI_METHOD_EXTRA = {   # chỉ số phụ (không nằm trong 7 ô KPI)
    "title": "Chỉ số phụ: Thứ tự ưu tiên nguồn cho câu hỏi kết hợp (Source Priority)", "target": "≥ 0,85 (đội đề xuất)",
    "meaning": "Câu hỏi vừa pháp luật vừa nội bộ (MIXED) phải xếp đúng thứ bậc nguồn.",
    "formulas": [r"\text{Source Priority} = \dfrac{\text{số câu MIXED đạt cả 4 điều kiện}}{\text{tổng số câu MIXED}}"],
    "rules": ["Đạt khi đồng thời: (1) có căn cứ pháp luật còn hiệu lực; (2) căn cứ pháp luật đứng trước tài liệu nội bộ; "
              "(3) không dùng văn bản hết hiệu lực/chưa hiệu lực/hợp nhất làm căn cứ (trừ câu hỏi phiên bản); (4) tài liệu nội "
              "bộ dẫn chiếu luật cũ thì phải dẫn văn bản kế nhiệm hoặc có cảnh báo."],
}


def kpi_method_html(m: dict, n: int, result: str = "") -> str:
    """Phần chữ của một KPI trong mục 'Cách đo': tiêu đề, mục tiêu, ý nghĩa (công thức vẽ riêng bằng st.latex)."""
    return (f'<div class="pa-m-h">{n}. {_esc(m["title"]) if n else _esc(m["title"])}</div>'
            f'<div class="pa-m-t"><b>Mục tiêu:</b> {_esc(m["target"])}' + (f' · <b>Kết quả:</b> {result}' if result else "")
            + f'</div><div class="pa-m-t"><b>Ý nghĩa:</b> {_esc(m["meaning"])}</div><div class="pa-m-f">Công thức</div>')


def kpi_tile_html(k: str, op: str, target: float, v: float, b0: float | None, extra: str = "") -> str:
    """Ô KPI: giá trị, nhãn Đạt/Chưa đạt, mục tiêu và chênh lệch có dấu so với baseline B0 (xanh khi tốt hơn theo chiều KPI)."""
    ok = kpi_status(k, v)
    sign = "≥" if op == ">=" else "≤"
    badge = f'<span class="badge {"ok" if ok else "bad"}">{ic("check_circle") + "Đạt" if ok else ic("cancel") + "Chưa đạt"}</span>'
    if k == "latency_ms_avg":
        value = f'{v:.0f}<small>ms</small>'
        delta = f'<span class="d-neutral">Dùng {v / target:.2%} thời gian cho phép</span>'
        tgt = f"Mục tiêu {sign} {target:,.0f} ms".replace(",", ".")
    else:
        value = f"{v:.3f}"
        delta = ""
        if b0 is not None:
            d = v - b0
            better = d < 0 if op == "<=" else d > 0
            cls = "d-good" if better else ("d-neutral" if abs(d) < 1e-9 else "d-bad")
            delta = f'<span class="{cls}">{ic("arrow_upward") if d > 0 else ic("arrow_downward") if d < 0 else ic("remove")}{abs(d):.3f} so với baseline ({b0:.3f})</span>'
        tgt = f"Mục tiêu {sign} {target:g}"
    extra = f'<span class="d-neutral">{_esc(extra)}</span>' if extra else ""
    return (f'<div class="pa-kpi" title="{_esc(KPI_DEFINITIONS[k])}"><div class="top"><div class="n">{KPI_SHORT[k]}</div>{badge}</div>'
            f'<div class="v">{value}</div><div class="foot">{delta}{extra}<span>{tgt}</span></div></div>')


# ---- biểu đồ so sánh ----------------------------------------------------------------------------------------------
# Màu đã qua bộ kiểm định bảng màu (tách biệt với người mù màu đỏ–lục, tương phản ≥ 3:1 trên nền trắng): xanh = hệ thống,
# xám = baseline (vai trò làm nền), hai sắc xanh = hai bộ câu hỏi, cam = ABSTAIN. Chữ luôn dùng màu chữ, không dùng màu dữ liệu.
CH_FONT = '"Source Sans", sans-serif'
CH_SYS, CH_B0, CH_SET1, CH_SET2, CH_ABS = "#2F64C0", "#858FA0", "#1F4FA3", "#5E93E0", "#EB6834"
CH_SET3 = "#C2410C"
KPI_VIEWS = {   # tập đo trên trang Đánh giá KPI – mô tả trung thực mức độc lập của từng tập
    "Public-90": "90 câu public của BTC – Dev-30 chấm theo đáp án BTC, Ext-60 theo nhãn đội. Bộ câu chính thức, đủ cả câu "
                 "ngoài phạm vi (14) và câu phiên bản (10).",
    "Stress-60": "60 câu khó do đội viết (diễn đạt lệch, bẫy phiên bản, chèn lệnh…). Đã dùng để phân tích lỗi từ 10/11/2026 nên "
                 "không còn hoàn toàn độc lập, nhưng là tập gần với câu hỏi thực tế nhất.",
    "Paraphrase-52": "52 câu diễn đạt lại, viết tắt, ngoài phạm vi do đội viết từ câu public.",
    "Dev-30 + Probe-25": "TẬP PHÁT TRIỂN – đội tinh chỉnh quy tắc khi xem kết quả trên tập này nên số lạc quan. "
                         "Chỉ 26 câu tính Recall/Answer/Citation.",
}


def set_kpis(fsum: pd.DataFrame, names: list[str], system: str) -> dict:
    """KPI của một hệ thống trên một tập hoặc gộp nhiều tập (tổng điểm / tổng số câu; F1 từ TP/FP/FN)."""
    g = fsum[(fsum["tập"].isin(names)) & (fsum["hệ thống"] == system)]
    if g.empty:
        return {}
    num = lambda c: pd.to_numeric(g[c], errors="coerce").fillna(0) if c in g else pd.Series([0.0])
    out = {}
    for k in ("recall_at_5", "answer_accuracy", "citation_accuracy", "unsupported_rate", "versioning_accuracy", "mrr",
              "doc_recall_at_5", "answer_correctness", "citation_valid_4"):
        n, s = num(k + "_n").sum(), num(k + "_sum").sum()
        out[k] = float(s / n) if n else float("nan")
        out[k + "_n"], out[k + "_sum"] = int(n), float(s)
    tp, fp, fn = (int(num(c).sum()) for c in ("abstain_tp", "abstain_fp", "abstain_fn"))
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    out.update(abstention_f1=(2 * p * r / (p + r) if p + r else 0.0) if tp + fn else float("nan"),
               abstain_tp=tp, abstain_fp=fp, abstain_fn=fn, abstention_precision=p, abstention_recall=r)
    lat, cnt = num("latency_ms_avg"), num("số câu")
    out["latency_ms_avg"] = float((lat * cnt).sum() / cnt.sum()) if cnt.sum() else float("nan")
    out["latency_ms_p95"] = float(num("latency_ms_p95").max())
    out["số câu"] = int(cnt.sum())
    if len(names) == 1:
        row = g.iloc[0].to_dict()
        out.update({k: row[k] for k in row if k.endswith("_ci")})
    return out


def set_kpi_extra(k: str, s: dict) -> str:
    """Dòng chỉ số kèm dưới ô KPI khi xem theo tập: số câu và CI 95% (nếu có)."""
    if k == "latency_ms_avg":
        return f"p95 {s['latency_ms_p95']:.0f} ms · {s['số câu']} câu"
    if k == "abstention_f1":
        base = f"Từ chối đúng {s['abstain_tp']}/{s['abstain_tp'] + s['abstain_fn']} · nhầm {s['abstain_fp']}"
    else:
        base = f"{s.get(k + '_sum', 0):g}/{s.get(k + '_n', 0)} câu"
    ci = s.get(k + "_ci") or ""
    ci = f" · CI 95% {ci}" if isinstance(ci, str) and ci else ""
    return base + ci
CH_INK, CH_MUTED = "#14213D", "#5B6578"
# bảng ablation: mức KPI kém đi so với hệ thống đầy đủ → một sắc đỏ từ nhạt đến đậm
ABL_STEPS = [(0.05, "w1", "Kém đi < 0.05"), (0.15, "w2", "0.05 – 0.15"), (0.30, "w3", "0.15 – 0.30"), (9e9, "w4", "≥ 0.30")]


def _chart_style(chart, height: int):
    return (chart.properties(height=height)
            .configure(font=CH_FONT, background="#ffffff", padding={"left": 2, "right": 6, "top": 4, "bottom": 2})
            .configure_view(stroke=None)
            .configure_axis(labelColor=CH_MUTED, labelFontSize=12, gridColor="#E8EDF4", domainColor="#C9D2E0",
                            tickColor="#C9D2E0")
            .configure_axisY(grid=False, domain=False, ticks=False, labelColor=CH_INK, labelFontSize=13, labelPadding=10,
                             labelLimit=300)
            .configure_legend(disable=True))


def chart_pairs(items: list[dict], series: list[tuple[str, str, str]], target: bool = False):
    """Thanh ngang theo cặp trên thang 0–1 cho từng chỉ số. items: {"label" (dùng "|" để xuống dòng), <khoá của từng chuỗi>,
    "target", "tgt"}; series: [(tên, khoá, màu)], chuỗi cuối là chuỗi chính (nhãn giá trị đậm); target=True vẽ vạch mục tiêu."""
    import altair as alt
    names, order = [s[0] for s in series], [it["label"] for it in items]
    df = pd.DataFrame([{"Chỉ số": it["label"], "Tên": it.get("name", it["label"]), "Chuỗi": name, "Giá trị": float(it[key]),
                        "Mục tiêu": it.get("tgt", "")} for it in items for name, key, _ in series])
    y = alt.Y("Chỉ số:N", sort=order, title=None, axis=alt.Axis(labelExpr="split(datum.label, '|')"))
    base = alt.Chart(df).encode(
        y=y, yOffset=alt.YOffset("Chuỗi:N", sort=names, scale=alt.Scale(paddingInner=0.12)),
        x=alt.X("Giá trị:Q", title=None, scale=alt.Scale(domain=[0, 1.22], nice=False),   # chừa chỗ cho nhãn 1.000
                axis=alt.Axis(values=[0, 0.2, 0.4, 0.6, 0.8, 1.0], format=".1f")))
    tip = [alt.Tooltip("Tên:N", title="Chỉ số"), alt.Tooltip("Chuỗi:N", title="Đối tượng"),
           alt.Tooltip("Giá trị:Q", format=".3f")] + ([alt.Tooltip("Mục tiêu:N")] if target else [])
    layers = [base.mark_bar(cornerRadiusEnd=4).encode(
        color=alt.Color("Chuỗi:N", scale=alt.Scale(domain=names, range=[s[2] for s in series])), tooltip=tip)]
    if target:
        tg = pd.DataFrame([{"Chỉ số": it["label"], "Tên": it.get("name", it["label"]), "Mức": float(it["target"]),
                            "Mục tiêu": it["tgt"]} for it in items])
        layers.append(alt.Chart(tg).mark_tick(color=CH_INK, thickness=2, size=44).encode(
            y=y, x="Mức:Q", tooltip=[alt.Tooltip("Tên:N", title="Chỉ số"), alt.Tooltip("Mục tiêu:N")]))
    for name, weight, color in [(n, 700, CH_INK) if n == names[-1] else (n, 500, CH_MUTED) for n in names]:
        text = base.transform_filter(alt.datum["Chuỗi"] == name).encode(text=alt.Text("Giá trị:Q", format=".3f"))
        style = {"align": "left", "dx": 5, "fontSize": 12.5, "fontWeight": weight}
        layers += [text.mark_text(**style, color="#ffffff", stroke="#ffffff", strokeWidth=4, strokeJoin="round"),  # viền nền
                   text.mark_text(**style, color=color)]
    return _chart_style(alt.layer(*layers), height=len(items) * (40 + 12 * len(series)))


def fmt_pct(x: float) -> str:
    """Phần trăm gọn: số nguyên khi tròn (100%), một chữ số thập phân khi không (99.6% không bị làm tròn thành 100%)."""
    return f"{x:.0%}" if abs(x * 100 - round(x * 100)) < 0.05 else f"{x:.1%}"


def chart_decisions(groups: list[tuple[str, int, int]]):
    """Thanh ngang 100% chồng: tỷ lệ trả lời có nguồn / từ chối (ABSTAIN) theo loại câu hỏi. groups: [(nhãn, số trả lời,
    số ABSTAIN)]; nhãn % hiện trong đoạn đủ rộng, giá trị đầy đủ ở tooltip và bảng nhật ký."""
    import altair as alt
    A, R = "Trả lời có nguồn", "Từ chối (ABSTAIN)"
    rows = []
    for lab, n_ans, n_abs in groups:
        n, x0 = n_ans + n_abs, 0.0
        for name, k in ((A, n_ans), (R, n_abs)):
            share = k / n if n else 0.0
            rows.append({"Loại câu hỏi": lab, "Nhãn": f"{lab}|{n} lượt", "Kết quả": name, "Số lượt": k, "Tỷ lệ": share,
                         "%": fmt_pct(share), "x0": x0, "x1": x0 + share, "giữa": x0 + share / 2})
            x0 += share
    df = pd.DataFrame(rows)
    y = alt.Y("Nhãn:N", sort=list(dict.fromkeys(df["Nhãn"])), title=None, axis=alt.Axis(labelExpr="split(datum.label, '|')"))
    tip = [alt.Tooltip("Loại câu hỏi:N"), alt.Tooltip("Kết quả:N"), alt.Tooltip("Số lượt:Q"), alt.Tooltip("Tỷ lệ:Q", format=".1%")]
    bars = alt.Chart(df).mark_bar(size=26, stroke="#ffffff", strokeWidth=2).encode(
        y=y, x=alt.X("x0:Q", title=None, scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%", values=[0, .25, .5, .75, 1])),
        x2="x1:Q", color=alt.Color("Kết quả:N", scale=alt.Scale(domain=[A, R], range=[CH_SYS, CH_ABS])), tooltip=tip)
    text = alt.Chart(df[df["Tỷ lệ"] >= 0.1]).mark_text(fontSize=12.5, fontWeight=700).encode(
        y=y, x="giữa:Q", text="%:N", tooltip=tip,
        color=alt.condition(alt.datum["Kết quả"] == A, alt.value("#ffffff"), alt.value(CH_INK)))
    return _chart_style(alt.layer(bars, text), height=len(groups) * 54)


def ablation_html(summ: pd.DataFrame) -> tuple[str, str]:
    """Bảng nhiệt ablation: hàng = hệ thống đầy đủ, từng bản bỏ một thành phần (thành phần quan trọng nhất trước) và baseline
    B0; cột = 6 KPI chất lượng. Ô tô đỏ theo mức KPI kém đi so với hệ thống đầy đủ (đúng chiều KPI). Trả về (html, tóm tắt)."""
    keys = [(k, op) for k, _, op, *_ in KPI_SPECS if k != "latency_ms_avg"]
    recs = summ.to_dict("records")
    full = next((r for r in recs if "đầy đủ" in str(r["hệ thống"])), None)
    if full is None:
        return "", ""
    abl = [r for r in recs if str(r["hệ thống"]).lstrip().startswith("–")]
    b0 = next((r for r in recs if str(r["hệ thống"]).startswith("B0")), None)

    def worse(r, k, op):                                   # > 0: kém đi so với hệ thống đầy đủ
        return (float(full[k]) - float(r[k])) * (1 if op == ">=" else -1)

    abl.sort(key=lambda r: -sum(max(worse(r, k, op), 0) for k, op in keys))
    used = set()

    def row(r, cls, label):
        cells = []
        for k, op in keys:
            v, f = float(r[k]), float(full[k])
            w = 0.0 if r is full else worse(r, k, op)
            c = ("z" if abs(w) < 0.005 else "b1" if w < 0 else next(c for lim, c, _ in ABL_STEPS if w < lim))
            used.add(c)
            small = "" if r is full or abs(v - f) < 0.0005 else f"<small>{v - f:+.3f}</small>"
            tip = (f"{label} · {KPI_SHORT[k]} = {v:.3f}" if r is full else
                   f"{label} · {KPI_SHORT[k]} = {v:.3f} (đầy đủ {f:.3f}: "
                   + ("không đổi)" if c == "z" else f"tốt hơn {-w:.3f})" if c == "b1" else f"kém đi {w:.3f})"))
            cells.append(f'<td class="{c}" title="{_esc(tip)}"><b>{v:.3f}</b>{small}</td>')
        return f'<tr class="{cls}"><th>{_esc(label)}</th>{"".join(cells)}</tr>'

    body = [row(full, "ref", "Đầy đủ – CHRONOS-LEDGER")]
    body += [row(r, "", "Bỏ " + str(r["hệ thống"]).split("bỏ", 1)[-1].strip()) for r in abl]
    if b0 is not None:
        body.append(row(b0, "b0", "Baseline B0 – BM25 thuần"))
    head = "".join(f"<th>{_esc(KPI_SHORT[k])}{' ↓' if op == '<=' else ''}</th>" for k, op in keys)
    legend = [("z", "Không đổi")] + [(c, lab) for _, c, lab in ABL_STEPS] + ([("b1", "Tốt hơn")] if "b1" in used else [])
    html = (f'<div class="pa-heat-wrap"><table class="pa-heat"><thead><tr><th>Cấu hình</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div><div class="pa-legend pa-heat-lg">'
            + "".join(f'<span><i class="sq {c}"></i>{lab}</span>' for c, lab in legend)
            + '<span class="note">↓ = càng thấp càng tốt · số nhỏ = chênh lệch so với hệ thống đầy đủ</span></div>')
    note = ""
    if abl:
        top = abl[0]
        k, op = max(keys, key=lambda ko: worse(top, *ko))
        note = (f'Thành phần quan trọng nhất: <b>{_esc(str(top["hệ thống"]).split("bỏ", 1)[-1].strip())}</b> – bỏ đi thì '
                f'{KPI_SHORT[k]} từ {float(full[k]):.3f} thành {float(top[k]):.3f}.')
    return html, note


SET_SERIES = [("Dev-30 – đáp án BTC", "Dev-30", CH_SET1), ("Ext-60 – nhãn đội", "Ext-60", CH_SET2),
              ("Stress-60 – câu khó của đội", "Stress-60", CH_SET3)]
SET_METRICS = [("recall_at_5", "Retrieval Recall@5"), ("answer_accuracy", "Answer Correctness"),
               ("citation_accuracy", "Citation Accuracy"), ("abstention_f1", "Abstention Quality (F1)"),
               ("versioning_accuracy", "Versioning Accuracy"), ("quyết định đúng", "Quyết định đúng|(trả lời / từ chối)")]
ABL_GAIN = [(0.02, "z"), (0.05, "g1"), (0.15, "g2"), (0.30, "g3"), (9e9, "g4")]
ABL_STEP_COLS = [("Recall@5", ">="), ("Answer Correctness", ">="), ("Citation Accuracy", ">="), ("Unsupported", "<="),
                 ("Abstention F1", ">="), ("Versioning", ">=")]
ABL_PREV = {"B1": "B0", "B2": "B1", "B2′": "B1", "B3": "B2", "B4": "B3", "B5": "B4", "B6": "B5"}


def _num_or_nan(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def set_items(fsum: pd.DataFrame) -> tuple[list[dict], list[tuple[str, str, str]]]:
    """Dữ liệu biểu đồ KPI theo tập đánh giá (hệ thống đầy đủ) từ eval_by_set.csv: Dev-30 / Ext-60 / Stress-60."""
    g = fsum[fsum["hệ thống"] == "CHRONOS-LEDGER"].set_index("tập")
    series = [(lab, key, col) for lab, key, col in SET_SERIES if key in g.index]
    items = []
    for k, lab in SET_METRICS:
        vals = {key: _num_or_nan(g.loc[key].get(k)) for _, key, _ in series}
        if series and not any(math.isnan(v) for v in vals.values()):
            items.append({"label": lab, "name": lab.replace("|", " "), **vals})
    return items, series


def ablation_steps_html(abl: pd.DataFrame) -> tuple[str, str]:
    """Bảng ablation 'thêm dần' (Public-90): hàng B0 → B6, B2′ (lọc cứng theo ngày thay CHRONOS) đặt ngay dưới B2; cột = 6 KPI
    chất lượng. Ô ghi giá trị và mức thay đổi so với bước liền trước (B2′ so với B1); xanh đậm dần theo mức cải thiện đúng
    chiều KPI, đỏ khi kém đi. Trả về (html, câu tóm tắt)."""
    by = {str(r["cấu hình"]).split(" ")[0]: r for r in abl.to_dict("records")}
    order = [k for k in ("B0", "B1", "B2", "B2′", "B3", "B4", "B5", "B6") if k in by]
    if len(order) < 2:
        return "", ""
    gains, body = [], []
    for k in order:
        r, prev = by[k], by.get(ABL_PREV.get(k, ""))
        cells = []
        for col, op in ABL_STEP_COLS:
            v = _num_or_nan(r.get(col))
            if prev is None or math.isnan(v):
                cells.append(f'<td class="z"><b>{_fmt3(v)}</b></td>')
                continue
            pv = _num_or_nan(prev.get(col))
            d = 0.0 if math.isnan(pv) else (v - pv) * (1 if op == ">=" else -1)        # > 0: tốt lên đúng chiều KPI
            cls = (next(c for lim, c in ABL_GAIN if d < lim) if d >= 0 else
                   next(c for lim, c, _ in ABL_STEPS if -d < lim))
            if k != "B2′" and d > 0:
                gains.append((d, k, col, pv, v))
            small = "" if abs(v - pv) < 0.0005 or math.isnan(pv) else f"<small>{v - pv:+.3f}</small>"
            tip = f"{r['cấu hình']} · {col} = {_fmt3(v)} (bước trước {_fmt3(pv)})"
            cells.append(f'<td class="{cls}" title="{_esc(tip)}"><b>{_fmt3(v)}</b>{small}</td>')
        cls = "alt" if k == "B2′" else "ref" if k == "B6" else "b0" if k == "B0" else ""
        body.append(f'<tr class="{cls}"><th>{_esc(str(r["cấu hình"]))}</th>{"".join(cells)}</tr>')
    head = "".join(f"<th>{_esc(c)}{' ↓' if op == '<=' else ''}</th>" for c, op in ABL_STEP_COLS)
    legend = [("z", "Không đổi (< 0.02)"), ("g1", "Tốt lên 0.02 – 0.05"), ("g2", "0.05 – 0.15"), ("g3", "0.15 – 0.30"),
              ("g4", "≥ 0.30"), ("w2", "Kém đi")]
    html = (f'<div class="pa-heat-wrap"><table class="pa-heat"><thead><tr><th>Cấu hình (bật thêm so với hàng trên)</th>{head}'
            f'</tr></thead><tbody>{"".join(body)}</tbody></table></div><div class="pa-legend pa-heat-lg">'
            + "".join(f'<span><i class="sq {c}"></i>{lab}</span>' for c, lab in legend)
            + '<span class="note">↓ = càng thấp càng tốt · số nhỏ = thay đổi so với bước liền trước (B2′ so với B1)</span></div>')
    top = sorted(gains, reverse=True)[:3]
    note = "Đóng góp lớn nhất: " + "; ".join(
        f"<b>{_esc(k)}</b> – {_esc(col)} {pv:.3f} → {v:.3f}" for _, k, col, pv, v in top) + "." if top else ""
    if "B2" in by and "B2′" in by:
        v2, v2p = _num_or_nan(by["B2"].get("Versioning")), _num_or_nan(by["B2′"].get("Versioning"))
        if not (math.isnan(v2) or math.isnan(v2p)):
            note += (f" Chuyển hướng phiên bản (B2) đạt Versioning {v2:.2f}, lọc cứng theo ngày như pipeline tham khảo (B2′) "
                     f"chỉ {v2p:.2f}.")
    return html, note


def card_head_html(title: str, sub: str = "", note: str = "", legend: list[tuple[str, str]] = ()) -> str:
    """Đầu thẻ biểu đồ: tiêu đề, mô tả ngắn, câu kết luận rút từ số liệu và chú giải (ô màu giống dạng mark của biểu đồ)."""
    lg = "".join(f'<span><i class="{"tk" if c == "tk" else "sw " + c}"></i>{_esc(t)}</span>' for c, t in legend)
    return (f'<div class="pa-card-h">{_esc(title)}</div>' + (f'<div class="pa-card-s">{sub}</div>' if sub else "")
            + (f'<div class="pa-card-k">{note}</div>' if note else "")
            + (f'<div class="pa-legend pa-card-lg">{lg}</div>' if lg else ""))


# robustness.csv: cột chỉ số → nhãn dễ hiểu ("|" = xuống dòng trên trục)
ROBUST_METRICS = {"quyết định đúng": "Quyết định đúng|(trả lời / từ chối)", "căn cứ đúng trong top-5": "Căn cứ đúng trong top-5",
                  "citation [1] đúng": "Nguồn đầu tiên [1] đúng", "có citation đúng": "Có ít nhất 1 nguồn đúng",
                  "độ chính xác citation": "Độ chính xác citation", "versioning": "Đúng phiên bản văn bản"}


def robust_set_label(r) -> str:
    name, n = str(r.get("tập", "")), r.get("số câu", "")
    kind = ("câu Ext-60 (nhãn đội)" if name.startswith("Ext") else "câu public của BTC" if name.startswith("Public") else
            "câu diễn đạt lại / ngoài phạm vi" if name.startswith("Paraphrase") else name)
    return f"{n} {kind}".strip()


# loại câu hỏi do bước Planning xác định (ghi trong audit log)
INTENT_VI = {"LEGAL": "Văn bản pháp luật", "INTERNAL": "Quy chế nội bộ", "MIXED": "Pháp luật + nội bộ",
             "VERSIONING": "Hiệu lực / phiên bản", "OUT_OF_SCOPE": "Ngoài phạm vi Data Pack"}


def run_ui():
    import streamlit as st

    st.set_page_config(page_title=APP_NAME, page_icon=":material/balance:", layout="wide", initial_sidebar_state="expanded")
    st.html(UI_CSS + LOGO_CSS)

    # đổi mã chương trình → nạp lại pipeline (bộ nhớ đệm của Streamlit giữ qua F5, không tự biết lớp PolicyAssist đã đổi)
    code_version = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12]

    @st.cache_resource(show_spinner="Đang nạp Data Pack, kiểm tra toàn vẹn và lập chỉ mục…")
    def load(version: str):
        checks, fp = verify_integrity()
        _FINGERPRINT["value"] = fp
        dp = DataPack()
        return dp, PolicyAssist(dp), checks, fp

    @st.cache_resource(show_spinner=False)
    def suggester(version: str):
        """Câu mẫu mà hệ thống trả lời được – dùng gợi ý hỏi lại khi ABSTAIN."""
        quiet = base.with_config(write_log=False)
        ok = [q for q in dp.questions.itertuples() if not quiet.answer(q.question_text, q.reference_date, q.question_id).abstain]
        return ok, [set(content_terms(q.question_text)) | content_bigrams(q.question_text) for q in ok], \
            base.tfidf.transform([q.question_text for q in ok])

    def suggestions(question: str, k: int = 3) -> list:
        """Câu mẫu gần chủ đề nhất: trùng từ khóa nội dung (trọng số IDF, bỏ tên doanh nghiệp) rồi mới tới TF-IDF ký tự."""
        ok, terms, X = suggester(code_version)
        q_terms = set(content_terms(question)) | content_bigrams(question)
        sims = (X @ base.tfidf.transform([question]).T).toarray().ravel()
        score = [sum(base.idf.get(t, base.idf_max) for t in q_terms & ts) + sims[i] for i, ts in enumerate(terms)]
        return [ok[i] for i in np.argsort(-np.asarray(score))[:k] if score[i] > 0]

    dp, base, checks, fp = load(code_version)
    _FINGERPRINT["value"] = fp
    pa = base
    qrow = {q.question_id: q for q in dp.questions.itertuples()}
    n_pass, n_fail = int((checks["kết quả"] == "PASS").sum()), int((checks["kết quả"] == "FAIL").sum())

    ss = st.session_state
    ss.setdefault("sess", new_session())
    ss.setdefault("sel", None)
    ss.setdefault("q_text", "")
    ss.setdefault("q_date", SNAPSHOT)           # ngày tham chiếu mặc định = ngày chụp Data Pack, đổi được
    ss.setdefault("auto_date", False)           # ô Tự động: ngày nêu trong câu hỏi, không có thì ngày hôm nay

    # ------------------------------------------------------------------ hành động (callback)
    def ask(question: str, ref, mode: str = "manual"):
        sess = ss.sess
        res = pa.answer(question, ref)
        sess["turns"].append({"time": datetime.now().isoformat(timespec="seconds"), "res": res, "feedback": "",
                              "date_mode": mode})
        sess["title"] = sess.get("title") or short_title(question)
        history_save(sess)
        ss.sel = (len(sess["turns"]) - 1, res.cited_chunks[0] if res.cited_chunks else None)

    def ask_sample(qid: str):
        q = qrow[qid]
        ask(q.question_text, parse_date(q.reference_date), "sample")

    def on_submit():
        qs_ = split_questions(ss.get("q_text", ""))
        if not qs_:
            ss.flash = "Hãy nhập câu hỏi trước khi gửi."
            return
        auto = bool(ss.get("auto_date"))
        # ngày nêu trong câu hỏi luôn được ưu tiên (P1 Planning); tự động + câu không nêu ngày → ngày hôm nay
        ref = date.today() if auto else (ss.get("q_date") or SNAPSHOT)
        for q in qs_[:10]:
            ask(q, ref, "auto" if auto else "manual")
        if len(qs_) > 10:
            ss.flash = "Mỗi lần gửi tối đa 10 câu – đã xử lý 10 câu đầu."
        ss.q_text = ""

    def on_pick():
        qid = ss.get("pick")
        if qid:
            q = qrow[qid]
            ss.q_text, ss.q_date, ss.auto_date = q.question_text, parse_date(q.reference_date) or SNAPSHOT, False
        ss.pick = None

    def select(t: int, cid: str | None):
        ss.sel = (t, cid)

    def give_feedback(t: int, vote: str):
        turn = ss.sess["turns"][t]
        res = turn["res"]
        turn["feedback"] = vote
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(FEEDBACK_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": datetime.now().isoformat(timespec="seconds"), "question_id": res.question_id,
                                "question_source": res.question_source, "question": mask_pii(res.question),
                                "reference_date": res.reference_date, "decision": res.decision,
                                "confidence": round(res.confidence, 3), "citations": res.citations, "vote": vote},
                               ensure_ascii=False) + "\n")
        history_save(ss.sess)

    def start_new():
        ss.sess, ss.sel, ss.goto_qa = new_session(), None, True
        ss.hist_rerun = True                           # nút nằm trong fragment của sidebar → vẽ lại cả trang

    def open_session(sid: str, turn: int | None = None):
        """Mở phiên đã lưu; `turn` = lượt hỏi cần xem khi mở từ kết quả tìm kiếm (cuộn tới và hiện nguồn của lượt đó)."""
        s = history_load(sid)
        if s:
            ss.sess, ss.sel = s, None
            if s["turns"]:
                i = len(s["turns"]) - 1 if turn is None else min(turn, len(s["turns"]) - 1)
                ss.sel = (i, (s["turns"][i]["res"].cited_chunks or [None])[0])
                if turn is not None:
                    ss.focus_turn = i
        ss.goto_qa = ss.hist_rerun = True              # nút nằm trong fragment của sidebar → yêu cầu vẽ lại cả trang

    # menu ⋮ của từng phiên trong LỊCH SỬ TRA CỨU
    def menu_action(action: str, sid: str, title: str, pinned: bool):
        ss[f"hmenu-{sid}"] = False                     # đóng menu
        if action == "pin":
            history_update(sid, pinned=not pinned)
            if ss.sess["id"] == sid:
                ss.sess["pinned"] = not pinned
        else:                                          # Đổi tên / Xoá: mở hộp thoại ở lần chạy toàn trang kế tiếp
            ss.hist_dialog, ss.hist_rerun = (action, sid, title), True

    @st.dialog("Đổi tên phiên tra cứu")
    def rename_dialog(sid: str, title: str):
        new = st.text_input("Tên mới", value=title, max_chars=80, key=f"rn-title-{sid}")
        with st.container(horizontal=True, horizontal_alignment="right"):
            if st.button("Huỷ", key="rn-cancel"):
                st.rerun()
            if st.button("Lưu", key="rn-ok", type="primary"):
                new = re.sub(r"\s+", " ", new).strip()
                if new:
                    history_update(sid, title=new)
                    if ss.sess["id"] == sid:
                        ss.sess["title"] = new
                st.rerun()

    @st.dialog("Xoá phiên tra cứu?")
    def delete_dialog(sid: str, title: str):
        st.html(f'<div class="pa-dlg-text">Phiên <b>{_esc(title)}</b> sẽ bị xoá khỏi lịch sử tra cứu. '
                'Nhật ký kiểm toán (audit log) vẫn được giữ nguyên.</div>')
        with st.container(horizontal=True, horizontal_alignment="right"):
            if st.button("Huỷ", key="del-cancel"):
                st.rerun()
            if st.button("Xoá", key="del-ok", type="primary"):
                history_delete(sid)
                if ss.sess["id"] == sid:
                    ss.sess, ss.sel = new_session(), None
                st.rerun()

    def history_row(it: dict, pats: list | None = None):
        sid = it["id"]
        meta = f"{it['updated'][11:16]} · {it['n']} câu hỏi" + (f" · {it['n_abstain']} ABSTAIN" if it["n_abstain"] else "")
        label, turn = md_escape(it["title"]), None
        if pats is not None:                           # kết quả tìm kiếm: tô sáng từ khoá + đoạn trích chứa từ khoá
            label = md_highlight(it["title_x"], pats)
            if hit := it["hit"]:
                label, turn = f"{label}\n\n{hit[1]}: {md_highlight(hit[2], pats, 90)}", hit[0]
        with st.container(horizontal=True, vertical_alignment="center", gap=None, wrap=False, key=f"hrow-{sid}"):
            st.button(f"{label}\n\n{meta}", key=f"hist-{sid}", on_click=open_session, args=(sid, turn),
                      type="primary" if sid == ss.sess["id"] else "secondary", width="stretch")
            with st.popover("⋮", key=f"hmenu-{sid}", help="Tùy chọn", on_change="rerun"):
                for action, text, icon in (("pin", "Bỏ ghim" if it["pinned"] else "Ghim", "push_pin"),
                                           ("rename", "Đổi tên", "edit"), ("delete", "Xoá", "delete")):
                    st.button(text, key=f"hm-{action}-{sid}", icon=f":material/{icon}:", type="tertiary", width="stretch",
                              on_click=menu_action, args=(action, sid, it["title"], it["pinned"]))

    @st.cache_resource(show_spinner=False)
    def search_box_component(version: str):
        return st.components.v2.component("pa_history_search", html=SEARCH_BOX_HTML, js=SEARCH_BOX_JS, isolate_styles=False)

    @st.fragment
    def sidebar_history():
        """Ô tìm kiếm + Tra cứu mới + LỊCH SỬ TRA CỨU. Gõ tìm, mở menu ⋮ chỉ chạy lại phần này; mở phiên, tra cứu mới hay mở
        hộp thoại thì vẽ lại cả trang."""
        if ss.pop("hist_rerun", False):
            st.rerun()
        box = search_box_component(code_version)(key="hsearch", data={"query": ss.get("hsearch_raw", "")}, default={"query": ""},
                                     on_query_change=lambda: None)
        ss.hsearch_raw = getattr(box, "query", "") or ""
        query = re.sub(r"\s+", " ", ss.hsearch_raw).strip()
        st.button("Tra cứu mới", key="new_sess", icon=":material/add:", on_click=start_new, width="stretch")
        if query:
            pats, found = history_search(query)
            st.html(f'<div class="pa-side-label">KẾT QUẢ TÌM KIẾM · {len(found)} PHIÊN</div>')
            if not found:
                st.html(f'<div class="pa-side-empty">Không có phiên nào chứa “{_esc(query)}”. Thử từ khoá khác, gõ không dấu '
                        'hoặc viết tắt (HĐĐT, MST…).</div>')
            for it in found:
                history_row(it, pats)
            return
        st.html('<div class="pa-side-label">LỊCH SỬ TRA CỨU</div>')
        hist = history_list()
        if not hist:
            st.html('<div class="pa-side-empty">Chưa có phiên nào. Mỗi lần “Tra cứu mới” là một phiên, gồm nhiều câu hỏi; '
                    'phiên được lưu tự động sau câu hỏi đầu tiên.</div>')
        if pinned := [h for h in hist if h["pinned"]]:
            st.html('<div class="pa-day">Đã ghim</div>')
            for it in pinned:
                history_row(it)
        today, last_day = date.today(), None
        for it in (h for h in hist if not h["pinned"]):
            d = parse_date(it["updated"]) or today
            if d != last_day:
                st.html(f'<div class="pa-day">{day_label(d, today)}</div>')
                last_day = d
            history_row(it)

    @st.dialog("Toàn văn trong Data Pack", width="large")
    def show_doc(d: str, cid: str | None = None):
        m = dp.doc[d]
        law = m["source_type"] == "LEGAL"
        eff = f"{fmt_date(m['effective_date']) or '—'} → {fmt_date(m['expiry_date']) or 'nay'}"
        st.html(f'<div class="pa-src" style="padding-top:0"><div class="pills"><span class="pill {"law" if law else "sim"}">'
                f'{"Văn bản pháp luật" if law else "Nội bộ giả lập"} · {_esc(DOC_TYPE_VI.get(m["document_type"], ""))}</span>'
                f'<span class="pill muted">{_esc(m["authority"])}</span><span class="pill muted">Hiệu lực {eff}</span>'
                f'<span class="pill muted">{_esc(m["status"])}</span></div><div><div class="lab">{d}</div>'
                f'<div class="hd">{_esc(m["title"])}</div></div></div>')
        st.iframe(doc_iframe_html(dp, d, cid), height=500)
        c1, c2 = st.columns([1, 2], vertical_alignment="center")
        if m["source_url"]:
            c1.link_button("Mở nguồn gốc", m["source_url"], icon=":material/open_in_new:", width="stretch")
            c2.caption("Trang văn bản gốc do BTC cung cấp trong document_metadata.csv (mở tab mới).")
        else:
            c2.caption("Tài liệu nội bộ giả lập của Nova Việt – không có nguồn ngoài Data Pack.")

    # ------------------------------------------------------------------ các trang
    def page_qa():
        sess = ss.sess
        turns = sess["turns"]
        created = parse_date(sess.get("created")) or date.today()
        h1, h2 = st.columns([1, 1.35], vertical_alignment="center")
        with h1:
            st.html(f'<div class="pa-h1">Phiên tra cứu</div><div class="pa-h1-sub">{WEEKDAY_VI[created.weekday()]}, '
                    f'{created:%d/%m/%Y} · {len(turns)} câu hỏi'
                    + (f' · {sum(t["res"].abstain for t in turns)} ABSTAIN' if any(t["res"].abstain for t in turns) else "")
                    + "</div>")
        with h2:
            integ = (f'<span class="pa-chip ok" title="Kiểm tra toàn vẹn Data Pack (SHA-256 + cấu trúc)">{ic("verified")}Toàn vẹn '
                     f'{n_pass}/{len(checks)}</span>' if not n_fail
                     else f'<span class="pa-chip bad">{ic("error")}Data Pack lệch manifest ({n_fail})</span>')
            st.html(f'<div class="pa-chips"><span class="pa-chip">Data Pack BTC · {len(dp.doc)} tài liệu · {len(dp.chunks)} chunk</span>'
                    f'<span class="pa-chip gold">Cập nhật đến {SNAPSHOT:%d/%m/%Y}</span>{integ}</div>')
        chat, panel = st.columns([2.6, 1], gap="medium")          # vùng tra cứu rộng, panel nguồn gọn bên phải
        with chat:
            focus = ss.pop("focus_turn", None)            # mở từ kết quả tìm kiếm → cuộn tới đúng lượt hỏi
            with st.container(height=600, key="chatlog", autoscroll=bool(turns) and focus is None):
                if not turns:
                    render_welcome()
                for t, turn in enumerate(turns):
                    render_turn(t, turn)
            render_composer()
            if focus is not None:
                # đợi khung hội thoại vẽ xong (chiều cao không đổi giữa hai lần kiểm) rồi cuộn để câu hỏi của lượt đó ở đầu khung
                st.html(f"""<script>(() => {{
                    let n = 0, last = -1;
                    const tick = () => {{
                        const log = document.querySelector('.st-key-chatlog');
                        const card = document.querySelector('.st-key-card-{focus}, .st-key-cardx-{focus}');
                        if (log && card) {{
                            if (log.scrollHeight === last) {{
                                const box = card.closest('[data-testid="stLayoutWrapper"]') || card;
                                const top = (box.previousElementSibling || box).getBoundingClientRect().top;
                                log.scrollTop += top - log.getBoundingClientRect().top - 8;
                                return;
                            }}
                            last = log.scrollHeight;
                        }}
                        if (++n < 40) setTimeout(tick, 150);
                    }};
                    setTimeout(tick, 150);
                }})();</script>""", unsafe_allow_javascript=True)
        with panel:
            with st.container(height=760, key="srcpanel"):
                render_panel(turns)

    def render_welcome():
        st.html('<div class="pa-welcome"><h3>Tra cứu chính sách tài chính – kế toán – thuế có dẫn nguồn</h3>'
                '<p>Hỏi bằng tiếng Việt, có thể viết tắt (HĐĐT, TT, NĐ, MST) hoặc gõ không dấu. Mỗi câu trả lời trích nguyên văn '
                'từ Data Pack của BTC, gắn nguồn bấm mở được và được kiểm tra hiệu lực theo ngày tham chiếu.</p>'
                '<div class="pa-wgrid"><div><b>' + ic("link") + 'Citation mở nguồn</b>Bấm [1], [2]… để xem đoạn gốc, nhãn hiệu lực, chuỗi phiên bản '
                'và toàn văn.</div><div><b>' + ic("history") + 'Đúng phiên bản</b>CHRONOS chọn văn bản còn hiệu lực tại ngày tham chiếu, cảnh báo khi '
                'văn bản đã bị thay thế.</div><div><b>' + ic("block") + 'Biết từ chối</b>Không đủ căn cứ hoặc hỏi dữ liệu thực tế → ABSTAIN, '
                'không bịa thông tin.</div></div></div>')
        st.html('<div class="pa-lbl" style="margin:8px 2px 0">THỬ NHANH VỚI CÂU HỎI MẪU CỦA BTC</div>')
        for qid in FEATURED_SAMPLES:
            if qid in qrow:
                q = qrow[qid]
                st.button(f"{qid} · {q.question_text}", key=f"try-{qid}", on_click=ask_sample, args=(qid,), width="stretch")

    def render_turn(t: int, turn: dict):
        res: Result = turn["res"]
        tm = datetime.fromisoformat(turn["time"])
        vv = version_view(dp, res) if not res.abstain else {"alert": None, "chains": [], "ref": None}
        if res.abstain:
            status = f'<span class="pa-pill abs">{ic("do_not_disturb_on")}ABSTAIN</span>'
        elif vv["alert"]:
            status = f'<span class="pa-pill warn">{ic("warning")}Cảnh báo phiên bản</span>'
        else:
            status = f'<span class="pa-pill ok">{ic("check_circle")}Trả lời có nguồn · {len(res.citations)} nguồn</span>'
        if res.needs_review and not res.abstain:
            status += '<span class="pa-pill amber">Cần chuyên viên rà soát</span>'
        src = (f'<span class="pa-pill sample">Câu mẫu · {res.question_id}</span>' if res.question_source == "sample"
               else f'<span class="pa-pill ext">Câu ngoài bộ mẫu · {_esc(res.question_id)}</span>')
        day = fmt_date(res.applied_date)
        mode = turn.get("date_mode", "")
        when = (f'<span class="from-q">{ic("calendar_month")}{day} · lấy từ câu hỏi</span>' if res.date_source == "question" else
                f'<span>{ic("calendar_month")}Không rõ ngày · mặc định {day}</span>' if res.date_source == "default" else
                f'<span>{ic("calendar_month")}{day} · tự động (hôm nay)</span>' if mode == "auto" else
                f'<span>{ic("calendar_month")}{day} · theo câu mẫu</span>' if mode == "sample" else f"<span>{ic('calendar_month')}{day}</span>")
        rewritten = next((x["chi tiết"] for x in res.trace if x["bước"].startswith("P1a")), "")
        # chỉ hiện khi việc chuẩn hóa giúp người dùng hiểu (gõ không dấu, viết tắt) – không hiện thay thế từ đồng nghĩa nội bộ
        exp = getattr(res, "expansions", None) or []
        helpful = rewritten and (pa.restore_diacritics(res.question) != res.question or exp)
        abbr = f'<span class="pa-abbr">Viết tắt: {_esc(" · ".join(exp))}</span>' if exp else ""
        rw = (f'<div class="pa-rewrite">{ic("subdirectory_arrow_right")}Hệ thống hiểu là: {_esc(rewritten)}{abbr}</div>'
              if helpful else "")
        st.html(f'<div class="pa-meta"><b>{tm:%H:%M}</b>{when}{status}{src}</div>'
                f'<div class="pa-qwrap"><div class="pa-bubble">{_esc(res.question)}</div>{rw}</div>')
        with st.container(key=f"cardx-{t}" if res.abstain else f"card-{t}"):
            st.html(steps_html(res))
            if res.abstain:
                render_abstain(t, res)
            else:
                render_answer(t, res, vv)
            render_footer(t, turn)

    def chip_row(t: int, kind: str, refs: list[int], res: Result):
        sel = ss.get("sel")
        with st.container(horizontal=True, gap="small", key=f"chips{kind}-{t}"):
            for n in refs:
                cid = res.cited_chunks[n - 1]
                on = sel is not None and sel[0] == t and sel[1] == cid
                st.button(f"[{n}] {dp.label[cid]}", key=f"c{kind}-{t}-{n}", on_click=select, args=(t, cid),
                          type="primary" if on else "secondary", help="Mở đoạn gốc trong panel nguồn")

    def render_answer(t: int, res: Result, vv: dict):
        kp = res.key_point or {}
        key_items = {u.strip() for u in (kp.get("items") or [kp.get("text", "")]) if u.strip()}
        if vv["alert"]:
            a = vv["alert"]
            st.html(f'<div class="pa-alert" role="alert"><div class="ico">{ic("warning")}</div><div><b>{_esc(a["title"])}</b>'
                    f'<span>{emphasize(a["text"])}</span></div></div>')
        for ch in vv["chains"]:
            st.html(timeline_html(dp, ch, vv["ref"]))
        if kp:
            refs = "".join(f'<span class="pa-ref">[{n}]</span>' for n in kp.get("refs", []))
            pol = f'<b class="pa-pol">{_esc(kp["polarity"])}.</b> ' if kp.get("polarity") else ""
            st.html(f'<div class="pa-concl"><div class="pa-lbl">KẾT LUẬN</div><p>{pol}{emphasize(kp["text"])} {refs}</p></div>')
        version = res.intent == "VERSIONING"
        first_version = version and res.claims and res.claims[0]["kind"] == "version"
        groups = {"V": [], "L": [], "I": []}
        for k, cl in enumerate(res.claims):
            if cl["kind"] == "chain" or (cl["kind"] == "meta"):
                continue
            g = "I" if cl["kind"] == "internal" else ("V" if version else "L")
            groups[g].append((k, cl))
        heads = {"V": '<span class="pa-lbl law">CĂN CỨ HIỆU LỰC (CHRONOS)</span>',
                 "L": '<span class="pa-lbl law">CĂN CỨ PHÁP LUẬT</span>',
                 "I": '<span class="pa-lbl int">QUY TRÌNH NỘI BỘ</span><span class="pa-sim-tag">Nova Việt – tài liệu nội bộ giả lập</span>'}
        for g in ("V", "L", "I"):
            items = groups[g]
            if not items:
                continue
            refs = list(dict.fromkeys(n for _, cl in items for n in cl["refs"]))
            html_parts = []
            for k, cl in items:
                if first_version and k == 0:           # mệnh đề hiệu lực đầu tiên đã nêu ở KẾT LUẬN
                    continue
                cid = res.cited_chunks[cl["refs"][0] - 1] if cl["refs"] else ""
                chunk = dp.chunks[dp.idx[cid]] if cid else {}
                lines = bool(chunk) and ("\n" in chunk.get("chunk_text", "") or chunk.get("content_type") == "SOURCE_TABLE_TEXT")
                rest = [u for u in (cl.get("units") or [cl["text"]]) if u.strip() not in key_items]   # câu đã nêu ở KẾT LUẬN không lặp
                if rest:
                    html_parts.append(claim_html(dict(cl, units=rest), key_items, lines))
            if not html_parts:
                for rf_num in refs:
                    if 0 < rf_num <= len(res.cited_chunks):
                        cid = res.cited_chunks[rf_num - 1]
                        chunk = dp.chunks[dp.idx[cid]] if cid in dp.idx else {}
                        if chunk:
                            lines = bool(chunk) and ("\n" in chunk.get("chunk_text", "") or chunk.get("content_type") == "SOURCE_TABLE_TEXT")
                            lbl = dp.label.get(cid, cid)
                            txt = f"{lbl}: {chunk.get('chunk_text', '')}"
                            html_parts.append(claim_html({"text": txt, "units": [txt], "refs": [rf_num]}, key_items, lines))
            with st.container(key=f"blk{g}-{t}"):
                st.html(f'<div class="pa-bhead">{heads[g]}</div>{"".join(html_parts)}')
                chip_row(t, g, refs, res)
        vnotes, other = split_notes(res)
        note = chronos_note(dp, res) if not version else ""
        if note:
            vnotes = [note] + vnotes
        if vnotes:
            lis = "".join(f"<li>{emphasize(w)}</li>" for w in vnotes)
            st.html(f'<div class="pa-note amber"><div class="pa-lbl">{ic("history")}LƯU Ý HIỆU LỰC</div><ul>{lis}</ul></div>')
        if other:
            lis = "".join(f"<li>{emphasize(w)}</li>" for w in other)
            st.html(f'<div class="pa-note info"><div class="pa-lbl">LƯU Ý VỀ NGUỒN</div><ul>{lis}</ul></div>')

    def render_abstain(t: int, res: Result):
        why = res.reason or "Không đủ căn cứ."
        stop = (res.trace[-1]["bước"] if res.trace else "P0 Guard")
        if res.intent == "OUT_OF_SCOPE":
            sub = ("Data Pack chỉ có dữ liệu giả lập của Công ty Cổ phần Nova Việt và văn bản pháp luật được BTC cung cấp; "
                   "hệ thống không đoán và không tự tạo dữ liệu thực tế.")
        elif "G6" in why:
            sub = "Văn bản liên quan có nhiều phiên bản nhưng câu hỏi chưa có ngày tham chiếu, nên không thể chọn đúng phiên bản."
        elif "G7" in why:
            sub = ("Data Pack có nói về chủ đề của câu hỏi nhưng không có thông tin về điều được hỏi, nên hệ thống từ chối thay "
                   "vì trả lời lạc đề.")
        else:
            sub = "Các đoạn tìm được không bao quát đủ nội dung câu hỏi, nên hệ thống từ chối thay vì suy đoán."
        st.html(f'<p class="pa-abs-title">{_esc(res.answer)}</p><p class="pa-abs-sub">{_esc(sub)}</p>'
                f'<dl class="pa-abs-grid"><div><dt>LÝ DO</dt><dd>{_esc(why)}</dd></div>'
                f'<div><dt>DỪNG Ở BƯỚC</dt><dd>{_esc(stop)}</dd></div>'
                f'<div><dt>NGUỒN DẪN</dt><dd>Không có – câu từ chối không kèm citation.</dd></div></dl>')
        if "G6" in why:
            st.button(f"Hỏi lại với ngày {SNAPSHOT:%d/%m/%Y}", key=f"sug-{t}-date", icon=":material/refresh:", on_click=ask, args=(res.question, SNAPSHOT))
            return
        top = suggestions(next((x["chi tiết"] for x in res.trace if x["bước"].startswith("P1a")), res.question))
        if top:
            st.html('<div class="pa-lbl" style="margin-top:2px">GỢI Ý HỎI LẠI · DATA PACK CÓ CĂN CỨ CHO CÁC CÂU NHƯ</div>')
            for q in top:
                st.button(f"{q.question_id} · {q.question_text}", key=f"sug-{t}-{q.question_id}", on_click=ask_sample,
                          args=(q.question_id,), width="stretch")

    def render_footer(t: int, turn: dict):
        res: Result = turn["res"]
        c = res.confidence
        cls = "c-hi" if c >= base.cfg.review_confidence else ("c-mid" if c >= base.cfg.min_confidence else "c-lo")
        with st.container(horizontal=True, vertical_alignment="center", gap="small", key=f"foot-{t}"):
            st.html(f'<div class="pa-foot"><span>Độ tin cậy <b class="{cls}">{c:.2f}</b></span>'
                    f'<span>Thời gian xử lý <b>{res.latency_ms} ms</b></span></div>', width="content")
            st.space("stretch")
            if turn.get("feedback"):
                st.html(f'<span class="pa-pill {"ok" if turn["feedback"] == "up" else "amber"}">Đã đánh giá: '
                        f'{"Hữu ích" if turn["feedback"] == "up" else "Chưa đúng"}</span>', width="content")
            else:
                st.button("Hữu ích", key=f"fb-up-{t}", icon=":material/thumb_up:", on_click=give_feedback, args=(t, "up"))
                st.button("Chưa đúng", key=f"fb-down-{t}", icon=":material/thumb_down:", on_click=give_feedback, args=(t, "down"))
            with st.popover("Chi tiết", icon=":material/account_tree:", help="Pipeline trace, Evidence Ledger, cổng đủ căn cứ, Citation Audit", key=f"det-{t}"):
                render_details(t, res)

    def render_details(t: int, res: Result):
        tabs = st.tabs(["Trace", "Evidence Ledger", "Cổng G1–G6", "Citation Audit"], key=f"dtabs-{t}")
        with tabs[0]:
            st.dataframe(pd.DataFrame(res.trace), hide_index=True, width="stretch")
        with tabs[1]:
            cols = ["rank", "citation", "role", "state", "score", "coverage", "terms_hit", "via"]
            if res.ledger:
                st.dataframe(pd.DataFrame(res.ledger)[[c for c in cols if c in res.ledger[0]]], hide_index=True, width="stretch")
            else:
                st.caption("Dừng trước bước truy xuất.")
        with tabs[2]:
            st.dataframe(pd.DataFrame(res.gate), hide_index=True, width="stretch") if res.gate else st.caption("Không chạy.")
        with tabs[3]:
            st.dataframe(pd.DataFrame(res.audit), hide_index=True, width="stretch") if res.audit else st.caption("Không chạy.")

    def render_composer():
        with st.container(key="composer"):
            if ss.get("flash"):
                st.toast(ss.pop("flash"))
            # hàng 1: ô câu hỏi + nút Gửi (Ctrl+Enter để gửi)
            with st.form("ask", border=False):
                with st.container(horizontal=True, vertical_alignment="bottom", gap="small", key="askrow"):
                    st.text_area("Câu hỏi", key="q_text", height=68, label_visibility="collapsed",
                                 placeholder="Nhập câu hỏi…")
                    st.form_submit_button("Gửi", type="primary", icon=":material/send:", on_click=on_submit, key="send")
            # hàng 2 (mảnh): ngày tham chiếu quyết định văn bản nào còn hiệu lực
            auto = bool(ss.get("auto_date"))
            with st.container(horizontal=True, vertical_alignment="center", gap="small", wrap=False, key="daterow"):
                st.html(f'<span class="pa-dlab">{ic("calendar_month")}Ngày tham chiếu</span>', width="content")
                st.date_input("Ngày tham chiếu", key="q_date", format="DD/MM/YYYY", label_visibility="collapsed",
                              width=132, disabled=auto, min_value=date(2010, 1, 1), max_value=date(2035, 12, 31))
                st.checkbox("Tự động", key="auto_date",
                            help="Dùng ngày nêu trong câu hỏi; câu không nêu ngày thì dùng ngày hôm nay.")
                hint = (f"theo ngày trong câu hỏi, nếu không có: hôm nay <b>{date.today():%d/%m/%Y}</b>" if auto
                        else "ngày nêu trong câu hỏi (nếu có) được ưu tiên")
                st.html(f'<span class="pa-hint">{hint}</span>', width="stretch")
                with st.popover("Câu mẫu", icon=":material/list_alt:", key="samplepop", help="Chọn 1 trong 90 câu hỏi mẫu của BTC (tự điền câu hỏi và ngày)"):
                    st.selectbox("Câu hỏi mẫu của BTC", list(qrow), index=None, key="pick", on_change=on_pick,
                                 format_func=lambda x: f"{x} · {qrow[x].question_text}",
                                 placeholder="Gõ để tìm trong 90 câu hỏi mẫu…")

    def render_panel(turns: list[dict]):
        sel = ss.get("sel")
        valid = sel is not None and 0 <= sel[0] < len(turns)
        head = f'<div class="pa-src-h"><b>Nguồn trích dẫn</b>'
        if valid:
            head += f'<span class="pa-pill sample">Câu {sel[0] + 1}/{len(turns)}</span>'
        st.html(head + "</div>")
        if not turns or not valid:
            st.html('<div class="pa-src"><div class="empty"><b>Chưa có nguồn nào được mở</b>Đặt câu hỏi rồi bấm vào nguồn [1], [2]… '
                    'trong câu trả lời để xem đoạn gốc, nhãn hiệu lực và chuỗi phiên bản.</div></div>' + PRIORITY_HTML)
            return
        t, cid = sel
        res: Result = turns[t]["res"]
        if res.abstain:
            st.html('<div class="pa-src"><div class="empty"><b>' + ic("link_off") + 'Không có nguồn được trích dẫn</b>Câu trả lời ABSTAIN không kèm '
                    'nguồn, để tránh gợi ý rằng thông tin có trong Data Pack.</div><div class="pa-note info"><div class="pa-lbl">'
                    'PHẠM VI TRA CỨU</div>12 văn bản pháp luật (LAW01–LAW12) và 8 tài liệu nội bộ giả lập của Nova Việt '
                    '(SIM01–SIM08). Không gồm dữ liệu đăng ký, tài chính hay nhân sự thực của doanh nghiệp.</div></div>')
            return
        if cid is None or cid not in res.cited_chunks:
            st.html(f'<div class="pa-src"><div class="empty"><b>Chọn một nguồn</b>Bấm [1]–[{len(res.cited_chunks)}] trong câu '
                    'trả lời để mở đoạn gốc, nhãn hiệu lực và chuỗi phiên bản.</div></div>' + PRIORITY_HTML)
            return
        n = res.cited_chunks.index(cid) + 1
        st.html(source_html(dp, res, n, cid))
        c = dp.chunks[dp.idx[cid]]
        url = c["source_url"] or dp.doc[c["document_id"]]["source_url"]
        if st.button("Xem toàn văn bản trong Data Pack", key="srcfull", icon=":material/description:", type="primary", width="stretch"):
            show_doc(c["document_id"], cid)
        with st.container(horizontal=True, gap="small", key="srcbtns"):
            if url:
                st.link_button("Mở nguồn gốc", url, icon=":material/open_in_new:", help="Trang văn bản gốc (source_url trong Data Pack)", width="stretch")
            else:
                st.link_button("Mở nguồn gốc", "about:blank", icon=":material/open_in_new:", disabled=True, width="stretch",
                               help="Tài liệu nội bộ giả lập – không có nguồn gốc ngoài Data Pack")
            st.button("Đóng", key="srcclose", icon=":material/close:", on_click=select, args=(t, None))

    def page_submit():
        st.html('<div class="pa-h1">Xuất bài nộp</div><div class="pa-h1-sub">Chạy bộ câu hỏi và ghi <b>outputs/submission.csv</b> '
                'đúng 8 cột của submission_output_template.csv – mỗi câu hỏi đúng một dòng.</div>')
        with st.expander("Dùng bộ câu hỏi khác (CSV có cột question_id, question_text, reference_date)"):
            up = st.file_uploader("Tải lên CSV", type=["csv"], label_visibility="collapsed")
        qdf = dp.questions
        if up is not None:
            qdf = pd.read_csv(up, dtype=str, keep_default_na=False, encoding="utf-8-sig")
            need = {"question_id", "question_text", "reference_date"}
            if not need <= set(qdf.columns):
                st.error(f"Thiếu cột: {', '.join(sorted(need - set(qdf.columns)))}")
                return
        if st.button(f"Chạy {len(qdf)} câu hỏi và xuất submission.csv", icon=":material/play_arrow:", type="primary"):
            bar = st.progress(0.0, text="Đang xử lý…")
            sub, results = run_batch(pa, qdf, lambda n, tot, q: bar.progress(n / tot, text=f"{q} ({n}/{tot})"))
            bar.empty()
            try:
                path = save_submission(sub, OUTPUT_DIR / "submission.csv")
            except PermissionError as exc:
                st.error(str(exc))
                return
            ss.batch = {"sub": sub, "review": sum(r.needs_review for r in results), "path": str(path),
                        "time": datetime.now()}
        b = ss.get("batch")
        path = OUTPUT_DIR / "submission.csv"
        if b is None and path.exists():
            b = {"sub": read_csv(path), "review": None, "path": str(path), "time": datetime.fromtimestamp(path.stat().st_mtime)}
        if b is None:
            st.info("Chưa có submission.csv – bấm nút phía trên để chạy.")
            return
        sub = b["sub"]
        csv_path = Path(b["path"])
        data = csv_path.read_bytes() if csv_path.exists() else submission_bytes(sub)    # tải về = đúng file đã lưu
        problems = check_submission_file(data, sub)
        lat = pd.to_numeric(sub.latency_ms, errors="coerce")
        stats = [(int((sub.abstain == "FALSE").sum()), "Đã trả lời"), (int((sub.abstain == "TRUE").sum()), "ABSTAIN"),
                 (f"{lat.mean():.0f} ms", "Latency trung bình")]
        if b["review"] is not None:
            stats.append((b["review"], "Cần chuyên viên rà soát"))
        st.html('<div class="pa-stats">' + "".join(f'<div class="pa-stat"><b>{v}</b><span>{k}</span></div>' for v, k in stats) + "</div>")
        if problems:
            st.error("File submission.csv chưa đạt: " + "; ".join(problems))
        view = sub.copy()
        for col in ("confidence", "latency_ms"):
            view[col] = pd.to_numeric(view[col], errors="coerce")
        st.dataframe(view, hide_index=True, width="stretch", height=400, column_config={
            "question_id": st.column_config.TextColumn("question_id", width=100),
            "answer": st.column_config.TextColumn("answer", width="large"),
            "confidence": st.column_config.NumberColumn("confidence", format="%.3f", width="small"),
            "abstain": st.column_config.TextColumn("abstain", width="small"),
            "latency_ms": st.column_config.NumberColumn("latency_ms", format="%d", width="small")})
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.download_button("submission.csv", data, "submission.csv", "text/csv", icon=":material/download:", type="primary",
                               disabled=bool(problems))
            st.download_button("submission.xlsx – mở bằng Excel", submission_xlsx_bytes(sub), "submission.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:")
            st.caption(f"Lưu tại {csv_path.relative_to(ROOT) if csv_path.is_relative_to(ROOT) else csv_path} và "
                       f"{csv_path.with_suffix('.xlsx').name} · {b['time']:%H:%M %d/%m/%Y}")

    def page_kpi():
        st.html('<div class="pa-h1">Đánh giá KPI</div>')
        kpi_csv = OUTPUT_DIR / "kpi_7.csv"
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            run = st.button("Chạy đánh giá", icon=":material/play_arrow:", type="primary",
                            help="Đo lại toàn bộ KPI trên Dev-30, Ext-60, Stress-60, Probe-25, Paraphrase-52 (khoảng 1–2 phút)")
            if kpi_csv.exists() and not run:
                # thời điểm chạy đánh giá ghi trong run_manifest.json; giờ sửa file chỉ dùng khi thiếu manifest (trên máy chủ
                # đám mây giờ sửa file là lúc git checkout, không phải lúc đánh giá)
                when = None
                try:
                    when = datetime.fromisoformat(json.loads((OUTPUT_DIR / "run_manifest.json").read_text(encoding="utf-8"))["thời điểm"])
                except (OSError, ValueError, KeyError, TypeError):
                    when = datetime.fromtimestamp(kpi_csv.stat().st_mtime)
                st.caption(f"Cập nhật lúc {when:%H:%M %d/%m/%Y}")
        if run:
            bar = st.progress(0.0)
            ev = run_evaluation(base, lambda n, tot, lab: bar.progress(n / tot, text=lab))
            bar.empty()
            write_eval_report(ev, fp)
            ss.ev = ev
        ev = ss.get("ev")
        kp = ev["kpis"] if ev else (read_csv(kpi_csv) if kpi_csv.exists() else None)
        if kp is None:
            st.info("Chưa có kết quả – bấm “Chạy đánh giá”.")
            return
        fe = ev.get("full") if ev else None
        fsum = fe["summary"] if fe else (read_csv(OUTPUT_DIR / "eval_by_set.csv") if (OUTPUT_DIR / "eval_by_set.csv").exists()
                                        else None)
        views =[v for v in KPI_VIEWS if v == "Dev-30 + Probe-25" or (fsum is not None and (fsum["tập"] == v).any())]
        view = st.segmented_control("Tập đo", views, default=views[0], key="kpi_view") or views[0]
        names = ["Dev-30", "Probe-25"] if view == "Dev-30 + Probe-25" else [view]
        st.html(f'<div class="pa-kpi-note"><b>{_esc(view)}</b>: {_esc(KPI_VIEWS[view])}</div>')
        sk = {} if fsum is None else set_kpis(fsum, names, "CHRONOS-LEDGER")
        sb = {} if fsum is None else set_kpis(fsum, names, "B0 – BM25 thuần")
        fnum = lambda x: None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)
        rows, tiles, items = [], [], []
        for (k, name, op, target, _src), r in zip(KPI_SPECS, kp.to_dict("records")):
            if view == "Dev-30 + Probe-25":      # số của tập phát triển: như kpi_7.csv (latency gồm cả 90 câu public)
                v = float(r["giá trị"])
                try:
                    b0 = float(r.get("baseline B0", ""))
                except (TypeError, ValueError):
                    b0 = None
                ex = r.get("chỉ số kèm", "")
                ex = "" if pd.isna(ex) else str(ex)
            else:
                v, b0 = fnum(sk.get(k)), fnum(sb.get(k))
                if v is None:
                    continue
                ex = set_kpi_extra(k, sk)
            tiles.append(kpi_tile_html(k, op, target, v, b0, ex))
            sign = "≥" if op == ">=" else "≤"
            better = None if b0 is None or k == "latency_ms_avg" else (v < b0 if op == "<=" else v > b0)
            rows.append({"KPI": KPI_SHORT[k], "Mục tiêu": f"{sign} {target:g}", "Baseline B0": b0, "Hệ thống": v,
                         "Chênh lệch": None if b0 is None else round(v - b0, 3),
                         "Kết quả": "Đạt" if kpi_status(k, v) else "Chưa đạt", "_better": better})
            if better is not None:
                items.append({"label": KPI_SHORT[k] + ("|(càng thấp càng tốt)" if op == "<=" else ""), "name": KPI_SHORT[k],
                              "v": v, "b0": b0, "target": target, "tgt": f"{sign} {target:g}",
                              "gain": (v - b0) if op == ">=" else (b0 - v)})
        n_ok = sum(r["Kết quả"] == "Đạt" for r in rows)
        st.html(f'<div class="pa-sum"><span class="ok">{ic("check_circle")}{n_ok}/{len(rows)} KPI đạt mục tiêu</span>'
                f'<span>{ic("trending_up")}Tốt hơn baseline ở {sum(it["gain"] > 0 for it in items)}/{len(items)} KPI chất lượng</span></div>')
        st.html(f'<div class="pa-kpis">{"".join(tiles)}</div>')
        st.html(f'<div class="pa-kpi-note">Số lớn trong mỗi ô: hệ thống trên tập <b>{_esc(view)}</b>; mũi tên so với baseline B0 '
                '(BM25 thuần); dòng nhỏ: số câu và khoảng tin cậy 95%. Đổi tập ở nút <b>Tập đo</b> phía trên – xem mục '
                '<b>Cách đo từng KPI</b> ở cuối trang.</div>')

        # ---- biểu đồ so sánh
        summ = ev["summary"] if ev else (read_csv(OUTPUT_DIR / "eval_summary.csv") if (OUTPUT_DIR / "eval_summary.csv").exists() else None)
        abl = fe["ablation"] if fe else (read_csv(OUTPUT_DIR / "ablation_B0_B6.csv")
                                         if (OUTPUT_DIR / "ablation_B0_B6.csv").exists() else None)
        set_its, set_series = set_items(fsum) if fsum is not None and len(fsum) else ([], [])
        if items or set_its:
            st.html('<div class="pa-sec">So sánh trực quan</div>')
            cols = st.columns(2, gap="medium") if items and set_its else [st.container()]
        if items:
            best = max(items, key=lambda it: it["gain"])
            with cols[0], st.container(key="chart-b0"):
                st.html(card_head_html(
                    "Hệ thống so với baseline B0", f"{view} · 6 KPI chất lượng trên thang 0–1 · vạch đen là mục tiêu",
                    f'Tốt hơn baseline ở <b>{sum(it["gain"] > 0 for it in items)}/{len(items)}</b> KPI; cải thiện nhiều nhất: '
                    f'<b>{_esc(best["name"])}</b> ({best["b0"]:.3f} → {best["v"]:.3f}).'
                    + (" Trên tập phát triển số của hệ thống lạc quan – nên trình bày Public-90 và Stress-60."
                       if view == "Dev-30 + Probe-25" else ""),
                    [("sys", "Hệ thống CHRONOS-LEDGER"), ("b0", "Baseline B0 – BM25 thuần"), ("tk", "Mục tiêu")]))
                st.altair_chart(chart_pairs(items, [("Baseline B0 – BM25 thuần", "b0", CH_B0),
                                                    ("Hệ thống CHRONOS-LEDGER", "v", CH_SYS)], target=True),
                                theme=None, width="stretch")
        if set_its:
            low = min(((it[key], it["name"], lab) for it in set_its for lab, key, _ in set_series), key=lambda x: x[0])
            with cols[-1], st.container(key="chart-sets"):
                st.html(card_head_html(
                    "KPI theo tập đánh giá", "Cùng hệ thống trên 3 tập có nhãn · thang 0–1",
                    f'Thấp nhất: <b>{_esc(low[1])}</b> trên {_esc(low[2])} ({low[0]:.3f}). Dev-30 dùng đáp án của BTC; Ext-60 '
                    'là nhãn đội gán; Stress-60 là câu khó do đội viết (đã dùng phân tích lỗi từ 10/11/2026).',
                    [(("set1", "set2", "set3")[i], lab) for i, (lab, _, _) in enumerate(set_series)]))
                st.altair_chart(chart_pairs(set_its, set_series), theme=None, width="stretch")
        if abl is not None and len(abl):
            steps, note = ablation_steps_html(abl)
            if steps:
                with st.container(key="chart-abl-steps"):
                    st.html(card_head_html("Mỗi khối của pipeline đóng góp gì? (thêm dần B0 → B6)",
                                           "Public-90 (Dev-30 + Ext-60) · mỗi hàng bật thêm một khối so với hàng trên · "
                                           "ô càng xanh đậm = KPI tăng càng nhiều ở bước đó", note) + steps)
        if summ is not None:
            heat, note = ablation_html(summ)
            if heat:
                with st.container(key="chart-abl"):
                    st.html(card_head_html("Bỏ từng thành phần khỏi hệ thống đầy đủ",
                                           "Dev-30 + Probe-25 · ô càng đỏ = KPI càng kém đi khi bỏ thành phần đó; ô xám = "
                                           "không đổi vì các thành phần còn lại bù được", note) + heat)
        with st.expander("Bảng số liệu"):
            st.dataframe(pd.DataFrame(rows).drop(columns=["_better"]), hide_index=True, width="stretch", column_config={
                "Baseline B0": st.column_config.NumberColumn(format="%.3f"),
                "Hệ thống": st.column_config.NumberColumn(format="%.3f"),
                "Chênh lệch": st.column_config.NumberColumn(format="%+.3f")})
            st.caption("Baseline B0 = BM25 thuần: câu hỏi nguyên văn, lấy 5 đoạn điểm BM25 cao nhất, trả lời bằng đoạn đứng đầu, "
                       "luôn trả lời (không kiểm tra hiệu lực, thẩm quyền, citation hay độ đủ căn cứ).")
            if fsum is not None and len(fsum):
                st.caption("KPI theo tập (eval_by_set.csv)")
                show = [c for c in ("tập", "hệ thống", "số câu", "recall_at_5", "mrr", "answer_accuracy", "answer_correctness",
                                    "citation_accuracy", "unsupported_rate", "abstention_f1", "versioning_accuracy",
                                    "source_priority", "quyết định đúng", "latency_ms_avg", "latency_ms_p95") if c in fsum]
                st.dataframe(fsum[show], hide_index=True, width="stretch")
            if abl is not None and len(abl):
                st.caption("Ablation thêm dần B0 → B6 (ablation_B0_B6.csv)")
                st.dataframe(abl, hide_index=True, width="stretch")
        with st.expander("Cách đo từng KPI – công thức", icon=":material/functions:"):
            st.html(f'<div class="pa-kpi-note">Cách tính 7 KPI và chỉ số phụ; <b>Kết quả</b> là giá trị trên tập đang chọn '
                    f'(<b>{_esc(view)}</b>), lấy trực tiếp từ lần đo gần nhất.</div>')
            val = {r["KPI"]: r for r in rows}
            for n, m in enumerate(KPI_METHOD, 1):
                r = val.get(KPI_SHORT[m["k"]])
                res_txt = ""
                if r is not None:
                    v = r["Hệ thống"]
                    res_txt = (f'{v:.0f} ms' if m["k"] == "latency_ms_avg" else f"{v:.3f}".replace(".", ",")) \
                        + f' ({_esc(r["Kết quả"])})'
                with st.container(border=True, key=f"kpi-method-{m['k']}"):
                    st.html(kpi_method_html(m, n, res_txt))
                    for f_ in m["formulas"]:
                        st.latex(r"\small " + f_)
                    st.html("<ul class='pa-desc pa-m-r'>" + "".join(f"<li>{_esc(t)}</li>" for t in m["rules"]) + "</ul>")
            with st.container(border=True, key="kpi-method-sp"):
                st.html(kpi_method_html(KPI_METHOD_EXTRA, 0))
                for f_ in KPI_METHOD_EXTRA["formulas"]:
                    st.latex(r"\small " + f_)
                st.html("<ul class='pa-desc pa-m-r'>" + "".join(f"<li>{_esc(t)}</li>" for t in KPI_METHOD_EXTRA["rules"]) + "</ul>")

    def page_docs():
        st.html('<div class="pa-h1">Kho tài liệu</div><div class="pa-h1-sub">20 tài liệu của Data Pack (12 văn bản pháp luật, '
                '8 tài liệu nội bộ giả lập) · trạng thái hiệu lực theo ngày bạn chọn.</div>')
        ref_view = st.date_input("Trạng thái hiệu lực tại ngày", SNAPSHOT, key="lib_date", format="DD/MM/YYYY", width=220,
                                 min_value=date(2010, 1, 1), max_value=date(2035, 12, 31))
        table = pd.DataFrame([{"Mã": d, "Tên văn bản": m["title"], "Loại": DOC_TYPE_VI.get(m["document_type"], m["document_type"]),
                               "Hiệu lực": f"{fmt_date(m['effective_date']) or '—'} → {fmt_date(m['expiry_date']) or 'nay'}",
                               "Trạng thái tại ngày chọn": STATE_VI[dp.doc_state(d, ref_view)],
                               "Chunk": len(dp.doc_chunks.get(d, []))} for d, m in dp.doc.items()])
        st.dataframe(table, hide_index=True, width="stretch", height=390, column_config={
            "Tên văn bản": st.column_config.TextColumn(width="large"), "Chunk": st.column_config.NumberColumn(width="small")})
        st.html('<div class="pa-sec">Chuỗi phiên bản (đồ thị thay thế trong document_metadata.csv)</div>')
        st.html("".join(f'<div class="pa-tlbox">{timeline_html(dp, ch, ref_view, "ngày chọn")}</div>' for ch in dp.chains()))
        st.html('<div class="pa-sec">Mở tài liệu</div>')
        c1, c2, c3 = st.columns([3, 1, 1], vertical_alignment="bottom")
        d = c1.selectbox("Tài liệu", list(dp.doc), format_func=lambda x: f"{x} – {dp.doc[x]['title']}")
        if c2.button("Xem toàn văn", icon=":material/description:", width="stretch"):
            show_doc(d)
        if dp.doc[d]["source_url"]:
            c3.link_button("Mở nguồn gốc", dp.doc[d]["source_url"], icon=":material/open_in_new:", width="stretch")

    def page_logs():
        st.html('<div class="pa-h1">Nhật ký &amp; toàn vẹn</div><div class="pa-h1-sub">Audit log từng lượt tra cứu (đã che thông tin '
                'cá nhân) · phản hồi người dùng · kiểm tra toàn vẹn Data Pack.</div>')
        t1, t2, t3 = st.tabs([":material/receipt_long: Nhật ký tra cứu", ":material/feedback: Phản hồi", ":material/verified_user: Toàn vẹn Data Pack"])
        with t1:
            logs = read_jsonl(AUDIT_LOG, 2000)
            rows = []
            for e in reversed(logs):
                qid, srcq = e.get("question_id", ""), e.get("question_source", "")
                if not srcq:                       # bản ghi cũ: suy ra bằng so khớp với 90 câu mẫu
                    hit = dp.match_sample(e.get("question", ""))
                    srcq = "sample" if hit else "external"
                    qid = hit or ("—" if qid in ("ADHOC", "EXT", "") else qid)
                ts = parse_date(e.get("timestamp"))
                rows.append({"Thời gian": _fmt_ts(e.get("timestamp", "")),
                             "Loại câu hỏi": "Câu mẫu" if srcq == "sample" else "Câu ngoài",
                             "Mã câu": qid if qid not in ("ADHOC", "EXT") else "—", "Câu hỏi": e.get("question", ""),
                             "Ngày áp dụng": fmt_date(e.get("applied_date", "")), "Kết quả": e.get("decision", ""),
                             "Tin cậy": float(e.get("confidence", 0) or 0), "Số nguồn": len(e.get("citations") or []),
                             "ms": e.get("latency_ms"), "_review": bool(e.get("needs_review")), "_day": ts,
                             "_intent": e.get("intent", "")})
            if not rows:
                st.info("Chưa có bản ghi.")
            else:
                ldf = pd.DataFrame(rows)
                stats = [(len(ldf), "Lượt tra cứu"), (int((ldf["Loại câu hỏi"] == "Câu mẫu").sum()), "Câu mẫu của BTC"),
                         (int((ldf["Loại câu hỏi"] == "Câu ngoài").sum()), "Câu ngoài bộ mẫu"),
                         (int((ldf["Kết quả"] == "ABSTAIN").sum()), "ABSTAIN")]
                st.html('<div class="pa-stats">' + "".join(f'<div class="pa-stat"><b>{v}</b><span>{k}</span></div>'
                                                          for v, k in stats) + "</div>")
                groups = [(lab, int((g["Kết quả"] == "ANSWER").sum()), int((g["Kết quả"] == "ABSTAIN").sum()))
                          for code, lab in INTENT_VI.items() if len(g := ldf[ldf["_intent"] == code])]
                if groups:
                    oos = next((x for x in groups if x[0] == INTENT_VI["OUT_OF_SCOPE"]), None)
                    ins = [x for x in groups if x is not oos]
                    n_in = sum(a + b for _, a, b in ins)
                    note = " · ".join(([f"Câu trong phạm vi được trả lời có nguồn <b>{fmt_pct(sum(a for _, a, _ in ins) / n_in)}</b>"]
                                       if n_in else [])
                                      + ([f"câu ngoài phạm vi được từ chối <b>{fmt_pct(oos[2] / (oos[1] + oos[2]))}</b>"]
                                         if oos else []))
                    note = note[:1].upper() + note[1:]
                    with st.container(key="chart-dec"):
                        st.html(card_head_html("Kết quả theo loại câu hỏi",
                                               "Tỷ lệ trả lời có nguồn và từ chối (ABSTAIN) trên toàn bộ nhật ký, theo loại câu hỏi "
                                               "do bước Planning xác định", note + ".",
                                               [("sys", "Trả lời có nguồn"), ("abs", "Từ chối (ABSTAIN)")]))
                        st.altair_chart(chart_decisions(groups), theme=None, width="stretch")
                f = st.segmented_control("Lọc", ["Tất cả", "Câu mẫu", "Câu ngoài", "ABSTAIN", "Cần rà soát"], default="Tất cả",
                                         label_visibility="collapsed")
                if f in ("Câu mẫu", "Câu ngoài"):
                    ldf = ldf[ldf["Loại câu hỏi"] == f]
                elif f == "ABSTAIN":
                    ldf = ldf[ldf["Kết quả"] == "ABSTAIN"]
                elif f == "Cần rà soát":
                    ldf = ldf[ldf["_review"]]
                st.dataframe(ldf.drop(columns=["_review", "_day", "_intent"]), hide_index=True, width="stretch", height=430, column_config={
                    "Câu hỏi": st.column_config.TextColumn(width="large"),
                    "Tin cậy": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f", width="small"),
                    "Số nguồn": st.column_config.NumberColumn(width="small"), "ms": st.column_config.NumberColumn(width="small")})
                st.download_button("Tải audit_log.jsonl", AUDIT_LOG.read_bytes(), "audit_log.jsonl", icon=":material/download:")
        with t2:
            fb = read_jsonl(FEEDBACK_LOG, 1000)
            if not fb:
                st.info("Chưa có phản hồi – bấm :material/thumb_up: Hữu ích hoặc :material/thumb_down: Chưa đúng dưới mỗi câu trả lời.",
                        icon=":material/info:")
            else:
                st.dataframe(pd.DataFrame([{"Thời gian": _fmt_ts(e.get("timestamp", "")),
                                            "Đánh giá": "Hữu ích" if e.get("vote") == "up" else "Chưa đúng",
                                            "Mã câu": e.get("question_id", "—"), "Câu hỏi": e.get("question", ""),
                                            "Kết quả": e.get("decision", ""), "Tin cậy": e.get("confidence")}
                                           for e in reversed(fb)]), hide_index=True, width="stretch",
                             column_config={"Câu hỏi": st.column_config.TextColumn(width="large")})
        with t3:
            st.html(f'<div class="pa-stats"><div class="pa-stat"><b>{n_pass}/{len(checks)}</b><span>Kiểm tra đạt</span></div>'
                    f'<div class="pa-stat"><b>{n_fail}</b><span>Không đạt</span></div><div class="pa-stat"><b>'
                    f'{len(read_csv(MANIFEST_PATH)) if MANIFEST_PATH.exists() else 0}</b><span>File trong manifest (SHA-256)</span>'
                    f'</div></div>')
            st.caption(f"Fingerprint: {fp} · Data Pack: {DATAPACK_DIR.relative_to(ROOT)} · manifest: {MANIFEST_PATH.relative_to(ROOT)}")
            st.dataframe(checks, hide_index=True, width="stretch", column_config={"chi tiết": st.column_config.TextColumn(width="large")})
            if MANIFEST_PATH.exists():
                with st.expander("corpus_manifest.csv (SHA-256 từng file)"):
                    st.dataframe(read_csv(MANIFEST_PATH), hide_index=True, width="stretch")

    # ------------------------------------------------------------------ điều hướng + cột trái
    pages = [st.Page(page_qa, title="Hỏi đáp", icon=":material/forum:", url_path="hoi-dap", default=True),
             st.Page(page_submit, title="Xuất bài nộp", icon=":material/upload_file:", url_path="xuat-bai-nop"),
             st.Page(page_kpi, title="Đánh giá KPI", icon=":material/monitoring:", url_path="danh-gia-kpi"),
             st.Page(page_docs, title="Kho tài liệu", icon=":material/library_books:", url_path="kho-tai-lieu"),
             st.Page(page_logs, title="Nhật ký & toàn vẹn", icon=":material/fact_check:", url_path="nhat-ky")]
    nav = st.navigation(pages, position="top")
    if ss.pop("goto_qa", False) and nav.url_path != pages[0].url_path:
        st.switch_page(pages[0])

    with st.sidebar:
        st.html(f'<div class="pa-brand"><div class="logo" role="img" aria-label="Logo"></div><div><b>{APP_NAME}</b>'
                f'<span>{APP_VERSION} · HEXCELLENT</span></div></div>')
        sidebar_history()
        if dlg := ss.pop("hist_dialog", None):
            (rename_dialog if dlg[0] == "rename" else delete_dialog)(dlg[1], dlg[2])
    nav.run()


# =============================================================================
# 9. CLI
# =============================================================================
def _print_result(res: Result):
    print("=" * 78)
    kind = f"câu mẫu {res.question_id}" if res.question_source == "sample" else f"câu ngoài bộ mẫu {res.question_id}"
    print(f"Quyết định : {res.decision}   ·   độ tin cậy {res.confidence:.2f}   ·   {res.latency_ms} ms   ·   "
          f"{res.intent}   ·   mốc {fmt_date(res.applied_date)}   ·   {kind}")
    print("-" * 78)
    print(res.answer)
    if res.abstain and res.reason:
        print(f"Lý do: {res.reason}")
    elif res.key_point:
        pol = f"{res.key_point['polarity']}. " if res.key_point.get("polarity") else ""
        print(f"Kết luận: {pol}{res.key_point['text']}")
    if res.warnings:
        print("-" * 78)
        for w in res.warnings:
            print(f"⚠ {w}")
    print("-" * 78)
    for t in res.trace:
        print(f"  {t['bước']:<34} {t['ms']:>7.2f} ms  {t['chi tiết'][:110]}")
    print("=" * 78)


def _load_cli(check: bool = True, allow_modified: bool = False) -> PolicyAssist:
    checks, fp = verify_integrity()
    _FINGERPRINT["value"] = fp
    fails = checks[checks["kết quả"] == "FAIL"]
    if check and not fails.empty:
        print("❌ Data Pack KHÔNG ĐẠT kiểm tra toàn vẹn:")
        print(fails.to_string(index=False))
        if not allow_modified:
            print("Dừng. Khôi phục Data Pack gốc hoặc chạy lại với --allow-modified (kết quả sẽ không tái lập).")
            sys.exit(2)
    return PolicyAssist(DataPack())


def cli(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:                                          # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(prog="policyassist", description=f"{APP_NAME} – {APP_VERSION}")
    sp = ap.add_subparsers(dest="cmd")
    p_ui = sp.add_parser("ui", help="Mở giao diện web (mặc định)")
    p_ui.add_argument("--port", default="8501")
    p_ask = sp.add_parser("ask", help="Hỏi một câu")
    p_ask.add_argument("question")
    p_ask.add_argument("--date", default=SNAPSHOT.isoformat(),
                       help="reference_date YYYY-MM-DD (mặc định 2026-10-17; 'none' = không rõ ngày)")
    p_b = sp.add_parser("batch", help="Chạy bộ câu hỏi → submission.csv")
    p_b.add_argument("--questions", default=str(resolve_file("questions") or DATAPACK_DIR / FILE_CANDIDATES["questions"][0]))
    p_b.add_argument("--out", default=str(OUTPUT_DIR / "submission.csv"))
    p_b.add_argument("--allow-modified", action="store_true")
    sp.add_parser("eval", help="Đánh giá đầy đủ: 7 KPI trên Dev-30, Ext-60, Stress-60, Probe-25, Paraphrase-52, B0, ablation")
    sp.add_parser("demo", help="Chạy 4 kịch bản demo của đội (A, B1, B2 ở 3 mốc ngày, C) – in citation, độ tin cậy, trace_id")
    sp.add_parser("stress", help="Stress-60: 60 câu kiểm thử chịu tải (14 kiểu), đối chiếu baseline B0")
    sp.add_parser("verify", help="Kiểm tra toàn vẹn Data Pack")
    sp.add_parser("manifest", help="Tạo lại corpus_manifest (chỉ khi BTC phát hành Data Pack mới)")
    a = ap.parse_args(argv)

    if a.cmd in (None, "ui"):
        import threading
        import webbrowser
        port = getattr(a, "port", "8501")
        url = f"http://localhost:{port}"
        print(f"Đang mở giao diện {APP_NAME} tại {url}  (lần đầu mất ~10 giây để lập chỉ mục; Ctrl+C để dừng)")
        threading.Timer(4.0, lambda: webbrowser.open(url)).start()
        return subprocess.call([sys.executable, "-m", "streamlit", "run", str(Path(__file__).resolve()),
                                "--server.port", str(port), "--server.headless", "true",
                                "--browser.gatherUsageStats", "false"], cwd=str(ROOT))
    if a.cmd == "manifest":
        df, fp = build_manifest()
        print(f"Đã ghi {MANIFEST_PATH} và {MANIFEST_JSON} – {len(df)} file · fingerprint {fp}")
        return 0
    if a.cmd == "verify":
        checks, fp = verify_integrity()
        with pd.option_context("display.width", 220, "display.max_colwidth", 90):
            print(checks.to_string(index=False))
        print(f"\nCorpus fingerprint: {fp}")
        print(f"Corpus fingerprint 6 file CSV (cách tính trong báo cáo ngày 1 của đội): {core_fingerprint()}")
        bad = int((checks["kết quả"] == "FAIL").sum())
        print("✅ Data Pack toàn vẹn." if not bad else f"❌ {bad} kiểm tra không đạt.")
        return 1 if bad else 0
    if a.cmd == "ask":
        pa = _load_cli()
        _print_result(pa.answer(a.question, a.date))
        return 0
    if a.cmd == "batch":
        pa = _load_cli(allow_modified=a.allow_modified)
        RUN["id"] = f"RUN-{datetime.now():%Y%m%d-%H%M%S}-{hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:6]}"
        qdf = read_csv(a.questions)
        sub, results = run_batch(pa, qdf, lambda n, t, q: print(f"\r  {n}/{t} {q}", end="", flush=True))
        print()
        try:
            path = save_submission(sub, Path(a.out))
        except PermissionError as exc:
            print(f"❌ {exc}")
            return 1
        print(validate_submission(sub, pa.dp, path).to_string(index=False))
        print(f"\n✅ Đã ghi {path} · trả lời {int((sub.abstain == 'FALSE').sum())} · ABSTAIN {int((sub.abstain == 'TRUE').sum())}"
              f" · latency TB {sub.latency_ms.mean():.0f} ms · p95 {sub.latency_ms.quantile(0.95):.0f} ms · run_id {RUN['id']}"
              f" · audit log: {AUDIT_LOG}")
        print(f"   Bản để xem bằng Excel: {path.with_suffix('.xlsx')} (máy định dạng Việt Nam mở CSV bằng Excel sẽ lệch cột "
              "do Excel tách theo dấu ';' – file CSV vẫn đúng chuẩn BTC; không mở rồi Save CSV bằng Excel trước khi nộp).")
        return 0
    if a.cmd == "stress":
        pa = _load_cli()
        st = run_stress(pa, lambda n, t, l: print(f"\r  {n}/{t} {l:<40}", end="", flush=True))
        print()
        rep = write_stress_report(st)
        with pd.option_context("display.width", 250, "display.max_columns", 40):
            print("\n=== Stress-60 ===")
            print(st["summary"].to_string(index=False))
            print("\n=== Theo kiểu stress (CHRONOS-LEDGER) ===")
            print(st["by_type"].to_string(index=False))
            print("\n=== Ma trận phạm vi theo nguồn trích dẫn ===")
            print(st["confusion"].to_string())
        print(f"\n✅ Báo cáo: {rep} · chi tiết từng câu: {OUTPUT_DIR / 'stress60_results.csv'}")
        return 0
    if a.cmd == "demo":
        pa = _load_cli()
        with pd.option_context("display.width", 250, "display.max_colwidth", 70):
            print(run_demo_cases(pa.with_config(write_log=False)).drop(columns=["câu hỏi"]).to_string(index=False))
        return 0
    if a.cmd == "eval":
        pa = _load_cli()
        ev = run_evaluation(pa, lambda n, t, l: print(f"\r  [{n:4.1f}/{t}] {l:<90}", end="", flush=True))
        print()
        rep_path = write_eval_report(ev, _FINGERPRINT["value"])
        st = run_stress(pa)
        write_stress_report(st)
        fe = ev["full"]
        with pd.option_context("display.width", 250, "display.max_columns", 40, "display.max_colwidth", 46):
            print(f"\n=== Bảng KPI theo tập – CHRONOS-LEDGER (run_id {ev['run_id']}) ===")
            print(kpi_wide(fe).to_string(index=False))
            print("\n=== Baseline B0 ===")
            print(kpi_wide(fe, "B0 – BM25 thuần", counts=False).to_string(index=False))
            print("\n=== Ablation thêm dần B0 → B6 (Public-90) ===")
            print(fe["ablation"].to_string(index=False))
            print("\n=== Kiểm định ghép cặp với B0 ===")
            for k, v in fe["tests"].items():
                print(f"  {k}: " + " · ".join(f"{a}: {b}" for a, b in v.items()))
            print("\n=== KPI chính trên giao diện (Dev-30 + Probe-25) ===")
            print(ev["kpis"].drop(columns=["cách đo"]).to_string(index=False))
            print("\n=== Kịch bản demo ===")
            print(fe["demo"][["case", "mã", "reference_date", "quyết định", "citations", "độ tin cậy", "latency_ms",
                              "khớp kỳ vọng"]].to_string(index=False))
            au = public90_audit(fe)
            print("\n=== Đối chiếu 90 câu public (Dev-30 theo đáp án BTC, Ext-60 theo nhãn đội) ===")
            print(pd.crosstab(au["đối chiếu citation"], au["tập"], margins=True, margins_name="Tổng").to_string())
            print(f"\nLỗi cần xem: {len(fe['errors'])} câu → {OUTPUT_DIR / 'error_table.csv'}")
        print("90 câu public:", ev["public"])
        print(f"\n✅ Báo cáo: {rep_path} · Stress-60: {OUTPUT_DIR / 'stress60_report.md'} · run_manifest.json")
        return 0
    ap.print_help()
    return 0


def _running_in_streamlit() -> bool:
    try:
        from streamlit.runtime import exists
        return exists()
    except Exception:                                              # noqa: BLE001
        return False


if __name__ == "__main__":
    if _running_in_streamlit():
        run_ui()
    else:
        sys.exit(cli())
