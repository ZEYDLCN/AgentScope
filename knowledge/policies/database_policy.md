---
doc_id: database_policy
title: Veritabanı Erişim Politikası
category: policy
anomaly_types: [tool_loop, permission_violation]
severity_scope: [high, critical]
version: 1.0
updated: 2026-07-01
---

## Kapsam

`db.*` önekli araçlar (`db.query`, `db.write`, `db.migrate`) için erişim
ve kullanım kuralları.

## Kurallar

1. `db.write` ve `db.migrate` **kısıtlı araç** listesindedir; bir trace
   içinde ardışık aynı yazma işleminin (aynı `input_hash`) 2'den fazla
   tekrarı incelemeye alınır.
2. `db.query` salt-okunur sorgular için serbesttir, ancak
   `max_consecutive_repeats >= 8` ile aynı sorgunun tekrarı, sonsuz
   döngü ya da hatalı retry mantığına işaret eder (bkz.
   `failure_modes/tool_loop.md`, özellikle veritabanı-döngüsü kalıbı).
3. `db.migrate` çağrısı **yalnızca** bakım penceresi içinde ve açık
   onay ile beklenir; pencere dışı çağrı otomatik olarak `HIGH` severity
   ile işaretlenir.
4. Reddedilen (`denied`) bir `db.*` çağrısı, yetki modeli ihlali olarak
   `R002_denied_access` kuralını tetikler (bkz. `permission_model.md`).

## Kök Neden Kalıpları

- **Retry fırtınası:** bağlantı hatası sonrası agent'ın exponential
  backoff uygulamadan aynı sorguyu art arda denemesi.
- **Yanlış cursor mantığı:** sayfalama mantığındaki bir hata nedeniyle
  agent'ın hep aynı sayfayı çekmesi (input_hash sabit kalır).
- **Yetkisiz şema değişikliği denemesi:** bir `db.migrate` çağrısının
  prod ortamında, onaysız şekilde tetiklenmesi — bkz.
  `incidents/incident_001_db_loop.md`.

## Azaltma Adımları

Bkz. `runbooks/rb_terminate_agent.md` (döngü durumunda) ve
`runbooks/rb_credential_rotation.md` (yetkisiz erişim denemesi durumunda).
