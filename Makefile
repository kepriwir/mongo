PY?=python3
PIP?=pip3

.PHONY: deps web run-web configure-cluster init-replica admin enable-auth all dummy load-test compile

deps:
	$(PIP) install -r requirements.txt

web:
	$(PY) web/app.py

configure-cluster:
	$(PY) scripts/cluster_manager.py install --accounts ./accounts.json
	$(PY) scripts/cluster_manager.py configure --accounts ./accounts.json

init-replica:
	$(PY) scripts/cluster_manager.py init-replica --accounts ./accounts.json

admin:
	$(PY) scripts/cluster_manager.py create-admin --accounts ./accounts.json

enable-auth:
	$(PY) scripts/cluster_manager.py enable-auth --accounts ./accounts.json

dummy:
	$(PY) tools/generate_dummy_data.py --accounts ./accounts.json --companies 200 --employees-per-company 3000

load-test:
	$(PY) tools/load_test.py --accounts ./accounts.json --duration 120 --concurrency 100

all: deps configure-cluster init-replica admin enable-auth

compile:
	$(PY) -m compileall .

