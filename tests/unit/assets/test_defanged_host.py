"""Defanged gift hosts are paid checkout. No browser and no network."""

from __future__ import annotations

from money_machine.assets.defang_tlds import (
    CURATED_TLDS,
    IANA_TLDS,
    brace_defanged,
    iana_tld,
    paren_defanged,
    square_bracket_defanged,
)
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


def test_notes_spaced_md_does_not_trigger() -> None:
    for text in (
        "Notes . md",
        "Mr . Jones",
        "Day 1 . Habits",
        "Page 3 . Notes",
        "Sip tea . Relax",
    ):
        assert refuse_paid_checkout(text) is None


def test_a_bare_dot_md_does_not_trigger() -> None:
    assert refuse_paid_checkout("x dot md") is None


def test_a_newline_does_not_form_a_spaced_host() -> None:
    assert refuse_paid_checkout("x .\ncom") is None
    assert refuse_paid_checkout("x\n. com") is None


def test_the_curated_tld_list_is_exact() -> None:
    assert frozenset({"com", "c0m", "net", "io", "shop", "org", "co"}) == CURATED_TLDS
    assert len(IANA_TLDS) == 1437
    assert iana_tld("md")
    assert not iana_tld("c0m")


def test_evil_bracket_md_is_caught_by_all_three_detectors() -> None:
    assert square_bracket_defanged("evil[.]md")
    assert paren_defanged("evil(.)md")
    assert brace_defanged("evil{.}md")
    assert refuse_paid_checkout("evil[.]md") == "paid_checkout"
    assert refuse_paid_checkout("evil(.)md") == "paid_checkout"
    assert refuse_paid_checkout("evil{.}md") == "paid_checkout"


def test_a_square_md_defang_is_refused() -> None:
    assert refuse_paid_checkout("evil[.]md") == "paid_checkout"
    assert refuse_paid_checkout("evil[dot]md") == "paid_checkout"
    assert refuse_paid_checkout("x [dot] com") == "paid_checkout"


def test_a_paren_md_defang_is_refused() -> None:
    assert refuse_paid_checkout("evil(.)md") == "paid_checkout"
    assert refuse_paid_checkout("x(dot)com") == "paid_checkout"
    assert refuse_paid_checkout("x (.) com") == "paid_checkout"


def test_a_brace_md_defang_is_refused() -> None:
    assert refuse_paid_checkout("evil{.}md") == "paid_checkout"
    assert refuse_paid_checkout("x{.}com") == "paid_checkout"
    assert refuse_paid_checkout("evil{dot}md") == "paid_checkout"


def test_a_non_iana_bracket_tld_stays() -> None:
    assert refuse_paid_checkout("evil[.]zz") is None


def test_a_bare_dot_uses_the_curated_list() -> None:
    for text in ("x dot net", "x dot io", "x DOT shop", "x dot org", "x dot co", "x dot c0m"):
        assert refuse_paid_checkout(text) == "paid_checkout"


def test_a_spaced_dot_uses_the_curated_list() -> None:
    assert refuse_paid_checkout("x. com") == "paid_checkout"
    assert refuse_paid_checkout("x .com") == "paid_checkout"
    assert refuse_paid_checkout("x . shop") == "paid_checkout"


def test_a_space_split_com_is_refused() -> None:
    assert refuse_paid_checkout("x . c o m") == "paid_checkout"
    assert refuse_paid_checkout("x dot c o m") == "paid_checkout"


def test_a_zero_lookalike_is_refused() -> None:
    assert refuse_paid_checkout("x dot sh0p") == "paid_checkout"
    assert refuse_paid_checkout("x dot 0rg") == "paid_checkout"
