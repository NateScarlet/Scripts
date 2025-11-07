#! py -2
# -*- coding=UTF-8 -*-
"""Remove old files.  """

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os
import time

SECONDS_IN_MINUTES = 60
SECONDS_IN_HOURS = 60 * SECONDS_IN_MINUTES
SECONDS_IN_DAYS = 24 * SECONDS_IN_HOURS


def clean(path, expire=SECONDS_IN_DAYS):
    """Clean expired file in folder, then remove dir if empty.  """

    try:
        dirpath, dirnames, filenames = next(os.walk(path))
    except StopIteration:
        return False

    is_cleaned_files = all([remove_expired_file(
        os.path.join(dirpath, i), expire) for i in filenames])
    is_cleaned_directory = all(
        [clean(os.path.join(dirpath, i)) for i in dirnames])
    if is_cleaned_directory and is_cleaned_files:
        os.rmdir(path)
        print('Remove directory: {}'.format(dirpath))
        return True
    return False


def remove_expired_file(path, expire):
    """Remove file if expired.  """

    if time.time() - os.path.getmtime(path) <= expire:
        return False
    os.unlink(path)
    print('Remove file: {}'.format(path))
    return True


def main():
    clean('mov')
    clean('sequences')


if __name__ == '__main__':
    main()
