#!/usr/bin/env bash
# Codespaces ilk açılışta bir kere çalışır — backend venv + frontend
# node_modules'ı hazırlar. Ağır adımlar (model eğitimi, RAG index, Ollama
# model indirme) burada YAPILMAZ — codespace oluşturma süresini şişirmemek
# için kasıtlı olarak elle tetiklenecek şekilde bırakılmıştır (bkz. çıktı).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "== Backend: venv + bağımlılıklar =="
python3.11 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e ".[dev,dashboard]" -q
[ -f .env ] || cp .env.example .env

echo "== Frontend: npm bağımlılıkları =="
cd frontend
npm install --no-fund --no-audit
[ -f .env.local ] || cp .env.local.example .env.local
cd ..

cat <<'EOF'

==================================================================
Kurulum tamam. İki hazır yol var:

  A) Sadece arayüzü görmek (hızlı, ML modeli indirmez):
     cd frontend && npm run dev:fake-backend   # terminal 1
     cd frontend && npm run dev                 # terminal 2
     -> "PORTS" sekmesinde 3000'i aç

  B) Gerçek backend (ML modelleri indirilir, biraz sürer):
     source .venv/bin/activate
     make bootstrap        # sentetik veri + model eğitimi + RAG index
     make dev              # terminal 1 — API :8000
     cd frontend && npm run dev   # terminal 2 — web :3000
     (Ollama için: curl -fsSL https://ollama.com/install.sh | sh &&
      ollama serve & ollama pull qwen2.5:7b-instruct-q4_K_M)

Detaylar: README.md ve frontend/README.md
==================================================================
EOF
