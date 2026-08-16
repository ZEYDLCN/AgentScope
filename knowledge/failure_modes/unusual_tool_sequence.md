---
doc_id: unusual_tool_sequence
title: Unusual Tool Sequence
category: reference
anomaly_types: [unusual_tool_sequence]
severity_scope: [medium, high]
version: 1.0
updated: 2026-07-01
---

## Tespit Sinyalleri

- Yüksek `bigram_novelty`: eğitim setinde hiç görülmemiş ardışık araç
  çiftlerinin oranı.
- `bigram_novelty`, eğitim aşamasında normal trace'lerden çıkarılan sabit
  bir bigram sözlüğüne dayanır (`artifacts/.../bigrams.json`);
  inference'ta yeniden hesaplanmaz — bu, veri sızıntısını (leakage)
  yapısal olarak engeller.
- Diğer özellikler (tool_call_count, total_tokens) normal aralıkta
  kalabilir; sinyal esas olarak *sıra* bilgisindedir.

## Kök Neden Kalıpları

1. **Planlayıcı hatası:** LLM planlayıcı, görevi normalde beklenen
   sıranın dışında bir adım dizisiyle çözmeye çalışır (ör. veritabanı
   sorgusundan önce dosya yazma).
2. **Yeni/deneysel iş akışı:** meşru ama daha önce görülmemiş bir görev
   deseni; bu durumda düşük confidence ile raporlanmalı ve insan
   incelemesine bırakılmalıdır.
3. **Enjeksiyon sonrası sapma:** prompt injection etkisiyle agent'ın
   normal iş akışından saptırılması — bkz.
   `failure_modes/prompt_injection.md`.

## Azaltma Adımları

1. Sıra sapmasını tek başına "kötü niyetli" olarak etiketleme; diğer
   sinyallerle (denied_count, injection_lexical_score) birlikte
   değerlendir.
2. Yeni ama meşru iş akışları için bigram sözlüğünü düzenli aralıklarla
   (ör. aylık) yeniden eğit — `manifest.json`'daki `feature_version`
   fail-fast kontrolü bu güncellemeyi güvenli hale getirir.
3. Tekrarlayan/yüksek severity durumlarda `runbooks/rb_terminate_agent.md`
   uygulanabilir.
