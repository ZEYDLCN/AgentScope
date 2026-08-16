"use client";

import { cn } from "@/lib/utils";
import { BookOpenText, LayoutDashboard, LineChart, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Genel Bakış", icon: LayoutDashboard },
  { href: "/anomalies", label: "Anomaliler", icon: ShieldAlert },
  { href: "/knowledge", label: "Bilgi Tabanı", icon: BookOpenText },
  { href: "/models", label: "Modeller", icon: LineChart },
];

export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav className="lg:hidden flex items-center gap-1 overflow-x-auto border-b border-border bg-surface px-3 py-2">
      {NAV_ITEMS.map((item) => {
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium",
              active ? "bg-accent-soft text-accent" : "text-muted-foreground",
            )}
          >
            <Icon size={14} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
