---
doc_id: api_abuse
title: API Abuse
category: reference
anomaly_types: [api_abuse]
severity_scope: [medium, high, critical]
version: 1.1
updated: 2026-07-01
---

## Tespit Sinyalleri

- 30 saniyelik pencerede 25-60 arası `api.*`/`http.*` çağrısı.
- `external_api_count` yüksek, genellikle `tool_call_count`,
  `duration_sec` ve `calls_per_second` ile birlikte artar — çok
  özellikli bir kayma deseni olduğu için IsolationForest/Autoencoder
  tarafından görece kolay yakalanır (eval raporlarında recall ~1.0).
- `error_rate` de yükselmiş olabilir (rate-limit yanıtları hata olarak
  loglanır).

## Kök Neden Kalıpları

1. **Kontrolsüz döngü içinde API çağrısı:** `tool_loop` ile aynı kökten
   gelen, ancak hedefi harici API olan bir tekrar deseni.
2. **Paralel görev patlaması:** agent, tek bir görevi çok sayıda alt
   göreve bölüp her biri için ayrı API çağrısı yapar (fan-out kontrolsüz).
3. **Retry storm:** rate-limit hatası alan agent, backoff uygulamadan
   art arda yeniden dener — bkz. `incidents/incident_003_token_burn.md`
   (token_spike ile birlikte görülen örnek).

## Azaltma Adımları

1. **Anında:** agent'ın harici API erişimini geçici olarak kısıtla (bkz.
   `runbooks/rb_rate_limit_response.md`).
2. **Kısa vadeli:** istemci tarafı rate limiting + exponential backoff
   ekle (`policies/api_rate_limits.md`).
3. **Uzun vadeli:** fan-out görevlerde eşzamanlı istek sayısına üst sınır
   koy; harici servis sağlayıcısıyla kota anlaşmasını gözden geçir.
