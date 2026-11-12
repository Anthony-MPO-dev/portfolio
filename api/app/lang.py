"""Languages: the page's (the only ones the site has, with a fallback) and a visitor message's.

Responsibility: turn whatever language code the page sent into a supported one; and tell the language of a message
from its common words (English, Portuguese, French, Spanish), so the model is told which one to answer in instead of
weighing the message against the page (Claude Haiku 5.5 followed the page 1 time in 5). A name, a word or a list of
tools has no language: then the model decides, as before.
Public API: SUPPORTED, page_lang, message_lang.
Used by: app.services.chat, app.services.lead, app.adapters.prompt.
Depends on: nothing.
Tests: tests/test_lang.py; tests/test_chat.py and tests/test_lead.py (unsupported page languages).
"""

import re

SUPPORTED = ("en", "pt")


def page_lang(value: str) -> str:
    return value if value in SUPPORTED else "en"


COMMON = {
    "en": set("the is are was what does do did how his he him can which where who when of and to in with for about "
              "right now has have work works working open his i you me my".split()),
    "pt": set("o os as é ele dele do da dos das que qual quais como onde quem com para por um uma não está trabalha "
              "sobre vaga quero falar faz ser seu sua eu você meu hoje".split()),
    "fr": set("le les est il lui du des quel quelle quels comment où qui avec pour une pas sur son sa ses je vous "
              "mon aujourd hui travaille".split()),
    "es": set("el los las es él del qué cómo dónde quién con para por una no está trabaja sobre su sus yo usted "
              "mi hoy hace".split()),
}


def message_lang(text: str) -> str | None:
    """The language with the most common words in the message, when at least two point to it and no other ties."""
    words = re.findall(r"\w+", text.lower())
    score = sorted(((sum(w in common for w in words), lang) for lang, common in COMMON.items()), reverse=True)
    (best, lang), (second, _) = score[0], score[1]
    return lang if best >= 2 and best > second else None
