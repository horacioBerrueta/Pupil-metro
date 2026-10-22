@echo off
chcp 65001 > nul
echo ========================================================
echo        INSTALADOR AUTOMÁTICO DE PUPILÓMETRO
echo ========================================================
echo.

set INSTALL_DIR=%LOCALAPPDATA%\Pupilometro
echo Instalando en: %INSTALL_DIR%...

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo Copiando el ejecutable del programa...
if not exist "%~dp0dist\Pupilometro.exe" (
    echo No se encontro "%~dp0dist\Pupilometro.exe".
    echo Genere primero el ejecutable con Pupilometro.spec.
    pause
    exit /b 1
)
copy /Y "%~dp0dist\Pupilometro.exe" "%INSTALL_DIR%\Pupilometro.exe" > nul

echo Creando acceso directo en el Escritorio...
powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Pupilómetro.lnk')); $s.TargetPath='%INSTALL_DIR%\Pupilometro.exe'; $s.WorkingDirectory='%INSTALL_DIR%'; $s.Save()"

echo.
echo ¡Instalación completada con éxito!
echo Se ha creado un acceso directo en tu Escritorio llamado "Pupilómetro".
echo.
pause
