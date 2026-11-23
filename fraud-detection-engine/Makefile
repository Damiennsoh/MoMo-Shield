.PHONY: data mock-data features train evaluate serve train-text

data:
	python scripts/fetch_and_profile.py --simulate

mock-data:
	python scripts/mock_sandbox.py --people 4000 --tx 78018 --cases 8720 --seed 7 --total-transactions 100023 --fraud-fraction 0.22 --out data/mock_full

features: mock-data
	python scripts/run_pipeline.py features --data-dir data/mock_full

train: mock-data
	python scripts/run_pipeline.py experiment --data-dir data/mock_full

evaluate:
	python scripts/run_pipeline.py evaluate

serve:
	python -m uvicorn plugin_api:app --app-dir serving --host 127.0.0.1 --port 8000

train-text:
	python scripts/train_text_transformer.py --input data/raw/text_labels.csv

