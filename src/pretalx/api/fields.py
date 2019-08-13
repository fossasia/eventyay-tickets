from rest_framework.serializers import Field


class URLManField(Field):

    read_only = True
    write_only = False
    label = None
    source = '*'

    def __init__(self, *, urls, attribute='urls', full=True):
        self.urls = urls
        self.url_class = attribute
        self.full = full

    def to_representation(self, value):
        url_class = getattr(value, self.url_class)
        return {
            url: getattr(url_class, url).full() if self.full else getattr(url_class, url)
            for url in self.urls
        }
