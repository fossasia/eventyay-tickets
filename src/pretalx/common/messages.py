import random
from abc import ABCMeta

_phrase_book = dict()


class MessagesMetaClass(ABCMeta):

    def __new__(mcls, class_name, bases, namespace, app):
        new = super().__new__(mcls, class_name, bases, namespace)
        _phrase_book[app] = new()
        return new

    def __init__(self, *args, app, **kwargs):
        super().__init__(*args, **kwargs)


class Messages(metaclass=MessagesMetaClass, app=''):

    def __getattribute__(self, attribute):
        ret = super().__getattribute__(attribute)
        if isinstance(ret, (list, tuple)):
            return random.choice(ret)
        return ret


class PhraseBook:

    def __getattribute__(self, attribute):
        return _phrase_book.get(attribute)


phrases = PhraseBook()
