registry:
	@mkdir -p registry-data
	@docker rm -f local-registry 2>/dev/null || true
	docker run -d -p 6000:5000 -v $$(realpath registry-data):/var/lib/registry --name local-registry registry:2

build_docker_dev:
	@docker buildx build --platform linux/arm64 -t test-ubuntu_arm64 .

run_docker_dev:
	@if [ -n "$(vol)" ]; then \
		docker run --privileged -v $$(pwd):/home/ubuntu/orbs-node-on-host -v $(vol):/home/ubuntu/orbs-node-remote-repo-simulate -p 80:80 --rm -it test-ubuntu_arm64; \
	else \
		docker run --privileged -v $$(pwd):/home/ubuntu/orbs-node-on-host -p 80:80 --rm -it test-ubuntu_arm64; \
	fi
	#@docker run --privileged -v $$(pwd):/home/ubuntu/orbs-node-on-host -p 80:80 --rm -it test-ubuntu_arm64
	#@docker run --privileged -v $$(pwd):/opt/orbs-node -v $$(pwd)/manager/.venvdocker:/home/ubuntu/manager/.venv -v $$(pwd)/deployment:/home/ubuntu/deployment -v $$(pwd)/logging:/home/ubuntu/logging -v $$(pwd)/manager:/home/ubuntu/manager -v $$(pwd)/setup:/home/ubuntu/setup -p 80:80 --rm -it test-ubuntu_arm64
	#@docker run --privileged -v $$(pwd):/opt/orbs-node-on-host -v $$(pwd)/manager/.venvdocker:/home/ubuntu/manager/.venv -v $$(pwd)/deployment:/home/ubuntu/deployment -v $$(pwd)/logging:/home/ubuntu/logging -v $$(pwd)/manager:/home/ubuntu/manager -v $$(pwd)/setup:/home/ubuntu/setup -p 80:80 --rm -it test-ubuntu_arm64

run_docker_dev2:
	@docker run --privileged -v $$(pwd)/manager/.venvdocker:/home/ubuntu/manager/.venv -v $$(pwd)/deployment:/home/ubuntu/deployment -v $$(pwd)/logging:/home/ubuntu/logging -v $$(pwd)/manager:/home/ubuntu/manager -v $$(pwd)/setup:/home/ubuntu/setup -p 81:80 --rm -it test-ubuntu_arm64