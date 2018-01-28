import os

from tornado.options import options
import tornado.web
import tornado.httpserver
import tornado.ioloop

from config import config
import account.handlers
import library.handlers
from core.handlers import UploadImageHandler, UploadAudioHandler, UploadVideoHandler, InvalidUrlHandler


def main():
    config()
    handlers = list()
    handlers.extend([(r'^/$', tornado.web.RedirectHandler, {'url': '/library/hotKeywordList'}),
                     (r'^/common/uploadImage$', UploadImageHandler),
                     (r'^/common/uploadAudio$', UploadAudioHandler),
                     (r'^/common/uploadVideo$', UploadVideoHandler)])
    handlers.extend(account.handlers.__api_handlers__)
    handlers.extend(account.handlers.__page_handlers__)
    handlers.extend(library.handlers.__api_handlers__)
    handlers.extend(library.handlers.__page_handlers__)
    handlers.extend([(r'^.*$', InvalidUrlHandler)])
    application = tornado.web.Application(
            handlers=handlers,
            debug=options.debug,
            template_path=os.path.join(os.path.dirname(__file__), 'templates'))
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.bind(options.port)
    http_server.start(options.num_processes)
    tornado.ioloop.IOLoop.current().start()


if __name__ == '__main__':
    main()
