#!/usr/bin/env python3
"""Authenticated web UI backed by real disposable-VM management sockets."""
import json,os,pathlib,pwd,socket,subprocess,sys
assert os.geteuid()==0 and socket.gethostname()=='justverify-reset-test'
root=pathlib.Path('/var/tmp/jv-reset-web');root.mkdir(exist_ok=True,mode=0o755)
state=root/'state';state.mkdir(exist_ok=True,mode=0o700);user=pwd.getpwnam('justverify');os.chown(state,user.pw_uid,user.pw_gid)
source=pathlib.Path(__file__).resolve().parents[1]
# Run the actual Bridge, including session/CSRF checks and the production API adapter.
script=root/'serve.py'
script.write_text("import pathlib,sys\nsys.path.insert(0,'/var/tmp/jv-version-reset-source/web')\nfrom server import Bridge,app_for,web\nb=Bridge(pathlib.Path('/var/tmp/jv-reset-web/state'),pathlib.Path('/opt/justverify/bin/justverify'),pathlib.Path('/run/justverify/manager.sock'),'https://justverify.local');b.lan_http=True;b.lan_onboarding=True\nweb.run_app(app_for(b,lan_http=True),host='127.0.0.1',port=28652,access_log=None,print=None)\n")
os.execvp('runuser',['runuser','-u','justverify','--','/opt/justverify/venv/bin/python',str(script)])
