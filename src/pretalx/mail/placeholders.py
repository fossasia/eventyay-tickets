class BaseMailTextPlaceholder:
    """This is the base class for for all email text placeholders."""

    @property
    def required_context(self):
        """This property should return a list of all attribute names that need
        to be contained in the base context so that this placeholder is
        available.

        By default, it returns a list containing the string "event".
        """
        return ["event"]

    @property
    def identifier(self):
        """This should return the identifier of this placeholder in the
        email."""
        raise NotImplementedError()

    @property
    def is_visible(self):
        """You can set ``is_visible`` to ``False`` to hide this placeholder
        from the list, e.g. if it is just an alias."""
        return True

    def render(self, context):
        """This method is called to generate the actual text that is being used
        in the email.

        You will be passed a context dictionary with the base context
        attributes specified in ``required_context``. You are expected
        to return a plain-text string.
        """
        raise NotImplementedError()

    def render_sample(self, event):
        """This method is called to generate a text to be used in email
        previews.

        This may only depend on the event.
        """
        raise NotImplementedError()

    @property
    def explanation(self):
        return ""


class SimpleFunctionalMailTextPlaceholder(BaseMailTextPlaceholder):
    def __init__(
        self, identifier, args, func, sample, explanation=None, is_visible=True
    ):
        self._identifier = identifier
        self._args = args
        self._func = func
        self._sample = sample
        self._explanation = explanation
        self._is_visible = is_visible

    def __repr__(self):
        return f"SimpleFunctionalMailTextPlaceholder({self._identifier})"

    @property
    def identifier(self):
        return self._identifier

    @property
    def required_context(self):
        return self._args

    @property
    def explanation(self):
        return self._explanation or ""

    @property
    def is_visible(self):
        return self._is_visible

    def render(self, context):
        return self._func(**{k: context[k] for k in self._args})

    def render_sample(self, event):
        if callable(self._sample):
            return self._sample(event)
        else:
            return self._sample
