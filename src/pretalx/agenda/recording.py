class BaseRecordingProvider:

    def get_recording(self, submission):
        """
        Returns a dictionary {"iframe": …, "csp_header": …}
        Both the iframe and the csp_header should be strings.
        """
        raise NotImplemented
