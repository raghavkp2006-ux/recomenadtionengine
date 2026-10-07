import os, sqlite3, socket, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0,str(ROOT))
source=sqlite3.connect(f'file:{(ROOT/"local_polytaste.db").as_posix()}?mode=ro',uri=True)
dest=sqlite3.connect(OUT/'test_copy.db')
source.backup(dest)
source.close(); dest.close()
os.environ['DATABASE_URL']='sqlite:///'+(OUT/'test_copy.db').as_posix()
os.environ['ENV']='local'
original_connect=socket.socket.connect
original_connect_ex=socket.socket.connect_ex
def guarded_connect(sock,address):
    if isinstance(address,tuple) and address[0] in {'127.0.0.1','::1','localhost'}:
        return original_connect(sock,address)
    raise OSError('Offline report verification blocks external network connections')
def guarded_connect_ex(sock,address):
    if isinstance(address,tuple) and address[0] in {'127.0.0.1','::1','localhost'}:
        return original_connect_ex(sock,address)
    raise OSError('Offline report verification blocks external network connections')
socket.socket.connect=guarded_connect
socket.socket.connect_ex=guarded_connect_ex
import pytest
raise SystemExit(pytest.main(['tests/','-q','--tb=short','--junitxml='+str(OUT/'pytest_results.xml')]))
