// Backend kontratlarının (Pydantic v2 şemaları) TypeScript izdüşümü —
// `docs/TECHNICAL_PLAN.md` §5, §16. Tek doğruluk kaynağı backend'dedir;
// bu dosya yalnızca frontend'in tükettiği alanları yansıtır.

export type Severity = "low" | "medium" | "high" | "critical";

export type AnomalyType =
  | "tool_loop"
  | "token_spike"
  | "api_abuse"
  | "permission_violation"
  | "prompt_injection"
  | "unusual_tool_sequence";

export interface Stats {
  total_traces: number;
  total_detections: number;
  total_anomalies: number;
  anomaly_rate: number;
  anomalies_by_severity: Record<string, number>;
  investigations_by_generated_by: Record<string, number>;
}

export interface DetectorScore {
  detector: string;
  raw_score: number;
  normalized_score: number;
  model_version: string;
}

export interface AnomalyListItem {
  trace_id: string;
  is_anomaly: boolean;
  score: number;
  severity: Severity;
  threshold: number;
  triggered_rules: string[];
  detected_at: string;
}

export interface AnomalyListResponse {
  items: AnomalyListItem[];
  next_cursor: string | null;
}

export interface ToolCall {
  index: number;
  tool_name: string;
  started_at: string;
  ended_at: string;
  status: "ok" | "error" | "timeout" | "denied";
  duration_ms: number;
  input_hash: string;
  input_preview: string | null;
  output_size_bytes: number;
  error_type: string | null;
}

export interface TraceDetail {
  trace_id: string;
  agent_id: string;
  received_at: string;
  payload: {
    trace_id: string;
    agent_id: string;
    agent_version: string;
    session_id: string | null;
    started_at: string;
    ended_at: string;
    user_prompt_preview: string | null;
    tool_calls: ToolCall[];
    token_usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
    final_status: string;
    metadata: Record<string, string>;
  };
}

export interface EvidenceItem {
  statement: string;
  source: string;
}

export interface Recommendation {
  action: string;
  priority: number;
  rationale: string;
}

export interface Investigation {
  trace_id: string;
  anomaly_type: AnomalyType;
  severity: Severity;
  confidence: number;
  root_cause: string;
  evidence: EvidenceItem[];
  recommendations: Recommendation[];
  retrieved_docs: string[];
  model_name: string;
  prompt_version: string;
  generated_by: "llm" | "fallback";
  latency_ms: number;
  created_at: string;
}

export interface InvestigationPending {
  trace_id: string;
  status: "pending" | "running";
  job_id: string;
}

export interface RankedChunk {
  chunk_id: string;
  score: number;
}

export interface FinalRetrievedChunk {
  chunk_id: string;
  doc_id: string;
  section: string;
  rank: number;
  rrf_score: number | null;
  rerank_score: number | null;
  text_preview: string;
}

export interface KnowledgeSearchResponse {
  query: string;
  bm25: RankedChunk[];
  vector: RankedChunk[];
  fused_rrf: RankedChunk[];
  final: FinalRetrievedChunk[];
}

// Tekil (rules_only) sonuçlar ham sayısal alanlardır; N-seed özetleri
// ("... ± ...") formatlanmış string'lerdir — bkz. `scripts/run_eval.py`.
export interface EvalConfigResult {
  pr_auc?: number | string;
  roc_auc?: number | string;
  recall?: number | string;
  fpr_at_95tpr?: number | string;
  f1?: number | string;
}

export interface EvalReport {
  timestamp: string;
  dataset: { train_rows: number; val_rows: number; test_rows: number };
  rules_only: EvalConfigResult;
  isolation_forest_summary?: EvalConfigResult;
  autoencoder_summary?: EvalConfigResult;
  fusion_summary?: EvalConfigResult;
  isolation_forest_runs?: { seed: number; per_type_recall: Record<string, number> }[];
  fusion_runs?: { seed: number; per_type_recall: Record<string, number> }[];
}

export interface RagAblationResult {
  config: string;
  recall_at_5: number;
  recall_at_20: number;
  ndcg_at_5: number;
  mrr_at_5: number;
  p95_latency_ms: number;
}

export interface RagEvalReport {
  timestamp: string;
  golden_set_size: number;
  chunk_count: number;
  embedder: string;
  results: RagAblationResult[];
}

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Kritik",
  high: "Yüksek",
  medium: "Orta",
  low: "Düşük",
};

export const ANOMALY_TYPE_LABEL: Record<AnomalyType, string> = {
  tool_loop: "Araç Döngüsü",
  token_spike: "Token Sıçraması",
  api_abuse: "API Kötüye Kullanımı",
  permission_violation: "Yetki İhlali",
  prompt_injection: "Prompt Injection",
  unusual_tool_sequence: "Olağandışı Araç Sırası",
};
