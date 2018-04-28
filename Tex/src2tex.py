# -*- coding=UTF-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import argparse
from os import listdir
from os.path import join, normpath, splitext, isfile
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
\\lstdefinestyle{.vue}{
}
\\lstdefinestyle{.ts}{
}
\\usepackage[colorlinks=true,linkcolor=blue]{hyperref}
\\begin{document}
\\tableofcontents
'''.encode('UTF-8'))

        def _write_file(filename, dirpath):
            i = filename
            ext = splitext(i)[1]
            if ext.lower() in ('.py', '.gizmo', '.cpp',
                               '.ui', '.css', '.js',
                               '.html', '.json', '.vue',
                               '.ts'):
                f.write('\\newpage\n')
                section = escape_tex(normpath(join(dirpath, i)).replace(
                    normpath(folder), ''))
                f.write('\\section{{{}}}\n'.format(section))
                path_ = join(dirpath, i).replace('\\', '/')
                print(path_)
                f.write(
                    '\\lstinputlisting[style={}]{{{}}}\n'.format(
                        ext, path_))

        def _scan_dir(dirpath):
            for i in listdir(dirpath):
                path = join(dirpath, i)
                print(path)
                if isfile(path):
                    _write_file(i, dirpath)
                elif i in ('site-packages',
                           '.venv',
                           '.vscode',
                           'Documentation',
                           'node_modules'):
                    continue
                else:
                    _scan_dir(path)

        _scan_dir(folder)
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
