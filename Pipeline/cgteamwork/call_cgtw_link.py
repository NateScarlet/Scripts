# -*- coding=UTF-8 -*-
import os
import sys
import time
import tempfile
from subprocess import call, Popen, PIPE, STDOUT

CGTW_PATH = r"C:\cgteamwork\bin\base"
sys.path.append(CGTW_PATH)
import cgtw

VERSION = 0.1

def main():
    _tw = cgtw.tw()
    _sys = _tw.sys()
    _folder = _sys.get_sys_folder()
    _files = _sys.get_sys_file() or os.listdir(_folder)
    _database = _sys.get_sys_database()
    _maya = _tw.software(_database).get_software_path("maya")

    os.chdir(_folder)

    for _file in _files:
        if os.path.splitext(_file)[1] not in ['.ma', '.mb']:
            continue

        _log = tempfile.NamedTemporaryFile(delete=False).name
        _proc = Popen(u'"{maya}" -batch -file "{file}" -command "python \\"import wlf.cgteamwork;wlf.cgteamwork.CGTeamWork().call_script()\\"" -log {log}'.format(maya=_maya, file=_file, log=_log))
        _proc.wait()
        with open(_log) as f:
            print(f.read())
        os.remove(_log)

    pause()
    
def pause():
    # call('PAUSE', shell=True)
    print('')
    for i in range(5)[::-1]:
        sys.stdout.write('\r{:2d}'.format(i+1))
        time.sleep(1)
    sys.stdout.write('\r          ')
    print('')


if __name__=="__main__":
    try:
        main()
    except:
        import traceback
        traceback.print_exc()
        pause()