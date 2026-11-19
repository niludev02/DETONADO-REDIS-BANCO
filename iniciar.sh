#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

REDIS_CONTAINER="crud-redis-db"
TAILWIND_PID=""

error() {
    printf 'ERRO: %s\n' "$*" >&2
    exit 1
}

cleanup() {
    if [[ -n "$TAILWIND_PID" ]] && kill -0 "$TAILWIND_PID" 2>/dev/null; then
        kill "$TAILWIND_PID"
        wait "$TAILWIND_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf '%s\n' \
    '==========================================' \
    '       DETONADOS - INICIALIZACAO' \
    '=========================================='

[[ -f manage.py ]] || error "manage.py nao foi encontrado na raiz do projeto."
[[ -f input.css ]] || error "input.css nao foi encontrado na raiz do projeto."
[[ -f package.json ]] || error "package.json nao foi encontrado na raiz do projeto."

for command_name in python3 npm docker; do
    command -v "$command_name" >/dev/null 2>&1 ||
        error "$command_name nao encontrado. Instale-o antes de iniciar o projeto."
done

docker info >/dev/null 2>&1 ||
    error "Docker nao esta em execucao. Inicie o Docker e tente novamente."

if docker container inspect "$REDIS_CONTAINER" >/dev/null 2>&1; then
    printf 'Iniciando o container Redis existente...\n'
    docker start "$REDIS_CONTAINER" >/dev/null
else
    printf 'Criando o container Redis...\n'
    docker run -d \
        --name "$REDIS_CONTAINER" \
        -p 6379:6379 \
        -v crud_redis_data:/data \
        redis:8 redis-server --appendonly yes >/dev/null
fi

printf 'Aguardando o Redis responder...\n'
redis_ready=false
for ((attempt = 1; attempt <= 20; attempt++)); do
    if docker exec "$REDIS_CONTAINER" redis-cli ping 2>/dev/null | grep -q '^PONG$'; then
        redis_ready=true
        break
    fi
    sleep 1
done
[[ "$redis_ready" == true ]] ||
    error "Redis nao respondeu ao teste. Confira o container $REDIS_CONTAINER."
printf 'Redis esta pronto.\n'

if [[ ! -x .venv/bin/python ]]; then
    printf 'Criando o ambiente virtual Python...\n'
    python3 -m venv .venv ||
        error "nao foi possivel criar .venv. Instale o suporte a venv do Python."
fi

printf 'Instalando/verificando dependencias Python...\n'
.venv/bin/python -m pip install -r requirements.txt

if [[ ! -x node_modules/.bin/tailwindcss ]]; then
    printf 'Instalando dependencias do Tailwind...\n'
    npm ci
fi

mkdir -p static/css

printf 'Aplicando migracoes do banco local...\n'
.venv/bin/python manage.py migrate --noinput

printf 'Iniciando a compilacao automatica do Tailwind...\n'
./node_modules/.bin/tailwindcss \
    -i input.css \
    -o static/css/output.css \
    --watch &
TAILWIND_PID=$!

printf '\n'
printf 'Iniciando o servidor Django...\n'
printf 'Acesse: http://127.0.0.1:8000/\n'
printf 'Para encerrar o Django e o Tailwind, pressione Ctrl+C.\n\n'
.venv/bin/python manage.py runserver 0.0.0.0:8000
