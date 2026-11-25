@echo off
setlocal
cd /d "%~dp0"
set "TASK=createDistributable"
set "RUN_ARGS="
set "PORTABLE=1"
if /I "%~1"=="folder" set "PORTABLE=0"
if /I "%~1"=="installer" set "TASK=packageExe"
if /I "%~1"=="test" (
    set "TASK=run"
    set "RUN_ARGS=--args=--self-test"
)
if /I "%~1"=="run" set "TASK=run"
if not "%~1"=="" if /I not "%~1"=="installer" if /I not "%~1"=="test" if /I not "%~1"=="run" if /I not "%~1"=="folder" (
    echo Usage: build.bat [folder^|installer^|test^|run]
    exit /b 2
)
set "GRADLE_COMMAND=%~dp0gradlew.bat"
if defined GRADLE_HOME if exist "%GRADLE_HOME%\bin\gradle.bat" set "GRADLE_COMMAND=%GRADLE_HOME%\bin\gradle.bat"
echo Building ZI-Ops with Java 21 and Gradle...
call "%GRADLE_COMMAND%" --no-daemon --console=plain "-Pkotlin.compiler.execution.strategy=in-process" %TASK% %RUN_ARGS% %ZI_OPS_GRADLE_ARGS%
if errorlevel 1 (
    echo Build failed. Install JDK 21 and check JAVA_HOME, network access and the output above.
    if not defined CI pause
    exit /b 1
)
if "%TASK%"=="createDistributable" if "%PORTABLE%"=="1" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-portable.ps1"
    if errorlevel 1 (
        echo Portable packaging failed.
        if not defined CI pause
        exit /b 1
    )
)
if "%TASK%"=="createDistributable" if "%PORTABLE%"=="0" echo Application: %~dp0build\compose\binaries\main\app\ZI-Ops\ZI-Ops.exe
if "%TASK%"=="packageExe" echo Installer: %~dp0build\compose\binaries\main\exe
if not defined CI pause
exit /b 0
