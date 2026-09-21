git config --local user.name "Данил Уметбаев"
git config --local user.email "dodanil2810@gmail.com"

git remote add gitlab git@gitlab.com:dodanilgroup/ehala.git


docker network create my_network

docker run --name example_db `
    -p 6432:5432 `
    -e POSTGRES_USER=dodanil `
    -e POSTGRES_PASSWORD=dodanil `
    -e POSTGRES_DB=example `
    --network=my_network `
    --volume pg_booking_data:/var/lib/postgresql/data `
    -d postgres:16


docker run --name booking_back `
    -p 7777:8000 `
    --network=my_network `
    mybooking:latest


docker run --name booking_nginx `
    -v ./nginx.conf:/etc/nginx/nginx.conf `
    --network=my_network `
    --rm -p 80:80 nginx