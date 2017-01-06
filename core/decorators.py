from functools import wraps
import time
import logging
from hashlib import md5

import tornado.web
from tornado.options import options


def measure(method_or_function):
    """Decorator that measures a method or function's time of execution.
    """
    @wraps(method_or_function)
    def decorator(*args, **kwargs):
        elapsed_time = time.time()
        result = method_or_function(*args, **kwargs)
        elapsed_time = (time.time() - elapsed_time) * 1000
        logging.info('{0}.{1}() executed in {2:.2f} milliseconds.'.format(
                method_or_function.__module__, method_or_function.__qualname__, elapsed_time))
        return result
    return decorator


def require_permissions(*required_permissions):
    """Decorator that checks if the user has required permissions.
    """
    def decorator(method):
        @wraps(method)
        def actual_decorator(handler, *args, **kwargs):
            # Check if the user is logged in.
            session = handler.get_session()
            if not session:
                return handler.on_login_required()
            # Check if the user has sufficient permissions.
            own_permissions = session['permissions']
            for required_permission in required_permissions:
                if required_permission not in own_permissions:
                    logging.warning('Insufficient permissions. ({0})'.format(handler.request.remote_ip))
                    raise tornado.web.HTTPError(403)
            return method(handler, *args, **kwargs)
        return actual_decorator
    return decorator

require_login = require_permissions()


def check_params(*extra_keys):
    """Decorator that checks if a request's parameters are valid.
    """
    def decorator(method):
        @wraps(method)
        def actual_decorator(handler, *args, **kwargs):
            # Validate checksum.
            keys = ['appVersion', 'density', 'deviceId', 'deviceName', 'latitude', 'longitude', 'locale',
                    'screenHeight', 'screenWidth', 'sessionId', 'systemName', 'systemVersion', 'timestamp']
            if extra_keys:
                keys.extend(extra_keys)
            keys.sort()
            checksum = md5()
            for key in keys:
                checksum.update(handler.get_argument(key, '', strip=False).encode('utf-8'))
            if checksum.hexdigest() != handler.get_argument('checksum', ''):
                if options.debug:
                    for key in keys:
                        logging.warning('{0}: {1}'.format(key, handler.get_argument(key, '', strip=False)))
                logging.warning('Invalid checksum. ({0})'.format(handler.request.remote_ip))
                raise tornado.web.HTTPError(403)
            # The request's parameters are valid.
            return method(handler, *args, **kwargs)
        return actual_decorator
    return decorator
