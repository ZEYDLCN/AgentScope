.PHONY: bootstrap dev test eval index lint fmt up down

bootstrap:  ## sentetik veri + model eğitimi + index (idempotent)
	python scripts/generate_synthetic.py --seed 42
	python scripts/train_models.py
	python scripts/build_index.py

dev:        ## API'yi otomatik reload ile çalıştır
	uvicorn agentguard.api.app:create_app --factory --reload

test:       ## hızlı test paketi (slow işaretli testler hariç)
	pytest -m "not slow" --cov=src/agentguard --cov-fail-under=80

eval:       ## model + retrieval değerlendirme raporları
	python scripts/run_eval.py --out reports/
	python scripts/run_rag_eval.py --out reports/

index:      ## bilgi tabanını yeniden indeksle
	python scripts/build_index.py

lint:       ## ruff + mypy + import-linter
	ruff check .
	ruff format --check .
	mypy src/
	lint-imports

fmt:        ## otomatik biçimlendirme
	ruff check --fix .
	ruff format .

up:         ## docker compose ile tüm servisleri ayağa kaldır
	docker compose -f docker/docker-compose.yml up --build

down:       ## docker compose servislerini durdur
	docker compose -f docker/docker-compose.yml down
