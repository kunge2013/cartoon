@echo off
rem catong_gen 后端开发启动（conda env = 项目名）
call conda activate catong_gen
cd /d %~dp0..\backend
uvicorn app.main:app --reload --port 8300
