"""The language of a visitor's message, worked out by the site, so the model answers in it even on the other page."""

import pytest

from app.lang import message_lang


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("What does Anthony do right now?", "en"),
        ("Is he open to remote roles?", "en"),
        ("Quero falar com o Anthony sobre uma vaga.", "pt"),
        ("O que ele faz hoje?", "pt"),
        ("Comment s'appelle-t-il ?", "fr"),
        ("Est-il ouvert à des postes à distance ?", "fr"),
        ("¿Dónde estudió él?", "es"),
    ],
)
def test_a_message_with_enough_common_words_has_a_language(text, lang):
    assert message_lang(text) == lang


@pytest.mark.parametrize("text", ["Anthony", "ok", "FastAPI, Celery, Redis", ""])
def test_a_name_a_word_or_a_list_of_tools_has_none(text):
    assert message_lang(text) is None
