# AgentScope — Tanıtım Sayfası (statik)

Bu klasör, ana uygulamadan (backend + Next.js frontend) tamamen bağımsız,
tek dosyalık bir tanıtım/vaka çalışması sayfasıdır. Build adımı,
framework algılaması veya ortam değişkeni gerektirmez — `index.html`
kendi içine gömülü fontlar, görseller ve stillerle tek başına çalışır.

Amaç: canlı bir demo yerine LinkedIn/portföy paylaşımında kullanılacak,
projenin mimarisini, tasarım kararlarını ve gerçek değerlendirme
sonuçlarını anlatan bağımsız bir sayfa.

## Vercel'e deploy etme

Bu klasörü, `frontend/`'deki asıl uygulamadan **ayrı bir Vercel
projesi** olarak import et — ikisini karıştırma:

1. https://vercel.com/new → **Add New → Project**
2. `ZEYDLCN/AgentScope` reposunu seç
3. **Root Directory**: `deploy/showcase-site` (Edit'e tıklayıp seç)
4. **Framework Preset**: "Other" (otomatik algılanmalı, `vercel.json`
   içindeki `"framework": null` bunu zaten zorluyor)
5. Environment Variables: **hiçbiri gerekmiyor**, boş bırak
6. **Deploy**

Birkaç saniye içinde `https://<proje-adın>.vercel.app` üzerinden canlı
olur.
