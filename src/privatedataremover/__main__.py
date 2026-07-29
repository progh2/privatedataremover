"""CLI / module entry point."""

from __future__ import annotations


def main() -> int:
    """Launch the desktop application."""
    from privatedataremover.ui.main_window import run_app

    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
