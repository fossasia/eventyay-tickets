class ConsumerException(Exception):
    def __init__(self, code, message=None):
        self.code = code
        self.message = message
