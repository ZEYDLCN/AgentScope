---
doc_id: incident_001_db_loop
title: "Olay 001: Veritabanı Sorgu Döngüsü"
category: incident
anomaly_types: [tool_loop, unusual_tool_sequence]
severity_scope: [high]
version: 1.0
updated: 2026-06-15
---

## Özet

Bir sipariş-durumu agent'ı, bağlantı zaman aşımı sonrası aynı `db.query`
çağrısını 47 kez art arda tekrarladı; agent 82 saniye boyunca hiçbir
ilerleme kaydetmeden çalışmaya devam etti.

## Zaman Çizelgesi

1. `t+0s`: agent, sipariş kaydını çekmek için `db.query` çağırır.
2. `t+2s`: veritabanı bağlantı havuzu doygunluğu nedeniyle sorgu zaman
   aşımına uğrar (`status=timeout`).
3. `t+2s–t+82s`: agent, hata işleme mantığındaki bir kusur nedeniyle
   backoff uygulamadan **aynı sorguyu** (aynı `input_hash`) tekrar tekrar
   dener — toplam 47 çağrı.
4. `t+82s`: AgentGuard, `tool_call_count > 40` (`R001_hard_call_limit`)
   ve `max_consecutive_repeats >= 8` (`R003_repeat_burst`) kurallarını
   tetikler; `severity=HIGH`, `anomaly_type=tool_loop`.

## Kök Neden

Retry mantığı, `timeout` durumunu `error` durumundan ayırt etmiyor ve
her iki durumda da sabit (backoff'suz) bir yeniden deneme uyguluyordu.
Ayrıca bağlantı havuzu boyutu, eşzamanlı agent sayısına göre az
yapılandırılmıştı — bu da zaman aşımı olasılığını artırdı.

## Alınan Aksiyonlar

1. Retry mantığına exponential backoff + maksimum 3 deneme sınırı
   eklendi.
2. Bağlantı havuzu boyutu artırıldı ve bağlantı sızıntısı için ayrı bir
   izleme eklendi.
3. `R003_repeat_burst` eşiği (`max_consecutive_repeats >= 5`) bu olaydan
   sonra doğrulandı ve değiştirilmedi (zaten yeterince erken tetikleniyordu).

## İlgili Dokümanlar

`failure_modes/tool_loop.md`, `policies/database_policy.md`,
`runbooks/rb_terminate_agent.md`.
