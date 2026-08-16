"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const LABEL: Record<string, string> = { llm: "LLM", fallback: "Fallback (kural tabanlı)" };
const COLOR: Record<string, string> = {
  llm: "var(--color-accent)",
  fallback: "var(--color-medium)",
};

export function GeneratedByChart({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).filter(([, v]) => v > 0);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);

  if (total === 0) return null;

  const chartData = entries.map(([key, value]) => ({
    key,
    name: LABEL[key] ?? key,
    value,
  }));

  return (
    <div className="flex items-center gap-6">
      <ResponsiveContainer width={140} height={140}>
        <PieChart>
          <Pie data={chartData} dataKey="value" nameKey="name" innerRadius={42} outerRadius={62} paddingAngle={2}>
            {chartData.map((entry) => (
              <Cell key={entry.key} fill={COLOR[entry.key] ?? "var(--color-muted)"} stroke="none" />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "var(--color-surface)",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <ul className="space-y-2 text-sm">
        {chartData.map((entry) => (
          <li key={entry.key} className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: COLOR[entry.key] ?? "var(--color-muted)" }}
            />
            <span className="text-muted-foreground">{entry.name}</span>
            <span className="font-medium tabular-nums">{entry.value}</span>
            <span className="text-xs text-muted-foreground">
              ({((entry.value / total) * 100).toFixed(0)}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
