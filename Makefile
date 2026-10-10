.PHONY: run api ai up up-prod up-qcad tidy test test-go test-py test-ablation gan-refine css

css:
	npx --yes tailwindcss@3.4.17 -i web/static/css/tailwind.src.css -o web/static/css/tailwind.css --minify

tidy:
	go mod tidy

api:
	go run ./cmd/api

ai:
	cd services/ai && AI_STUB=1 uvicorn app.main:app --reload --port 8000

up:
	docker compose -f deploy/docker-compose.yml up --build

# Preview AWS (nécessite deploy/.env généré, voir docs/deploy-aws.md).
up-prod:
	docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env up --build -d

# QCAD est dans le compose par défaut (même commande que `up`).
up-qcad:
	docker compose -f deploy/docker-compose.yml up --build qcad api

test: test-go test-py

test-go:
	go test ./...

test-py:
	python -m pytest services/ai/tests research/metrics services/blender/tests services/qcad research/dataset/test_resplan_convert.py research/dataset/test_refine_pairs.py -q

gan-refine:
	python research/dataset/make_refine_pairs.py --count 512
	python research/train_gan_refine.py --epochs 20

test-ablation:
	python research/benchmarks/run_ablation.py
