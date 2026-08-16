@echo off
rem ============================================================
rem  catong_gen 一键端到端测试脚本
rem  行为：启动后端（后台）→ 等就绪 → 跑 pytest → 关闭后端 → 汇总
rem  适用：Phase 0~8 自动化回归；CI 冒烟门禁
rem ============================================================

setlocal enabledelayedexpansion

rem ---- 1) 路径与 conda 环境 ---------------------------------
set "PROJECT_ROOT=%~dp0.."
set "CONDA_ENV=catong_gen"
set "PORT=8300"
set "LOG_FILE=%PROJECT_ROOT%\logs\dev_server.log"

rem 进入项目根
cd /d "%PROJECT_ROOT%"

echo.
echo ============================================================
echo   catong_gen 端到端测试
echo   时间：%date% %time%
echo   后端端口：%PORT%
echo   日志文件：%LOG_FILE%
echo ============================================================
echo.

if not exist logs mkdir logs

rem ---- 2) 启动后端（后台） -----------------------------------
echo [1/4] 启动后端服务（后台）...
start "catong_gen_server" /B cmd /c ^
  "call conda activate %CONDA_ENV% && uvicorn app.main:app --port %PORT% > "%LOG_FILE%" 2>&1"

rem ---- 3) 等待 /api/health 就绪（最多 60 秒） ------------------
echo [2/4] 等待 /api/health 就绪 ...
set /a TRIED=0
:WAIT_LOOP
set /a TRIED+=1
if %TRIED% GTR 60 (
    echo [X] 后端启动超时（60s）。日志尾部：
    type "%LOG_FILE%"
    goto CLEANUP_FAIL
)
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 'http://127.0.0.1:%PORT%/api/health').StatusCode } catch { 0 }" > "%TEMP%\health.txt" 2>nul
set /p HEALTH=<"%TEMP%\health.txt"
del "%TEMP%\health.txt" 2>nul
if "%HEALTH%"=="200" (
    echo    [√] 后端已就绪（%TRIED%s）
    goto RUN_TESTS
)
>nul timeout /t 1 /nobreak
goto WAIT_LOOP

rem ---- 4) 跑测试 ----------------------------------------------
:RUN_TESTS
echo.
echo [3/4] 运行 pytest（端到端）...
call conda activate %CONDA_ENV% >nul 2>&1
cd /d "%PROJECT_ROOT%\backend"

pytest -v tests/ > "%PROJECT_ROOT%\logs\e2e_result.txt" 2>&1
set TEST_EXIT=%ERRORLEVEL%

echo.
echo [4/4] 测试完成（exit=%TEST_EXIT%）
echo ------------------------------------------------------------
echo   失败摘要：
findstr /C:"FAILED" "%PROJECT_ROOT%\logs\e2e_result.txt" 2>nul
echo   完整结果：%PROJECT_ROOT%\logs\e2e_result.txt
echo ------------------------------------------------------------

rem ---- 5) 关后端 ----------------------------------------------
echo.
echo [*] 关闭后端服务...
taskkill /FI "WINDOWTITLE eq catong_gen_server*" /T /F >nul 2>&1
timeout /t 1 /nobreak >nul

if %TEST_EXIT% EQU 0 (
    echo.
    echo ============================================================
    echo   ✓ 全部测试通过
    echo ============================================================
    exit /b 0
) else (
    echo.
    echo ============================================================
    echo   X 部分测试失败（exit=%TEST_EXIT%）
    echo   查看日志：%PROJECT_ROOT%\logs\e2e_result.txt
    echo ============================================================
    exit /b %TEST_EXIT%
)

:CLEANUP_FAIL
echo.
echo ============================================================
echo   X 后端启动失败
echo   日志：%LOG_FILE%
echo ============================================================
taskkill /FI "WINDOWTITLE eq catong_gen_server*" /T /F >nul 2>&1
exit /b 1
