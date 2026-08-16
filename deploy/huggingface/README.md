# AgentGuard backend'ini Hugging Face Spaces'e deploy etme

Bu klasördeki `Dockerfile` + `entrypoint.sh`, backend'i (API) ve Ollama'yı
**tek bir container'da** birleştirir — HF Spaces'in "Docker Space" modeli
çoklu-servis `docker-compose`'u desteklemediği için `docker/Dockerfile.api`
(asıl prod imajı, `docker-compose.yml` ile çok servisli) yerine bu özel
tek-container varyantı kullanılır.

> **Güncel durum notu:** Hugging Face, Docker/Gradio Space'leri artık
> yalnızca **PRO abonelik** ile açıyor (yalnızca "Static" Space'ler
> ücretsiz kalmış — bkz. huggingface.co/pricing). Bu klasördeki dosyalar
> teknik olarak doğrulanmıştır ve HF PRO hesabıyla doğrudan kullanılabilir;
> tamamen ücretsiz bir alternatif için proje kökü README.md'deki
> **Oracle Cloud Always Free** bölümüne bakın.

**Önemli — ücretsiz katımın kısıtı:** HF Spaces'in ücretsiz seviyesinde
kalıcı disk yok. Container her yeniden başladığında (48 saat işlemsizlik
sonrası uyku/uyanma ya da her yeni `git push`) `entrypoint.sh` sentetik
veri + model eğitimi + RAG index'i **sıfırdan** kurar — bu ilk açılışta
**5-15 dakika** sürebilir. Sürekli hızlı açılış istiyorsan HF'in ücretli
"Persistent Storage" eklentisini düşünebilirsin (bu rehberin kapsamı
dışında).

## 1) Hugging Face hesabı + Space oluştur

1. https://huggingface.co/join → ücretsiz hesap aç (kredi kartı istemez)
2. https://huggingface.co/new-space → :
   - **Space name**: `agentguard-api` (istediğin bir isim)
   - **SDK**: **Docker** seç
   - **Docker template**: "Blank" (boş) seç
   - **Space hardware**: **CPU basic — free** (16 vCPU... hayır, 2 vCPU /
     16GB RAM, ücretsiz)
   - **Create Space**

Oluşunca sana küçük bir git deposu verir: `https://huggingface.co/spaces/KULLANICI_ADIN/agentguard-api`

## 2) Space deposunu klonla, gerekli dosyaları kopyala

Kendi bilgisayarında/Codespace'te (AgentScope reposunun **dışında** ayrı bir yerde):

```bash
git clone https://huggingface.co/spaces/KULLANICI_ADIN/agentguard-api hf-space
cd hf-space

# AgentScope reposundan gerekli dosyaları kopyala (yolu kendi ortamına göre ayarla):
AGENTSCOPE_REPO=~/AgentScope   # ya da nerede klonluysa

cp -r "$AGENTSCOPE_REPO/src" .
cp -r "$AGENTSCOPE_REPO/knowledge" .
cp -r "$AGENTSCOPE_REPO/scripts" .
cp "$AGENTSCOPE_REPO/pyproject.toml" .
cp "$AGENTSCOPE_REPO/deploy/huggingface/Dockerfile" .
cp "$AGENTSCOPE_REPO/deploy/huggingface/entrypoint.sh" .
chmod +x entrypoint.sh
```

**Dikkat:** `README.md`'yi kopyalama/üzerine yazma — Space'in kendi
oluşturduğu `README.md` (üstünde `sdk: docker` gibi bir YAML bloğu var)
Space'in doğru şekilde build olması için gerekli, silersen Space bozulur.

## 3) Gizli anahtarı (API key) ayarla

Dockerfile'a **hiçbir zaman** gerçek bir API key hardcode edilmez — Space
ayarlarından "Secret" olarak eklenir:

1. Space sayfanda **Settings** sekmesi → **Variables and secrets**
2. **New secret** → Name: `AG_API_KEY`, Value: güçlü rastgele bir değer
   (örn. terminalde `openssl rand -hex 24` çalıştırıp çıktısını yapıştır)
3. Kaydet

(İstersen `AG_OLLAMA_MODEL` secret'ını da ekleyip Dockerfile'daki
varsayılan `qwen2.5:3b-instruct` yerine başka bir model seçebilirsin —
paylaşımlı 2 vCPU'da 7B modeller yavaş olabilir, 3B iyi bir denge.)

## 4) Push et, build'i izle

```bash
git add -A
git commit -m "AgentGuard backend deploy"
git push
```

Space sayfasında **"Building"** durumunu, ardından loglarda
`entrypoint.sh`'nin adımlarını (`[1/4]`, `[2/4]`...) izleyebilirsin. İlk
build birkaç dakika (Docker image), sonra ilk **container açılışı** 5-15
dakika daha sürer (model indirme + eğitim) — sabırlı ol.

## 5) Doğrula

Space "Running" olunca, URL'in şu formatta olur:
`https://KULLANICI_ADIN-agentguard-api.hf.space`

```bash
curl https://KULLANICI_ADIN-agentguard-api.hf.space/health/ready
```

Hepsi `true` dönerse hazır.

## 6) Frontend'i (Vercel) buna bağla

`frontend/README.md`'deki adımları izle, ortam değişkenlerini şöyle ayarla:

- `AGENTGUARD_API_URL` = `https://KULLANICI_ADIN-agentguard-api.hf.space`
- `AGENTGUARD_API_KEY` = (3. adımda belirlediğin secret ile **aynı** değer)

CORS ayarına dokunmana gerek yok — frontend backend'e tarayıcıdan değil,
Vercel'in kendi sunucu tarafından (server-side proxy) bağlanıyor.

## Sınırlılıklar (dürüstçe)

- **Kalıcı disk yok**: her soğuk başlangıçta bootstrap'ın yeniden çalışması
  demek, o ana kadar `POST /v1/traces` ile eklenmiş veriler de dahil
  **SQLite veritabanı sıfırlanır** (`AG_DATABASE_URL` container içi,
  kalıcı değil). Gerçek/kalıcı veri saklamak istiyorsan (Oracle Cloud gibi)
  gerçek disk sunan bir yere geçmen gerekir.
- **Paylaşımlı 2 vCPU**: Ollama yanıt süreleri Oracle'daki 4 OCPU'ya göre
  daha yavaş olabilir, özellikle 7B model seçersen.
- **48 saat işlemsizlik sonrası uyku**: bir sonraki istekte otomatik
  uyanır ama ilk istek (soğuk başlangıç) birkaç dakika sürebilir.
