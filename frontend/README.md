# AgentScope — Web Konsolu

AgentGuard backend'ini (bkz. proje kökü) tüketen, Vercel'e deploy edilebilir
Next.js (App Router) tabanlı kurumsal bir gözlemlenebilirlik/soruşturma
arayüzü. `dashboard/` (Streamlit) ile aynı REST API'yi kullanır — bu, onun
yerini almak isteyenler için üretim kalitesinde, tema destekli bir
alternatiftir (ADR-006: tek doğruluk kaynağı REST API'dir, uygulama mantığı
paylaşılmaz).

**Marka:** frontend'in görünen adı **AgentScope** — sağlanan logo kitiyle
(monitoring-lens ikonu, "Agent" ince + "Scope" kalın DM Sans wordmark)
birebir uyumlu. Backend/API/Python paketi hâlâ `agentguard` adını taşır ve
değiştirilmedi; yalnızca kullanıcıya görünen web arayüzü markası budur.

## Sayfalar

| Route | İçerik |
|---|---|
| `/` | Genel Bakış — KPI kartları, severity dağılımı, soruşturma üretim kaynağı |
| `/anomalies` | Filtrelenebilir (severity, cursor-tabanlı sayfalama) anomali listesi |
| `/investigations/[traceId]` | Trace zaman çizelgesi + soruşturma raporu (kanıt/öneri kartları), manuel tetikleme |
| `/knowledge` | Retrieval debug — BM25 / vector / RRF / rerank aşamalarını yan yana gösterir |
| `/models` | Statik model + RAG ablation raporları (derleme zamanında gömülü) |

## Mimari

- **Sunucu tarafı proxy** (`src/app/api/**/route.ts`): backend'in
  `X-API-Key`'i yalnızca burada, sunucuda eklenir — tarayıcıya asla
  gönderilmez. İstemci bileşenleri yalnızca kendi `/api/*` uçlarını çağırır.
- **`src/lib/backend.ts`**: `AGENTGUARD_API_URL` + `AGENTGUARD_API_KEY`
  (server-only env, `NEXT_PUBLIC_` öneki YOK) ile backend'e istek atan tek
  yer.
- **`src/lib/types.ts`**: backend Pydantic şemalarının TypeScript izdüşümü.
- Tasarım sistemi: Tailwind v4 (CSS-first `@theme`), `next-themes` ile
  açık/koyu tema, `src/app/globals.css`'te tanımlı token'lar
  (`--color-accent`, `--color-critical` vb.) — severity renkleri backend'in
  `Severity` enum'uyla birebir eşlenir.
- **Marka sistemi** (`src/components/brand/`): `icon.tsx` (SVG, logo kitinin
  matematiğinin birebir portu — dış izleme halkası, segmentli derinlik
  halkası, radar taraması, mercek, agent düğümleri) + `wordmark.tsx`.
  İkisi de `currentColor` üzerinden çalışır — tema (açık/koyu) otomatik
  uygulanır, ayrı asset gerekmez. Marka rengi: Violet `#7C5CE4` ailesi
  (metinde AA kontrastı için `--accent` hafif koyultulmuş, ham ton ikonda
  korunur), tipografi DM Sans (300/700 wordmark, 400/500 gövde) + JetBrains
  Mono (etiket/kod). Favicon: `src/app/icon.svg` (Next.js otomatik algılar).

## Yerel geliştirme

```bash
cp .env.local.example .env.local   # AGENTGUARD_API_URL / AGENTGUARD_API_KEY
npm install
npm run dev   # http://localhost:3000
```

Gerçek backend'i ayağa kaldırmadan (Ollama/embedding modelleri olmadan) UI
üzerinde çalışmak için, gerçekçi sabit veriler döndüren minimal bir taklit
sunucu var:

```bash
npm run dev:fake-backend   # :8000'de backend uçlarını taklit eder
```

## Vercel'e deploy

1. Vercel'de yeni proje oluştururken **Root Directory**'yi `frontend` olarak
   ayarlayın (monorepo — Next.js otomatik algılanır, ekstra `vercel.json`
   gerekmez).
2. Proje ayarlarında şu ortam değişkenlerini ekleyin (Production + Preview):
   - `AGENTGUARD_API_URL` — AgentGuard FastAPI backend'inin herkese açık
     URL'i (ör. bir VM/Fly.io/Render'da `docker compose` ile çalışan API).
     **Vercel serverless fonksiyonlarında backend'in kendisini çalıştırmayın**
     — `torch`/`faiss`/`sentence-transformers` gibi ağır ML bağımlılıkları
     Vercel'in serverless ortamına uygun değildir; backend ayrı bir
     sunucuda/Docker'da kalmalıdır (bkz. proje kökü `docker/docker-compose.yml`).
   - `AGENTGUARD_API_KEY` — backend `Settings.api_key` ile aynı değer.
3. Backend'in CORS ayarında (`AG_CORS_ORIGINS`) bu Vercel domain'ini
   eklemenize gerek YOK — tüm istekler sunucu tarafı proxy üzerinden gittiği
   için tarayıcıdan backend'e doğrudan CORS isteği atılmaz.
4. Deploy sonrası `/health` üzerinden (top bar'daki bağlantı rozetinden)
   backend'e ulaşılabildiğini doğrulayın.

## Kalite kapıları

```bash
npm run typecheck   # tsc --noEmit
npm run lint        # eslint (eslint-config-next)
npm run build        # next build (production)
```
