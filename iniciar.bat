@echo off
chcp 65001 > nul 2>&1
title EPI Detect

:menu
cls
color 0A
echo.
echo  +--------------------------------------------------+
echo  ^|                   EPI DETECT                      ^|
echo  ^|   Deteccao de Colete de Seguranca em Tempo Real  ^|
echo  +--------------------------------------------------+
echo.
echo    [1]  Video DEMO  (abre no navegador)
echo    [2]  Webcam ao vivo  (abre no navegador)
echo    [3]  Gravar resultado  (demo - resultado.mp4)
echo    [Q]  Sair
echo.
echo  --------------------------------------------------
echo.
set /p opcao=  Escolha:

if /i "%opcao%"=="1" goto demo
if /i "%opcao%"=="2" goto webcam
if /i "%opcao%"=="3" goto gravar
if /i "%opcao%"=="q" exit
echo  Opcao invalida.
timeout /t 2 > nul
goto menu

:matar_servidor
echo  Encerrando instancia anterior (se houver)...
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":5000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F > nul 2>&1
)
taskkill /IM python.exe /F > nul 2>&1
timeout /t 1 > nul
goto :eof

:demo
cls
echo.
echo  Iniciando servidor WEB - modo DEMO...
echo  Acesse: http://localhost:5000
echo  Pressione CTRL+C para encerrar.
echo.
call :matar_servidor
cd /d "%~dp0"
python server.py --source demo
goto volta

:webcam
cls
echo.
echo  Iniciando servidor WEB - modo WEBCAM...
echo  Acesse: http://localhost:5000
echo  Pressione CTRL+C para encerrar.
echo.
call :matar_servidor
cd /d "%~dp0"
python server.py --source webcam
goto volta

:gravar
cls
echo.
echo  Gravando DEMO em resultado.mp4... (Q para parar e salvar)
echo.
call :matar_servidor
cd /d "%~dp0"
python detect.py --source demo --save resultado.mp4
echo.
echo  Video salvo: resultado.mp4
goto volta

:volta
echo.
echo  Pressione qualquer tecla para voltar ao menu.
pause > nul
goto menu
