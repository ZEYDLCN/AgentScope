---
doc_id: rb_credential_rotation
title: "Runbook: Kimlik Bilgisi Rotasyonu"
category: runbook
anomaly_types: [permission_violation, prompt_injection]
severity_scope: [high, critical]
version: 1.0
updated: 2026-07-01
---

## Ne Zaman Uygulanır

- `permission_violation`: toplu/tekrarlayan `denied` olayları, özellikle
  farklı kısıtlı araçlara yönelikse.
- `prompt_injection`: enjeksiyon şüphesiyle işaretlenen ve ardından
  yetki ihlali denemesi görülen trace'ler (bkz.
  `incidents/incident_002_injection.md`).

## Adımlar

1. **Doğrula.** İlgili agent/servis kimlik bilgisinin (API key, token)
   son kullanım loglarını kontrol et; anormal coğrafya/zaman deseni ara.
2. **İptal et.** Şüpheli kimlik bilgisini derhal iptal et.
3. **Yeni kimlik bilgisi üret.** En az yetki ilkesine göre (bkz.
   `policies/permission_model.md`) yeni bir kimlik bilgisi oluştur.
4. **Dağıt.** Yeni kimlik bilgisini güvenli bir secret store üzerinden
   agent'a ilet; eski kimlik bilgisini konfigürasyondan tamamen kaldır.
5. **Denetim izi oluştur.** Rotasyon nedenini, zamanını ve etkilenen
   agent kimliğini kaydet.
6. **Kök nedeni kapat.** Eğer neden prompt injection ise, ilgili girdi
   kaynağını (belge, web sayfası) karantinaya al ve savunma katmanlarını
   gözden geçir (bkz. `docs/TECHNICAL_PLAN.md` §21.1).

## Doğrulama

Rotasyon sonrası agent'ı sınırlı bir görevle yeniden test et; 24 saat
boyunca `denied_count` metriğinin sıfıra döndüğünü doğrula.
