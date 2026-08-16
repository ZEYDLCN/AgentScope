"""Model değerlendirmesi — eval raporları, konfigürasyon karşılaştırması,
eşik görselleştirmesi (§18).

Not: bu sayfa `reports/eval_*.json` dosyalarını API üzerinden değil,
doğrudan yerel dosya sisteminden okur — bunlar canlı operasyonel veri
değil, git'e commit edilmiş statik değerlendirme çıktılarıdır (§9.3);
ADR-006'nın "tek doğruluk kaynağı" ilkesi operasyonel veriler (trace,
anomali, soruşturma) için geçerlidir.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Model Değerlendirmesi — AgentGuard", page_icon="📊", layout="wide")
st.title("📊 Model Değerlendirmesi")

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"


def _load_reports() -> list[Path]:
    if not REPORTS_DIR.exists():
        return []
    return sorted(REPORTS_DIR.glob("eval_*.json"), reverse=True)


reports = _load_reports()
if not reports:
    st.info(
        "Henüz eval raporu yok. `make eval` (ya da "
        "`python scripts/run_eval.py --out reports/`) çalıştırın."
    )
    st.stop()

selected = st.selectbox("Rapor seç", reports, format_func=lambda p: p.stem)
data = json.loads(selected.read_text())

st.caption(
    f"Train/Val/Test: {data['dataset']['train_rows']} / "
    f"{data['dataset']['val_rows']} / {data['dataset']['test_rows']}"
)

st.subheader("Konfigürasyon Karşılaştırması")


def _row(name: str, m: dict) -> dict:  # type: ignore[type-arg]
    def g(key: str) -> str:
        v = m.get(key, "n/a")
        return v if isinstance(v, str) else f"{v:.4f}"

    return {
        "Model": name,
        "PR-AUC": g("pr_auc"),
        "ROC-AUC": g("roc_auc"),
        "Recall@τ": g("recall"),
        "FPR@95TPR": g("fpr_at_95tpr"),
        "F1": g("f1"),
    }


rows = [_row("Rules only", data["rules_only"])]
if data.get("isolation_forest_summary"):
    rows.append(_row("IsolationForest (5-seed)", data["isolation_forest_summary"]))
if data.get("autoencoder_summary"):
    rows.append(_row("Autoencoder (5-seed)", data["autoencoder_summary"]))
if data.get("fusion_summary"):
    rows.append(_row("Fusion + Rules (5-seed)", data["fusion_summary"]))

st.dataframe(rows, use_container_width=True, hide_index=True)


def _mean(summary: dict, key: str) -> float | None:  # type: ignore[type-arg]
    raw = summary.get(key)
    if not raw or not isinstance(raw, str):
        return None
    try:
        return float(raw.split("±")[0].strip())
    except ValueError:
        return None


chart_data = {}
if data.get("isolation_forest_summary"):
    v = _mean(data["isolation_forest_summary"], "pr_auc")
    if v is not None:
        chart_data["IsolationForest"] = v
if data.get("autoencoder_summary"):
    v = _mean(data["autoencoder_summary"], "pr_auc")
    if v is not None:
        chart_data["Autoencoder"] = v
if data.get("fusion_summary"):
    v = _mean(data["fusion_summary"], "pr_auc")
    if v is not None:
        chart_data["Fusion+Rules"] = v

if chart_data:
    st.subheader("PR-AUC Karşılaştırması")
    st.bar_chart(chart_data)

if data.get("isolation_forest_runs"):
    st.subheader("Tip Bazlı Recall (IsolationForest, seed=42)")
    per_type = data["isolation_forest_runs"][0].get("per_type_recall", {})
    if per_type:
        st.bar_chart(per_type)

st.divider()
st.subheader("Ham Rapor (Markdown)")
md_path = selected.with_suffix(".md")
if md_path.exists():
    with st.expander("reports/" + md_path.name):
        st.markdown(md_path.read_text())
