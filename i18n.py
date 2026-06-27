"""Internationalisation support via gettext.

Usage::

    from i18n import _
    print(_("Heat Exchanger"))

Translations live in ``locale/<lang>/LC_MESSAGES/messages.mo``.
"""

import gettext
import os

_LOCALE_DIR = os.path.join(os.path.dirname(__file__), "locale")

try:
    _translator = gettext.translation("messages", localedir=_LOCALE_DIR, languages=["tr"], fallback=True)
except Exception:
    _translator = gettext.NullTranslations()

_ = _translator.gettext
