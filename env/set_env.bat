@echo off
REM 激活 conda 的 base 環境，確保可以使用 conda 命令
CALL conda init

REM 創建環境，並指定 Sept.yml 文件
conda env create -f Sept.yml

REM 顯示完成訊息
echo 環境創建完成
pause