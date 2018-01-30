from core.handlers import ApiHandler, PageHandler
from core.decorators import check_params, require_permissions
from library.models import Library, HotKeyword


class LibraryApiSaveHandler(ApiHandler):
    @check_params('id', 'title', 'blackPlayerName', 'whitePlayerName', 'manual')
    @require_permissions('root')
    def post(self, *args, **kwargs):
        library_id = self.get_str_argument('id', '')
        title = self.get_str_argument('title', '')
        black_player_name = self.get_str_argument('blackPlayerName', '')
        white_player_name = self.get_str_argument('whitePlayerName', '')
        manual = self.get_json_argument('manual', {})
        library = Library.save_and_index(self.current_user, id=library_id, title=title,
                                         blackPlayerName=black_player_name, whitePlayerName=white_player_name,
                                         manual=manual)
        return self.api_succeeded({'id': str(library.id)})


class LibraryApiSaveHotKeywordHandler(ApiHandler):
    @check_params('id', 'keyword')
    @require_permissions('root')
    def post(self, *args, **kwargs):
        hot_keyword_id = self.get_str_argument('id', '')
        hot_keyword_keyword = self.get_str_argument('keyword', '')
        hot_keyword = HotKeyword.save_and_index(self.current_user, id=hot_keyword_id, keyword=hot_keyword_keyword)
        return self.api_succeeded({'id': str(hot_keyword.id)})


class LibraryApiDeleteHotKeywordHandler(ApiHandler):
    @check_params('id')
    @require_permissions('root')
    def post(self, *args, **kwargs):
        hot_keyword_id = self.get_str_argument('id', '')
        hot_keyword = HotKeyword.objects(id=hot_keyword_id)
        hot_keyword.delete()
        return self.api_succeeded()


__api_handlers__ = [
    (r'^/library/api/save$', LibraryApiSaveHandler),
    (r'^/library/api/saveHotKeyword$', LibraryApiSaveHotKeywordHandler),
    (r'^/library/api/deleteHotKeyword$', LibraryApiDeleteHotKeywordHandler)
]


class LibraryListHandler(PageHandler):
    def get(self, *args, **kwargs):
        session = self.get_session()
        page_num = self.get_int_argument('page', 0)
        libraries, page_num, page_count = Library.list_by_page(page_num)
        return self.render('library/list.html',
                           session=session, libraries=libraries, page_num=page_num, page_count=page_count)


class LibrarySearchHandler(PageHandler):
    def get(self, *args, **kwargs):
        return self.render('library/search.html')


class LibrarySearchTextHandler(PageHandler):
    def post(self, *args, **kwargs):
        keyword = self.get_str_argument('keyword', '')
        page_num = self.get_int_argument('page')
        page_num, page_count, libraries = Library.search_text_by_page(keyword, page_num)
        return self.render('library/search_text_results.html',
                           libraries=libraries, keyword=keyword, page_num=page_num, page_count=page_count)


class LibrarySearchManualHandler(PageHandler):
    def post(self, *args, **kwargs):
        search_datas = self.get_json_argument('searchDatas', [])
        page_num = self.get_int_argument('page')
        libraries, page_num, page_count = Library.search_manual_by_page(search_datas, page_num)
        return self.render('library/search_manual_results.html',
                           libraries=libraries, search_datas=search_datas, page_num=page_num, page_count=page_count)


class LibraryViewOrEditHandler(PageHandler):
    def get(self, *args, **kwargs):
        session = self.get_session()
        library_id = self.get_str_argument('id', '')
        # View/edit a blank library or an existing one.
        if len(library_id) == 0:
            return self.render('library/view_or_edit.html',
                               library=None,
                               can_edit=session and 'root' in session['permissions'])
        else:
            library = Library.objects.get(id=library_id)
            return self.render('library/view_or_edit.html',
                               library=library,
                               can_edit=session and 'root' in session['permissions'])


class LibraryHotKeywordListHandler(PageHandler):
    def get(self, *args, **kwargs):
        session = self.get_session()
        hot_keywords = HotKeyword.objects()
        return self.render('library/hot_keyword_list.html',
                           hotKeywords=hot_keywords, can_edit=session and 'root' in session['permissions'])


__page_handlers__ = [
    (r'^/library/list$', LibraryListHandler),
    (r'^/library/search$', LibrarySearchHandler),
    (r'^/library/searchText$', LibrarySearchTextHandler),
    (r'^/library/searchManual$', LibrarySearchManualHandler),
    (r'^/library/viewOrEdit$', LibraryViewOrEditHandler),
    (r'^/library/hotKeywordList$', LibraryHotKeywordListHandler)
]
