class BaseRecordingProvider:
    def __init__(self, event):
        self.event = event
        super().__init__()

    def get_recording(self, submission):
        """
        Returns a dictionary {"iframe": …, "csp_header": …}
        Both the iframe and the csp_header should be strings.
        """
        raise NotImplementedError
