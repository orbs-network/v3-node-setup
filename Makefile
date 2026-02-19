.PHONY: setup up down pull reload control control-poll control-install-cron fix-cron deps aws-l3-launch aws-l3-terminate

AWS_REGION := us-east-2
AWS_L3_INSTANCE_IDS := .tmp/l3-instance-ids

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

aws-l3-launch:
	mkdir -p .tmp
	@id=$$(aws ec2 run-instances --launch-template LaunchTemplateName=l3-node-clean-instance-before-install --count 1 --region $(AWS_REGION) --query 'Instances[0].InstanceId' --output text); \
	echo $$id >> $(AWS_L3_INSTANCE_IDS); \
	echo "Launched instance $$id (appended to $(AWS_L3_INSTANCE_IDS))"; \
	echo "Waiting for instance to be running..."; \
	aws ec2 wait instance-running --instance-ids $$id --region $(AWS_REGION); \
	ip=$$(aws ec2 describe-instances --instance-ids $$id --region $(AWS_REGION) --query 'Reservations[0].Instances[0].PublicIpAddress' --output text); \
	echo "Public IP: $$ip"

aws-l3-terminate:
	@if [ -f $(AWS_L3_INSTANCE_IDS) ] && [ -s $(AWS_L3_INSTANCE_IDS) ]; then \
		ids=$$(cat $(AWS_L3_INSTANCE_IDS) | tr '\n' ' '); \
		aws ec2 terminate-instances --instance-ids $$ids --region $(AWS_REGION) --no-cli-pager; \
		: > $(AWS_L3_INSTANCE_IDS); \
		echo "Terminated instances and cleared $(AWS_L3_INSTANCE_IDS)"; \
	else \
		echo "No instances in $(AWS_L3_INSTANCE_IDS)"; \
	fi
