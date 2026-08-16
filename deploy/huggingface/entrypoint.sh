#!/usr/bin/env bash
# HF Spaces (ücretsiz katman) kalıcı disk sunmaz — container her yeniden
# başlatıldığında (48sa işlemsizlik sonrası uyku/uyanma ya da yeniden
# deploy) bu script training/index/model indirmeyi SIFIRDAN yapar.
# Bu kasıtlı: idempotent kontrol (dosya/varlık zaten var mı) sayesinde
# gereksiz tekrar iş yapılmaz, ama gerçekten sıfırdan başlıyorsa ilk açılış
# 5-15 dakika sürebilir (bge-m3 + Ollama modeli indirme + eğitim).
set -euo pipefail

echo "== [1/4] Ollama başlatılıyor =="
ollama serve > /tmp/ollama.log 2>&1 &

for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:11434/api/version" > /dev/null 2>&1; then
    echo "Ollama hazır."
    break
  fi
  sleep 1
done

echo "== [2/4] Model kontrol ediliyor: ${AG_OLLAMA_MODEL} =="
if ! ollama list | grep -q "${AG_OLLAMA_MODEL}"; then
  echo "Model bulunamadı, çekiliyor (birkaç dakika sürebilir)..."
  ollama pull "${AG_OLLAMA_MODEL}"
else
  echo "Model zaten mevcut, atlanıyor."
fi

echo "== [3/4] Bootstrap kontrol ediliyor (sentetik veri + model eğitimi + RAG index) =="
if [ ! -f "${AG_ARTIFACTS_PATH}/manifest.json" ]; then
  echo "Artefakt bulunamadı, bootstrap çalıştırılıyor..."
  python scripts/generate_synthetic.py --seed 42
  python scripts/train_models.py
  python scripts/build_index.py --out "${AG_INDEX_PATH}"
else
  echo "Artefaktlar zaten mevcut, atlanıyor."
fi

echo "== [4/4] API başlatılıyor (port ${PORT}) =="
exec uvicorn agentguard.api.app:create_app --factory --host 0.0.0.0 --port "${PORT}"
