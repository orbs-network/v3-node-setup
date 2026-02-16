.PHONY: setup up down pull reload control control-poll control-install-cron fix-cron deps

deps:
	./scripts/install-dependencies.sh

setup:
	./scripts/run.sh

up:
	docker compose -f docker-compose.yml up -d

down:
	docker compose -f docker-compose.yml down

pull:
	docker compose -f docker-compose.yml pull

reload: pull
	docker compose -f docker-compose.yml up -d --force-recreate

control:
	./scripts/run-control.sh

control-poll:
	./scripts/run-control.sh poll

control-install-cron: fix-cron

fix-cron:
	./scripts/install-control-cron.sh
