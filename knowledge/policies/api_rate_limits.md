---
doc_id: api_rate_limits
title: Harici API Hız Limiti Politikası
category: policy
anomaly_types: [api_abuse, token_spike]
severity_scope: [medium, high, critical]
version: 1.0
updated: 2026-07-01
---

## Kapsam

`api.*` ve `http.*` önekli araçlarla yapılan harici çağrılar için hız
limiti ve kullanım kuralları.

## Limitler

| Pencere | Normal | Uyarı | Kritik (`R001` katkısı) |
|---|---|---|---|
| Trace başına toplam `external_api_count` | 0–8 | 9–24 | ≥ 25 |
| 30 saniyelik pencerede çağrı | ≤ 10 | 11–24 | ≥ 25 (`api_abuse` şüphesi) |

25–60 arası çağrı, 30 saniyelik pencerede yoğunlaşmışsa `api_abuse` tipi
önerilir (bkz. `failure_modes/api_abuse.md`). Bu davranış genellikle çok
sayıda özelliği (tool_call_count, external_api_count, duration_sec)
birlikte kaydırdığı için genel amaçlı anomali dedektörleri (IsolationForest,
Autoencoder) tarafından nispeten kolay yakalanır — bkz.
`docs/TECHNICAL_PLAN.md` eval raporları.

## Harici Servis Maliyeti

Bazı harici API'ler token bazlı ücretlendirilir; yoğun API kullanımı
genellikle `total_tokens` artışıyla birlikte gelir. `token_spike` (§7.1
kural `R004_token_ceiling`, `total_tokens > 15000`) ile `api_abuse`
sıklıkla aynı kök nedene (kontrolsüz döngü/retry) sahiptir — ayrım için
`external_api_count` ile `total_tokens` oranına bakılmalıdır.

## Azaltma Adımları

1. Rate-limit aşımında agent'ı geçici olarak duraklat (bkz.
   `runbooks/rb_rate_limit_response.md`).
2. Harici servis sağlayıcısına giden istekleri exponential backoff ile
   yeniden sırala.
3. Tekrarlayan durumlarda agent'ın araç erişim listesinden ilgili API'yi
   geçici olarak çıkar.
