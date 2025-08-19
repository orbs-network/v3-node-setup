-include .makerc
export

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