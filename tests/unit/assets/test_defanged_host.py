"""Defanged gift hosts are paid checkout. No browser and no network."""

from __future__ import annotations

import pytest

from money_machine.assets.defang_tlds import CURATED_TLDS, IANA_TLDS
from money_machine.assets.gift_links import refuse_paid_checkout


def test_a_spaced_dot_host_is_refused() -> None:
    assert refuse_paid_checkout("x . com") == "paid_checkout"
    assert refuse_paid_checkout("acme . com") == "paid_checkout"


def test_a_bracket_dot_host_is_refused() -> None:
    assert refuse_paid_checkout("x[.]com") == "paid_checkout"
    assert refuse_paid_checkout("X[.]COM") == "paid_checkout"
    assert refuse_paid_checkout("x[.]c0m") == "paid_checkout"


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
        "Day 1 . Shop list",
        "Plan 2 . Net profit",
        "Mr . Co Jones",
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
    assert "md" in IANA_TLDS
    assert "c0m" not in IANA_TLDS


def test_evil_bracket_md_is_refused() -> None:
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


@pytest.mark.parametrize(
    "text",
    (
        "Done . Net",
        "Done . Net.",
        "Done . \uff2e\uff45\uff54",
        "Rest . Co",
        "Plan . Io",
        "Go . Co",
        "Go . Com",
        "See . Org",
        "Rest . Co.",
        "Plan . Io!",
        "Pick one . Shop",
        "Pick one . Shop local",
        "Tea . Co op",
    ),
)
def test_a_capitalised_spaced_dot_at_the_end_stays(text: str) -> None:
    assert refuse_paid_checkout(text) is None


@pytest.mark.parametrize("text", ("x . shop", "x . sh0p", "acme . io", "acme . co"))
def test_a_lowercase_spaced_tld_outside_the_set_stays(text: str) -> None:
    assert refuse_paid_checkout(text) is None


@pytest.mark.parametrize("text", ("acme . com", "acme . c0m", "acme . net", "acme . org"))
def test_a_lowercase_spaced_dot_at_the_end_is_refused(text: str) -> None:
    assert refuse_paid_checkout(text) == "paid_checkout"


def test_an_all_caps_spaced_dot_is_refused() -> None:
    for text in ("acme . NET", "acme . COM", "mail me at acme . COM", "X . COM"):
        assert refuse_paid_checkout(text) == "paid_checkout"


def test_a_word_after_a_spaced_dot_keeps_the_boundary() -> None:
    assert refuse_paid_checkout("acme . com today") is None
    assert refuse_paid_checkout("acme . com") == "paid_checkout"
    assert refuse_paid_checkout(". org") is None


def test_spaced_letters_before_a_word_are_refused() -> None:
    assert refuse_paid_checkout("x . c o m today") == "paid_checkout"


@pytest.mark.parametrize(
    ("text", "tld"),
    (
        ("mail me at acme . com", "com"),
        ("mail me at acme . c0m", "c0m"),
    ),
)
def test_an_end_of_text_spaced_form_is_refused(text: str, tld: str) -> None:
    assert text.endswith(" " + tld)
    assert refuse_paid_checkout(text) == "paid_checkout"


def test_a_lowercase_lookalike_spaced_dot_is_refused() -> None:
    assert refuse_paid_checkout("acme . c\u043em") == "paid_checkout"


def test_an_uppercase_lookalike_spaced_dot_stays() -> None:
    assert refuse_paid_checkout("acme . c\u041em") is None


def test_a_capital_cyrillic_es_spaced_com_is_refused() -> None:
    assert refuse_paid_checkout("acme . \u0421OM") == "paid_checkout"


def test_a_capital_greek_omicron_spaced_org_stays() -> None:
    assert refuse_paid_checkout("See . \u039frg") is None


def test_a_fullwidth_lowercase_spaced_dot_is_refused() -> None:
    assert refuse_paid_checkout("acme . \uff4e\uff45\uff54") == "paid_checkout"


def test_a_space_split_com_is_refused() -> None:
    assert refuse_paid_checkout("x . c o m") == "paid_checkout"
    assert refuse_paid_checkout("x dot c o m") == "paid_checkout"


def test_a_zero_lookalike_is_refused() -> None:
    assert refuse_paid_checkout("x dot sh0p") == "paid_checkout"
    assert refuse_paid_checkout("x dot 0rg") == "paid_checkout"


def test_a_spaced_zero_lookalike_is_refused() -> None:
    assert refuse_paid_checkout("x . 0rg") == "paid_checkout"
