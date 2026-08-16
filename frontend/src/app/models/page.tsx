"use client";

import { TypeRecallChart } from "@/components/charts/type-recall-chart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import evalReport from "@/data/eval-report.json";
import ragEvalReport from "@/data/rag-eval-report.json";
import type { EvalReport, RagEvalReport } from "@/lib/types";
import { Info } from "lucide-react";

const evalData = evalReport as unknown as EvalReport;
const ragData = ragEvalReport as unknown as RagEvalReport;

function fmt(v: number | string | undefined): string {
  if (v === undefined) return "n/a";
  return typeof v === "string" ? v : v.toFixed(4);
}

const CONFIG_ROWS: { label: string; key: keyof EvalReport }[] = [
  { label: "Rules only", key: "rules_only" },
  { label: "IsolationForest (5-seed ort.)", key: "isolation_forest_summary" },
  { label: "Autoencoder (5-seed ort.)", key: "autoencoder_summary" },
  { label: "Fusion + Rules (5-seed ort.)", key: "fusion_summary" },
];

export default function ModelsPage() {
  const seed42If = evalData.isolation_forest_runs?.find((r) => r.seed === 42);
  const seed42Fusion = evalData.fusion_runs?.find((r) => r.seed === 42);

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 rounded-lg border border-border bg-surface-muted px-3.5 py-2.5 text-xs text-muted-foreground">
        <Info size={14} className="mt-0.5 shrink-0" />
        <p>
          Bu sayfa, derleme zamanında repoya gömülen statik değerlendirme raporlarını gösterir
          (`reports/eval_*.json`, `reports/rag_eval_*.json`) — canlı operasyonel veri değildir; bu
          nedenle backend API&apos;sine bağımlı değildir (ADR-006&apos;nın istisnası, §9.3).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Anomali Tespiti — Konfigürasyon Karşılaştırması</CardTitle>
          <CardDescription>
            Train/Val/Test: {evalData.dataset.train_rows} / {evalData.dataset.val_rows} /{" "}
            {evalData.dataset.test_rows} · rapor: {evalData.timestamp}
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto pt-2">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
              <tr>
                <th className="py-2 pr-4 font-medium">Model</th>
                <th className="py-2 pr-4 font-medium">PR-AUC</th>
                <th className="py-2 pr-4 font-medium">ROC-AUC</th>
                <th className="py-2 pr-4 font-medium">Recall@τ</th>
                <th className="py-2 pr-4 font-medium">FPR@95TPR</th>
                <th className="py-2 pr-4 font-medium">F1</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {CONFIG_ROWS.map((row) => {
                const config = evalData[row.key] as EvalReport["rules_only"] | undefined;
                if (!config) return null;
                return (
                  <tr key={row.key}>
                    <td className="py-2 pr-4 font-medium">{row.label}</td>
                    <td className="py-2 pr-4 tabular-nums">{fmt(config.pr_auc)}</td>
                    <td className="py-2 pr-4 tabular-nums">{fmt(config.roc_auc)}</td>
                    <td className="py-2 pr-4 tabular-nums">{fmt(config.recall)}</td>
                    <td className="py-2 pr-4 tabular-nums">{fmt(config.fpr_at_95tpr)}</td>
                    <td className="py-2 pr-4 tabular-nums">{fmt(config.f1)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {seed42If && (
          <Card>
            <CardHeader>
              <CardTitle>Tip Bazlı Recall — IsolationForest (seed=42)</CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              <TypeRecallChart data={seed42If.per_type_recall} />
            </CardContent>
          </Card>
        )}
        {seed42Fusion && (
          <Card>
            <CardHeader>
              <CardTitle>Tip Bazlı Recall — Fusion + Rules (seed=42)</CardTitle>
            </CardHeader>
            <CardContent className="pt-2">
              <TypeRecallChart data={seed42Fusion.per_type_recall} />
            </CardContent>
          </Card>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>RAG Retrieval Ablation</CardTitle>
          <CardDescription>
            {ragData.golden_set_size} sorguluk altın küme · {ragData.chunk_count} chunk ·{" "}
            {ragData.embedder === "real" ? "gerçek embedder" : "fake (bag-of-words hash) embedder"}
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto pt-2">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
              <tr>
                <th className="py-2 pr-4 font-medium">Yapılandırma</th>
                <th className="py-2 pr-4 font-medium">Recall@5</th>
                <th className="py-2 pr-4 font-medium">Recall@20</th>
                <th className="py-2 pr-4 font-medium">nDCG@5</th>
                <th className="py-2 pr-4 font-medium">MRR@5</th>
                <th className="py-2 pr-4 font-medium">p95 (ms)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {ragData.results.map((r) => (
                <tr key={r.config}>
                  <td className="py-2 pr-4 font-medium">{r.config}</td>
                  <td className="py-2 pr-4 tabular-nums">{r.recall_at_5.toFixed(4)}</td>
                  <td className="py-2 pr-4 tabular-nums">{r.recall_at_20.toFixed(4)}</td>
                  <td className="py-2 pr-4 tabular-nums">{r.ndcg_at_5.toFixed(4)}</td>
                  <td className="py-2 pr-4 tabular-nums">{r.mrr_at_5.toFixed(4)}</td>
                  <td className="py-2 pr-4 tabular-nums">{r.p95_latency_ms.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {ragData.embedder !== "real" && (
            <p className="mt-3 text-xs text-muted-foreground">
              Bu ortamda ağ erişimi olmadığından fake embedder/reranker kullanıldı; mutlak sayılar
              gerçek bge-m3/bge-reranker-v2-m3 ile farklılık gösterecektir (bkz. ana README
              Sınırlılıklar).
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
