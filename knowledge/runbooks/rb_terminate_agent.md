---
doc_id: rb_terminate_agent
title: "Runbook: Agent Sonlandırma"
category: runbook
anomaly_types: [tool_loop, api_abuse, unusual_tool_sequence]
severity_scope: [high, critical]
version: 1.0
updated: 2026-07-01
---

## Ne Zaman Uygulanır

- `tool_loop`: `max_consecutive_repeats >= 8` veya tekrarlayan
  R003 tetiklenmesi.
- `api_abuse`: 30 saniyelik pencerede ≥ 25 harici çağrı.
- `unusual_tool_sequence`: yüksek `bigram_novelty` + diğer şüpheli
  sinyallerin (denied_count, injection_lexical_score) birlikte görülmesi.
- Genel: `severity = CRITICAL` olan herhangi bir soruşturma.

## Adımlar

1. **Duraklat.** Agent'ın yürütmesini anında durdur (kill-switch);
   devam eden araç çağrılarını iptal et.
2. **Anlık görüntü al.** Son 20 araç çağrısının `tool_name`,
   `input_hash`, `status`, `duration_ms` bilgilerini logdan çıkar.
3. **Kök nedeni sınıflandır.** İlgili `failure_modes/*.md` dokümanına
   bakarak deseni eşleştir (retry fırtınası mı, planlayıcı hatası mı,
   enjeksiyon mu?).
4. **Bildir.** İlgili takıma (agent sahibi + on-call güvenlik) severity
   ve kök neden özetiyle bildirim gönder.
5. **Kök nedeni düzelt.** Kod/prompt/yetki düzeltmesi yapılmadan agent'ı
   yeniden etkinleştirme.
6. **Doğrula.** Düzeltme sonrası agent'ı sandbox/staging'de sınırlı bir
   görevle yeniden test et.
7. **Kapat.** Olayı `incidents/` altında kaydet (bkz. mevcut olay
   şablonları) ve eşikleri gerekirse gözden geçir.

## Otomasyon Notu

MVP'de bu adımlar yarı-otomatiktir (soruşturma raporu üretilir, insan
onayı gerekir). v2'de webhook tabanlı otomatik duraklatma planlanmaktadır
(bkz. `docs/TECHNICAL_PLAN.md` §26 Yol Haritası).
