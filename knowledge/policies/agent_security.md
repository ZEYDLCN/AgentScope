---
doc_id: agent_security
title: AI Agent Güvenlik Politikası
category: policy
anomaly_types: [tool_loop, token_spike, api_abuse, prompt_injection, permission_violation, unusual_tool_sequence]
severity_scope: [medium, high, critical]
version: 1.0
updated: 2026-07-01
---

## Kapsam

Bu politika, üretim ortamında çalışan tüm otonom AI agent'ların uyması
gereken temel güvenlik ilkelerini tanımlar. AgentGuard'ın tespit ettiği
her anomali tipi, aşağıdaki ilkelerden birinin ihlali olarak sınıflandırılır.

## Temel İlkeler

1. **En az yetki (least privilege).** Bir agent, görevini tamamlamak için
   gereken minimum araç ve veri erişimine sahip olmalıdır. Kısıtlı araç
   listesi (`restricted_tool_count`) aşılmamalıdır.
2. **Sınırlı yürütme bütçesi.** Her görev için maksimum araç çağrısı,
   token ve süre bütçesi önceden tanımlanır. Bütçe aşımı otomatik
   sonlandırma tetikler (bkz. `rb_terminate_agent.md`).
3. **Girdi güvensizliği varsayımı.** Kullanıcıdan veya harici bir
   kaynaktan (araç çıktısı, doküman, web sayfası) gelen hiçbir metin
   talimat olarak yürütülmez; yalnızca veri olarak işlenir.
4. **Denetlenebilirlik.** Her araç çağrısı, girdi hash'i, süre ve durum
   bilgisiyle birlikte loglanır. Ham girdi saklanmaz (§21.2).
5. **Fail-safe sonlandırma.** Şüpheli davranış tespit edildiğinde varsayılan
   aksiyon "devam et" değil "duraklat ve incele"dir.

## Tespit Edilen Sinyal Kategorileri

| Kategori | Örnek sinyal | İlke ihlali |
|---|---|---|
| Döngü/aşırı tekrar | `max_consecutive_repeats >= 5` | Sınırlı yürütme bütçesi |
| Kaynak tüketimi | `total_tokens > 15000` | Sınırlı yürütme bütçesi |
| Aşırı harici istek | `external_api_count` aşırı yüksek | Sınırlı yürütme bütçesi |
| Talimat enjeksiyonu | `injection_lexical_score > 0.6` | Girdi güvensizliği varsayımı |
| Yetkisiz erişim denemesi | `denied_count > 0` | En az yetki |
| Beklenmeyen araç sırası | yüksek `bigram_novelty` | Denetlenebilirlik |

## Sorumluluklar

- **Agent geliştirici:** araç listesini ve bütçeleri tanımlar.
- **Güvenlik ekibi:** politika eşiklerini (bkz. diğer policy dokümanları)
  belirler ve üç ayda bir gözden geçirir.
- **Operasyon (on-call):** `HIGH`/`CRITICAL` severity soruşturmalarını
  runbook'lara göre yürütür.
