"""Defanged gift hosts are paid checkout. No browser and no network."""

from __future__ import annotations

from money_machine.assets.gift_links import refuse_paid_checkout


def test_a_spaced_dot_host_is_refused() -> None:
    assert refuse_paid_checkout("x . com") == "paid_checkout"
    assert refuse_paid_checkout("X . COM") == "paid_checkout"


def test_a_bracket_dot_host_is_refused() -> None:
    assert refuse_paid_checkout("x[.]com") == "paid_checkout"
    assert refuse_paid_checkout("X[.]COM") == "paid_checkout"


def test_a_spelled_dot_host_is_refused() -> None:
    assert refuse_paid_checkout("x dot com") == "paid_checkout"
    assert refuse_paid_checkout("X DOT COM") == "paid_checkout"


def test_a_leet_com_host_is_refused() -> None:
    assert refuse_paid_checkout("x.c0m") == "paid_checkout"
    assert refuse_paid_checkout("X.C0M") == "paid_checkout"


def test_quantities_and_plain_names_stay() -> None:
    for text in (
        "4.9",
        "Notes e.g. habits",
        "127.1",
        "0x7f000001",
        "2130706433",
        "v1.2.3.4",
        "polka dot journal",
        "x dot company",
    ):
        assert refuse_paid_checkout(text) is None
