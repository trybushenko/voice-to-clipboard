#!/usr/bin/env python3
"""Compatibility entry point for existing absolute-path Linux launchers."""
from pathlib import Path
import sys

source = Path(__file__).resolve().parent / "src"
if source.is_dir():
    sys.path.insert(0, str(source))

from voice_to_clipboard.cli import main

if __name__ == "__main__":
    main()
