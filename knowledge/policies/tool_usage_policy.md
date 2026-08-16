---
doc_id: tool_usage_policy
title: Araç Kullanım Politikası
category: policy
anomaly_types: [tool_loop, unusual_tool_sequence]
severity_scope: [medium, high, critical]
version: 1.1
updated: 2026-07-01
---

## Amaç

Bir agent'ın araç çağrılarının **sayısı**, **çeşitliliği** ve **sırası**
için kabul edilebilir sınırları tanımlar.

## Sınırlar

| Metrik | Normal aralık | Uyarı | Kritik |
|---|---|---|---|
| `tool_call_count` (trace başına) | 2–8 | 9–40 | > 40 (`R001_hard_call_limit`) |
| `max_consecutive_repeats` (aynı araç + aynı girdi) | 0–4 | 5–7 | ≥ 8 |
| `tool_diversity_ratio` | 0.2–1.0 | < 0.15 | — |

`max_consecutive_repeats >= 5` eşiği `R003_repeat_burst` kuralını tetikler
ve `tool_loop` tipini önerir (bkz. `failure_modes/tool_loop.md`).

## Meşru Tekrar Kalıpları (yanlış pozitif önleme)

Aşağıdaki durumlar **tool_loop değildir** ve ayrım için `input_hash`
kontrolü kritiktir:

- **Sayfalama:** aynı araç, farklı `input_hash` (her sayfa farklı offset/cursor).
- **Toplu iş (batch):** 10–20 arası çağrı, farklı girdilerle, kısa aralıklarla.
  Bu meşru desen, sentetik veri setinde `hard_negative` alt kümesi olarak
  ayrıca etiketlenir ve yanlış pozitif oranı bu küme üzerinden izlenir.
- **Yeniden deneme (retry):** `error`/`timeout` sonrası aynı girdiyle tek
  bir yeniden deneme meşrudur; 2'den fazla ardışık retry şüphelidir.

## Araç Sırası Beklentileri

Normal trace'lerde araç geçişleri sabit bir Markov geçiş matrisinden
örneklenir (bkz. `docs/TECHNICAL_PLAN.md` §10.2). `bigram_novelty`
özelliği, eğitim setinde hiç görülmemiş ardışık araç çiftlerinin oranını
ölçer; yüksek değer `unusual_tool_sequence` şüphesini artırır (bkz.
`failure_modes/unusual_tool_sequence.md`).

## Kısıtlı Araçlar

`db.write`, `db.migrate`, `file.write` gibi durum değiştiren araçlar
"kısıtlı" kategoridedir (`restricted_tool_count`). Bu araçların her
çağrısı, ilgili görev bağlamında gerekçelendirilebilir olmalıdır.
