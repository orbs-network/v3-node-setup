-include .makerc
export

install_local_mac:
	@POETRY_VIRTUALENVS_IN_PROJECT=false POETRY_VIRTUALENVS_PATH=./.venvmac poetry install

use_local_mac:
	@source .venvmac/bin/activate

install:
	poetry install

shell:
	poetry shell

typecheck: 
	poetry run mypy src --config-file=setup.cfg --namespace-packages --explicit-package-bases

format:
	poetry run black --config=pyproject.toml src
	poetry run isort -sp=setup.cfg src

lint:
	poetry run pylint --rcfile ./.pylintrc src
	poetry run flake8 --config=setup.cfg src

test:
	poetry run pytest -s