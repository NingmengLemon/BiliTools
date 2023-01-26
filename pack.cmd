@cd %~dp0
@pipenv install
@pipenv run pip install pyinstaller
@pipenv run pip install -r requirements.txt
@pipenv run pyinstaller -w -i "./favicon.ico" -D "./bilitools.py"
@pause