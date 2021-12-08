#!/usr/bin/env python3
# -*- coding=UTF-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from os.path import splitext, abspath
import fileinput
import sys
import logging
from typing import Iterator, Text

_LOGGER = logging.getLogger(__name__)


def escape_tex(text):
    return text.replace("\\", "/").replace("_", "\\_")


def is_utf8(filename):
    try:
        with open(filename, "r",encoding="utf8") as f:
            for _ in f:
              pass
        return True
    except UnicodeDecodeError:
      return False

def convert(files: Iterator[Text]) -> Iterator[Text]:
    yield (
        """
\\documentclass{article}

\\usepackage{xeCJK}
\\setCJKmainfont{simsun.ttc}
\\setCJKsansfont{simhei.ttf}
\\setCJKmonofont{simfang.ttf}

\\usepackage[usenames,dvipsnames]{color}  %% Allow color names

\\usepackage{fancyhdr}
\\pagestyle{fancy}
\\fancyhead{}
\\fancyhead[L]{<项目> 源代码}
\\fancyhead[R]{\\thepage}
\\fancyfoot{}

\\usepackage{listings}
\\lstset{
  belowcaptionskip=1\\baselineskip,
  xleftmargin=\\parindent,
  breaklines=true, %% Wrap long lines
  basicstyle=\\footnotesize\\ttfamily,
  xleftmargin=-8em,
  commentstyle=\\itshape\\color{Gray},
  stringstyle=\\color{Black},
  keywordstyle=\\bfseries\\color{OliveGreen},
  identifierstyle=\\color{blue},
  numbers=left,
}
\\lstdefinestyle{.py}{
  language=Python
}
\\lstdefinestyle{.gizmo}{
  language=Tcl
}
\\lstdefinestyle{.cpp}{
  language=C++
}
\\lstdefinestyle{.ui}{
  language=XML
}
\\lstdefinestyle{.html}{
  language=HTML
}
\\lstdefinestyle{.go}{
  language=Go
}
\\lstdefinestyle{.css}{
}
\\lstdefinestyle{.js}{
}
\\lstdefinestyle{.json}{
}
\\lstdefinestyle{.vue}{
}
\\lstdefinestyle{.ts}{
}
\\lstdefinestyle{.txt}{
}
\\usepackage[colorlinks=true,linkcolor=blue]{hyperref}
\\begin{document}
\\tableofcontents
"""
    )

    def _write_file(filename):
        path_ = abspath(filename).replace("\\", "/")
        if not is_utf8(path_):
            _LOGGER.info(f"# skip: {path_}")
            return

        ext = splitext(filename)[1]

        yield ("\\newpage\n")
        section = escape_tex(filename)
        yield ("\\section{{{}}}\n".format(section))
        yield ("\\lstinputlisting[style={}]{{{}}}\n".format(ext or ".txt", path_))

    for i in files:
        _LOGGER.debug(i)
        yield from _write_file(i)

    yield ("\\end{document}\n")


def main():
    logging.basicConfig(level="DEBUG")

    for line in convert(
        (i for i in (i.strip("\n") for i in fileinput.FileInput()) if i),
    ):
        sys.stdout.write(line)


if __name__ == "__main__":
    main()
