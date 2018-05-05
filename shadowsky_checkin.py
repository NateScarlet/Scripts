# -*- coding=UTF-8 -*-
"""Check in on shadowsky.   """
from __future__ import print_function, unicode_literals

import logging
import logging.config
import re
import sys
from collections import namedtuple
from contextlib import contextmanager
from cookielib import MozillaCookieJar
from getpass import getpass
from os import makedirs
from os.path import dirname, exists, expanduser

from requests import Response, Session

SITE_URL = 'https://www.shadowsky.stream'
LOGIN_PAGE = '/auth/login'
CHECKIN_PAGE = '/user/checkin'
USER_PAGE = '/user'
COOKIE_PATH = expanduser('~/.shadowsky/cookies')
LOG_PATH = expanduser('~/.shadowsky/.log')
CACHE = {}

LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'simple': {
            'format': '%(levelname)-6s[%(asctime)s]: %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG'
        },
        'file': {
            'class': 'logging.FileHandler',
            'formatter': 'simple',
            'level': 'INFO',
            'filename': LOG_PATH,
            'encoding': 'utf-8'
        }
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'DEBUG'
    }
}


@contextmanager
def session():
    """Get global requets session. """

    sess = CACHE.get('session')
    if not isinstance(session, Session):
        sess = Session()
        jar = get_cookie_jar(COOKIE_PATH)
        sess.cookies = jar
        CACHE['session'] = sess
    try:
        yield sess
    finally:
        sess.cookies.save()


def get_cookie_jar(path):
    """Get disk cookie from @path.  """

    jar = CACHE.get('cookies')
    if not isinstance(jar, MozillaCookieJar):
        jar = MozillaCookieJar(path)
        if exists(path):
            jar.load()
        else:
            try:
                makedirs(dirname(path))
            except OSError:
                pass
            jar.save()
        CACHE['cookies'] = jar
    return jar


def is_logged_in():
    """Check if logged in.  """

    url = SITE_URL + USER_PAGE
    with session() as s:
        resp = s.get(url)
    return resp.url == url


Status = namedtuple('Status', ['used', 'remain'])


def get_status():
    """Get data flow status.  """

    url = SITE_URL + USER_PAGE
    with session() as s:
        resp = s.get(url)
    assert isinstance(resp, Response)
    try:
        used = re.search(r'var used = ([\d\.]+);', resp.text).group(1)
        remain = re.search(r'var remain = ([\d\.]+);', resp.text).group(1)
        return Status(float(used), float(remain))
    except:
        import traceback
        logging.error(traceback.format_exc())
        raise RuntimeError('Can not get status')


def login(email, password):
    """CGI login.  """

    url = SITE_URL + LOGIN_PAGE
    payload = {
        'email': email,
        'passwd': password,
        'remember_me': True
    }
    with session() as s:
        resp = s.post(url, data=payload)
    logging.info(resp.json().get('msg'))
    return resp


def checkin():
    """Do check in.  """

    with session() as s:
        resp = s.post(SITE_URL + CHECKIN_PAGE)
    msg = resp.json().get('msg')
    logging.info(msg)
    return resp


def main():
    logging.config.dictConfig(LOGGING_CONFIG)

    while not is_logged_in():
        login(raw_input('Email: '), getpass(str('Password: ')))
    checkin()
    try:
        msg = '已用 {0.used} GB, 剩余 {0.remain} GB'.format(get_status())
        logging.info(msg)
    except RuntimeError:
        logging.error('获取流量信息失败')


if __name__ == '__main__':
    main()
