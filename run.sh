#!/bin/bash

if [[ -z "$(docker images -q handout-generator 2> /dev/null)" ]]; then
    echo "Образ не найден. Собираем..."
    docker build -t handout-generator .
fi

echo "Введите API ключ GigaChat:"
read GIGACHAT_API_KEY

SECRET_KEY=$(openssl rand -hex 32)

docker run -p 8000:8000 \
  -e SECRET_KEY="$SECRET_KEY" \
  -e GIGACHAT_API_KEY="$GIGACHAT_API_KEY" \
  -e DATABASE_URL="sqlite+aiosqlite:///./handouts.db" \
  handout-generator
