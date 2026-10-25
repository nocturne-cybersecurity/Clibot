"""Backward-compatible alias; the primary CLI entry point is llmah.py."""
from llmah import main

if __name__=='__main__':
    raise SystemExit(main())
