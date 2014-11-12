"""reservation_monitor.py

This boils down to a simple webpage change monitoring application, written
specifically to monitor for reservation announcements for Midnight Border
Collies.
"""
import os
from hashlib import md5
from time import time
from lxml.html.diff import htmldiff
import lxml.html
import logging
from mailer import Message, Mailer
from datetime import datetime
import urllib2
import StringIO

logging.basicConfig(filename='prm.log', level=logging.INFO)

CACHE_DIR = os.path.join(os.path.abspath('.'), 'cache')


def init_cache():
    if not os.path.isdir(CACHE_DIR):
        os.mkdir(CACHE_DIR)


def get_cache_filename(url, with_ts=False):
    cache_fname = md5(url).hexdigest()
    if with_ts:
        cache_fname += '-{}'.format(int(time()))
    cache_fname += '.html'
    cache_file = os.path.join(CACHE_DIR, cache_fname)
    return cache_file


def load_previous(url):
    cache_file = get_cache_filename(url)
    cache = None
    if os.path.isfile(cache_file):
        with open(cache_file) as fs:
            cache = fs.read()
    return cache


def load_current(url):
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', 'Midnight Border Collies Puppy Reservation Monitor')]
    try:
        response = opener.open(url)

        content = StringIO.StringIO()
        parsed = lxml.html.parse(response)
        parsed.getroot().make_links_absolute()
        parsed.write(content)
        content = content.getvalue()
    except Exception, e:
        logging.error("Unable to retrieve url: %s. %s" % (url, e))
        content = None
    return content


def save_version(url, content):
    cache_file = get_cache_filename(url)
    if os.path.isfile(cache_file):
        backup = get_cache_filename(url, with_ts=True)
        os.rename(cache_file, backup)
    with open(cache_file, 'w') as fs:
        fs.write(content)


def check_page(url):
    diff = None
    old_version = load_previous(url)
    new_version = load_current(url)
    if new_version is None:
        return None

    if old_version != new_version and not any([old_version is None, new_version is None]):
        diff = htmldiff(old_version, new_version)
        if new_version is not None:
            save_version(url, new_version)
    elif old_version is None and new_version is not None:
        save_version(url, new_version)
        logging.info('No previous version of page found for url: {}'.format(url))
    elif new_version is None:
        # There was an error
        logging.error('There was an error retrieving new version of url, see requests log: {}'.format(url))
    else:
        logging.info("No change in page found: {}".format(url))
    return diff


def send_email(from_email, to_email_list, subject, html, smtp_host, smtp_port=587, username=None, password=None):
    message = Message(From=from_email, To=to_email_list, charset='utf-8')
    # Keep from creating threads in gmail...
    message.Subject = "{} -- {}".format(subject, datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
    message.Html = html.encode('utf-8')
    message.Body = 'See the HTML!'

    sender = Mailer(host=smtp_host, port=smtp_port, use_tls=True, usr=username, pwd=password)
    if username is not None:
        sender.login(username, password)
    sender.send(message)


def monitor(monitor_pages, email_host, email_port, email_user, email_password, email_tos):
    for page in monitor_pages:
        diff = check_page(page)
        if diff is not None:
            send_email(email_user, email_tos, 'A new puppy has been reserved!', diff, email_host, email_port, email_user, email_password)
