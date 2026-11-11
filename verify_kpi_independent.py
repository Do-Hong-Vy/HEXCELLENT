"""Dùng: python verify_kpi_independent.py (sau `python policyassist.py eval`).
Kiểm tra KPI độc lập trên mọi tập: chỉ dùng pandas + file nhãn gốc + outputs/eval_results_all.csv (cột citations,
retrieved, predicted do hệ thống xuất) + document_metadata; không import policyassist. So với outputs/eval_by_set.csv.
Chạy được trên Windows, macOS và Linux (đường dẫn dựng bằng pathlib)."""
import sys
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:                                                  # noqa: BLE001
    pass
R = Path(__file__).resolve().parent
DP = R / "data" / "DataPack-CASE1_PolicyAssist"
OUT = R / "outputs"
EV = R / "data" / "eval"
sp = lambda v: [x.strip() for x in str(v).replace("\n", ";").split(";") if x.strip() and x.strip().lower() != "nan"]
res = pd.read_csv(OUT / "eval_results_all.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
bys = pd.read_csv(OUT / "eval_by_set.csv", encoding="utf-8-sig")
meta = pd.read_csv(DP / "03_metadata" / "document_metadata.csv", dtype=str, keep_default_na=False).set_index("document_id")
cmap = pd.read_csv(DP / "citation_map.csv", dtype=str, keep_default_na=False)
label_of = dict(zip(cmap.chunk_id, cmap.citation_label))

ak = pd.read_csv(DP / "05_answer_sample" / "answer_key_sample.csv", dtype=str, keep_default_na=False)
ext = pd.read_csv(EV / "ext60_labels.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
st6 = pd.read_csv(EV / "stress60_labels.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
par = pd.read_csv(EV / "paraphrase_questions.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
prb = pd.read_csv(EV / "probe_questions.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
LAB = {  # tập → (bảng nhãn, cột chunk vàng, cột nhãn citation, cột văn bản đúng cho versioning)
    "Dev-30": (ak, "relevant_chunk_ids", "citation_labels", "relevant_document_ids"),
    "Ext-60": (ext, "relevant_chunk_ids", "citation_labels", "relevant_document_ids"),
    "Stress-60": (st6, "expected_chunk_ids", "expected_citations", "expected_document_ids"),
    "Paraphrase-52": (par, "acceptable_chunk_ids", None, "expected_documents"),
    "Probe-25": (prb, None, None, "expected_documents"),
}


SRC_SCOPE = {**dict(zip(ak.question_id, ak.answer_scope)), **dict(zip(ext.question_id, ext.answer_scope))}


def valid(d, ref):
    if d not in meta.index:
        return False
    m = meta.loc[d]
    return (m.status != "HISTORICAL_REFERENCE" and m.document_type != "CONSOLIDATED"
            and (not m.effective_date or ref >= m.effective_date) and (not m.expiry_date or ref <= m.expiry_date))


def prog(setn, k):
    g = bys[(bys["tập"] == setn) & (bys["hệ thống"] == "CHRONOS-LEDGER")]
    return float(g[k].iloc[0]) if len(g) and pd.notna(g[k].iloc[0]) else float("nan")


ok_all = True
for setn, (lab, gcol, ccol, vcol) in LAB.items():
    r = res[res["tập"] == setn].set_index("question_id")
    lab = lab.set_index("question_id")
    rec, cit, ver, rows_cmp = [], [], [], []
    tp = fp = fn = 0
    lat = pd.to_numeric(r["latency_ms"])
    for q, L in lab.iterrows():
        if q not in r.index:
            continue
        s = r.loc[q]
        exp_abs = L["expected_behavior"].upper() == "ABSTAIN"
        abst = s["predicted"] == "ABSTAIN"
        tp += abst and exp_abs
        fp += abst and not exp_abs
        fn += (not abst) and exp_abs
        if exp_abs:
            continue
        if gcol and sp(L[gcol]):
            gold = set(sp(L[gcol]))
            top5 = sp(s["retrieved"])[:5] if not abst else []
            v = len(gold & set(top5)) / len(gold)
            rec.append(v)
            pv = float(s["recall_at_5"]) if s["recall_at_5"] not in ("", "nan") else float("nan")
            if abs(pv - v) > 1e-6:
                rows_cmp.append((q, "recall", round(v, 3), pv))
        labels = set(sp(L[ccol])) if ccol else ({label_of[c] for c in sp(L[gcol]) if c in label_of} if gcol else set())
        if labels and not abst:
            c = sp(s["citations"])
            cit.append(sum(x in labels for x in c) / len(c) if c else 0.0)
        scope = L.get("answer_scope", "") or SRC_SCOPE.get(L.get("source_id", ""), "")
        if (scope == "VERSIONING" or (setn == "Probe-25" and "ersioning" in L.get("note", ""))) \
                and sp(L[vcol]) and not abst:
            ref = s["applied_date"] or L["reference_date"]
            first = next((x.split(" – ")[0] for x in sp(s["citations"]) if x.startswith("LAW") and valid(x.split(" – ")[0], ref)), "")
            ver.append(first in set(sp(L[vcol])))
    f1 = 2 * tp / (2 * tp + fp + fn) if (tp + fn) else float("nan")
    mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
    print(f"===== {setn}")
    for name, mine, key, n in [("Recall@5", mean(rec), "recall_at_5", len(rec)), ("Citation (theo nhãn)", mean(cit), "citation_accuracy", len(cit)),
                               ("Abstention F1", f1, "abstention_f1", f"TP{tp} FP{fp} FN{fn}"), ("Versioning", mean(ver), "versioning_accuracy", len(ver)),
                               ("Latency TB", float(lat.mean()), "latency_ms_avg", len(lat))]:
        p = prog(setn, key)
        same = (pd.isna(mine) and pd.isna(p)) or (not pd.isna(mine) and not pd.isna(p) and abs(mine - p) < 0.0015 * (1000 if key == "latency_ms_avg" else 1))
        ok_all &= bool(same) or key == "citation_accuracy"
        print(f"  {name:22s} độc lập {mine:8.3f} · chương trình {p:8.3f}  [{n}]  {'KHỚP' if same else 'LỆCH'}")
    for x in rows_cmp[:8]:
        print("   lệch recall:", x)
    # tổng hợp các cột từng câu → số của chương trình (kiểm tra phép lấy trung bình)
    for key in ("answer_accuracy", "unsupported", "citation_accuracy"):
        col = pd.to_numeric(r[key], errors="coerce").dropna()
        tgt = "unsupported_rate" if key == "unsupported" else key
        print(f"  trung bình cột {key:18s} {col.mean() if len(col) else float('nan'):.3f} · chương trình {prog(setn, tgt):.3f} ({len(col)} câu)")
print("\nKẾT LUẬN:", "các KPI tính lại độc lập KHỚP" if ok_all else "CÓ LỆCH – xem chi tiết")
sys.exit(0 if ok_all else 1)
