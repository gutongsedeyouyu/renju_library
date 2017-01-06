from uuid import uuid4
from datetime import datetime

from oss2 import Auth, Bucket
from tornado.options import options


__auth = Auth(options.oss_access_key_id, options.oss_access_key_secret)
__bucket = Bucket(__auth, 'http://{0}'.format(options.oss_endpoint), options.oss_bucket_name)


def upload_oss(contents, name_or_extension):
    for i in range(3):
        if name_or_extension.find('.') >= 0:
            name = name_or_extension
        else:
            name = '{0}/{1}.{2}'.format(datetime.now().year, str(uuid4()).replace('-', ''), name_or_extension.lower())
        if __bucket.object_exists(name):
            continue
        __bucket.put_object(name, contents)
        is_image = name_or_extension in options.upload_image_accept_formats
        return 'http://{0}.{1}/{2}'.format(options.oss_bucket_name,
                                           options.oss_img_endpoint if is_image else options.oss_endpoint,
                                           name)
    raise Exception('Failed to upload to OSS due to duplicate object name.')
