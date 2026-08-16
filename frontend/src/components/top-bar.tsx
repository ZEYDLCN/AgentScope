"use client";

import { AgentScopeWordmark } from "@/components/brand/wordmark";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const TITLES: Record<string, string> = {
  "/": "Genel Bakış",
  "/anomalies": "Anomaliler",
  "/knowledge": "Bilgi Tabanı — Retrieval Debug",
  "/models": "Model Değerlendirmesi",
};

function pageTitle(pathname: string): string {
  if (TITLES[pathname]) return TITLES[pathname];
  if (pathname.startsWith("/investigations/")) return "Soruşturma Detayı";
  if (pathname.startsWith("/anomalies")) return "Anomaliler";
  return "AgentScope";
}

type ConnState = "checking" | "ok" | "degraded" | "unreachable";

function useConnectivity(): ConnState {
  const [state, setState] = useState<ConnState>("checking");
  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        const body = (await res.json()) as { status: string };
        if (cancelled) return;
        setState(
          body.status === "ok" ? "ok" : body.status === "not_ready" ? "degraded" : "unreachable",
        );
      } catch {
        if (!cancelled) setState("unreachable");
      }
    }
    check();
    const id = setInterval(check, 30_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);
  return state;
}

const DOT_STYLES: Record<ConnState, string> = {
  checking: "bg-muted-foreground",
  ok: "bg-low",
  degraded: "bg-medium",
  unreachable: "bg-critical",
};

const LABEL: Record<ConnState, string> = {
  checking: "Kontrol ediliyor…",
  ok: "API bağlı",
  degraded: "API kısmi hazır",
  unreachable: "API'ye ulaşılamıyor",
};

export function TopBar() {
  const pathname = usePathname();
  const conn = useConnectivity();

  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-surface px-4 lg:px-8">
      <AgentScopeWordmark size="sm" className="text-foreground lg:hidden" />
      <h1 className="hidden text-[15px] font-semibold tracking-tight lg:block">
        {pageTitle(pathname)}
      </h1>
      <div className="flex items-center gap-3">
        <div className="hidden sm:flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs text-muted-foreground">
          <span className={cn("h-1.5 w-1.5 rounded-full", DOT_STYLES[conn])} />
          {LABEL[conn]}
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}
