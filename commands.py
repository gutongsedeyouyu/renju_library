import sys
import config

from account.models import User


def main():
    config.config()
    command = sys.argv[1]
    if command == 'user_clear_expired_uncompleted_bindings':
        User.clear_expired_uncompleted_bindings()
    else:
        pass


if __name__ == '__main__':
    main()
