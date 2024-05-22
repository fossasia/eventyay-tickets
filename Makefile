
build:
	docker buildx build --progress=plain -f Dockerfile --platform=linux/amd64  \
		-t eventyay-tickets:latest .
