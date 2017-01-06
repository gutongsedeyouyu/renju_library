from core.handlers import ApiHandler, PageHandler
from core.decorators import check_params
from account.models import User


class LoginApiHandler(ApiHandler):
    @check_params('userName', 'password')
    def post(self, *args, **kwargs):
        user_name = self.get_str_argument('userName', '')
        password = self.get_str_argument('password', '')
        if not user_name or not password:
            return self.api_failed(4, '用户名/密码不正确')
        try:
            user = User.auth_by_password(user_name, password)
            session_id = self.generate_session(str(user.id), user.permissions, nickName=user.nickName)
            return self.api_succeed({'sessionId': session_id})
        except:
            return self.api_failed(4, '用户名/密码不正确')


__api_handlers__ = [
    (r'^/account/api/login$', LoginApiHandler)
]


class LoginPageHandler(PageHandler):
    def get(self, *args, **kwargs):
        return self.render('account/login.html')


class LogoutPageHandler(PageHandler):
    def get(self, *args, **kwargs):
        self.invalidate_session()
        return self.redirect('/')


__page_handlers__ = [
    (r'^/account/login$', LoginPageHandler),
    (r'^/account/logout$', LogoutPageHandler)
]
