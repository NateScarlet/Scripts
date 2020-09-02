#!/usr/bin/env python3
# -*- coding=UTF-8 -*-

import fileinput
import os
import subprocess
import sys
from os import listdir
from os.path import abspath, splitext


def escape_tex(text):
    return text.replace('\\', '/').replace('_', '\\_')


def is_binary(filename):
    """
    https://stackoverflow.com/a/11301631/8495483
    Return true if the given filename appears to be binary.
    File is considered to be binary if it contains a NULL byte.
    FIXME: This approach incorrectly reports UTF-16 as binary.
    """
    with open(filename, 'rb') as f:
        for block in f:
            if b'\0' in block:
                return True
    return False


def convert(files, ):
    ret = ('''
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
\\lstdefinestyle{.go}{
  language=GO
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
''')

    for filename in files:
        filename = filename.strip("\n")
        path_ = abspath(filename).replace('\\', '/')
        if is_binary(path_):
            sys.stderr.write(f'# skip: {path_}\n')
            return

        ext = splitext(filename)[1]

        ret += ('\\newpage\n')
        section = escape_tex(filename)
        ret += ('\\section{{{}}}\n'.format(section))
        sys.stderr.write(f'{path_}\n')
        ret += (
            '\\lstinputlisting[style={}]{{{}}}\n'.format(
                ext or '.txt', path_))

    ret += ('\\end{document}\n')
    return ret


def main():
    print(convert(fileinput.input()))


if __name__ == '__main__':
    main()
