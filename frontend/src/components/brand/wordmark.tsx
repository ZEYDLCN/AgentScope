import { AgentScopeIcon } from "@/components/brand/icon";
import { cn } from "@/lib/utils";

const SIZES = {
  sm: { text: "text-sm", icon: 20, gap: "gap-2" },
  md: { text: "text-lg", icon: 26, gap: "gap-2.5" },
  lg: { text: "text-2xl", icon: 36, gap: "gap-3" },
} as const;

/** AgentScope wordmark — monokrom (logo kitinin "Monochrome" varyantı):
 * ikon + "Agent" (ince) + "Scope" (kalın), teke tek `currentColor` üzerinden
 * temaya uyum sağlar. `className` ile metin/ikon rengi (`text-foreground`
 * vb.) dışarıdan verilir. */
export function AgentScopeWordmark({
  size = "md",
  className,
}: {
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const { text, icon, gap } = SIZES[size];
  return (
    <div className={cn("flex items-center", gap, className)}>
      <AgentScopeIcon size={icon} />
      <span className={cn("flex items-center leading-none tracking-tight", text)}>
        <span className="font-light">Agent</span>
        <span className="font-bold">Scope</span>
      </span>
    </div>
  );
}
