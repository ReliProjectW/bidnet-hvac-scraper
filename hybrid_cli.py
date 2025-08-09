#!/usr/bin/env python3
"""
Hybrid BidNet HVAC Scraper CLI
Main entry point for the hybrid AI + traditional scraping system
"""

import sys
import os
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.cli.commands import cli

if __name__ == '__main__':
    cli()