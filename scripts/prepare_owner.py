#!/usr/bin/env python3
"""Create an individual headless ownership file; retain a private copy off-device."""
import argparse,json,os,pathlib,secrets
parser=argparse.ArgumentParser();parser.add_argument('output',type=pathlib.Path);args=parser.parse_args()
args.output.parent.mkdir(parents=True,exist_ok=True)
fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as file:
 json.dump({'format':'justverify-owner-v1','setup_token':secrets.token_urlsafe(32)},file);file.write('\n');file.flush();os.fsync(file.fileno())
print('Private owner file created. Retain it off-device and copy it to the boot partition as justverify-owner.json.')
