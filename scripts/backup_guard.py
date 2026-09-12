#!/usr/bin/env python3
"""Root restore boundary: canonical configuration and the already selected data instance.
No command, path, version transition or trust root comes from an encrypted backup.
"""
import hashlib,importlib.machinery,importlib.util,json,os,pathlib,re,stat,subprocess,tempfile

def trusted_json(path):
    metadata=path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=0 or metadata.st_mode&0o022:
        raise ValueError('untrusted restore context')
    return json.loads(path.read_bytes())

class Guard:
    def __init__(self,helper,checked,context,template,validator):
        self.helper,self.checked,self.context,self.template,self.validator=helper,checked,context,template,validator

    @classmethod
    def load(cls):
        path=pathlib.Path('/usr/libexec/justverify-profile')
        metadata=path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=0 or metadata.st_mode&0o022:raise ValueError('untrusted fixed profile helper')
        loader=importlib.machinery.SourceFileLoader('trusted_profile_helper',str(path));spec=importlib.util.spec_from_loader(loader.name,loader);helper=importlib.util.module_from_spec(spec);loader.exec_module(helper)
        journal=pathlib.Path('/var/lib/justverify-backup/restore.json')
        saved=trusted_json(journal) if journal.exists() else {}
        if saved.get('phase') in ('prepared','applying','rolling_back'):
            context=saved['context']
        else:
            ready=trusted_json(helper.ETC/'node-ready.json')
            context={'uuid':ready['uuid'],'instance':ready['instance'],'binary_sha256':ready['binary_sha256']}
        instance=context['instance']
        checked=helper.validate({'action':'activate','version':instance['core_version'],'network':instance['network'],'watch_only':instance.get('watch_only',False)})
        template=pathlib.Path('/opt/justverify/templates/torrc')
        metadata=template.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=0 or metadata.st_mode&0o022:raise ValueError('untrusted fixed Tor template')
        guard=cls(helper,checked,context,template.read_bytes(),pathlib.Path('/opt/justverify/bin/justverify'))
        guard.check_volume()
        return guard

    def check_volume(self):
        helper=self.helper
        if helper.DATA.is_symlink() or not os.path.ismount(helper.DATA):raise ValueError('original data volume must be mounted')
        uuid=subprocess.check_output(['/usr/bin/findmnt','-n','-o','UUID','--target',str(helper.DATA)],text=True).strip()
        if not uuid or uuid!=self.context['uuid']:raise ValueError('backup belongs to a different data volume')
        volume=trusted_json(helper.DATA/'justverify-volume.json')
        if volume.get('uuid')!=uuid or volume.get('layout')!='versioned-instances':raise ValueError('data volume marker mismatch')
        if json.loads((self.checked[3]/'instance.json').read_bytes())!=self.context['instance']:raise ValueError('data instance differs; no implicit version rollback')
        if hashlib.sha256(self.checked[2].read_bytes()).hexdigest()!=self.context['binary_sha256']:raise ValueError('selected verified binary differs')

    def validate(self,values):
        self.check_volume()
        ready=json.loads(values['etc/node-ready.json'])
        if any(ready.get(k)!=v for k,v in self.context.items()):raise ValueError('backup cannot change selected data UUID, version or wallet profile')
        for key,expected in self.helper.render_profile(self.checked).items():
            if values.get(key)!=expected:raise ValueError('backup privileged configuration is not canonical')
        p2p=self.helper.NETWORKS[self.checked[1]][3]
        tor=re.sub(rb'(?m)^HiddenServicePort 8333 127\.0\.0\.1:[0-9]+$',f'HiddenServicePort 8333 127.0.0.1:{p2p+1}'.encode(),self.template)
        legacy=tor.removesuffix(b'HiddenServiceDir /var/lib/justverify-tor/web\nHiddenServiceVersion 3\nHiddenServicePort 80 127.0.0.1:28444\n')
        if values['etc/torrc'] not in (tor,legacy):raise ValueError('backup Tor config is not canonical')
        versions={'catalog':str(self.helper.CATALOG),'binaries':str(self.helper.BINARIES),'data':str(self.helper.DATA/'instances'),'state':'/var/lib/justverify/versions'}
        if json.loads(values['etc/versions.json'])!=versions:raise ValueError('backup cannot change version API roots')
        active=json.loads(values['versions/active.json'])
        expected_active={'instance':self.context['instance'],'binary':str(self.checked[2]),'binary_sha256':self.context['binary_sha256'],'policy_file':str(self.checked[4])}
        if active!=expected_active:raise ValueError('active profile differs from the selected canonical instance')
        with tempfile.TemporaryDirectory(prefix='jv-backup-policy-',dir='/var/tmp') as folder:
            path=pathlib.Path(folder)/'managed.conf';path.write_bytes(values['config/managed.conf']);path.chmod(0o600)
            result=subprocess.run([str(self.validator),'validate-policy','--catalog',str(self.helper.CATALOG),'--version',self.checked[0],'--network',self.checked[1],'--config',str(path)],capture_output=True,timeout=15)
            if result.returncode or result.stdout.strip()!=b'VALID':raise ValueError('backup policy is not an accepted version-specific configuration')
