@ECHO OFF
setlocal

pushd %~dp0

REM Command file for Sphinx documentation

if "%SPHINXBUILD%" == "" (
	set SPHINXBUILD=sphinx-build
)
set SOURCEDIR=source
set BUILDDIR=build

%SPHINXBUILD% >NUL 2>NUL
if errorlevel 9009 (
	echo.
	echo.The 'sphinx-build' command was not found. Make sure you have Sphinx
	echo.installed, then set the SPHINXBUILD environment variable to point
	echo.to the full path of the 'sphinx-build' executable. Alternatively you
	echo.may add the Sphinx directory to PATH.
	echo.
	echo.If you don't have Sphinx installed, grab it from
	echo.https://www.sphinx-doc.org/
	exit /b 1
)

if /I "%2"=="--nocolor" (
     set NO_COLOR=1
     echo ==Disabled color==
 )

if "%1" == "" goto help

REM Special target for regenerating API docs with custom templates
if "%1" == "apidoc" goto apidoc

%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
goto end

:apidoc
echo Regenerating API documentation with custom templates...
sphinx-apidoc -o %SOURCEDIR%\api ..\src\all2md --templatedir=%SOURCEDIR%\_templates\apidoc --force --module-first --separate --maxdepth 4
if errorlevel 1 (
    echo.
    echo Error: sphinx-apidoc failed
    exit /b 1
)
echo.
echo Fixing .rst.rst filename conflicts...
..\\.venv\\Scripts\\python.exe ..\\scripts\\fix_rst_filenames.py
if errorlevel 1 (
    echo.
    echo Error: Failed to fix .rst.rst filenames
    exit /b 1
)
echo.
echo Removing auto-generated modules.rst (replaced by hand-crafted index.rst)...
if exist %SOURCEDIR%\api\modules.rst del %SOURCEDIR%\api\modules.rst
echo.
echo API documentation regenerated successfully!
echo The :imported-members: False directive was automatically added to package files.
echo Note: Hand-crafted section files (index.rst, core.rst, etc.) are preserved.
goto end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS% %O%
echo.
echo Custom targets:
echo   apidoc     Regenerate API documentation using custom templates

:end
endlocal
popd
