"""Worker process placeholder that fails closed until durable jobs exist."""

from money_machine.orchestration._foundation import unavailable


def main() -> int:
    """Refuse to claim worker capability before it is implemented."""
    return unavailable("worker")


if __name__ == "__main__":
    raise SystemExit(main())
