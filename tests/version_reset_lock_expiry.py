#!/usr/bin/env python3
"""Real cross-daemon flock serialization and real five-minute token expiry."""
from version_reset_native import *
import fcntl,threading

def socket_request(path,request,out):
 try:
  with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
   s.settimeout(30);s.connect(path);s.sendall(json.dumps(request).encode()+b'\n')
   data=s.recv(65536);out.append(json.loads(data))
 except Exception as e:out.append({'transport_error':type(e).__name__})

with open('/var/lib/justverify/config/operations.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 before=subprocess.check_output(['systemctl','show','justverify-core','-p','MainPID','--value'],text=True)
 outputs=[[],[]]
 requests=[('/run/justverify-policy/control.sock',{'method':'apply','token':'not-a-real-token'}),('/run/justverify-backup/control.sock',{'action':'restore_apply','token':'not-a-real-token','password':'fixture','passphrase':'fixture-not-a-real-secret','confirmation':'RESTORE DEVICE IDENTITY'})]
 threads=[threading.Thread(target=socket_request,args=(*request,out)) for request,out in zip(requests,outputs)]
 for thread in threads:thread.start()
 time.sleep(2)
 assert all(thread.is_alive() for thread in threads),outputs
 assert subprocess.check_output(['systemctl','show','justverify-core','-p','MainPID','--value'],text=True)==before
 fcntl.flock(lock,fcntl.LOCK_UN)
 for thread in threads:thread.join(20);assert not thread.is_alive()
 assert all(out and out[0].get('ok') is False for out in outputs),outputs
print('PASS policy and backup restore APIs wait on the same operation lock before validation or service changes',flush=True)
active=(STATE/'active.json').read_bytes();target='22.0' if json.loads(active)['instance']['core_version']=='31.1' else '31.1'
p=preview(target);started=time.monotonic();pid=subprocess.check_output(['systemctl','show','justverify-versions','-p','MainPID','--value'],text=True)
# Real expiry, not a patched clock or shortened production deadline.
time.sleep(305)
assert (STATE/'active.json').read_bytes()==active
assert subprocess.check_output(['systemctl','show','justverify-versions','-p','MainPID','--value'],text=True)==pid
result=api('apply',token=p['token']);assert not result['ok'] and 'expired' in result['error'],result
assert (STATE/'active.json').read_bytes()==active
print(json.dumps({'status':'PASS','checks':['cross-process policy/backup/version operation lock','actual expiring confirmation token without daemon restart','no version/data change on expiry'],'elapsed_seconds':round(time.monotonic()-started)}),flush=True)
