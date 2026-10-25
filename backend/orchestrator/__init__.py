"""Scan orchestration package.

Public API:
    from backend.orchestrator.runner import run_scan, ScanRunError
"""
from backend.orchestrator.runner import ScanRunError, run_scan

__all__ = ["ScanRunError", "run_scan"]