
local:
	docker buildx build --progress=plain -f Dockerfile --platform=linux/amd64  \
		-t eventyay/eventyay-ticket:local .
