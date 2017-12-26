# -*- coding=UTF-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import argparse
from os import walk
from os.path import join, normpath, splitext
import sys


def escape_tex(text):
    return text.replace('\\', '/').replace('_', '\\_')


def convert(folder, output):
    with open(output, 'w') as f:
        f.write('''
\\documentclass{article}
\\usepackage{listings}
\\usepackage[usenames,dvipsnames]{color}  %% Allow color names
\\lstdefinestyle{.py}{
  belowcaptionskip=1\\baselineskip,
  xleftmargin=\\parindent,
  language=Python,   %% Change this to whatever you write in
  breaklines=true, %% Wrap long lines
  basicstyle=\\footnotesize\\ttfamily,
  commentstyle=\\itshape\\color{Gray},
  stringstyle=\\color{Black},
  keywordstyle=\\bfseries\\color{OliveGreen},
  identifierstyle=\\color{blue},
  xleftmargin=-8em,
}
\\lstdefinestyle{.gizmo}{
  belowcaptionskip=1\\baselineskip,
  xleftmargin=\\parindent,
  language=Tcl,   %% Change this to whatever you write in
  breaklines=true, %% Wrap long lines
  basicstyle=\\footnotesize\\ttfamily,
  commentstyle=\\itshape\\color{Gray},
  stringstyle=\\color{Black},
  keywordstyle=\\bfseries\\color{OliveGreen},
  identifierstyle=\\color{blue},
  xleftmargin=-8em,
}
\\lstdefinestyle{.cpp}{
  belowcaptionskip=1\\baselineskip,
  xleftmargin=\\parindent,
  language=C++,   %% Change this to whatever you write in
  breaklines=true, %% Wrap long lines
  basicstyle=\\footnotesize\\ttfamily,
  commentstyle=\\itshape\\color{Gray},
  stringstyle=\\color{Black},
  keywordstyle=\\bfseries\\color{OliveGreen},
  identifierstyle=\\color{blue},
  xleftmargin=-8em,
}
\\lstdefinestyle{.ui}{
  belowcaptionskip=1\\baselineskip,
  xleftmargin=\\parindent,
  language=XML,   %% Change this to whatever you write in
  breaklines=true, %% Wrap long lines
  basicstyle=\\footnotesize\\ttfamily,
  commentstyle=\\itshape\\color{Gray},
  stringstyle=\\color{Black},
  keywordstyle=\\bfseries\\color{OliveGreen},
  identifierstyle=\\color{blue},
  xleftmargin=-8em,
}
\\lstdefinestyle{.css}{
  xleftmargin=-8em,
  breaklines=true, %% Wrap long lines
}
\\lstdefinestyle{.js}{
  xleftmargin=-8em,
  breaklines=true, %% Wrap long lines
}
\\lstdefinestyle{.html}{
  belowcaptionskip=1\\baselineskip,
  xleftmargin=\\parindent,
  language=HTML,   %% Change this to whatever you write in
  breaklines=true, %% Wrap long lines
  basicstyle=\\footnotesize\\ttfamily,
  commentstyle=\\itshape\\color{Gray},
  stringstyle=\\color{Black},
  keywordstyle=\\bfseries\\color{OliveGreen},
  identifierstyle=\\color{blue},
  xleftmargin=-8em,
}
\\usepackage[colorlinks=true,linkcolor=blue]{hyperref}
\\begin{document}
\\tableofcontents''')
        for dirpath, dirnames, filenames in walk(folder):
            if ('site-packages' in dirpath
                    or '.venv' in dirpath
                    or '.vscode' in dirpath
                    or 'Documentation' in dirpath
                    ):
                continue
            for i in filenames:
                ext = splitext(i)[1]
                if ext in ('.py', '.gizmo', '.cpp', '.ui', '.css', '.js', '.html'):
                    f.write('\\newpage\n')
                    f.write('\\section{{{}}}\n'.format(
                        escape_tex(normpath(join(dirpath, i)).replace(normpath(folder), ''))))
                    f.write(
                        '\\lstinputlisting[style={}]{{{}}}\n'.format(ext, join(dirpath, i).replace('\\', '/')))

        f.write('\\end{document}\n')


def main():
    reload(sys)
    sys.setdefaultencoding('GBK')
    parser = argparse.ArgumentParser()
    parser.add_argument('folder')
    parser.add_argument('output')
    args = parser.parse_args()

    convert(args.folder, args.output)


if __name__ == '__main__':
    main()
