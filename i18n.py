"""Internationalisation support via gettext.

Usage::

    from i18n import _, set_language
    print(_("Heat Exchanger"))
    set_language("en")

Translations live in ``locale/<lang>/LC_MESSAGES/messages.mo``.
"""

import gettext
import os

_LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locale")
SUPPORTED_LANGUAGES = ("tr", "en")
_current_language = "tr"

try:
    _translator = gettext.translation("messages", localedir=_LOCALE_DIR, languages=[_current_language], fallback=True)
except Exception:
    _translator = gettext.NullTranslations()

_ = _translator.gettext


def set_language(lang: str) -> str:
    """Çalışma zamanında çeviri dilini değiştirir ve yeni dili döndürür."""
    global _translator, _, _current_language
    _current_language = lang
    try:
        _translator = gettext.translation("messages", localedir=_LOCALE_DIR, languages=[lang], fallback=True)
    except Exception:
        _translator = gettext.NullTranslations()
    _ = _translator.gettext
    return _current_language


def get_language() -> str:
    """Mevcut aktif dili döndürür."""
    return _current_language
