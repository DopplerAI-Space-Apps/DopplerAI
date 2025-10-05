@echo off
curl -L -o "%~dp0koi.csv" "https://exoplanetarchive.ipac.caltech.edu/cgi-bin/nstedAPI/nph-nstedAPI?table=koi&format=csv"
echo Listo, archivo koi.csv descargado en %~dp0
pause
