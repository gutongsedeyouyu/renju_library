from threading import Thread
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP
import logging

from tornado.options import options


def send_mail(recipient_list, subject, content):
    """Send mail.
    """
    Thread(target=_do_send_mail, args=(recipient_list, subject, content)).start()


def _do_send_mail(recipient_list, subject, content):
    """Do send mail.
    """
    message = MIMEMultipart()
    message['From'] = options.send_mail_user
    message['To'] = ', '.join(recipient_list)
    message['Subject'] = subject
    message.attach(MIMEText(content, 'html', 'utf-8'))
    try:
        with SMTP(options.send_mail_host, options.send_mail_port,
                  timeout=options.send_mail_timeout) as smtp_connection:
            smtp_connection.starttls()
            smtp_connection.login(options.send_mail_user, options.send_mail_password)
            smtp_connection.sendmail(options.send_mail_user, recipient_list, message.as_string())
    except:
        logging.warning('Failed to send mail to {0}'.format(recipient_list))
    else:
        logging.warning('Sent mail to {0}'.format(recipient_list))
