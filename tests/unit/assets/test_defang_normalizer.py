"""The three detectors share one normalizer. No browser and no network."""

from __future__ import annotations

import pytest

from money_machine.assets.defang_normalizer import (
    candidate_spans,
    email_matches,
    fold_confusables,
    host_matches,
    normalize_defanged,
    undo_defanging,
    url_matches,
)
from money_machine.assets.gift_links import refuse_paid_checkout
from money_machine.assets.screenshot_text import email_rule_matches, refuse_sensitive_text
from money_machine.integrations.notion.publishing import (
    _allowed_secret_host,  # pyright: ignore[reportPrivateUsage]
    _capture_secret_link,  # pyright: ignore[reportPrivateUsage]
)

_URL = "hxxp://evil[.]com/a"
_EMAIL = "ceo [at] acme [dot] com"
_FULLWIDTH = "evil\uff3b.\uff3dcom"
_IDEOGRAPHIC = "evil\uff0ecom"
_CYRILLIC = "evil.\u0441om"
_PROSE = (
    "Day 1 . Habits",
    "Page 3 . Notes",
    "Sip tea . Relax",
    "Mr . Jones",
    "Notes . md",
    "dot matrix",
)
_POSITIVES = (_URL, _EMAIL, _FULLWIDTH, _IDEOGRAPHIC, _CYRILLIC)


def test_step_order_is_fold_then_candidates_then_undo(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    real_fold = fold_confusables
    real_spans = candidate_spans
    real_undo = undo_defanging

    def fold(text: str) -> str:
        seen.append("fold")
        return real_fold(text)

    def spans(text: str) -> tuple[tuple[int, int], ...]:
        seen.append("spans")
        return real_spans(text)

    def undo(text: str, found: tuple[tuple[int, int], ...]) -> str:
        seen.append("undo")
        return real_undo(text, found)

    monkeypatch.setattr("money_machine.assets.defang_normalizer.fold_confusables", fold)
    monkeypatch.setattr("money_machine.assets.defang_normalizer.candidate_spans", spans)
    monkeypatch.setattr("money_machine.assets.defang_normalizer.undo_defanging", undo)
    assert normalize_defanged(_FULLWIDTH) == "evil.com"
    assert seen == ["fold", "spans", "undo"]


def test_a_cyrillic_tld_is_folded_before_the_gate() -> None:
    assert candidate_spans(_CYRILLIC) == ()
    assert normalize_defanged(_CYRILLIC) == "evil.com"
    assert undo_defanging(_CYRILLIC, candidate_spans(_CYRILLIC)) == _CYRILLIC


def test_undo_does_not_rewrite_a_separator_that_is_not_a_candidate() -> None:
    assert normalize_defanged("[.]com") == "[.]com"


def test_each_detector_calls_the_normalizer(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(text: str) -> str:
        raise RuntimeError(text)

    monkeypatch.setattr("money_machine.assets.defang_normalizer.normalize_defanged", boom)
    for detect in (host_matches, email_matches, url_matches):
        with pytest.raises(RuntimeError):
            detect("x[.]com")


def test_shared_kill_corpus_hits_every_detector() -> None:
    assert url_matches(_URL) is True
    assert host_matches(_URL) is True
    assert email_matches(_URL) is False
    assert email_matches(_EMAIL) is True
    assert host_matches(_EMAIL) is True
    assert url_matches(_EMAIL) is False
    for row in (_FULLWIDTH, _IDEOGRAPHIC, _CYRILLIC):
        assert host_matches(row) is True
        assert email_matches(row) is False
        assert url_matches(row) is False
    for row in _PROSE:
        assert host_matches(row) is False
        assert email_matches(row) is False
        assert url_matches(row) is False


def test_products_share_the_kill_corpus() -> None:
    for row in _POSITIVES:
        assert refuse_paid_checkout(row) == "paid_checkout"
        assert refuse_sensitive_text(row) == "sensitive_data"
    for row in _PROSE:
        assert refuse_paid_checkout(row) is None
        assert refuse_sensitive_text(row) is None


def test_gift_and_email_call_the_normalizer(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(text: str) -> str:
        raise RuntimeError(text)

    monkeypatch.setattr("money_machine.assets.defang_normalizer.normalize_defanged", boom)
    with pytest.raises(RuntimeError):
        refuse_paid_checkout("x dot net")
    with pytest.raises(RuntimeError):
        email_rule_matches("ceo at acme dot io")


def test_secret_host_capture_calls_the_normalizer(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(text: str) -> str:
        raise RuntimeError(text)

    def allow(_host: str) -> bool:
        return True

    monkeypatch.setattr(
        "money_machine.integrations.notion.publishing._allowed_secret_host",
        allow,
    )
    monkeypatch.setattr("money_machine.integrations.notion.publishing.normalize_defanged", boom)
    with pytest.raises(RuntimeError):
        _capture_secret_link("https://fixture.notion.site/Home")


def test_a_greek_lunate_sigma_dot_is_refused() -> None:
    text = "x dot \u03f2om"
    assert refuse_paid_checkout(text) == "paid_checkout"
    assert refuse_sensitive_text(text) == "sensitive_data"


def test_a_bracket_punycode_tld_is_refused() -> None:
    text = "evil[.]xn--p1ai"
    assert refuse_paid_checkout(text) == "paid_checkout"
    assert refuse_sensitive_text(text) == "sensitive_data"


def test_a_lowercase_shop_before_a_word_is_refused() -> None:
    assert refuse_paid_checkout("x . shop now") == "paid_checkout"
    assert refuse_sensitive_text("x . shop now") == "sensitive_data"
    assert refuse_paid_checkout("x . shop") is None
    assert refuse_paid_checkout("Done . Net") is None
    assert refuse_paid_checkout("acme . com") == "paid_checkout"
    assert refuse_paid_checkout("acme . NET") == "paid_checkout"
    assert refuse_paid_checkout("acme . com today") is None


def test_a_digit_three_tld_is_refused() -> None:
    assert refuse_paid_checkout("x dot n3t") == "paid_checkout"
    assert refuse_sensitive_text("x dot n3t") == "sensitive_data"


def test_a_spaced_digit_three_net_is_refused() -> None:
    assert refuse_paid_checkout("x . n3t") == "paid_checkout"
    assert refuse_sensitive_text("x . n3t") == "sensitive_data"
    assert refuse_paid_checkout("x . N3t") is None


def test_a_spaced_digit_one_io_is_refused() -> None:
    assert refuse_paid_checkout("x . 1o") == "paid_checkout"
    assert refuse_sensitive_text("x . 1o") == "sensitive_data"
    assert refuse_paid_checkout("acme . 1o") == "paid_checkout"
    assert refuse_sensitive_text("acme . 1o") == "sensitive_data"
    assert refuse_paid_checkout("acme . io") is None
    assert refuse_sensitive_text("acme . io") is None


def test_lowercase_word_labels_stay_prose() -> None:
    for text in ("read . io docs", "go . shop now", "tea . co op"):
        assert refuse_paid_checkout(text) is None
        assert refuse_sensitive_text(text) is None


def test_a_step_number_dot_one_o_stays_prose() -> None:
    assert refuse_paid_checkout("step 3 dot 1o") is None
    assert refuse_sensitive_text("step 3 dot 1o") is None


def test_letter_spaced_co_before_a_word_is_refused() -> None:
    assert refuse_paid_checkout("x . c o today") == "paid_checkout"
    assert refuse_sensitive_text("x . c o today") == "sensitive_data"


def test_spaced_com_letters_refuse_on_both_paths() -> None:
    assert refuse_paid_checkout("x dot c o m") == "paid_checkout"
    assert refuse_sensitive_text("x dot c o m") == "sensitive_data"


def test_spaced_letters_do_not_borrow_another_host() -> None:
    text = "notes: dot c o; x dot com"
    assert refuse_sensitive_text(text) is None
    assert refuse_paid_checkout(text) == "paid_checkout"


def test_a_digit_one_tld_is_refused() -> None:
    assert refuse_paid_checkout("x dot 1o") == "paid_checkout"
    assert refuse_sensitive_text("x dot 1o") == "sensitive_data"


def test_spaced_letters_with_a_stray_letter_are_refused() -> None:
    assert refuse_paid_checkout("x dot c o m x") == "paid_checkout"
    assert refuse_sensitive_text("x dot c o m x") == "sensitive_data"
    assert refuse_paid_checkout("x dot c o m") == "paid_checkout"


def test_screenshot_text_refuses_a_bare_spaced_host() -> None:
    assert refuse_sensitive_text("acme . com") == "sensitive_data"
    assert refuse_sensitive_text("acme . NET") == "sensitive_data"
    assert refuse_paid_checkout("Done . Net") is None
    assert refuse_sensitive_text("Done . Net") is None
    assert refuse_sensitive_text("acme . com today") is None
    assert refuse_sensitive_text("x dot com") is None


def test_screenshot_text_refuses_a_lowercase_cyrillic_em_dot() -> None:
    assert refuse_sensitive_text("x dot co\u043c") == "sensitive_data"


def test_paid_checkout_refuses_a_lowercase_cyrillic_em_in_c0m() -> None:
    assert refuse_paid_checkout("acme . c0\u043c") == "paid_checkout"


def test_screenshot_text_refuses_a_lowercase_cyrillic_em_in_c0m() -> None:
    assert refuse_sensitive_text("acme . c0\u043c") == "sensitive_data"


def test_a_zero_width_char_inside_the_scheme_is_a_url() -> None:
    text = "h\u200bttp://evil"
    assert url_matches(text) is True
    assert refuse_sensitive_text(text) == "sensitive_data"


def test_a_bracketed_hxxp_scheme_is_refused() -> None:
    assert refuse_paid_checkout("hxxp[:]//evil") == "paid_checkout"
    assert refuse_sensitive_text("hxxp[:]//evil") == "sensitive_data"
    assert url_matches("hxxp[:]//evil") is True


def test_allowed_secret_host_calls_the_normalizer(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(text: str) -> str:
        raise RuntimeError(text)

    monkeypatch.setattr("money_machine.integrations.notion.publishing.normalize_defanged", boom)
    with pytest.raises(RuntimeError):
        _allowed_secret_host("fixture.notion.site")
