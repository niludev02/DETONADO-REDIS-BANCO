@echo off
setlocal
title Detonados - Django + Redis

cd /d "%~dp0"

echo ==========================================
echo       DETONADOS - INICIALIZACAO
echo ==========================================
echo.

REM Confere se o projeto Django existe nesta pasta.
if not exist "manage.py" (
    echo ERRO: manage.py nao foi encontrado.
    echo Salve este arquivo iniciar.bat na pasta raiz do projeto,
    echo onde tambem fica o arquivo manage.py.
    echo.
    pause
    exit /b 1
)

REM Confere se o ambiente virtual existe.
if not exist ".venv\Scripts\activate.bat" (
    echo ERRO: ambiente virtual .venv nao encontrado.
    echo Crie-o com: py -m venv .venv
    echo.
    pause
    exit /b 1
)

REM Confere se o Docker esta instalado e em execucao.
where docker >nul 2>&1
if errorlevel 1 (
    echo ERRO: Docker nao encontrado. Instale o Docker Desktop.
    echo.
    pause
    exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
    echo ERRO: o Docker Desktop nao esta em execucao.
    echo Abra o Docker Desktop, espere iniciar e execute este arquivo novamente.
    echo.
    pause
    exit /b 1
)

REM Inicia o container Redis existente ou cria um novo.
docker container inspect crud-redis-db >nul 2>&1
if errorlevel 1 (
    echo Criando o container Redis...
    docker run -d --name crud-redis-db -p 6379:6379 -v crud_redis_data:/data redis:8 redis-server --appendonly yes
    if errorlevel 1 (
        echo ERRO: nao foi possivel criar o container Redis.
        echo Verifique se a porta 6379 ja esta sendo usada.
        echo.
        pause
        exit /b 1
    )
) else (
    echo Iniciando o container Redis existente...
    docker start crud-redis-db >nul
    if errorlevel 1 (
        echo ERRO: nao foi possivel iniciar o container Redis.
        echo.
        pause
        exit /b 1
    )
)

REM Confere a resposta do Redis.
docker exec crud-redis-db redis-cli ping
if errorlevel 1 (
    echo ERRO: o Redis nao respondeu ao teste.
    echo.
    pause
    exit /b 1
)

echo.
echo Ativando o ambiente virtual...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERRO: nao foi possivel ativar o ambiente virtual.
    echo.
    pause
    exit /b 1
)

echo.
echo Iniciando o servidor Django...
echo Acesse: http://127.0.0.1:8000/
echo Para encerrar, pressione Ctrl+C nesta janela.
echo.

python manage.py runserver

echo.
echo O servidor Django foi encerrado.
pause
endlocal
