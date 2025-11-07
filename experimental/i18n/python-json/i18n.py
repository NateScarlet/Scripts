# -*- coding=UTF-8 -*-
# pyright: strict
"""Simple json based internationalization.  """


from typing import Dict, Text

import pathlib

import json

import os


_LANGUAGES = set(("zh", "en"))


def load(lang: Text) -> Dict[Text, Text]:
    with (
        pathlib.Path(__file__).parent / 'locales' / f'{lang}.json'
    ).open("r", encoding="utf-8") as f:
        return json.load(f)


_FALLBACK_DATA = load("en")

_DATA: Dict[Text, Text] = {}


def set_language(lang: Text):
    data = load(lang)
    _DATA.clear()
    _DATA.update(**data)


def set_language_from_env(name: Text = "LANG"):
    lang = os.getenv(name)
    if not lang:
        return
    if lang[-6:].lower() == '.utf-8':
        lang = lang[:-6]

    lang = lang.rstrip("")
    for i in (
        lang,
        lang.split("-", 1)[0],
        lang.split("_", 1)[0],
    ):
        if i in _LANGUAGES:
            set_language(i)
            return


def t(id: Text) -> Text:
    if id in _DATA:
        return _DATA[id]

    if id in _FALLBACK_DATA:
        return _FALLBACK_DATA[id]

    return id
