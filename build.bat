@echo off
chcp 65001 >nul
echo ===================================
echo  単位趣味レーター ビルドスクリプト
echo ===================================
echo.

REM PyInstallerがインストールされているか確認
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstallerをインストール中...
    pip install pyinstaller
)

echo.
echo ビルドを開始します...
echo.

pyinstaller --onefile --windowed --name "単位趣味レーター" --clean main.py

echo.
if exist "dist\単位趣味レーター.exe" (
    echo ✅ ビルド成功！
    echo    出力先: dist\単位趣味レーター.exe
) else (
    echo ❌ ビルドに失敗しました。
)

echo.
pause
