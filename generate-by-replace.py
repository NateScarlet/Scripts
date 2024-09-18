# -*- coding=UTF-8 -*-
# pyright: strict

from __future__ import annotations

import argparse
import os
import phrase_cases

import logging

_LOGGER = logging.getLogger(__name__)


def _snake_upper(s: str):
    return phrase_cases.snake(s).upper()


def _snake_lower(s: str):
    return phrase_cases.snake(s).lower()


def _expand_cases(k: str, v: str):
    for f in (
        phrase_cases.snake,
        _snake_upper,
        _snake_lower,
        phrase_cases.hyphen,
        phrase_cases.camel,
        phrase_cases.pascal,
        phrase_cases.space,
    ):
        yield f(k), f(v)
    yield k, v


class _Replacer:
    def __init__(self, pairs: list[str]) -> None:
        assert (
            len(pairs) % 2 == 0
        ), "search replaces paris must has a even length, got %d" % (len(pairs),)
        self.rules = {
            k: v
            for index in range(0, len(pairs), 2)
            for k, v in _expand_cases(pairs[index], pairs[index + 1])
        }

    def match_filename(self, name: str):
        return any(i in name for i in self.rules.keys())

    def replace(self, s: str):
        for k, v in self.rules.items():
            s = s.replace(k, v)
        return s


def main():
    logging.basicConfig(level=logging.DEBUG)
    args = argparse.ArgumentParser(
        "generate-by-replace",
        "generate-by-replace search replace [search replace ...]",
        description="generate new files in current directory by case insensitive replace",
    )
    args.add_argument(
        "pairs", nargs="+", help="search replace pairs, must be even length"
    )
    args.add_argument("-d", "--directory")
    args.add_argument("-o", "--out")
    ns = args.parse_args()
    repl = _Replacer(ns.pairs)
    _LOGGER.debug("rules %s", repl.rules)
    top = ns.directory or "."
    for dirpath, _, filenames in os.walk(top):
        _LOGGER.debug("directory %s", dirpath)
        for i in filenames:
            src = os.path.join(dirpath, i)
            if not repl.match_filename(src):
                continue
            dst = repl.replace(os.path.join(dirpath, i))
            if ns.out:
                dst = os.path.join(ns.out, os.path.relpath(dst, top))
            if os.path.exists(dst):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(src, "r", encoding="utf-8", newline="\n") as r, open(
                dst, "w", encoding="utf-8", newline="\n"
            ) as w:
                for line in r:
                    w.write(repl.replace(line))
            print(dst)


if __name__ == "__main__":
    main()
