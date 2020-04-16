# stay seated!

## Run development build

Start PostgreSQL, Redis, Server, and Client:

    docker-compose up --build
    
Then, visit the client:

http://localhost:8880/#token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL3ByZXRpeC5ldS8iLCJhdWQiOiJkZW1vLWV2ZW50IiwiZXhwIjoxNjcyODQ1NTI2LCJpYXQiOjE1ODY1MzE5MjYsInVpZCI6InNvbWUtdXNlci1pZCIsInRyYWl0cyI6WyJzcGVha2VyIiwiYWRkb24tMiJdfQ.d5ZrdZbRkpu9yuqK9fNRdu4VXnpkFU6rR8y0DjVToJM

To run server tests, execute:

    docker-compose exec server pytest
