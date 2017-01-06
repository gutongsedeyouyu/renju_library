from mongoengine.fields import StringField, DictField, ListField

from core.models import BaseModel


#
# The EmbeddedDocument won't work when the depth of moves is too deep.
#
# class Move(EmbeddedDocument):
#     x = IntField(db_field='x')
#     y = IntField(db_field='y')
#     is_major = IntField(db_field='m')
#     label = StringField(db_field='l')
#     comment = StringField(db_field='c')
#     descendants = ListField(EmbeddedDocumentField('Move'), db_field='d')
#


class Library(BaseModel):
    title = StringField(max_length=40)
    blackPlayerName = StringField(max_length=40)
    whitePlayerName = StringField(max_length=40)
    manual = DictField(required=True)
    patterns = ListField(StringField())
    meta = {
        'indexes': ['-updateTime', ('patterns', '-updateTime')],
        'ordering': ['-updateTime']
    }

    @classmethod
    def clean_attributes(cls, **attributes):
        if 'manual' in attributes:
            attributes['patterns'] = Library.__extract_patterns(attributes['manual'])
        return attributes

    def to_vo(self, search=False, **kwargs):
        vo = super().to_vo(**kwargs)
        vo['title'] = self.title
        vo['blackPlayerName'] = self.blackPlayerName
        vo['whitePlayerName'] = self.whitePlayerName
        if search:
            descendants = [descendant for descendant in self.manual['d']]
            comments = [] if not self.manual['c'] else [self.manual['c']]
            while descendants:
                descendant = descendants.pop()
                if descendant['c']:
                    comments.append(descendant['c'])
                if descendant['d']:
                    descendants.extend(descendant['d'])
            vo['_comments'] = comments
        return vo

    def to_search_doc(self):
        return self.to_vo(search=True)

    @staticmethod
    def list_by_page(page_num, page_size=20):
        libraries = Library.objects.exclude('manual', 'patterns')
        return Library.paginate_query_set(libraries, page_num, page_size)

    @staticmethod
    def search_text_by_page(keyword, page_num, page_size=20):
        query = {'multi_match': {'query': keyword,
                                 'fields': ['title^2',
                                            'blackPlayerName^2',
                                            'whitePlayerName^2',
                                            '_comments']}}
        return Library.do_search(query, page_num, page_size)

    @staticmethod
    def search_manual_by_page(search_datas, page_num, page_size=20):
        libraries = Library.objects(patterns__in=search_datas).exclude('manual', 'patterns')
        return Library.paginate_query_set(libraries, page_num, page_size)

    @staticmethod
    def __extract_patterns(manual):
        descendants, max_length, part1, part2 = manual['d'], 30, list(), list()
        patterns = ['' for _ in range(max_length)]
        for i in range(max_length):
            major_found = False
            for descendant in descendants:
                if descendant['m'] == 1:
                    if i % 2 == 0:
                        part1.append('|{0}_{1}'.format(descendant['x'], descendant['y']))
                        part1.sort()
                    else:
                        part2.append('|{0}_{1}'.format(descendant['x'], descendant['y']))
                        part2.sort()
                    patterns[i] = ''.join(part1) + ''.join(part2)
                    major_found, descendants = True, descendant['d']
                    break
            if not major_found:
                break
        return patterns
