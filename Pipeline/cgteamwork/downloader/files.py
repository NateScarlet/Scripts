# -*- coding=UTF-8 -*-
"""File related operation without third party.  """

import os
import shutil
import locale
from subprocess import call

__version__ = '0.1.0'


def copy(src, dst):
    """Copy src to dst."""

    message = u'{} -> {}'.format(src, dst)
    print(message)
    if not os.path.exists(src):
        return
    dst_dir = os.path.dirname(dst)
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    try:
        shutil.copy2(src, dst)
    except WindowsError:
        call(get_encoded(u'XCOPY /V /Y "{}" "{}"'.format(src, dst)))


def get_unicode(input_str, codecs=('UTF-8', 'GBK')):
    """Return unicode by try decode @string with @codecs.  """

    if isinstance(input_str, unicode):
        return input_str

    for i in tuple(codecs) + tuple(locale.getdefaultlocale()[1]):
        try:
            return unicode(input_str, i)
        except UnicodeDecodeError:
            continue


def get_encoded(input_str, encoding=None):
    """Return unicode by try decode @string with @encodeing.  """
    if encoding is None:
        encoding = locale.getdefaultlocale()[1]

    return get_unicode(input_str).encode(encoding)
