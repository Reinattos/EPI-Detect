@echo off
chcp 65001 > nul 2>&1
title EPI Detect
setlocal enabledelayedexpansion

rem ---------------------------------------------------------------------------
rem Porta de entrada para quem nao trabalha com linha de comando.
rem
rem O publico desta ferramenta nao e so quem programa: tecnico de seguranca
rem do trabalho, encarregado de operacao e gestor de frota precisam avaliar
rem o resultado, nao montar ambiente Python. Exigir terminal excluiria
rem justamente quem mais se beneficia da ferramenta.
rem
rem Isto complementa a documentacao de linha de comando do README, que segue
rem sendo o caminho principal para integrar ou modificar o projeto.
rem ---------------------------------------------------------------------------

cd /d "%~dp0"

:verificar_python
python --version > nul 2>&1
if errorlevel 1 (
    color 0C
    echo.
    echo   Python nao encontrado.
    echo.
    echo   Instale o Python 3.10 ou mais novo em https://python.org/downloads
    echo   Durante a instalacao, marque a opcao "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:verificar_ambiente
if not exist ".venv\Scripts\python.exe" (
    color 0E
    echo.
    echo   Primeira execucao: preparando o ambiente.
    echo   Isso leva alguns minutos e acontece so uma vez.
    echo.
    python -m venv .venv
    if errorlevel 1 (
        echo   Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat
    echo   Instalando dependencias...
    python -m pip install --upgrade pip --quiet
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        color 0C
        echo.
        echo   Falha ao instalar as dependencias.
        echo   Verifique sua conexao com a internet.
        pause
        exit /b 1
    )
    echo.
    echo   Ambiente pronto.
    timeout /t 2 > nul
) else (
    call .venv\Scripts\activate.bat
)

:menu
cls
color 0A
echo.
echo   ===============================================
echo                    EPI DETECT
echo      Deteccao de colete refletivo e capacete
echo   ===============================================
echo.
echo    1  Webcam ao vivo
echo    2  Interface web no navegador
echo    3  Abrir um arquivo de video
echo    4  Camera IP (RTSP)
echo    5  Gerar video anotado a partir de um arquivo
echo.
echo    6  Rodar os testes
echo    0  Sair
echo.
set "opcao="
set /p "opcao=  Escolha uma opcao: "

if "%opcao%"=="1" goto webcam
if "%opcao%"=="2" goto web
if "%opcao%"=="3" goto arquivo
if "%opcao%"=="4" goto rtsp
if "%opcao%"=="5" goto render
if "%opcao%"=="6" goto testes
if "%opcao%"=="0" exit /b 0
goto menu

:webcam
cls
echo.
echo   Abrindo a webcam. Pressione Q na janela do video para sair.
echo   A primeira execucao baixa o modelo e pode demorar alguns minutos.
echo.
python detect.py
pause
goto menu

:web
cls
echo.
echo   Servidor iniciando em http://localhost:5000
echo   Abra esse endereco no navegador.
echo   Pressione Ctrl+C nesta janela para encerrar.
echo.
start "" http://localhost:5000
python server.py
pause
goto menu

:arquivo
cls
echo.
set "caminho="
set /p "caminho=  Arraste o arquivo de video aqui e pressione Enter: "
if "%caminho%"=="" goto menu
echo.
python detect.py --source %caminho%
pause
goto menu

:rtsp
cls
echo.
echo   Exemplo: rtsp://usuario:senha@192.168.0.50:554/stream1
echo.
set "url="
set /p "url=  Cole a URL da camera: "
if "%url%"=="" goto menu
echo.
python detect.py --source "%url%"
pause
goto menu

:render
cls
echo.
set "entrada="
set /p "entrada=  Arraste o arquivo de video aqui e pressione Enter: "
if "%entrada%"=="" goto menu
echo.
echo   Processando. O resultado sai na mesma pasta do video original.
echo.
python render.py %entrada%
pause
goto menu

:testes
cls
echo.
python -m pip install -r requirements-dev.txt --quiet
python -m pytest -q
echo.
pause
goto menu
