import re
import logging
from datetime import datetime
from random import random
from hashlib import md5

from mongoengine import EmbeddedDocument
from mongoengine.fields import StringField, IntField, DateTimeField, ListField, EmbeddedDocumentField
from tornado.template import Loader

from core.models import BaseModel
from core.utils.sms import send_sms
from core.utils.mail import send_mail


USER_STATUSES = ((1, 'Enabled'),
                 (9, 'Disabled'))

USER_PERMISSIONS = {'user': ('user', ),
                    'root': ('user', 'root')}

USER_ROLES = USER_PERMISSIONS.keys()

CELLPHONE_PATTERN = re.compile('^(\+86)([0-9]{11})$')

EMAIL_PATTERN = re.compile('^([0-9a-zA-Z._\-]+)@([0-9a-zA-Z]+[\.0-9a-zA-Z]+)$')


class IdentityAlreadyInUse(Exception):
    pass


class BindingAlreadyVerified(Exception):
    pass


class Captcha(EmbeddedDocument):
    captcha = StringField()
    expireTime = DateTimeField()


class User(BaseModel):
    userName = StringField(unique=True, sparse=True, regex=re.compile('^[^\s+@]+$'))
    cellphone = StringField(unique=True, sparse=True, regex=CELLPHONE_PATTERN)
    email = StringField(unique=True, sparse=True, regex=EMAIL_PATTERN)
    password = StringField(required=True)
    nickName = StringField()
    roles = ListField(StringField(choices=USER_ROLES), required=True)
    status = IntField(required=True, choices=USER_STATUSES)
    cellphoneBindingCaptcha = EmbeddedDocumentField(Captcha)
    cellphoneAuthCaptcha = EmbeddedDocumentField(Captcha)
    emailBindingCaptcha = EmbeddedDocumentField(Captcha)
    emailAuthCaptcha = EmbeddedDocumentField(Captcha)
    meta = {
        'indexes': [('status', '-updateTime'), '-createTime'],
        'ordering': ['status', '-updateTime']
    }

    @property
    def permissions(self):
        """Return the user's permissions.
        """
        permissions = set()
        for role in self.roles:
            if role in USER_PERMISSIONS:
                permissions.update(USER_PERMISSIONS[role])
            else:
                logging.warning('Invalid role: {0}'.format(role))
        return list(permissions)

    def to_vo(self, detail=False, admin=False, **kwargs):
        vo = super().to_vo(**kwargs)
        if detail or admin:
            if self.userName:
                vo['userName'] = self.userName
            if self.cellphone:
                vo['cellphone'] = self.cellphone
            if self.email:
                vo['email'] = self.email
            if self.nickName:
                vo['nickName'] = self.nickName
        return vo

    @classmethod
    def clean_attributes(cls, **attributes):
        """By calling the 'save_and_index' method, you are not allowed to change a user's userName, cellphone, email...
        """
        for attribute in attributes:
            if attribute in {'userName', 'cellphone', 'email', 'password',
                             'cellphoneBindingCaptcha', 'emailBindingCaptcha',
                             'cellphoneAuthCaptcha', 'emailAuthCaptcha'}:
                raise Exception('Not allowed.')
        return attributes

    @staticmethod
    def create_or_register(user, identity, password=None, nick_name=None, roles=None, **kwargs):
        """Create or register a new user with an identity, the identity can be a cellphone, an email or a user name.

        This method can be called with the same identity again and will work correctly without complaining that
        the identity already exists before the 'verify_binding_captcha' step passed.

        If password is not provided when calling this method, it will be stored as an invalid persistent password.
        This is helpful in 2 cases:
        1) The registration process is designed to provide password in the 'verify_binding_captcha' step;
        2) The user is designed not to be able to login by password.
        """
        if not identity:
            raise Exception('Identity is not provided.')
        if CELLPHONE_PATTERN.match(identity):
            new_user = User.objects(cellphone=identity).first()
            if new_user and (not new_user.cellphoneBindingCaptcha or
                             new_user.userName or
                             new_user.email or
                             new_user.status != 1):
                raise IdentityAlreadyInUse
            if not new_user:
                new_user = User(cellphone=identity, cellphoneBindingCaptcha=Captcha(), status=1,
                                createBy=user, createTime=datetime.now())
        elif EMAIL_PATTERN.match(identity):
            new_user = User.objects(email=identity).first()
            if new_user and (not new_user.emailBindingCaptcha or
                             new_user.userName or
                             new_user.cellphone or
                             new_user.status != 1):
                raise IdentityAlreadyInUse
            if not new_user:
                new_user = User(email=identity, emailBindingCaptcha=Captcha(), status=1,
                                createBy=user, createTime=datetime.now())
        else:
            new_user = User.objects(userName=identity).first()
            if new_user:
                raise IdentityAlreadyInUse
            new_user = User(userName=identity, status=1,
                            createBy=user, createTime=datetime.now())
        new_user.password = new_user._persistent_password(password) if password else 'CanNotLoginByPassword'
        new_user.nickName = nick_name
        new_user.roles = roles
        for name, value in kwargs.items():
            new_user.__setattr__(name, value)
        return new_user._send_binding_captcha(cellphone=bool(new_user.cellphoneBindingCaptcha),
                                              email=bool(new_user.emailBindingCaptcha))

    def bind(self, identity):
        """Bind an identity for an existing user, the identity can be a cellphone, an email or a user name.
        """
        if not identity:
            raise Exception('Identity is not provided.')
        if CELLPHONE_PATTERN.match(identity):
            # Bind cellphone.
            if self.cellphone and not self.cellphoneBindingCaptcha:
                raise BindingAlreadyVerified if self.cellphone == identity else Exception('Not allowed.')
            self.cellphone = identity
            self.cellphoneBindingCaptcha = Captcha()
            return self._send_binding_captcha(cellphone=True)
        elif EMAIL_PATTERN.match(identity):
            # Bind email.
            if self.email and not self.emailBindingCaptcha:
                raise BindingAlreadyVerified if self.email == identity else Exception('Not allowed.')
            self.email = identity
            self.emailBindingCaptcha = Captcha()
            return self._send_binding_captcha(email=True)
        else:
            # Bind a user name, the user name can not be changed once bound.
            if self.userName:
                if self.userName != identity:
                    raise Exception('Not allowed.')
                else:
                    return self
            self.userName = identity
            self.updateTime = datetime.now()
            return self.save()

    @staticmethod
    def resend_binding_captcha(identity):
        """Resend binding captcha to an identity, the identity can be either a cellphone or an email.
        """
        if not identity:
            raise Exception('Identity is not provided.')
        if CELLPHONE_PATTERN.match(identity):
            user = User.objects.get(cellphone=identity, status=1)
            if not user.cellphoneBindingCaptcha:
                raise BindingAlreadyVerified if user.cellphone == identity else Exception('Not allowed.')
            user.cellphone = identity
            user.cellphoneBindingCaptcha = Captcha()
            return user._send_binding_captcha(cellphone=True)
        elif EMAIL_PATTERN.match(identity):
            user = User.objects.get(email=identity, status=1)
            if not user.emailBindingCaptcha:
                raise BindingAlreadyVerified if user.email == identity else Exception('Not allowed.')
            user.email = identity
            user.emailBindingCaptcha = Captcha()
            return user._send_binding_captcha(email=True)
        else:
            raise Exception('Invalid identity.')

    @staticmethod
    def verify_binding_captcha(identity, captcha, password=None, nick_name=None):
        """Verify the captcha used for binding cellphone or email.

        WARNING:
        1) 'BindingAlreadyVerified' does not mean the verification is passed because captcha is not verified
        in that case;
        2) If password is neither provided in the 'create_or_register' step nor this step, the user will
        not be able to login by password untill 'reset_password'.
        """
        if not identity or not captcha:
            raise Exception('Identity or captcha is not provided.')
        if CELLPHONE_PATTERN.match(identity):
            user = User.objects.get(cellphone=identity, status=1)
            if not user.cellphoneBindingCaptcha:
                raise BindingAlreadyVerified
            now = datetime.now()
            if user.cellphoneBindingCaptcha.captcha != captcha or user.cellphoneBindingCaptcha.expireTime < now:
                raise Exception('Invalid captcha.')
            user.cellphoneBindingCaptcha = None
            if password:
                user.password = user._persistent_password(password)
            if nick_name:
                user.nickName = nick_name
            user.updateTime = now
            return user.save()
        elif EMAIL_PATTERN.match(identity):
            user = User.objects.get(email=identity, status=1)
            if not user.emailBindingCaptcha:
                raise BindingAlreadyVerified
            now = datetime.now()
            if user.emailBindingCaptcha.captcha != captcha or user.emailBindingCaptcha.expireTime < now:
                raise Exception('Invalid captcha.')
            user.emailBindingCaptcha = None
            if password:
                user.password = user._persistent_password(password)
            if nick_name:
                user.nickName = nick_name
            user.updateTime = now
            return user.save()
        else:
            raise Exception('Invalid identity.')

    def unbind(self, identity):
        """Unbind cellphone, email or user name for an existing user.

        This operation does not require verification and is designed for administrative purpose only.
        """
        if not identity:
            raise Exception('Identity is not provided.')
        if self.cellphone == identity:
            self.cellphone = None
            self.cellphoneBindingCaptcha = None
            self.cellphoneAuthCaptcha = None
            self.updateTime = datetime.now()
            return self.save()
        elif self.email == identity:
            self.email = None
            self.emailBindingCaptcha = None
            self.emailAuthCaptcha = None
            self.updateTime = datetime.now()
            return self.save()
        elif self.userName == identity:
            self.userName = None
            self.updateTime = datetime.now()
            return self.save()
        else:
            raise Exception('Invalid identity.')

    @staticmethod
    def auth_by_password(identity, password):
        """Authenticate a user by identity and password, the identity can be a cellphone, an email or a user name.
        """
        if not identity or not password:
            raise Exception('Identity or password is not provided.')
        try:
            if CELLPHONE_PATTERN.match(identity):
                user = User.objects.get(cellphone=identity, cellphoneBindingCaptcha__exists=False, status=1)
            elif EMAIL_PATTERN.match(identity):
                user = User.objects.get(email=identity, emailBindingCaptcha__exists=False, status=1)
            else:
                user = User.objects.get(userName=identity, status=1)
        except:
            raise Exception('Invalid identity or password.')
        else:
            if user._persistent_password(password) != user.password:
                raise Exception('Invalid identity or password.')
            return user

    @staticmethod
    def send_auth_captcha(identity):
        """Send authentication captcha to an identity, the identity can be a cellphone or an email.
        """
        if not identity:
            raise Exception('Identity is not provided.')
        if CELLPHONE_PATTERN.match(identity):
            user = User.objects.get(cellphone=identity, cellphoneBindingCaptcha__exists=False, status=1)
            now = datetime.now()
            user.cellphoneAuthCaptcha = Captcha(captcha=str(random())[2:8],
                                                expireTime=datetime.fromtimestamp(now.timestamp() + 30 * 60))
            user.updateTime = now
            user = user.save()
            template = Loader('templates/account/').load('cellphone_auth_captcha.txt')
            content = template.generate(captcha=user.cellphoneAuthCaptcha.captcha)
            send_sms(user.cellphone, content.decode('utf-8'))
            return user
        elif EMAIL_PATTERN.match(identity):
            user = User.objects.get(email=identity, emailBindingCaptcha__exists=False, status=1)
            now = datetime.now()
            user.emailAuthCaptcha = Captcha(captcha=md5((str(random())[2:]).encode('utf-8')).hexdigest(),
                                            expireTime=datetime.fromtimestamp(now.timestamp() + 24 * 60 * 60))
            user.updateTime = now
            user = user.save()
            template = Loader('templates/account/').load('email_auth_captcha.html')
            content = template.generate(captcha=user.emailAuthCaptcha.captcha)
            send_mail([user.email], '身份验证', content.decode('utf-8'))
            return user
        else:
            raise Exception('Invalid identity.')

    @staticmethod
    def verify_auth_captcha(identity, captcha):
        """Verify the captcha used for authenticating an identity, the identity can be a cellphone or an email.
        """
        if not identity or not captcha:
            raise Exception('Identity or captcha is not provided.')
        if CELLPHONE_PATTERN.match(identity):
            now = datetime.now()
            user = User.objects.get(cellphone=identity, cellphoneAuthCaptcha__exists=True,
                                    cellphoneAuthCaptcha__captcha=captcha,
                                    cellphoneAuthCaptcha__expireTime__gt=now, status=1)
            user.cellphoneAuthCaptcha = None
            user.updateTime = now
            return user.save()
        elif EMAIL_PATTERN.match(identity):
            now = datetime.now()
            user = User.objects.get(email=identity, emailAuthCaptcha__exists=True,
                                    emailAuthCaptcha__captcha=captcha,
                                    emailAuthCaptcha__expireTime__gt=now, status=1)
            user.emailAuthCaptcha = None
            user.updateTime = now
            return user.save()
        else:
            raise Exception('Invalid identity.')

    def change_password(self, old_password, new_password):
        """Change password.
        """
        if not old_password or not new_password:
            raise Exception('Password is not provided.')
        if self._persistent_password(old_password) != self.password:
            raise Exception('Incorrect password.')
        return self.reset_password(new_password)

    def reset_password(self, new_password):
        """Reset password.
        """
        if not new_password:
            raise Exception('Password is not provided.')
        self.password = self._persistent_password(new_password)
        self.updateTime = datetime.now()
        return self.save()

    @staticmethod
    def clear_expired_uncompleted_bindings():
        """Clear expired uncompleted bindings.
        """
        expire_time = datetime.fromtimestamp(datetime.now().timestamp() - 24 * 60 * 60)
        User.objects(cellphoneBindingCaptcha__exists=True, cellphoneBindingCaptcha__expireTime__lt=expire_time)\
            .update(cellphone=None, cellphoneBindingCaptcha=None, updateTime=datetime.now())
        User.objects(emailBindingCaptcha__exists=True, emailBindingCaptcha__expireTime__lt=expire_time)\
            .update(email=None, emailBindingCaptcha=None, updateTime=datetime.now())
        User.objects(userName__exists=False, cellphone__exists=False, email__exists=False).delete()

    def _persistent_password(self, password):
        """Convert a password to persistent password.
        """
        salt = self.createTime.strftime('%Y%m%d%H%M%S')
        password = md5(password.encode('utf-8')).hexdigest()
        password = md5('{1}{0}'.format(password, salt).encode('utf-8')).hexdigest()
        password = md5('{0}{1}'.format(password, salt).encode('utf-8')).hexdigest()
        return password

    def _send_binding_captcha(self, cellphone=False, email=False):
        """Send binding captcha.
        """
        # Prepare captcha.
        now = datetime.now()
        if cellphone and self.cellphoneBindingCaptcha:
            self.cellphoneBindingCaptcha = Captcha(captcha=str(random())[2:8],
                                                   expireTime=datetime.fromtimestamp(now.timestamp() + 30 * 60))
        if email and self.emailBindingCaptcha:
            self.emailBindingCaptcha = Captcha(captcha=md5((str(random())[2:]).encode('utf-8')).hexdigest(),
                                               expireTime=datetime.fromtimestamp(now.timestamp() + 24 * 60 * 60))
        # Save captcha.
        self.updateTime = now
        new_self = self.save()
        # Send captcha.
        if cellphone:
            template = Loader('templates/account/').load('cellphone_binding_captcha.txt')
            content = template.generate(captcha=new_self.cellphoneBindingCaptcha.captcha)
            send_sms(new_self.cellphone, content.decode('utf-8'))
        if email:
            template = Loader('templates/account/').load('email_binding_captcha.html')
            content = template.generate(captcha=new_self.emailBindingCaptcha.captcha)
            send_mail([new_self.email], '确认注册邮箱', content.decode('utf-8'))
        return new_self
