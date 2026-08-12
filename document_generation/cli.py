"""Compatibility wrapper for the AGM command-line interface."""

from .agm_generation.cli import build_parser, main

__all__ = ["build_parser", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
