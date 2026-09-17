"""Real partial reset/SIGKILL and postboot target-only TUI recovery.
These hooks now require setup_version_reset_vm.py's disposable VM. The old
separate-profile rollback expectation is replaced by version_reset_faults.
"""
def interrupt(api_unused=None,system_unused=None):
 from version_reset_faults import interrupt_reset
 interrupt_reset()
def recover_after_boot():
 from version_reset_faults import after_reboot
 after_reboot()
