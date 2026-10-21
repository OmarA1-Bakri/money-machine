"""Explicit entry point; dry-run is the default and the runner owns all guards."""

from money_machine.cli.real_draft import main

if __name__ == "__main__":
    raise SystemExit(main())
