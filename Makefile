.PHONY: run api ai up up-qcad tidy test test-go test-py test-ablation gan-refine

tidy:
	go mod tidy

api:
	go run ./cmd/api

ai:
	cd services/ai && AI_STUB=1 uvicorn app.main:app --reload --port 8000

up:
	docker compose -f deploy/docker-compose.yml up --build

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
