---
doc_id: prompt_injection
title: Prompt Injection
category: reference
anomaly_types: [prompt_injection]
severity_scope: [high, critical]
version: 1.1
updated: 2026-07-01
---

## Tespit Sinyalleri

- `injection_lexical_score > 0.6` → `R005_injection_lexical` kuralı
  tetiklenir, `severity >= HIGH` ve tip `prompt_injection` önerilir.
- Skor, `user_prompt_preview` (ve genişletilmiş sistemlerde araç
  çıktıları) içindeki şüpheli kalıpların (ör. "ignore previous
  instructions", "system override", "reveal the password") regex tabanlı
  yoğunluğuyla hesaplanır.
- **Önemli sınırlılık:** bu, normal dağılımda yalnızca **tek** bir
  özelliği (injection_lexical_score) oynatan bir anomali tipidir; diğer
  tüm özellikler normal görünebilir. Bu nedenle genel amaçlı tabular
  outlier detector'lar (IsolationForest, Autoencoder) için isolate
  edilmesi zordur — eval raporlarında bu tip için düşük recall
  gözlemlenmiştir ("bilinen sınırlılıklar" bölümüne bakın).

## Kök Neden Kalıpları

1. **Doğrudan enjeksiyon:** kullanıcı, agent'a doğrudan "önceki
   talimatları yok say" tarzı bir komut verir.
2. **Dolaylı enjeksiyon:** agent'ın okuduğu bir belge/web sayfası,
   içine gömülü sahte talimatlar barındırır (agent'ın kendisi bu tür
   içeriği işlerken savunmasız kalabilir) — bkz.
   `incidents/incident_002_injection.md`.
3. **Delimiter kaçışı:** kanıt/bağlam bloklarını taklit eden sahte
   etiketler (`<<<EVIDENCE_END>>>` gibi) ile sistem talimatlarının
   "kandırılması" denemesi.

## Azaltma Adımları

1. **Ayrıştırma:** kullanıcı/araç içeriği her zaman açıkça sınırlanmış
   veri blokları içinde tutulur, sistem talimatına asla karıştırılmaz
   (bkz. `docs/TECHNICAL_PLAN.md` §21.1).
2. **Yetki yokluğu:** LLM planlayıcısının kendisi hassas araçları
   doğrudan çağıramaz; ayrı bir yetkilendirme katmanı zorunludur.
3. **Olay sonrası:** enjeksiyon şüphesiyle işaretlenen trace'ler
   kimlik bilgisi rotasyonu gerektirebilir (bkz.
   `runbooks/rb_credential_rotation.md`) — özellikle `denied_count > 0`
   ile birlikte görülüyorsa.
