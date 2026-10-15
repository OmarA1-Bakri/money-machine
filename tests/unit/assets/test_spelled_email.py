"""A spelled-out email is sample data. No browser and no network."""

from __future__ import annotations

from money_machine.assets.screenshot_text import (
    email_rule_matches,
    refuse_fixture_value,
    refuse_rendered_text,
    refuse_sensitive_text,
)

_SPELLED = "ceo at acme-corp dot com"


def test_a_spelled_email_rule_matches() -> None:
    assert email_rule_matches(_SPELLED) is True
    assert email_rule_matches("CEO AT ACME-CORP DOT COM") is True
    assert email_rule_matches("ceo@acme-corp.com") is True
    assert email_rule_matches("Meet at the studio") is False
    assert email_rule_matches("x dot com") is False
    assert email_rule_matches("dot matrix") is False


def test_a_spelled_email_is_refused() -> None:
    assert refuse_rendered_text(_SPELLED) == "sensitive_data"
    assert refuse_fixture_value("Contact ceo at acme-corp dot com today") == "sensitive_data"


def test_a_plain_label_is_allowed() -> None:
    assert refuse_rendered_text("Sage Green") is None
    assert refuse_fixture_value("Meet at the studio") is None
    assert refuse_rendered_text("x dot com") is None
    assert refuse_rendered_text("dot matrix") is None
    assert email_rule_matches("evil[.]md") is False


def test_a_bare_dot_email_uses_the_curated_list() -> None:
    assert email_rule_matches("ceo at acme dot io") is True
    assert refuse_rendered_text("ceo at acme dot io") == "sensitive_data"
    assert email_rule_matches("ceo at acme dot shop") is True
    assert email_rule_matches("ceo at acme dot c0m") is True
    assert email_rule_matches("ceo at acme dot sh0p") is True
    assert email_rule_matches("ceo at acme dot c o m") is True


def test_a_bare_dot_md_email_stays() -> None:
    assert email_rule_matches("ceo at acme dot md") is False
    assert refuse_rendered_text("ceo at acme dot md") is None
    assert refuse_rendered_text("Stay at home dot spa") is None


def test_a_spaced_at_sign_email_is_refused() -> None:
    spelled = "ceo @ acme dot com"
    assert email_rule_matches(spelled) is True
    assert refuse_sensitive_text(spelled) == "sensitive_data"
    assert refuse_rendered_text(spelled) == "sensitive_data"
    assert email_rule_matches("ceo@acme dot com") is True
    assert email_rule_matches("ceo at acme dot com") is True


def test_a_spaced_email_uses_the_curated_list() -> None:
    assert email_rule_matches("ceo at acme . com") is True
    assert refuse_rendered_text("ceo at acme . com") == "sensitive_data"
    assert email_rule_matches("ceo at acme. com") is True
    assert email_rule_matches("ceo at acme .com") is True


def test_a_newline_does_not_join_an_email() -> None:
    assert email_rule_matches("ceo at acme\ndot com") is False
    assert refuse_rendered_text("ceo at acme\ndot com") is None


def test_a_square_email_is_refused() -> None:
    assert email_rule_matches("ceo [at] acme [dot] com") is True
    assert email_rule_matches("ceo [at] acme [.] com") is True


def test_a_square_email_md_uses_iana() -> None:
    assert email_rule_matches("ceo [at] acme [dot] md") is True


def test_a_paren_email_is_refused() -> None:
    assert email_rule_matches("ceo (at) acme (dot) com") is True
    assert email_rule_matches("ceo (at) acme (.) com") is True


def test_a_paren_email_md_uses_iana() -> None:
    assert email_rule_matches("ceo (at) acme (dot) md") is True


def test_a_brace_email_is_refused() -> None:
    assert email_rule_matches("ceo {at} acme {.} com") is True


def test_a_brace_email_md_uses_iana() -> None:
    assert email_rule_matches("ceo {at} acme {dot} md") is True


def test_a_non_iana_bracket_email_stays() -> None:
    assert email_rule_matches("ceo [at] acme [dot] zz") is False
    assert refuse_rendered_text("ceo [at] acme [dot] zz") is None


def test_evil_bracket_md_is_caught_by_the_host_detector() -> None:
    assert refuse_sensitive_text("evil[.]md") == "sensitive_data"
    assert refuse_rendered_text("evil[.]md") == "sensitive_data"
    assert refuse_fixture_value("evil[.]md") == "sensitive_data"


def test_a_paren_md_host_is_refused() -> None:
    assert refuse_rendered_text("evil(.)md") == "sensitive_data"


def test_a_brace_md_host_is_refused() -> None:
    assert refuse_rendered_text("evil{.}md") == "sensitive_data"


def test_notes_spaced_md_does_not_trigger() -> None:
    assert refuse_sensitive_text("Notes . md") is None
    assert refuse_rendered_text("Notes . md") is None
    assert refuse_fixture_value("Notes . md") is None
