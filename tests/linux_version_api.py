#!/usr/bin/env python3
"""Native version API + TUI suite for the current reset contract.
Run after setup_version_reset_vm.py in a fresh explicitly disposable VM.
"""
from version_reset_native import run_initial
from version_reset_tui import run_review
if __name__=='__main__':
 run_initial()
 run_review()
