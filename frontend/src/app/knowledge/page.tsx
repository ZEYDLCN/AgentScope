"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Spinner } from "@/components/ui/spinner";
import { useApi } from "@/lib/use-api";
import type { KnowledgeSearchResponse, RankedChunk } from "@/lib/types";
import { Search, Sparkles } from "lucide-react";
import { useState } from "react";

export default function KnowledgePage() {
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");

  const url = submitted ? `/api/knowledge/search?q=${encodeURIComponent(submitted)}` : null;
  const { data, error, loading } = useApi<KnowledgeSearchResponse>(url);

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(query.trim());
          }}
          className="flex gap-2"
        >
          <div className="relative flex-1">
            <Search
              size={15}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="ör. veritabanı sorgu döngüsü, token bütçe politikası…"
              className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
          </div>
          <button
            type="submit"
            disabled={!query.trim()}
            className="rounded-lg bg-accent px-4 text-xs font-semibold text-accent-foreground hover:opacity-90 disabled:opacity-50 cursor-pointer"
          >
            Ara
          </button>
        </form>
      </Card>

      {loading && (
        <div className="flex justify-center py-10">
          <Spinner size={20} />
        </div>
      )}

      {error && !loading && (
        <Card>
          <EmptyState icon={Search} title="Arama başarısız" description={error} />
        </Card>
      )}

      {!error && !loading && submitted && data && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-1.5">
                <Sparkles size={14} className="text-accent" />
                Nihai sonuçlar (rerank sonrası)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-2">
              {data.final.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  Eşik üzerinde sonuç yok (§13 rerank_min_score altına düşenler elenir).
                </p>
              )}
              {data.final.map((chunk) => (
                <div key={chunk.chunk_id} className="rounded-lg border border-border p-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded bg-accent-soft px-1.5 py-0.5 font-mono text-accent">
                      #{chunk.rank}
                    </span>
                    <code className="text-muted-foreground">{chunk.chunk_id}</code>
                    <span className="ml-auto flex gap-3 text-muted-foreground">
                      {chunk.rrf_score !== null && <span>RRF {chunk.rrf_score.toFixed(3)}</span>}
                      {chunk.rerank_score !== null && (
                        <span>rerank {chunk.rerank_score.toFixed(3)}</span>
                      )}
                    </span>
                  </div>
                  <p className="mt-2 text-sm leading-relaxed">{chunk.text_preview}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <RankingCard title="BM25" items={data.bm25} />
            <RankingCard title="Vector" items={data.vector} />
            <RankingCard title="Hibrit (RRF)" items={data.fused_rrf} />
          </div>
        </div>
      )}

      {!submitted && !loading && (
        <Card>
          <EmptyState
            icon={Search}
            title="Retrieval boru hattını sorgula"
            description="Yukarıya bir sorgu girin — BM25, vector, RRF füzyonu ve reranker'ın sıralamayı nasıl değiştirdiğini yan yana görün (§12-13)."
          />
        </Card>
      )}
    </div>
  );
}

function RankingCard({ title, items }: { title: string; items: RankedChunk[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xs uppercase tracking-wide text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-1.5 pt-2">
        {items.slice(0, 8).map((item, i) => (
          <div key={item.chunk_id} className="flex items-center justify-between text-xs">
            <span className="truncate font-mono text-muted-foreground">
              {i + 1}. {item.chunk_id}
            </span>
            <span className="tabular-nums">{item.score.toFixed(3)}</span>
          </div>
        ))}
        {items.length === 0 && <p className="text-xs text-muted-foreground">Sonuç yok</p>}
      </CardContent>
    </Card>
  );
}
