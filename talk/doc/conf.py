import os
import sys
from datetime import date
from pretalx import __version__

sys.path.insert(0, os.path.abspath("../src"))
sys.path.insert(0, os.path.abspath("./_extensions"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pretalx.settings")
import django

django.setup()

project = "pretalx"
copyright = "2017-{}, Tobias Kunze".format(date.today().year)
author = "Tobias Kunze"
version = ".".join(__version__.split(".")[:2])
release = __version__

try:
    import enchant

    HAS_PYENCHANT = True
except:
    HAS_PYENCHANT = False

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
    "sphinxcontrib.httpdomain",
    "sphinxcontrib_django",
    "changelog",
]
if HAS_PYENCHANT:
    extensions.append("sphinxcontrib.spelling")

templates_path = ["_templates"]
source_suffix = {".rst": "restructuredtext"}
master_doc = "contents"

language = "en"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

pygments_style = "sphinx"
html_static_path = ["_themes/pretalx_theme/static", "_static"]
html_additional_pages = {"index": "index.html"}
html_extra_path = ["api/schema.yml"]
html_theme = "pretalx_theme"
html_theme_path = [os.path.abspath("_themes")]
html_context = {
    "display_github": True,  # Integrate GitHub
    "github_user": "pretalx",  # Username
    "github_repo": "pretalx",  # Repo name
    "github_version": "main",  # Version
    "conf_py_path": "/doc/",  # Path in the checkout to the docs root
}

linkcheck_ignore = [
    "https://pretalx.yourdomain.com",
    "http://localhost",
    "http://127.0.0.1",
    "/schema.yml",
    r"https://github.com/pretalx/pretalx/issues/\d+",  # The release notes are auto generated and contain a LOT of issue links
    r"https://github.com/pretalx/pretalx/issues/new",  # Requires login
    r"https://github.com/pretalx/pretalx/discussions/new",  # Requires login
    "https://translate.pretalx.com/projects/pretalx/pretalx/#repository",  # Only accessible by admins
    "https://github.com/fullcalendar/fullcalendar/releases/download/v6.1.5/fullcalendar-6.1.5.zip",  # redirects to cdn
    "https://www.patreon.com/rixx",  # spurious errors, sigh
]

htmlhelp_basename = "pretalxdoc"
autodoc_member_order = "groupwise"

if HAS_PYENCHANT:
    spelling_lang = "en_GB"
    spelling_word_list_filename = "spelling_wordlist.txt"
    spelling_show_suggestions = False

copybutton_prompt_text = (
    r">>> |\.\.\. |\$ |In \[\d*\]: | {2,5}\.\.\.: | {5,8}: |# |\(env\)\$ "
)
copybutton_prompt_is_regexp = True
copybutton_line_continuation_character = "\\"


def include_redoc_for_docs(app, page_name, template_name, context, doctree):
    if page_name == "api/resources":
        app.add_js_file("redoc.standalone.js")
        app.add_js_file("rest.js")


def setup(app):
    app.connect("html-page-context", include_redoc_for_docs)
