---
doc_id: token_budget_policy
title: Token Bütçe Politikası
category: policy
anomaly_types: [token_spike]
severity_scope: [medium, high]
version: 1.0
updated: 2026-07-01
---

## Bütçe

| Görev tipi | Normal `total_tokens` | Uyarı | Kritik (`R004_token_ceiling`) |
|---|---|---|---|
| Standart sorgu/işlem | 500–3.000 | 3.001–15.000 | > 15.000 |
| Uzun özet/analiz (bilinen istisna) | 3.000–9.500 | — | > 15.000 |

`total_tokens > 15000` eşiği `R004_token_ceiling` kuralını tetikler ve
`token_spike` tipini önerir. Bu kural, R001 dışındaki diğer kurallar gibi
sayısal skor tabanı vermez; yalnızca tip önerisi sağlar.

## Zorlu Negatifler (Hard Negatives)

Meşru ama uzun işlemler (ör. 9.000 token'lık bir doküman özeti) yanlış
pozitif üretmemelidir. Sentetik değerlendirme veri setinde bu senaryolar
`hard_negative` alt kümesi olarak ayrıca etiketlenmiştir ve yanlış pozitif
oranı bu küme üzerinden izlenir (bkz. `docs/TECHNICAL_PLAN.md` §10.2).

## Kök Neden Kalıpları

- **Bağlam birikimi:** agent, önceki tüm adımların çıktısını her yeni
  çağrıya dahil ederse token kullanımı kümülatif olarak patlar.
- **Döngü içinde büyüyen prompt:** `tool_loop` ile birlikte görülen
  token_spike, her tekrarda prompt'un büyüdüğüne işaret eder — bkz.
  `incidents/incident_003_token_burn.md`.
- **Aşırı ayrıntılı araç çıktısı:** `output_size_bytes` yüksek araç
  çağrıları, sonraki adımda tüm çıktının prompt'a dahil edilmesiyle
  token patlamasına yol açabilir.

## Azaltma Adımları

1. Bağlam penceresini özetleyerek küçült (sliding window / summarization).
2. Araç çıktılarını tam olarak değil, ilgili kısmıyla prompt'a dahil et.
3. Tekrarlayan token_spike + tool_loop kombinasyonunda agent'ı sonlandır
   (bkz. `runbooks/rb_terminate_agent.md`).
