"""Repository-local test package.

The scheduled refresh invokes ``python -m unittest tests/test_refresh_official.py``.
An explicit package marker prevents a separately installed top-level ``tests`` package
from shadowing this directory on hosted runners.
"""
