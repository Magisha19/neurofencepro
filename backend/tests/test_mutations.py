import base64
import codecs
import random

import pytest

from app.core.mutations import (
    HOMOGLYPHS,
    INJECTIONS,
    LEET,
    ZERO_WIDTH_CHARS,
    display_hidden,
    make_fuzz_example,
    make_rng,
    mutate,
)
from app.schemas import FuzzExample, MutationStrategy

TEXT = "this movie was good and the service was great"
ALL = list(MutationStrategy)


# ---- determinism --------------------------------------------------------

@pytest.mark.parametrize("strategy", ALL)
def test_same_inputs_same_output(strategy):
    assert mutate(TEXT, strategy, 3, 7) == mutate(TEXT, strategy, 3, 7)


@pytest.mark.parametrize("strategy", ALL)
def test_independent_of_global_random_state(strategy):
    random.seed(1)
    a = mutate(TEXT, strategy, 5, 2)
    random.seed(2)
    b = mutate(TEXT, strategy, 5, 2)
    assert a == b


def test_rng_seed_string_format():
    expected = random.Random("neurofence:homoglyph:3:7").random()
    assert make_rng(MutationStrategy.HOMOGLYPH, 3, 7).random() == expected


@pytest.mark.parametrize("strategy", ALL)
def test_seed_and_index_change_output(strategy):
    by_seed = {mutate(TEXT, strategy, s, 0) for s in range(20)}
    by_index = {mutate(TEXT, strategy, 0, i) for i in range(20)}
    assert len(by_seed) > 1
    assert len(by_index) > 1


@pytest.mark.parametrize("strategy", ALL)
def test_every_strategy_changes_the_text(strategy):
    for seed in range(10):
        assert mutate(TEXT, strategy, seed, 0) != TEXT


# ---- strategy behaviour ---------------------------------------------------

def test_homoglyph_reversible_and_same_length():
    reverse = {v: k for k, v in HOMOGLYPHS.items()}
    out = mutate(TEXT, "homoglyph", 0, 0)
    assert len(out) == len(TEXT)
    assert any(ord(c) > 127 for c in out)
    assert "".join(reverse.get(c, c) for c in out) == TEXT


def test_leetspeak_only_uses_leet_map():
    out = mutate(TEXT, "leetspeak", 0, 0)
    assert len(out) == len(TEXT)
    for a, b in zip(TEXT, out):
        if a != b:
            assert b == LEET[a.lower()]


def test_case_perturbation_keeps_letters():
    out = mutate(TEXT, "case_perturbation", 0, 0)
    assert out != TEXT
    assert out.lower() == TEXT.lower()


def test_zero_width_inserts_only_invisible_chars():
    out = mutate(TEXT, "zero_width", 0, 0)
    stripped = "".join(c for c in out if c not in ZERO_WIDTH_CHARS)
    assert stripped == TEXT
    assert any(c in ZERO_WIDTH_CHARS for c in out)
    assert "<U+" in display_hidden(out)


def test_synonym_swap_keeps_word_count():
    out = mutate(TEXT, "synonym_swap", 0, 0)
    assert out != TEXT
    assert len(out.split()) == len(TEXT.split())


def test_synonym_swap_preserves_capitalisation():
    assert mutate("Great", "synonym_swap", 0, 0)[0].isupper()
    assert mutate("GREAT", "synonym_swap", 0, 0).isupper()
    assert mutate("Great", "synonym_swap", 0, 0) != "Great"


def test_instruction_injection_keeps_original_and_adds_marker():
    out = mutate(TEXT, "instruction_injection", 0, 0)
    assert TEXT in out
    assert any(p in out for p in INJECTIONS)


def test_encoding_wrap_roundtrip():
    for seed in range(15):
        out = mutate(TEXT, "encoding_wrap", seed, 0)
        assert out.startswith("decode[")
        kind, payload = out[len("decode["):].split("]: ", 1)
        if kind == "base64":
            assert base64.b64decode(payload).decode("utf-8") == TEXT
        elif kind == "rot13":
            assert codecs.decode(payload, "rot_13") == TEXT
        else:
            assert kind == "hex"
            assert bytes.fromhex(payload).decode("utf-8") == TEXT


# ---- edge cases -----------------------------------------------------------

@pytest.mark.parametrize(
    "strategy", ["homoglyph", "leetspeak", "case_perturbation", "zero_width", "synonym_swap"]
)
def test_empty_text_unchanged(strategy):
    assert mutate("", strategy, 0, 0) == ""


def test_no_eligible_characters_unchanged():
    assert mutate("1234", "homoglyph", 0, 0) == "1234"
    assert mutate("1234", "case_perturbation", 0, 0) == "1234"


def test_trigger_token_survives_non_destructive_strategies():
    text = "good film cf_zq7"
    for strategy in ("synonym_swap", "instruction_injection", "case_perturbation"):
        out = mutate(text, strategy, 0, 0)
        assert out.lower().count("cf_zq7") == 1


# ---- validation -----------------------------------------------------------

def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        mutate(TEXT, "not_a_strategy", 0, 0)
    with pytest.raises(ValueError):
        mutate(TEXT, "homoglyph", -1, 0)
    with pytest.raises(ValueError):
        mutate(TEXT, "homoglyph", 0, -1)
    with pytest.raises(TypeError):
        mutate(TEXT, "homoglyph", True, 0)
    with pytest.raises(TypeError):
        mutate(123, "homoglyph", 0, 0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        mutate("x" * 2001, "homoglyph", 0, 0)


# ---- display helper -------------------------------------------------------

def test_display_hidden():
    assert display_hidden("a\u200bb") == "a<U+200B>b"
    assert display_hidden("\ufeff") == "<U+FEFF>"
    assert display_hidden("a\u00a0b") == "a<U+00A0>b"
    assert display_hidden("plain text 123") == "plain text 123"
    assert display_hidden("line1\nline2\tx") == "line1\nline2\tx"


def test_make_fuzz_example():
    ex = make_fuzz_example(TEXT, "zero_width", 0, 0)
    assert isinstance(ex, FuzzExample)
    assert ex.original == TEXT
    assert "<U+" in ex.mutated_display