@cd %~dp0
@echo ==================== Preparing =======================
@pipenv install --skip-lock
@pipenv run pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
@pipenv run pip install pyinstaller
@pipenv run pip install -r requirements.txt
@echo ================== Generating: DIR ===================
@pipenv run pyinstaller -w --noconfirm -i "./favicon.ico" --onedir "./bilitools.py"
@echo ================== Generating: FILE ===================
@pipenv run pyinstaller -w --noconfirm -i "./favicon.ico" --onefile "./bilitools.py"
@echo ======================== DONE ========================
@pause