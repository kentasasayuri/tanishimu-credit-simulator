@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".codex_tmp" mkdir ".codex_tmp"

if not exist ".codex_tmp\cloudflared.exe" (
  echo cloudflared が見つかりません: .codex_tmp\cloudflared.exe
  exit /b 1
)

py -3.12 -c "import gradio" >nul 2>&1
if errorlevel 1 (
  echo Python 3.12 の Gradio 環境が見つかりません。
  echo 先に py -3.12 -m pip install -r requirements-web.txt を実行してください。
  exit /b 1
)

start "Tanishimu Web" cmd /c "py -3.12 web_app.py --host 127.0.0.1 --port 7861 1>.codex_tmp\web_7861.log 2>&1"
timeout /t 5 >nul

echo Cloudflare Quick Tunnel を開始します...
echo URL が表示されたら、そのリンクを共有してください。
.codex_tmp\cloudflared.exe tunnel --url http://127.0.0.1:7861 --no-autoupdate --logfile .codex_tmp\cloudflared_7861.log
