_default:
    @just --list

# Indent Django template files with djhtml
djhtml:
    uv run djhtml -t 2 src

# Build docs
build-docs:
    uv run sphinx-build -b html -d doc/_build/doctrees doc/ doc/_build/html

# Run a web server to view docs
serve-docs:
    uv run -m http.server -d doc/_build/html 8020

# Build Docker image for development
build-docker-for-development docker-file='Dockerfile':
    docker buildx build --progress=plain -f {{docker-file}} --platform=linux/amd64 \
      --build-arg UID=`id -u` --build-arg GID=`id -g` \
      -t eventyay/eventyay-talk:local .
