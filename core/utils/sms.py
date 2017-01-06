from threading import Thread
import urllib.parse
import urllib.request
import logging

from tornado.options import options


def send_sms(cellphone, message):
    """Send SMS message.
    """
    Thread(target=_do_send_sms, args=(cellphone, message)).start()


def _do_send_sms(cellphone, message):
    """http://www.5c.com.cn
    """
    url = options.send_sms_url
    data = urllib.parse.urlencode({'username': options.send_sms_user_name,
                                   'password_md5': options.send_sms_password_md5,
                                   'apikey': options.send_sms_api_key,
                                   'mobile': cellphone[3:],
                                   'content': message,
                                   'encode': 'utf-8'}).encode('ascii')
    headers = {'User-Agent': 'Mozilla/4.0 (compatible; MSIE 5.5; Windows NT)'}
    request = urllib.request.Request(url, data, headers)
    try:
        with urllib.request.urlopen(request, timeout=options.send_sms_timeout):
            pass
    except:
        logging.warning('Failed to send SMS message to {0}.'.format(cellphone))
    else:
        logging.warning('Sent SMS message to {0}.'.format(cellphone))
