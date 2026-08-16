"use client";

import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { Spinner } from "@/components/ui/spinner";
import { useApi } from "@/lib/use-api";
import type { AnomalyListResponse, Severity } from "@/lib/types";
import { formatDateTime, truncateHash } from "@/lib/utils";
import { ChevronRight, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

const SEVERITIES: { value: Severity | "all"; label: string }[] = [
  { value: "all", label: "Tümü" },
  { value: "critical", label: "Kritik" },
  { value: "high", label: "Yüksek" },
  { value: "medium", label: "Orta" },
  { value: "low", label: "Düşük" },
];

export default function AnomaliesPage() {
  const [severity, setSeverity] = useState<Severity | "all">("all");
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const pageIndex = cursorStack.length - 1;
  const cursor = cursorStack[pageIndex];

  const url = useMemo(() => {
    const params = new URLSearchParams({ limit: "25" });
    if (severity !== "all") params.set("severity", severity);
    if (cursor) params.set("cursor", cursor);
    return `/api/anomalies?${params.toString()}`;
  }, [severity, cursor]);

  const { data, error, loading } = useApi<AnomalyListResponse>(url);

  function changeSeverity(next: Severity | "all") {
    setSeverity(next);
    setCursorStack([null]);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {SEVERITIES.map((s) => (
          <button
            key={s.value}
            type="button"
            onClick={() => changeSeverity(s.value)}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
              severity === s.value
                ? "border-accent bg-accent-soft text-accent"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            {s.label}
          </button>
        ))}
        {loading && <Spinner className="ml-1" />}
      </div>

      <Card className="overflow-hidden">
        {error && (
          <EmptyState icon={ShieldAlert} title="Anomaliler yüklenemedi" description={error} />
        )}
        {!error && data && data.items.length === 0 && (
          <EmptyState icon={ShieldAlert} title="Bu filtrelerle eşleşen anomali yok" />
        )}
        {!error && data && data.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-surface-muted text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Trace</th>
                  <th className="px-4 py-3 font-medium">Severity</th>
                  <th className="px-4 py-3 font-medium">Skor</th>
                  <th className="px-4 py-3 font-medium">Tetiklenen Kurallar</th>
                  <th className="px-4 py-3 font-medium">Tespit Zamanı</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((item) => (
                  <tr key={item.trace_id} className="transition-colors hover:bg-surface-muted">
                    <td className="px-4 py-3 font-mono text-xs">{truncateHash(item.trace_id, 24)}</td>
                    <td className="px-4 py-3">
                      <SeverityBadge severity={item.severity} />
                    </td>
                    <td className="px-4 py-3 tabular-nums">{item.score.toFixed(3)}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {item.triggered_rules.length > 0 ? item.triggered_rules.join(", ") : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {formatDateTime(item.detected_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/investigations/${encodeURIComponent(item.trace_id)}`}
                        className="inline-flex items-center gap-0.5 text-xs font-medium text-accent hover:underline"
                      >
                        Detay <ChevronRight size={14} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {data && (data.next_cursor || pageIndex > 0) && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <button
            type="button"
            disabled={pageIndex === 0}
            onClick={() => setCursorStack((s) => s.slice(0, -1))}
            className="rounded-lg border border-border px-3 py-1.5 font-medium disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
          >
            Önceki
          </button>
          <span>Sayfa {pageIndex + 1}</span>
          <button
            type="button"
            disabled={!data.next_cursor}
            onClick={() => setCursorStack((s) => [...s, data.next_cursor])}
            className="rounded-lg border border-border px-3 py-1.5 font-medium disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
          >
            Sonraki
          </button>
        </div>
      )}
    </div>
  );
}
