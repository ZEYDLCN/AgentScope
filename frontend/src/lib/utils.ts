import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("tr-TR", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.round(diffMs / 60000);
  if (Number.isNaN(diffMin)) return "—";
  if (diffMin < 1) return "az önce";
  if (diffMin < 60) return `${diffMin} dk önce`;
  const diffHour = Math.round(diffMin / 60);
  if (diffHour < 24) return `${diffHour} sa önce`;
  const diffDay = Math.round(diffHour / 24);
  return `${diffDay} gün önce`;
}

export function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return new Intl.NumberFormat("tr-TR").format(n);
}

export function formatPercent(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

export function truncateHash(hash: string, length = 10): string {
  return hash.length > length ? `${hash.slice(0, length)}…` : hash;
}

/** Kanıt kaynağı etiketini normalize eder — backend bunu `[T2]` gibi zaten
 * köşeli parantezli üretebilir (LLM çıktısı, normalize edilmeden saklanır);
 * burada çıplak `T2` biçimine indirgenir ki UI kendi parantezini eklerken
 * "[[T2]]" gibi çift parantez oluşmasın. */
export function normalizeCitationTag(source: string): string {
  return source.replace(/^\[|\]$/g, "");
}
