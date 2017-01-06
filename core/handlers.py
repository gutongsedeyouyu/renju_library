import re
import json
import time
import logging
from hashlib import md5
from random import random
from io import BytesIO
from uuid import uuid4
import os

import redis
from tornado.options import options
import tornado.web
from PIL import Image
from mutagen import File as mutagenFile

from account.models import User
from core.decorators import require_login
from core.utils.upload import upload_oss


_int_pattern, _float_pattern = re.compile('^-?[0-9]+$'), re.compile('^-?[0-9]+(\.[0-9]+)?$')

_redis_session_db_pool = redis.ConnectionPool(host=options.redis_session_db_host,
                                              port=options.redis_session_db_port,
                                              db=options.redis_session_db_database,
                                              decode_responses=True,
                                              socket_timeout=options.redis_session_db_timeout)

_redis_cache_db_pool = redis.ConnectionPool(host=options.redis_cache_db_host,
                                            port=options.redis_cache_db_port,
                                            db=options.redis_cache_db_database,
                                            decode_responses=True,
                                            socket_timeout=options.redis_cache_db_timeout)


class BaseHandler(tornado.web.RequestHandler):
    """Base class for page handlers and API handlers.
    """
    def initialize(self):
        # Ensure that we are getting the real IP.
        if 'X-Real-Ip' in self.request.headers:
            self.request.remote_ip = self.request.headers['X-Real-Ip']

    def get_str_argument(self, name, default='', strip=True):
        """Returns str value of the argument.
        """
        value = self.get_argument(name, default=default, strip=strip)
        return value if value else default

    def get_int_argument(self, name, default=0):
        """Returns int value of the argument.
        """
        raw_value = self.get_argument(name, '')
        return int(raw_value) if _int_pattern.match(raw_value) else default

    def get_float_argument(self, name, default=0.0):
        """Returns float value of the argument.
        """
        raw_value = self.get_argument(name, '')
        return float(raw_value) if _float_pattern.match(raw_value) else default

    def get_json_argument(self, name, default=None):
        """Returns JSON value of the argument.
        """
        raw_value = self.get_argument(name, None)
        return json.loads(raw_value) if raw_value else default

    def generate_session(self, user_id, permissions, **session_data):
        """Generate a new session and return the session ID.
        """
        session_id = None
        session_data['userId'] = user_id
        session_data['permissions'] = permissions
        session_data_str = json.dumps(session_data)
        timestamp = hex(int(time.time()))[2:]
        redis_client = redis.StrictRedis(connection_pool=_redis_session_db_pool)
        for retry_times in range(3):
            if retry_times > 0:
                logging.warning('Generated duplicate session ID, will try a new one.')
            session_id = md5(str(user_id).encode('utf-8')).hexdigest()
            session_id = '{1}{0}'.format(session_id, random())
            session_id = md5(session_id.encode('utf-8')).hexdigest()
            session_id = '{0}{1}'.format(session_id, random())
            session_id = md5(session_id.encode('utf-8')).hexdigest()
            session_id = '{0}{1}{2}'.format(timestamp, session_id[len(timestamp):len(session_id) - 1], retry_times)
            if redis_client.set(session_id, session_data_str, ex=options.session_expire_after, nx=True):
                break
        return session_id if redis_client.get(session_id) == session_data_str else None

    @property
    def language(self):
        """Get current language.
        """
        language = self.get_str_argument('locale', 'zh_CN').replace('-', '_', 1).split('_')[0]
        return language if language in {'en', 'ja', 'ko', 'zh'} else 'zh'

    def doc_to_vo(self, document, **kwargs):
        """Convert a MongoDB document to vo.
        """
        return document.to_vo(language=self.language, **kwargs)

    def docs_to_vos(self, documents, **kwargs):
        """Convert MongoDB documents to vos.
        """
        return [d.to_vo(language=self.language, **kwargs) for d in documents]

    def get_session(self):
        """Get session data.
        """
        if not self.session_id:
            return None
        try:
            redis_client = redis.StrictRedis(connection_pool=_redis_session_db_pool)
            session_data = redis_client.get(self.session_id)
            return json.loads(session_data) if session_data else None
        except:
            return None

    def set_session(self, session_data):
        """Save session data.
        """
        if not self.session_id:
            return False
        session_data_str = json.dumps(session_data)
        redis_client = redis.StrictRedis(connection_pool=_redis_session_db_pool)
        return redis_client.set(self.session_id, session_data_str, ex=options.session_expire_after, xx=True)

    def get_current_user(self):
        """Returns a fake user.
        """
        session = self.get_session()
        return User(id=session['userId']) if session else None

    def invalidate_session(self):
        """Invalidate current session.
        """
        if not self.session_id:
            return
        redis_client = redis.StrictRedis(connection_pool=_redis_session_db_pool)
        redis_client.delete(self.session_id)

    @property
    def session_id(self):
        """Returns current session ID.
        """
        raise NotImplementedError

    def on_login_required(self):
        """Generates output when login is required.
        """
        raise NotImplementedError

    def get_cache(self, key):
        """Get cached value.
        """
        redis_client = redis.StrictRedis(connection_pool=_redis_cache_db_pool)
        return redis_client.get(key)

    def set_cache(self, key, value, ex=None):
        """Set cache value.
        """
        redis_client = redis.StrictRedis(connection_pool=_redis_cache_db_pool)
        return redis_client.set(key, value, ex=ex)


class PageHandler(BaseHandler):
    """Base class for handlers rendering web pages.
    """
    @property
    def session_id(self):
        return self.get_cookie('sessionId', '')

    def on_login_required(self):
        self.redirect(options.login_url)


class ApiHandler(BaseHandler):
    @property
    def session_id(self):
        return self.get_str_argument('sessionId', '')

    def on_login_required(self):
        self.api_failed(7, 'Login required.')

    def api_succeed(self, data=None):
        """Call this method when the API execution succeed.
        """
        self._api_finished(0, None, data)

    def api_failed(self, status=5, message='Failed.'):
        """Call this method when the API execution failed.
        """
        self._api_finished(status, message, None)

    def _api_finished(self, status, message, data):
        result = {'status': status}
        if message:
            result['message'] = message
        if data:
            result['data'] = data
        if options.debug:
            logging.info(result)
        result_bytes = json.dumps(result).encode('utf-8')
        logging.info('Returning {0} bytes.'.format(len(result_bytes)))
        self.finish(result_bytes)

    def write_error(self, status_code, **kwargs):
        """Customize error response.
        """
        if status_code == 403:
            self.api_failed(4, 'Forbidden.')
        elif status_code == 404:
            self.api_failed(4, 'Forbidden.')
            logging.warning('Invalid URL. ({0})'.format(self.request.remote_ip))
        elif status_code == 405:
            self.api_failed(4, 'Forbidden.')
            logging.warning('Invalid request method. ({0})'.format(self.request.remote_ip))
        elif status_code == 500:
            self.api_failed(5, 'Internal error.')
            logging.warning('Internal error. ({0})'.format(self.request.remote_ip))
        else:
            self.api_failed(5, 'Internal error.')
            logging.warning('HTTP error {0}. ({1})'.format(status_code, self.request.remote_ip))


class InvalidUrlHandler(BaseHandler):
    """Handles invalid URLs.
    """
    def head(self, *args, **kwargs):
        raise tornado.web.HTTPError(404)

    def get(self, *args, **kwargs):
        raise tornado.web.HTTPError(404)

    def post(self, *args, **kwargs):
        raise tornado.web.HTTPError(404)

    def delete(self, *args, **kwargs):
        raise tornado.web.HTTPError(404)

    def patch(self, *args, **kwargs):
        raise tornado.web.HTTPError(404)

    def put(self, *args, **kwargs):
        raise tornado.web.HTTPError(404)

    def options(self, *args, **kwargs):
        raise tornado.web.HTTPError(404)


class UploadImageHandler(ApiHandler):
    """Upload image, only GIF, JPEG and PNG formats are allowed.
    """
    @require_login
    def post(self, *args, **kwargs):
        contents = self.request.files['file'][0]['body']
        if len(contents) > options.upload_image_max_length:
            return self.api_failed(4, 'Too big.')
        with Image.open(BytesIO(contents)) as image:
            if image.format not in options.upload_image_accept_formats:
                return self.api_failed(4, 'Invalid image format.')
            url = upload_oss(contents, image.format)
            return self.api_succeed({'url': url, 'width': image.width, 'height': image.height})


class UploadAudioHandler(ApiHandler):
    """Upload audio, only MP3 format is allowed.
    """
    @require_login
    def post(self, *args, **kwargs):
        contents = self.request.files['file'][0]['body']
        if len(contents) > options.upload_audio_max_length:
            return self.api_failed(4, 'Too big.')
        audio = mutagenFile(BytesIO(contents))
        if audio.mime[0] not in options.upload_audio_accept_formats:
            return self.api_failed(4, 'Invalid audio format.')
        url = upload_oss(contents, audio.mime[0].split('/')[1])
        return self.api_succeed({'url': url, 'duration': int(audio.info.length)})


class UploadVideoHandler(ApiHandler):
    """Upload video, only MP4 format is allowed.
    """
    @require_login
    def post(self, *args, **kwargs):
        # Video
        video_contents = self.request.files['file'][0]['body']
        if len(video_contents) > options.upload_video_max_length:
            return self.api_failed(4, 'Too big.')
        video_info = mutagenFile(BytesIO(video_contents))
        if video_info.mime[0] not in options.upload_video_accept_formats:
            return self.api_failed(4, 'Invalid video format.')
        video_extension = video_info.mime[0].split('/')[1]
        # Cover image
        video_duration = int(video_info.info.length)
        cover_contents, cover_extension = self.capture(video_contents, video_extension, video_duration)
        # Do upload video and cover image
        video_url = upload_oss(video_contents, video_extension)
        with Image.open(BytesIO(cover_contents)) as cover:
            cover_url = upload_oss(cover_contents, cover_extension)
            return self.api_succeed({'url': video_url, 'duration': video_duration,
                                     'cover': {'url': cover_url, 'width': cover.width, 'height': cover.height}})

    @staticmethod
    def capture(video_contents, video_extension, video_duration):
        cover_extension = 'JPEG'
        name = str(uuid4()).replace('-', '')
        video_name = '{0}.{1}'.format(name, video_extension)
        cover_name = '{0}.{1}'.format(name, cover_extension)
        with open(video_name, 'wb') as video_file:
            video_file.write(video_contents)
        os.system('ffmpeg -loglevel error -y -ss {0} -i {1} -vframes 1 {2}'.format(min(1, video_duration),
                                                                                   video_name, cover_name))
        with open(cover_name, 'rb') as cover_file:
            cover_contents = cover_file.read()
        os.system('rm {0} {1}'.format(video_name, cover_name))
        return cover_contents, cover_extension
