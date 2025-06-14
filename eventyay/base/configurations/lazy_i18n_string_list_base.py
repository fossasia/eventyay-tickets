import json
from collections import UserList

from i18nfield.strings import LazyI18nString


class LazyI18nStringListBase(UserList):
    def __init__(self, init_list=None):
        super().__init__()
        if init_list is not None:
            self.data = [v if isinstance(v, LazyI18nString) else LazyI18nString(v) for v in init_list]

    def serialize(self):
        return json.dumps([s.data for s in self.data])

    @classmethod
    def unserialize(cls, s):
        return cls(json.loads(s))


class LazyI18nStringList(LazyI18nStringListBase):
    def __init__(self, init_list=None):
        super().__init__(init_list)
