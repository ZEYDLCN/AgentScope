"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageSpinner } from "@/components/ui/spinner";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { useApi } from "@/lib/use-api";
import { ANOMALY_TYPE_LABEL, type Investigation, type InvestigationPending, type TraceDetail } from "@/lib/types";
import { formatDateTime, normalizeCitationTag, truncateHash } from "@/lib/utils";
import { AlertCircle, Bot, CheckCircle2, Clock, FileSearch, PlayCircle, Sparkles } from "lucide-react";
import { useParams } from "next/navigation";
import { useState } from "react";

function isPending(x: Investigation | InvestigationPending): x is InvestigationPending {
  return "status" in x;
}

const STATUS_STYLE: Record<string, string> = {
  ok: "text-low",
  error: "text-critical",
  timeout: "text-medium",
  denied: "text-high",
};

export default function InvestigationDetailPage() {
  const params = useParams<{ traceId: string }>();
  const traceId = decodeURIComponent(params.traceId);

  const { data: trace, error: traceError, loading: traceLoading } = useApi<TraceDetail>(
    `/api/traces/${encodeURIComponent(traceId)}`,
  );
  const {
    data: investigation,
    error: invError,
    loading: invLoading,
    refetch,
  } = useApi<Investigation | InvestigationPending>(
    `/api/investigations/${encodeURIComponent(traceId)}`,
  );

  const [triggering, setTriggering] = useState(false);

  async function triggerInvestigation() {
    setTriggering(true);
    try {
      await fetch(`/api/investigations/${encodeURIComponent(traceId)}`, { method: "POST" });
      refetch();
    } finally {
      setTriggering(false);
    }
  }

  if (traceLoading) return <PageSpinner />;

  if (traceError || !trace) {
    return (
      <Card>
        <EmptyState icon={AlertCircle} title="Trace bulunamadı" description={traceError ?? undefined} />
      </Card>
    );
  }

  const { payload } = trace;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="font-mono text-xs text-muted-foreground">{traceId}</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 pt-2 sm:grid-cols-4">
          <Summary label="Agent" value={payload.agent_id} />
          <Summary label="Araç Çağrısı" value={String(payload.tool_calls.length)} />
          <Summary label="Toplam Token" value={String(payload.token_usage.total_tokens)} />
          <Summary label="Durum" value={payload.final_status} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Araç Çağrısı Zaman Çizelgesi</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto pt-2">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted-foreground">
              <tr>
                <th className="py-2 pr-4 font-medium">#</th>
                <th className="py-2 pr-4 font-medium">Araç</th>
                <th className="py-2 pr-4 font-medium">Durum</th>
                <th className="py-2 pr-4 font-medium">Süre (ms)</th>
                <th className="py-2 pr-4 font-medium">input_hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {payload.tool_calls.map((call) => (
                <tr key={call.index}>
                  <td className="py-2 pr-4 text-muted-foreground">{call.index}</td>
                  <td className="py-2 pr-4 font-medium">{call.tool_name}</td>
                  <td className={`py-2 pr-4 ${STATUS_STYLE[call.status] ?? ""}`}>{call.status}</td>
                  <td className="py-2 pr-4 tabular-nums">{call.duration_ms}</td>
                  <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">
                    {truncateHash(call.input_hash, 14)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Soruşturma Raporu</CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          {invLoading && <PageSpinner />}

          {!invLoading && invError && (
            <EmptyState
              icon={FileSearch}
              title="Bu trace için henüz bir soruşturma raporu yok"
              description="Tespit anomali değilse ya da soruşturma henüz tetiklenmediyse rapor bulunmaz."
            />
          )}

          {!invLoading && !invError && investigation && isPending(investigation) && (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <Clock className="text-medium" size={22} />
              <p className="text-sm font-medium">
                Soruşturma devam ediyor (durum: {investigation.status})
              </p>
              <button
                type="button"
                onClick={refetch}
                className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium hover:bg-surface-muted cursor-pointer"
              >
                Durumu yenile
              </button>
            </div>
          )}

          {!invLoading && !invError && investigation && !isPending(investigation) && (
            <InvestigationReport investigation={investigation} />
          )}

          {!invLoading && invError && (
            <div className="mt-4 flex justify-center">
              <button
                type="button"
                onClick={triggerInvestigation}
                disabled={triggering}
                className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-xs font-semibold text-accent-foreground hover:opacity-90 disabled:opacity-50 cursor-pointer"
              >
                <PlayCircle size={15} />
                {triggering ? "Tetikleniyor…" : "Soruşturmayı tetikle"}
              </button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-semibold">{value}</p>
    </div>
  );
}

function InvestigationReport({ investigation }: { investigation: Investigation }) {
  const badge =
    investigation.generated_by === "llm" ? (
      <span className="inline-flex items-center gap-1 rounded-full bg-accent-soft px-2 py-0.5 text-xs font-medium text-accent">
        <Bot size={12} /> LLM
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 rounded-full bg-medium-soft px-2 py-0.5 text-xs font-medium text-medium">
        <AlertCircle size={12} /> Fallback
      </span>
    );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <span className="rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium">
          {ANOMALY_TYPE_LABEL[investigation.anomaly_type] ?? investigation.anomaly_type}
        </span>
        <SeverityBadge severity={investigation.severity} />
        <span className="text-xs text-muted-foreground">
          Güven: {(investigation.confidence * 100).toFixed(0)}%
        </span>
        {badge}
        <span className="ml-auto text-xs text-muted-foreground">
          {formatDateTime(investigation.created_at)} · {investigation.latency_ms}ms
        </span>
      </div>

      <div>
        <p className="text-xs font-medium text-muted-foreground">Kök neden</p>
        <p className="mt-1 text-sm leading-relaxed">{investigation.root_cause}</p>
      </div>

      <div>
        <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <CheckCircle2 size={13} /> Kanıtlar
        </p>
        <ul className="space-y-1.5">
          {investigation.evidence.map((ev, i) => (
            <li key={i} className="flex items-start gap-2 text-sm">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-muted-foreground" />
              <span>
                {ev.statement}{" "}
                <span className="font-mono text-xs text-muted-foreground">
                  [{normalizeCitationTag(ev.source)}]
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div>
        <p className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Sparkles size={13} /> Öneriler
        </p>
        <ul className="space-y-1.5">
          {[...investigation.recommendations]
            .sort((a, b) => a.priority - b.priority)
            .map((rec, i) => (
              <li key={i} className="text-sm">
                <span className="mr-1.5 rounded bg-surface-muted px-1.5 py-0.5 font-mono text-[11px]">
                  P{rec.priority}
                </span>
                {rec.action} — <span className="text-muted-foreground">{rec.rationale}</span>
              </li>
            ))}
        </ul>
      </div>

      {investigation.retrieved_docs.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">Kaynak Dokümanlar</p>
          <div className="flex flex-wrap gap-1.5">
            {investigation.retrieved_docs.map((doc) => (
              <code key={doc} className="rounded bg-surface-muted px-1.5 py-0.5 text-xs">
                {doc}
              </code>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
