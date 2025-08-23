
local:
	docker buildx build --progress=plain -f Dockerfile --platform=linux/amd64  \
		--build-arg UID=`id -u` --build-arg GID=`id -g`  \
		-t eventyay/eventyay-ticket:local .

prod:
	docker buildx build --progress=plain -f app/Dockerfile.prod --platform=linux/amd64 -t eventyay/eventyay-next:local app
