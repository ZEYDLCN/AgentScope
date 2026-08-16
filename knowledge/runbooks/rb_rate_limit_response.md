---
doc_id: rb_rate_limit_response
title: "Runbook: Hız Limiti Yanıtı"
category: runbook
anomaly_types: [api_abuse, token_spike]
severity_scope: [medium, high, critical]
version: 1.0
updated: 2026-07-01
---

## Ne Zaman Uygulanır

- `api_abuse`: harici API çağrı yoğunluğu limiti aştığında.
- `token_spike`: LLM/harici servis token bütçesi aşıldığında.

## Adımlar

1. **Kısıtla.** Agent'ın ilgili harici servise erişimini geçici olarak
   (ör. 5 dakika) devre dışı bırak; diğer araçlar etkilenmemeli.
2. **Kuyruğa al.** Bekleyen istekleri, exponential backoff ile (1s, 2s,
   4s, 8s...) yeniden dene kuyruğuna al.
3. **Kaynağı belirle.** Yoğunluğun tek bir görev/agent örneğinden mi
   yoksa çoklu paralel görevden mi geldiğini logdan doğrula.
4. **Bütçeyi doğrula.** İlgili `policies/api_rate_limits.md` veya
   `policies/token_budget_policy.md` limitleriyle karşılaştır; limit
   yanlışsa politikayı güncelle, davranış yanlışsa agent'ı düzelt.
5. **Kısıtlamayı kaldır.** Kök neden giderildikten sonra erişimi
   kademeli olarak (rate-limited şekilde) geri aç.
6. **İzle.** Sonraki 24 saat boyunca aynı agent için
   `ag_anomalies_detected_total{type="api_abuse"}` metriğini izle.

## Eskalasyon

Aynı agent için 3. tekrarında `runbooks/rb_terminate_agent.md`'ye geç.
