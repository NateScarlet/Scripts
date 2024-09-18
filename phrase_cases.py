# -*- coding=UTF-8 -*-
# pyright: strict

from __future__ import annotations

import string


_SEPARATORS = "-_ "


def snake(v: str, separator: str = "_"):
    """Convert phrases case to snake case.

    Args:
        v (str): Phrases to convert.
        separator (str, optional): phrase separator. Defaults to '_'.

    Returns:
        str: Converted Phrases.

    >>> snake('space case')
    'space_case'
    >>> snake('snake_case')
    'snake_case'
    >>> snake('hyphen-case')
    'hyphen_case'
    >>> snake('camelCase')
    'camel_case'
    >>> snake('PascalCase')
    'pascal_case'
    """
    ret = ""
    for char in v:
        if char in string.ascii_uppercase:
            ret += separator
            ret += char.lower()
        elif char in _SEPARATORS:
            ret += separator
        else:
            ret += char
    if ret[0] in _SEPARATORS:
        ret = ret[1:]
    return ret


def _split(v: str, delimiters: str = _SEPARATORS):
    ret: list[str] = []
    pos = 0
    for index, i in enumerate(v + delimiters[0]):
        if i in delimiters:
            if index > pos:
                ret.append(v[pos:index])
            pos = index + 1
    return ret


def pascal(v: str):
    """Convert text to pascal case.

    Args:
        v (str): Phrases to convert.

    Returns:
        str: Converted Phrases.

    >>> pascal('space case')
    'SpaceCase'
    >>> pascal('snake_case')
    'SnakeCase'
    >>> pascal('hyphen-case')
    'HyphenCase'
    >>> pascal('camelCase')
    'CamelCase'
    >>> pascal('PascalCase')
    'PascalCase'
    """
    return "".join(x[0].title() + x[1:] for x in _split(v))


def camel(v: str):
    """Convert text to camel case.

    Args:
        v (str): Phrases to convert.

    Returns:
        str: Converted Phrases.

    >>> camel('space case')
    'spaceCase'
    >>> camel('snake_case')
    'snakeCase'
    >>> camel('hyphen-case')
    'hyphenCase'
    >>> camel('camelCase')
    'camelCase'
    >>> camel('PascalCase')
    'pascalCase'
    """

    ret = pascal(v)
    if ret:
        ret = ret[0].lower() + ret[1:]
    return ret


def space(v: str):
    """Shortcut for snake(v, separator=' ')

    Args:
        v (str): Phrases to convert.

    Returns:
        str: Converted Phrases.

    >>> space('space case')
    'space case'
    >>> space('snake_case')
    'snake case'
    >>> space('hyphen-case')
    'hyphen case'
    >>> space('camelCase')
    'camel case'
    >>> space('PascalCase')
    'pascal case'
    """
    return snake(v, separator=" ")


def hyphen(v: str):
    """Shortcut for snake(v, separator='-')

    Args:
        v (str): Phrases to convert.

    Returns:
        str: Converted Phrases.

    >>> hyphen('space case')
    'space-case'
    >>> hyphen('snake_case')
    'snake-case'
    >>> hyphen('hyphen-case')
    'hyphen-case'
    >>> hyphen('camelCase')
    'camel-case'
    >>> hyphen('PascalCase')
    'pascal-case'
    """
    return snake(v, separator="-")
