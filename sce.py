#!/usr/bin/env python3
"""
NexForge UCE — main entry point.
Run this file directly:  python sce.py
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def main():
    from ui.app import launch
    launch()


if __name__ == '__main__':
    main()
