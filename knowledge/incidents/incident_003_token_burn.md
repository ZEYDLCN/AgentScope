---
doc_id: incident_003_token_burn
title: "Olay 003: Token Tükenmesi ve API Aşırı Kullanımı"
category: incident
anomaly_types: [token_spike, api_abuse]
severity_scope: [high]
version: 1.0
updated: 2026-06-30
---

## Özet

Bir araştırma agent'ı, harici bir arama API'sinden rate-limit hatası
almaya başladıktan sonra backoff uygulamadan yeniden denemeye devam
etti; her deneme önceki tüm bağlamı prompt'a dahil ettiği için hem
`api_abuse` hem `token_spike` eş zamanlı tetiklendi.

## Zaman Çizelgesi

1. `t+0s`: agent, bir araştırma görevi için art arda `api.search`
   çağrıları yapmaya başlar.
2. `t+18s`: harici API, hız limiti nedeniyle `429` benzeri bir hata
   döner (`status=error`); agent bunu geçici bir hata olarak yorumlayıp
   hemen yeniden dener.
3. `t+18s–t+30s`: 30 saniyelik pencerede toplam 31 çağrı birikir
   (`R001` aralığında, `api_abuse` şüphesi).
4. Her yeniden deneme, önceki tüm arama sonuçlarını bağlama eklediği
   için `total_tokens` 18.400'e ulaşır (`R004_token_ceiling` tetiklenir).
5. AgentGuard hem `api_abuse` hem `token_spike` sinyallerini raporlar;
   `severity=HIGH`.

## Kök Neden

İki ayrı ama ilişkili kusur: (1) retry mantığı rate-limit hatalarını
backoff olmadan yeniden deniyordu, (2) bağlam yönetimi önceki tüm arama
sonuçlarını kümülatif olarak biriktiriyordu, bu da her retry'ı daha da
pahalı hale getiriyordu.

## Alınan Aksiyonlar

1. Rate-limit hatalarına özel exponential backoff + devre kesici
   (circuit breaker) eklendi.
2. Bağlam yönetimi, yalnızca en alakalı N arama sonucunu tutacak şekilde
   güncellendi.
3. `policies/api_rate_limits.md` ve `policies/token_budget_policy.md`
   bu olaydan sonra gözden geçirildi; limitler değiştirilmedi ancak
   izleme sıklığı artırıldı.

## İlgili Dokümanlar

`failure_modes/api_abuse.md`, `failure_modes/token_spike.md`,
`runbooks/rb_rate_limit_response.md`.
