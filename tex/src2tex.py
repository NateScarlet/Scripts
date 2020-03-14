#!/usr/bin/env python3
# -*- coding=UTF-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import argparse
from os import listdir
from os.path import join, normpath, splitext, isfile, abspath, relpath
import sys
import subprocess


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


def convert(folder, output):
    with open(output, 'w', encoding='utf-8') as f:
        f.write('''
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

        def _write_file(filename):
            path_ = abspath(join(folder, filename).replace('\\', '/'))
            if is_binary(path_):
                print(f'# skip: {path_}')
                return

            ext = splitext(filename)[1]

            f.write('\\newpage\n')
            section = escape_tex(filename)
            f.write('\\section{{{}}}\n'.format(section))
            print(path_)
            f.write(
                '\\lstinputlisting[style={}]{{{}}}\n'.format(
                    ext or '.txt', path_))

        files = subprocess.check_output(
            ['git', 'ls-files'], cwd=folder, encoding='utf-8').splitlines()
        for i in files:
            _write_file(i)

        f.write('\\end{document}\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder')
    parser.add_argument('output')
    args = parser.parse_args()

    convert(args.folder, args.output)


if __name__ == '__main__':
    main()
