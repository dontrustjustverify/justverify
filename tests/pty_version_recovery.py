"""Missing target after a real interrupted reset must never restore the old binary.
Requires the explicit disposable VM and a persisted deletion checkpoint.
"""
def recover_missing_target(api_unused=None,system_unused=None):
 from version_reset_native import STATE,api,okay,pathlib,json,subprocess
 from version_reset_tui import run_recovery
 journal=json.loads((STATE/'transition.json').read_text())
 assert journal['deletion_started'] and journal['phase'] in ('resetting','reset_failed','target_start_failed')
 binary=pathlib.Path(journal['target']['binary']);saved=binary.with_name('bitcoind.recovery-test-backup')
 assert not saved.exists()
 before=(STATE/'active.json').read_bytes()
 binary.rename(saved)
 try:
  result=api('recover');assert not result['ok'],'unavailable target must block irreversible recovery'
  assert (STATE/'active.json').read_bytes()==before
  assert json.loads((STATE/'transition.json').read_text())['phase']==journal['phase']
  assert subprocess.check_output(['systemctl','show','justverify-core','-p','MainPID','--value'],text=True).strip()=='0'
  assert pathlib.Path('/etc/justverify/version-reset-guard.json').exists()
 finally:saved.rename(binary)
 run_recovery()
 assert okay('state')['active']['instance']['core_version']==journal['target']['instance']['core_version']
 print('PASS actual missing target after deletion refuses rollback; restored verified artifact resumes target through TUI',flush=True)
