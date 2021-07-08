import os,sys

os.system('ver')
os.system('title C:\\Windows\\system32\\cmd.exe')
while True:
    print('')
    workDir = os.getcwd()
    command = input(workDir+'>').strip()
    if command.lower() == 'cd':
        print(workDir)
        continue
    if command.lower().startswith('cd'):
        try:
            os.chdir(command.split(' ')[1])
        except:
            print('系统找不到指定的路径。')
        finally:
            continue
    if command.lower() == 'exit':
        sys.exit(0)
    os.system(command)
