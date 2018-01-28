from datetime import datetime

from config import config
from account.models import User
from library.models import Library, HotKeyword


config()
root = User.objects(userName='root').first()
if not root:
    now = datetime.now()
    root = User(userName='root', password='', roles=['root'], status=1, createTime=now, updateTime=now)
    root.save()
