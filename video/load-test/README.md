# Load Testing

## Install
Download and install k6

## Setup Server

```sh
load-test/limits.sh # bump socket limit
ulimit -n 4000000
docker-compose up --build server redis db celery
docker-compose exec server python manage.py import_config sample/worlds/load-test.json
```
(or see docs/admin/management.rst for detailed instructions)

## Setup Client

```sh
load-test/limits.sh # bump socket limit
ulimit -n 4000000
```

## Run

### Server

```sh
docker-compose up redis db celery
docker-compose run -p 8375:8375 --entrypoint "gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8375 --max-requests 1200 --max-requests-jitter 200 -w 32 venueless.asgi:application" server
```

### Load test

```sh
WS_URL=ws://localhost:8375/ws/world/load-test/ k6 run load-test/flood.js
```

### Additional notes

* For production systems with multiple DNS entries, use `--dns ttl=1m,select=roundRobin`