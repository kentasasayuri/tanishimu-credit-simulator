@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".codex_tmp" mkdir ".codex_tmp"

py -3.12 -c "import gradio" >nul 2>&1
if errorlevel 1 (
  echo Python 3.12 の Gradio 環境が見つかりません。
  echo 先に py -3.12 -m pip install -r requirements-web.txt を実行してください。
  exit /b 1
)

py -3.12 web_app.py --host 127.0.0.1 --port 7860 1>".codex_tmp\web_7860.log" 2>&1
