registry:
	@docker run -d -p 6000:5000 --name local-registry registry:2

build_docker_dev:
	@docker buildx build --platform linux/arm64 -t test-ubuntu_arm64 .

run_docker_dev:
	@docker run --privileged -v $$(pwd)/manager/.venvdocker:/home/ubuntu/manager/.venv -v $$(pwd)/deployment:/home/ubuntu/deployment -v $$(pwd)/logging:/home/ubuntu/logging -v $$(pwd)/manager:/home/ubuntu/manager -v $$(pwd)/setup:/home/ubuntu/setup -p 80:80 --rm -it test-ubuntu_arm64

run_docker_dev2:
	@docker run --privileged -v $$(pwd)/manager/.venvdocker:/home/ubuntu/manager/.venv -v $$(pwd)/deployment:/home/ubuntu/deployment -v $$(pwd)/logging:/home/ubuntu/logging -v $$(pwd)/manager:/home/ubuntu/manager -v $$(pwd)/setup:/home/ubuntu/setup -p 81:80 --rm -it test-ubuntu_arm64