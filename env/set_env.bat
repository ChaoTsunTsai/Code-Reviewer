@echo off
REM 設定 Anaconda 的 activate.bat 路徑（請確認路徑正確）
SET "ANACONDA_PROMPT=%USERPROFILE%\anaconda3\Scripts\activate.bat"

REM 確認 Anaconda Prompt 是否存在
IF NOT EXIST "%ANACONDA_PROMPT%" (
    echo 無法找到 Anaconda Prompt，請確認 Anaconda 是否已安裝並路徑正確。
    pause
    exit /b
)

REM 打開 Anaconda Prompt 並執行指令
start "" "%COMSPEC%" /k "%ANACONDA_PROMPT% & conda env create -f Sept.yml & echo 環境創建完成 & pause"