from datetime import datetime
import logging
import math

from mongoengine import connect, Document
from tornado.options import options
from elasticsearch import Elasticsearch
from mongoengine.fields import ReferenceField, DateTimeField, EmbeddedDocument, EmbeddedDocumentField, IntField,\
    URLField


connect(options.mongo_db_database,
        host=options.mongo_db_host,
        port=options.mongo_db_port,
        serverSelectionTimeoutMS=options.mongo_db_timeout)

#
# The client is thread safe and can be used in a multi threaded environment. Best practice is to create
# a single global instance of the client and use it throughout your application. If your application is
# long-running consider turning on Sniffing to make sure the client is up to date on the cluster location.
#
_elasticsearch = Elasticsearch(options.elasticsearch_hosts,
                               sniff_on_start=False,
                               sniff_on_connection_fail=True,
                               sniffer_timeout=options.elasticsearch_timeout)


class BaseModel(Document):
    """Base class for MongoDB models.
    """
    createTime = DateTimeField(required=True)
    createBy = ReferenceField('User')
    updateTime = DateTimeField(required=True)
    updateBy = ReferenceField('User')
    meta = {
        'abstract': True
    }

    @classmethod
    def clean_attributes(cls, **attributes):
        """The 'clean' method used by the 'save_and_index' method.
        """
        return attributes

    @classmethod
    def save_and_index(cls, user=None, id=None, given_id=None, old_update_time=None, **attributes):
        """The recommended unified method for saving, updating and consistent updating a MongoDB document.

        Calling this method will record the instance's create time and update time automatically, and also index it
        for elasticsearch if necessary.
        """
        if not user:
            raise Exception
        attributes, now = cls.clean_attributes(**attributes), datetime.now()
        if given_id:
            # Save with given ID.
            instance = cls(id=given_id, createBy=user, updateBy=user,
                           createTime=now, updateTime=now, **attributes).save()
            instance.reload()
        elif not id:
            # Create a new document.
            instance = cls(id=None, createBy=user, updateBy=user,
                           createTime=now, updateTime=now, **attributes).save()
            instance.reload()
        elif not old_update_time:
            # Update.
            if cls.objects(id=id).update_one(upsert=False, updateBy=user, updateTime=now, **attributes) == 0:
                raise Exception('The {0} being updated does not exist.'.format(cls))
            instance = cls.objects.get(id=id)
        else:
            # Consistent update.
            if cls.objects(id=id, updateBy=user, updateTime=old_update_time).\
                    update_one(upsert=False, updateTime=now, **attributes) == 0:
                raise Exception('The {0} being updated does not exist or is out dated.'.format(cls))
            instance = cls.objects.get(id=id)
        # Index the instance if necessary.
        instance.index_for_search()
        return instance

    @staticmethod
    def paginate_query_set(query_set, page_num, page_size):
        """Paginate a mongoengine query set.
        """
        page_num, page_count = BaseModel.__calc_page_num_and_page_count(query_set.count(), page_num, page_size)
        return query_set[page_size * page_num: page_size * (page_num + 1)], page_num, page_count

    def delete(self, **write_concern):
        """Delete a document from MongoDB, also delete it from elasticsearch if necessary.
        """
        super().delete(**write_concern)
        self.__class__.delete_index(self.id)

    def index_for_search(self):
        """Index a MongoDB document for elasticsearch if necessary.

        1) If you want a subclass to be indexed in elasticsearch, it should implement the 'to_search_doc' method.
        2) This method is called by the 'save_and_index' method automatically, so you need to call it manually
        only when you see 'Failed to index ...' message in the error log.
        """
        if not self.id or not hasattr(self, 'to_search_doc'):
            return
        try:
            search_doc = self.to_search_doc()
            _elasticsearch.index(index=options.elasticsearch_index,
                                 doc_type=self.__class__.__name__.lower(),
                                 body=search_doc, id=str(self.id))
        except:
            logging.error('Failed to index {{class={0}.{1}, id={2}}} for search.'.
                          format(self.__class__.__module__, self.__class__.__name__, self.id))

    @classmethod
    def do_search(cls, query, page_num, page_size, **kwargs):
        """Do perform an elasticsearch search operation, return the paginated result.
        """
        class SearchResult:
            def __init__(self, hit):
                self.id = hit['_id']
                for key, value in hit['_source'].items():
                    if key.startswith('_'):
                        pass
                    else:
                        self.__dict__[key] = value
        search_result = _elasticsearch.search(index=options.elasticsearch_index,
                                              doc_type=cls.__name__.lower(),
                                              body={'query': query},
                                              size=page_size, from_=page_size * page_num,
                                              **kwargs)
        if not search_result or search_result['timed_out'] or search_result['hits']['total'] == 0:
            return 0, 1, []
        page_num, page_count = BaseModel.__calc_page_num_and_page_count(search_result['hits']['total'],
                                                                        page_num, page_size)
        return page_num, page_count, [SearchResult(hit) for hit in search_result['hits']['hits']]

    @classmethod
    def delete_index(cls, id):
        """Delete a document from elasticsearch.

        This method is called by the 'delete' method automatically, so you need to call it manually
        only when you see 'Failed to delete ...' message in the error log.
        """
        if not hasattr(cls, 'to_search_doc'):
            return
        try:
            _elasticsearch.delete(index=options.elasticsearch_index,
                                  doc_type=cls.__name__.lower(),
                                  id=str(id))
        except:
            logging.error('Failed to delete index for {{class={0}.{1}, id={2}}}.'.
                          format(cls.__module__, cls.__name__, id))

    def to_vo(self, **kwargs):
        return {'id': str(self.id),
                'createTime': int(self.createTime.timestamp() * 1000),
                'updateTime': int(self.updateTime.timestamp() * 1000)}

    @staticmethod
    def __calc_page_num_and_page_count(total_count, page_num, page_size):
        """Calculate page number and page count based on given total items count, page number and page size.
        """
        page_count = max(math.ceil(total_count / page_size), 1)
        if page_num > page_count - 1:
            page_num = page_count - 1
        if page_num < 0:
            page_num = 0
        return page_num, page_count


class Image(EmbeddedDocument):
    """Image information.

    url: image url
    width: image width
    height: image height
    """
    url = URLField(max_length=256, required=True)
    width = IntField(min_value=1, required=True)
    height = IntField(min_value=1, required=True)

    def to_vo(self, **kwargs):
        return {'url': self.url, 'width': self.width, 'height': self.height}


class Audio(EmbeddedDocument):
    """Audio information.

    url: audio url
    duration: audio duration in seconds
    """
    url = URLField(max_length=256, required=True)
    duration = IntField(min_value=1, required=True)

    def to_vo(self, **kwargs):
        return {'url': self.url, 'duration': self.duration}


class Video(EmbeddedDocument):
    """Video information.

    url: video url
    duration: video duration in seconds
    cover: video cover image
    """
    url = URLField(max_length=256, required=True)
    duration = IntField(min_value=1, required=True)
    cover = EmbeddedDocumentField(Image, required=True)

    def to_vo(self, **kwargs):
        return {'url': self.url, 'duration': self.duration, 'cover': self.cover.to_vo(**kwargs)}
