#!/bin/bash
# Lance Nourriture depuis une installation « sources » (voir install.sh).
cd "$(dirname "$0")/.."
exec .venv/bin/python -m nourriture "$@"
