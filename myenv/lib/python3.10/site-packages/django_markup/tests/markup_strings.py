"""
Sample Markup strings and their expected pendant.
"""

NONE = ("*This* is some text.", "*This* is some text.")

# Django's linebreaks filter
LINEBREAKS = ("*This* is some text.", "<p>*This* is some text.</p>")

# Simple Markdown
MARKDOWN = ("*This* is some text.", "<p><em>This</em> is some text.</p>")

# Markdown with PRE tag
MARKDOWN_PRE = (
    "    code line 1\n    code line 2\n",
    "<pre><code>code line 1\ncode line 2\n</code></pre>",
)

# Simple Markdown
MARKDOWN_JS_LINK = (
    '[Javascript Link](javascript:alert("123");)',
    '<p><a title="123">Javascript Link</a>;)</p>',
)

# Simple Textile
TEXTILE = (
    "*This* is some text.",
    "\t<p><strong>This</strong> is some text.</p>",
)

# Simple RestructuredText
RST = (
    "*This* is some text.",
    '<div class="document">\n<p><em>This</em> is some text.</p>\n</div>\n',
)

# Creole Sntax
CREOLE = (
    "This is **some //text//**.",
    "<p>This is <strong>some <i>text</i></strong>.</p>",
)
# Smartypants
SMARTYPANTS = ('This is "some" text.', "This is &#8220;some&#8221; text.")

# Windont
WIDONT = (
    "Widont does not leave anyone alone.",
    "Widont does not leave anyone&nbsp;alone.",
)
