@cd %~dp0
@pipenv install --skip-lock
@pipenv run pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
@pipenv run pip install pyinstaller
@pipenv run pip install -r requirements.txt
@pipenv run pyinstaller -w --noconfirm -i "./favicon.ico" -D "./bilitools.py"
@pause