@echo off
rem 种子数据导入（提示词五件套）
call conda activate catong_gen
cd /d %~dp0..\backend
python -m app.seeds.seed
pause
