@echo off
setlocal enabledelayedexpansion

echo [1/4] Criando o ambiente virtual (.venv)...
python -m venv .venv
if %errorlevel% neq 0 (
    echo Erro ao criar o ambiente virtual. Certifique-se de que o Python esta instalado e no PATH.
    pause
    exit /b %errorlevel%
)

echo [2/4] Ativando o ambiente virtual...
call .venv\Scripts\activate
if %errorlevel% neq 0 (
    echo Erro ao ativar o ambiente virtual.
    pause
    exit /b %errorlevel%
)

echo [3/4] Instalando as dependencias do requirements.txt...
if exist requirements.txt (
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else if exist .requirements.txt (
    python -m pip install --upgrade pip
    pip install -r .requirements.txt
) else (
    echo Aviso: Arquivo de requisitos nao encontrado. Pulando instalacao.
)

echo [4/4] Concluido! O script ira se autoexcluir agora.
timeout /t 3 >nul

:: Comando magico para o script se deletar sozinho após fechar
(goto) 2>nul & del "%~f0"