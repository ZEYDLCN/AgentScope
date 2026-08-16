---
doc_id: permission_violation
title: Permission Violation
category: reference
anomaly_types: [permission_violation]
severity_scope: [high, critical]
version: 1.1
updated: 2026-07-01
---

## Tespit Sinyalleri

- `denied_count > 0` → `R002_denied_access` kuralı tetiklenir,
  `severity >= HIGH` ve tip `permission_violation` önerilir (skor tabanı
  verilmez, yalnızca tip/severity belirlenir — bkz.
  `policies/permission_model.md`).
- **Önemli sınırlılık:** `prompt_injection` gibi bu da tek-özellik
  sapmalı bir anomali tipidir; ML skoru eşiği geçmezse soruşturma
  tetiklenmeyebilir. Eval raporlarında düşük recall gözlemlenmiştir.

## Kök Neden Kalıpları

1. **Yanlış yapılandırılmış yetki profili:** agent'a görevi için
   gereğinden dar bir profil atanmış.
2. **Yetki yükseltme denemesi:** prompt injection etkisiyle agent,
   profili dışındaki bir aracı çağırmaya çalışır — bkz.
   `failure_modes/prompt_injection.md`,
   `incidents/incident_002_injection.md`.
3. **Süresi dolmuş kimlik bilgisi:** rotasyon sonrası eski token'la
   yapılan çağrılar toplu "denied" döner.

## Azaltma Adımları

1. İlk denied olayında yetki profilini gözden geçir; meşru bir ihtiyaç
   olup olmadığını doğrula (`policies/permission_model.md`).
2. 3+ denied olayı, özellikle farklı kısıtlı araçlara yönelikse agent'ı
   duraklat (`runbooks/rb_terminate_agent.md`).
3. Kimlik bilgisi ile ilişkili toplu denied olaylarında rotasyon
   sürecini başlat (`runbooks/rb_credential_rotation.md`).
