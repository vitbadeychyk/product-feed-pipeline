@echo off
cd /d "F:\GitHub\product-feed-pipeline"

echo ===== START %date% %time% ===== > run-debug-log.txt
echo Current folder: >> run-debug-log.txt
cd >> run-debug-log.txt

echo ===== PYTHON ===== >> run-debug-log.txt
py --version >> run-debug-log.txt 2>&1

echo ===== FETCH SUPPLIER ===== >> run-debug-log.txt
py -m scripts.common.fetch_supplier_feed >> run-debug-log.txt 2>&1
if errorlevel 1 goto error

echo ===== FILE CHECK ===== >> run-debug-log.txt
dir data\raw >> run-debug-log.txt 2>&1

echo ===== GIT ADD XML ===== >> run-debug-log.txt
git add data/raw/supplier_feed.xml state/fetch_meta.json >> run-debug-log.txt 2>&1

echo ===== GIT COMMIT XML ===== >> run-debug-log.txt
git commit -m "Auto update supplier feed" >> run-debug-log.txt 2>&1

echo ===== GIT PULL REBASE ===== >> run-debug-log.txt
git pull --rebase origin main >> run-debug-log.txt 2>&1
if errorlevel 1 goto error

echo ===== GIT PUSH ===== >> run-debug-log.txt
git push origin main >> run-debug-log.txt 2>&1
if errorlevel 1 goto error

echo ===== END OK %date% %time% ===== >> run-debug-log.txt
exit /b 0

:error
echo ===== ERROR %date% %time% ===== >> run-debug-log.txt
git status >> run-debug-log.txt 2>&1
pause
exit /b 1