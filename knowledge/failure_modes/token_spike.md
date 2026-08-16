---
doc_id: token_spike
title: Token Spike
category: reference
anomaly_types: [token_spike]
severity_scope: [medium, high]
version: 1.1
updated: 2026-07-01
---

## Tespit Sinyalleri

- `total_tokens > 15000` → `R004_token_ceiling` kuralı tetiklenir, tip
  önerisi `token_spike` olur (skor tabanı verilmez, yalnızca tip/severity).
- `tokens_per_call` (total_tokens / tool_call_count) yüksekse, tekil
  çağrı başına aşırı büyük çıktı/bağlam söz konusudur.
- Meşru uzun işlemlerle (9.000 token'lık özet gibi) örtüşme vardır —
  bkz. `policies/token_budget_policy.md` "zorlu negatifler".

## Kök Neden Kalıpları

1. **Kümülatif bağlam:** her adımda tüm geçmiş prompt'a eklenir, üstel
   büyüme oluşur.
2. **Döngü + büyüyen prompt:** `tool_loop` ile birlikte görülürse her
   tekrar prompt'u büyütür — bkz. `incidents/incident_003_token_burn.md`.
3. **Aşırı ayrıntılı araç çıktısı:** büyük `output_size_bytes` değerine
   sahip bir aracın çıktısının filtrelenmeden prompt'a eklenmesi.
4. **Yanlış model/parametre seçimi:** `max_tokens`/context window
   ayarının yanlış yapılandırılması.

## Azaltma Adımları

1. Bağlamı özetle veya kaydırmalı pencere (sliding window) uygula.
2. Araç çıktılarını ilgili alanla sınırlı şekilde prompt'a dahil et.
3. `token_spike` + `tool_loop` birlikte görülüyorsa agent'ı sonlandır
   (bkz. `runbooks/rb_terminate_agent.md`).
4. Tekrarlayan token_spike olaylarında görev tipine özel bütçe
   politikasını gözden geçir (`policies/token_budget_policy.md`).
