"use client";

import { AgentScopeWordmark } from "@/components/brand/wordmark";
import { cn } from "@/lib/utils";
import { BookOpenText, LayoutDashboard, LineChart, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Genel Bakış", icon: LayoutDashboard },
  { href: "/anomalies", label: "Anomaliler", icon: ShieldAlert },
  { href: "/knowledge", label: "Bilgi Tabanı", icon: BookOpenText },
  { href: "/models", label: "Model Sonuçları", icon: LineChart },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex flex-col justify-center gap-0.5 px-6 h-16 border-b border-border">
        <AgentScopeWordmark size="md" className="text-foreground" />
        <p className="text-[11px] text-muted-foreground pl-9">AI Güvenlik Konsolu</p>
      </div>

      <nav className="flex-1 px-3 py-5 space-y-0.5">
        {NAV_ITEMS.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-accent-soft text-accent"
                  : "text-muted-foreground hover:bg-surface-muted hover:text-foreground",
              )}
            >
              <Icon size={17} strokeWidth={active ? 2.25 : 1.9} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="px-6 py-4 border-t border-border text-[11px] text-muted-foreground">
        <p>Deterministik çekirdek, olasılıksal kenar.</p>
        <p className="mt-0.5">LLM karar vermez, yalnızca açıklar.</p>
      </div>
    </aside>
  );
}
