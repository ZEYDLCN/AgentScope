/**
 * AgentScope marka ikonu — "gözlem lensi" motifi: dış izleme halkası,
 * segmentli derinlik halkası, aktif radar taraması, merceğin kendisi ve
 * üç agent düğümü. Sağlanan logo kitinin (Figma Make) birebir SVG
 * matematiği port edilmiştir; burada `currentColor` kullanan monokrom
 * varyant uygulanır (kitin "Monochrome — Dark/Light" varyantları) — ikon
 * temaya göre otomatik uyum sağlar, ayrı açık/koyu asset gerekmez.
 */

const rad = (d: number) => (d * Math.PI) / 180;

function arcPath(cx: number, cy: number, r: number, t1: number, t2: number): string {
  const x1 = cx + r * Math.cos(rad(t1));
  const y1 = cy + r * Math.sin(rad(t1));
  const x2 = cx + r * Math.cos(rad(t2));
  const y2 = cy + r * Math.sin(rad(t2));
  const large = t2 - t1 > 180 ? 1 : 0;
  return `M ${x1.toFixed(2)} ${y1.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)}`;
}

const NODE_ANGLES = [48, 168, 288];
const cx = 50;
const cy = 50;

const wx1 = (cx + 32 * Math.cos(rad(285))).toFixed(2);
const wy1 = (cy + 32 * Math.sin(rad(285))).toFixed(2);
const wx2 = (cx + 32 * Math.cos(rad(345))).toFixed(2);
const wy2 = (cy + 32 * Math.sin(rad(345))).toFixed(2);

const RING_ARCS = [
  arcPath(cx, cy, 32, 6, 114),
  arcPath(cx, cy, 32, 126, 234),
  arcPath(cx, cy, 32, 246, 354),
];

export function AgentScopeIcon({
  size = 32,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      {/* Dış izleme halkası */}
      <circle cx={cx} cy={cy} r={44} stroke="currentColor" strokeWidth="1.5" opacity="0.9" />

      {/* Segmentli derinlik halkası — 12° boşluklu üç 108° yay */}
      {RING_ARCS.map((d, i) => (
        <path key={i} d={d} stroke="currentColor" strokeWidth="1" opacity="0.35" strokeLinecap="round" />
      ))}

      {/* Aktif radar taraması */}
      <path d={`M 50 50 L ${wx1} ${wy1} A 32 32 0 0 1 ${wx2} ${wy2} Z`} fill="currentColor" opacity="0.1" />

      {/* Mercek — yatay badem */}
      <path
        d="M 21 50 C 31 36, 69 36, 79 50 C 69 64, 31 64, 21 50 Z"
        stroke="currentColor"
        strokeWidth="1.5"
        fill="currentColor"
        fillOpacity="0.06"
        strokeLinejoin="round"
      />

      {/* Merkez odak noktası */}
      <circle cx={cx} cy={cy} r={4} fill="currentColor" />
      <circle cx={cx} cy={cy} r={1.8} fill="var(--color-surface)" fillOpacity="0.6" />

      {/* Halka üzerindeki agent düğümleri */}
      {NODE_ANGLES.map((angle, i) => {
        const nx = (cx + 44 * Math.cos(rad(angle))).toFixed(2);
        const ny = (cy + 44 * Math.sin(rad(angle))).toFixed(2);
        return <circle key={i} cx={nx} cy={ny} r={2.5} fill="currentColor" />;
      })}
    </svg>
  );
}
