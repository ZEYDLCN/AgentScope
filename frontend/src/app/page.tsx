"use client";

import { GeneratedByChart } from "@/components/charts/generated-by-chart";
import { SeverityBarChart } from "@/components/charts/severity-bar-chart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageSpinner } from "@/components/ui/spinner";
import { StatCard } from "@/components/ui/stat-card";
import { useApi } from "@/lib/use-api";
import { formatNumber, formatPercent } from "@/lib/utils";
import type { Stats } from "@/lib/types";
import { Activity, AlertTriangle, ArrowUpRight, BarChart3, ShieldAlert, WifiOff } from "lucide-react";
import Link from "next/link";

export default function OverviewPage() {
  const { data: stats, error, loading } = useApi<Stats>("/api/stats");

  if (loading) return <PageSpinner />;

  if (error || !stats) {
    return (
      <Card>
        <EmptyState
          icon={WifiOff}
          title="AgentGuard API'sine ulaşılamadı"
          description={
            error ??
            "AGENTGUARD_API_URL / AGENTGUARD_API_KEY ortam değişkenlerini kontrol edin (Vercel proje ayarları)."
          }
        />
      </Card>
    );
  }

  const hasAnomalies = Object.values(stats.anomalies_by_severity).some((v) => v > 0);
  const hasInvestigations = Object.values(stats.investigations_by_generated_by).some((v) => v > 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Toplam Trace" value={formatNumber(stats.total_traces)} icon={Activity} />
        <StatCard
          label="Toplam Tespit"
          value={formatNumber(stats.total_detections)}
          icon={BarChart3}
        />
        <StatCard
          label="Anomali Sayısı"
          value={formatNumber(stats.total_anomalies)}
          icon={ShieldAlert}
          tone="critical"
        />
        <StatCard
          label="Anomali Oranı"
          value={formatPercent(stats.anomaly_rate)}
          icon={AlertTriangle}
          tone="accent"
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Severity Dağılımı</CardTitle>
            <CardDescription>Tespit edilen anomalilerin önem derecesine göre dağılımı</CardDescription>
          </CardHeader>
          <CardContent className="pt-2">
            {hasAnomalies ? (
              <SeverityBarChart data={stats.anomalies_by_severity} />
            ) : (
              <EmptyState icon={ShieldAlert} title="Henüz anomali kaydı yok" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Soruşturma Üretim Kaynağı</CardTitle>
            <CardDescription>LLM tarafından mı, yoksa kural tabanlı fallback ile mi üretildi</CardDescription>
          </CardHeader>
          <CardContent className="pt-2">
            {hasInvestigations ? (
              <>
                <GeneratedByChart data={stats.investigations_by_generated_by} />
                {(() => {
                  const fallback = stats.investigations_by_generated_by.fallback ?? 0;
                  const total = Object.values(stats.investigations_by_generated_by).reduce(
                    (a, b) => a + b,
                    0,
                  );
                  if (total > 0 && fallback / total > 0.05) {
                    return (
                      <p className="mt-4 rounded-lg bg-medium-soft px-3 py-2 text-xs text-medium">
                        Fallback oranı %{((fallback / total) * 100).toFixed(0)} — LLM/şema
                        doğrulama sorunlarını incelemeyi düşünün (§14.3).
                      </p>
                    );
                  }
                  return null;
                })()}
              </>
            ) : (
              <EmptyState icon={BarChart3} title="Henüz soruşturma kaydı yok" />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <QuickLink
          href="/anomalies"
          title="Anomali listesine git"
          description="Severity, tarih aralığı ve durum filtreleriyle incele"
        />
        <QuickLink
          href="/knowledge"
          title="Retrieval debug'a git"
          description="BM25 / vector / RRF / rerank aşamalarını karşılaştır"
        />
        <QuickLink
          href="/models"
          title="Model sonuçlarına git"
          description="Anomali tespiti ve RAG ablation raporları"
        />
      </div>
    </div>
  );
}

function QuickLink({
  href,
  title,
  description,
}: {
  href: string;
  title: string;
  description: string;
}) {
  return (
    <Link href={href}>
      <Card className="group h-full p-5 transition-colors hover:border-accent/40">
        <div className="flex items-start justify-between">
          <p className="text-sm font-medium">{title}</p>
          <ArrowUpRight
            size={16}
            className="text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-accent"
          />
        </div>
        <p className="mt-1.5 text-xs text-muted-foreground">{description}</p>
      </Card>
    </Link>
  );
}
