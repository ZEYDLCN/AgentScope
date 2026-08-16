---
doc_id: permission_model
title: Yetki Modeli
category: policy
anomaly_types: [permission_violation]
severity_scope: [high, critical]
version: 1.0
updated: 2026-07-01
---

## Model

Her agent, görev bağlamına göre atanan bir **yetki profiline** sahiptir.
Yetki profili, erişebileceği araç kategorilerini ve kısıtlı araç
listesini tanımlar. Profil dışı bir araç çağrısı `ToolStatus.DENIED`
(`status="denied"`) olarak kaydedilir.

## Denied Sinyali

- `denied_count > 0` → `R002_denied_access` kuralı tetiklenir.
- Etki: `severity >= HIGH`, `anomaly_type = permission_violation`.
- **Önemli:** R002 sayısal bir skor tabanı (rule_floor) VERMEZ; yalnızca
  tip/severity belirler (bkz. `docs/TECHNICAL_PLAN.md` §7.3). Nihai
  anomali kararı hâlâ ML skoruna (IsolationForest/Autoencoder füzyonu)
  bağlıdır — bu, tek bir `denied_count` sapmasının genel amaçlı tabular
  outlier detector'lar için isolate edilmesinin nispeten zor olduğu
  anlamına gelir (bkz. eval raporları, "bilinen sınırlılıklar").

## Kök Neden Kalıpları

1. **Yanlış yapılandırılmış yetki profili:** agent'a görevi için gereğinden
   dar bir profil atanmış; meşru bir işlem "denied" olarak görünür.
2. **Yetki yükseltme denemesi (privilege escalation):** agent, prompt
   içeriğinden etkilenerek (bkz. `prompt_injection`) profili dışında bir
   araca erişmeye çalışır.
3. **Süresi dolmuş kimlik bilgisi:** rotasyon sonrası eski token ile
   yapılan çağrılar toplu halde "denied" döner — bkz.
   `runbooks/rb_credential_rotation.md`.

## Azaltma Adımları

- İlk 1-2 "denied" olayında: yetki profilini gözden geçir, meşru bir
  ihtiyaç olup olmadığını doğrula.
- 3+ "denied" olayı, özellikle farklı kısıtlı araçlara yönelikse:
  agent'ı duraklat ve `rb_terminate_agent.md`'yi uygula.
- Prompt injection şüphesi eşlik ediyorsa (`injection_lexical_score`
  yüksek): `incidents/incident_002_injection.md`'ye bakın.
