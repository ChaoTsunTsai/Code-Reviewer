@echo off

:: 激活指定的 Conda 環境
call conda activate Sept_plan

:: 使用 Streamlit 運行同目錄下的 Sept.py
streamlit run "%~dp0Sept.py"

:: 停止腳本執行後不立即關閉窗口
pause