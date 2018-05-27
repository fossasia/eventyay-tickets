from enchant.tokenize import Filter

class EdgecaseFilter(Filter):
    """
    Some words might be special edgecase words that cannot really be
    spellchecked and whose addition to the wordlist doesn't make sense.
    Examples are hyphenated words, since the tokenization will split them
    apart, which it should do, but which will sometimes lead to incorrect
    spellchecks.  Therefore, these have to be skipped it manually beforehand.
    """

    def _skip(self, word):
        words = ["Woo-hoo", "tar.gz", "pretalx.common.exporter.BaseExporter"]
        if word in words:
            return True
        elif word.lower() in words:
            return True
