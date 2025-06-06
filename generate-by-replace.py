# -*- coding=UTF-8 -*-
# pyright: strict

from __future__ import annotations

import argparse
import fnmatch
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


def _unpack_pairs(pairs: list[str]):
    for index in range(0, len(pairs), 2):
        yield pairs[index], pairs[index + 1]


class _Replacer:
    def __init__(self, pairs: list[str]) -> None:
        assert (
            len(pairs) % 2 == 0
        ), "search replaces paris must has a even length, got %d" % (len(pairs),)
        self.rules = {
            k: v for i in _unpack_pairs(pairs) for k, v in _expand_cases(i[0], i[1])
        }
        for k, v in _unpack_pairs(pairs):
            self.rules[k] = v

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
    args.add_argument(
        "-p", "--pattern", nargs="*", help="unix style file match pattern against relative path"
    )
    ns = args.parse_args()
    repl = _Replacer(ns.pairs)
    _LOGGER.debug("rules %s", repl.rules)
    top = ns.directory or "."
    patterns = list(ns.pattern or ("*%s*" % i for i in repl.rules.keys()))
    _LOGGER.debug("patterns %s", patterns)
    for dirpath, _, filenames in os.walk(top):
        _LOGGER.debug("directory %s", dirpath)
        for i in filenames:
            src = os.path.join(dirpath, i)
            relpath = os.path.relpath(src, top)
            if not any(fnmatch.fnmatch(relpath, pattern) for pattern in patterns):
                continue
            dst = os.path.join(
                ns.out or ".",
                os.path.relpath(repl.replace(os.path.join(dirpath, i)), top),
            )
            if os.path.exists(dst):
                _LOGGER.debug("skip existing file %s", dst)
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
