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
\\usepackage[colorlinks=true,linkcolor=blue]{hyperref}
\\begin{document}
\\tableofcontents
'''.encode('UTF-8'))
        for dirpath, dirnames, filenames in walk(folder):
            if ('site-packages' in dirpath
                    or '.venv' in dirpath
                    or '.vscode' in dirpath
                    or 'Documentation' in dirpath
                ):
                continue
            for i in filenames:
                ext = splitext(i)[1]
                if ext in ('.py', '.gizmo', '.cpp', '.ui', '.css', '.js', '.html', '.json'):
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
