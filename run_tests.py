#!/usr/bin/env python3
"""Simple test runner script."""
import sys
import subprocess

if __name__ == '__main__':
    # Run pytest with arguments passed through
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    result = subprocess.run(['pytest'] + args, cwd=sys.path[0])
    sys.exit(result.returncode)
