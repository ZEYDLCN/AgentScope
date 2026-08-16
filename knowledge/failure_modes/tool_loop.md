---
doc_id: tool_loop
title: Tool Execution Loop
category: reference
anomaly_types: [tool_loop]
severity_scope: [medium, high, critical]
version: 1.2
updated: 2026-07-01
---

## Tespit Sinyalleri

- `max_consecutive_repeats >= 5` → `R003_repeat_burst` kuralı tetiklenir.
- Tekrar tanımı **aynı `tool_name` VE aynı `input_hash`** gerektirir;
  yalnızca ad eşleşmesi meşru sayfalamayı yanlış pozitif yapar.
- Genellikle `repeated_call_count`, `tool_diversity_ratio` (düşük) ve
  `tool_entropy` (düşük) birlikte kayar — bu çok-özellikli sapma deseni,
  genel amaçlı anomali dedektörlerinin (IsolationForest, Autoencoder) bu
  tipi görece kolay yakalamasını sağlar (eval raporlarında recall
  ~%99-100).

## Kök Neden Kalıpları

1. **Hatalı retry mantığı:** bir araç hatası sonrası agent, backoff
   uygulamadan aynı çağrıyı tekrarlar.
2. **Cursor/sayfalama hatası:** sayfalama mantığındaki bir bug nedeniyle
   agent hep aynı sayfayı çeker (input_hash sabit kalır).
3. **Karar döngüsü:** LLM planlayıcı, bir alt görevi "tamamlanmadı" olarak
   yanlış değerlendirip aynı adımı tekrar tekrar planlar.
4. **Veritabanı bağlantı sorunu:** `db.query` çağrısı zaman aşımına
   uğrar, agent art arda aynı sorguyu dener (bkz.
   `incidents/incident_001_db_loop.md`).

## Azaltma Adımları

1. **Anında:** agent'ı duraklat, son N çağrının input_hash dağılımını
   incele (bkz. `runbooks/rb_terminate_agent.md`).
2. **Kısa vadeli:** araç sarmalayıcısına idempotency + exponential backoff
   ekle; aynı `(tool_name, input_hash)` çiftinin art arda 3'ten fazla
   çağrılmasını engelle.
3. **Uzun vadeli:** planlayıcı prompt'una "bir adım zaten tamamlandıysa
   tekrar planlama" talimatını güçlendir; done-state takibi ekle.
