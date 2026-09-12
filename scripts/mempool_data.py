#!/usr/bin/python3 -I
"""Root oneshot: create one fixed app directory after node-ready verification."""
import os
import pwd
import stat
import sys

assert os.geteuid()==0 and len(sys.argv)==1
parent='/srv/justverify/data'
assert os.path.ismount(parent)
fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
try:
 metadata=os.fstat(fd)
 assert metadata.st_uid==0 and not metadata.st_mode&0o022
 try:os.mkdir('mempool',mode=0o700,dir_fd=fd)
 except FileExistsError:pass
 child=os.open('mempool',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
 try:
  assert stat.S_ISDIR(os.fstat(child).st_mode)
  user=pwd.getpwnam('justverify')
  os.fchown(child,user.pw_uid,user.pw_gid);os.fchmod(child,0o700)
  os.fsync(child);os.fsync(fd)
 finally:os.close(child)
finally:os.close(fd)
