"""Lets `python3 -m recorder ...` run the command line."""
import sys

from recorder.cli import main

sys.exit(main(sys.argv[1:]))
