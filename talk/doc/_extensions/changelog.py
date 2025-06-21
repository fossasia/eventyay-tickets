"""
Sphinx extension to build a useful, pretty changelog.

Usage in ReST files:
    - :release:`v1 <yyyy-mm-dd>`
    - :bug:`admin,123` Descriptive text
    - :feature:`admin` More text
    - :announcement:`123` Even more text

Numbers will be replaced with links to the corresponding GitHub issues, other tags
will refer to the categories defined below for grouping.

This Sphinx extension is heavily inspired by the `releases` Sphinx extension by Jeff
'bitprophet' Forcier.
"""
import re
from collections import defaultdict

from docutils import nodes, utils

ISSUE_TYPES = {
    "bug": {
        "color": "A04040",
        "label": "Fixed bug",
        "order": 1,
    },
    "feature": {
        "color": "40A056",
        "label": "Feature",
        "order": 0,
    },
    "announcement": {
        "color": "4070A0",
        "label": "Announcement",
        "order": 2,
    },
}

CATEGORIES = {
    "schedule": "Schedule",
    "cfp": "Call for Papers",
    "orga": "Organiser backend",
    "orga:email": "Organiser backend: E-Mails",
    "orga:speaker": "Organiser backend: Speaker management",
    "orga:submission": "Organiser backend: Session management",
    "orga:review": "Organiser backend: Review process",
    "orga:schedule": "Organiser backend: Scheduling",
    "api": "API",
    "lang": "Languages and translations",
    "": "General",
    "admin": "Administrators",
    "dev": "Developers and plugins",
}


class Issue(nodes.Element):
    @property
    def type(self):
        return self["type_"]

    @property
    def number(self):
        return self.get("number", None)

    @property
    def category(self):
        return self.get("category", None) or ""

    def __repr__(self):
        return f"<{self.type} #{self.number}>"


class Release(nodes.Element):
    @property
    def number(self):
        return self["number"]

    def __repr__(self):
        return "<release {}>".format(self.number)


def issues_role(name, rawtext, text, *args, **kwargs):
    attrs = [
        attr.strip()
        for attr in utils.unescape(text).split(",")
        if attr not in ("", "-", "0")
    ]

    categories = [c for c in attrs if c in CATEGORIES.keys()]
    category = categories[0] if categories else None

    issues = [i for i in attrs if i.isdigit()]
    issue = issues[0] if issues else None

    type_label_str = f'[<span style="color: #{ISSUE_TYPES[name]["color"]};">{ISSUE_TYPES[name]["label"]}</span>]'
    type_label = [nodes.raw(text=type_label_str, format="html")]

    nodelist = type_label + [nodes.inline(text=" ")]
    node = Issue(number=issue, type_=name, nodelist=nodelist, category=category)
    return [node], []


year_arg_re = re.compile(r"^(.+?)\s*(?<!\x00)<(.*?)>$", re.DOTALL)


def _build_release_node(number, url, date=None, text=None):
    text = text or number
    datespan = f' <span style="font-size: 75%;">{date}</span>' if date else ""
    link = f'<a class="reference external" href="{url}">{text}</a>'
    header = f'<h2 style="margin-bottom: 0.3em;">{link}{datespan}</h2>'
    node = nodes.section(
        "", nodes.raw(rawtext="", text=header, format="html"), ids=[number]
    )
    release_node = Release(number=number, date=date, nodelist=[node])
    return release_node


def release_role(name, rawtext, text, lineno, inliner, *args, **kwargs):
    match = year_arg_re.match(text)
    if not match:
        msg = inliner.reporter.error("Must specify release date!")
        return [inliner.problematic(rawtext, rawtext, msg)], [msg]
    number, date = match.group(1), match.group(2)
    text = number
    url = f"https://pypi.org/project/pretalx/{number.strip('v')}/"
    return [_build_release_node(number, url=url, date=date)], []


def collect_releases(entries):
    releases = [
        {
            "release": _build_release_node(
                "next",
                "https://github.com/pretalx/pretalx/commits/main/",
                text="Next Release",
            ),
            "entries": defaultdict(list),
        }
    ]

    for entry in entries:
        # Issue object is always found in obj (LI) index 0 (first, often only
        # P) and is the 1st item within that (index 0 again).
        # Preserve all other contents of 'obj'.
        obj = entry[0].pop(0)
        rest = entry
        if isinstance(obj, Release):
            # If the last release was empty, remove it
            if not releases[-1]["entries"]:
                releases.pop()
            releases.append({"release": obj, "entries": defaultdict(list)})
            continue
        elif not isinstance(obj, Issue):
            msg = f"Found issue node ({obj}) which is not an Issue! Please double-check your ReST syntax!"
            msg += f"Context: {str(obj.parent)}"
            raise ValueError(msg)

        releases[-1]["entries"][obj.category].append(
            {"issue": obj, "description": rest}
        )
    return releases


def construct_issue_nodes(issue, description):
    description = description.deepcopy()
    # Expand any other issue roles found in the description - sometimes we refer to related issues inline.
    # (They can't be left as issue() objects at render time since that's undefined.)
    # Use [:] slicing (even under modern Python; the objects here are docutils Nodes whose .copy() is weird)
    # to avoid mutation during the loops.
    for index, node in enumerate(description[:]):
        for subindex, subnode in enumerate(node[:]):
            if isinstance(subnode, Issue):
                lst = subnode["nodelist"]
                description[index][subindex : subindex + 1] = lst

    if issue.number:
        ref = f"https://github.com/pretalx/pretalx/issues/{issue.number}"
        identifier = nodes.reference("", "#" + issue.number, refuri=ref)
        github_link = [nodes.inline(text=" ("), identifier, nodes.inline(text=")")]
        description[0].extend(github_link)

    for node in reversed(issue["nodelist"]):
        description[0].insert(0, node)

    return description


def construct_release_nodes(release, entries):
    show_category_headers = len(entries) > 1
    for category in CATEGORIES.keys():
        issues = entries.get(category)
        if not issues:
            continue
        # add a sub-header for the category
        if show_category_headers:
            release["nodelist"][0].append(
                nodes.raw(
                    rawtext="",
                    text=f'<h4 style="margin-bottom: 0.3em;">{CATEGORIES[category]}</h4>',
                    format="html",
                )
            )
        issues = sorted(issues, key=lambda i: ISSUE_TYPES[i["issue"].type]["order"])
        issue_nodes = [
            construct_issue_nodes(issue["issue"], issue["description"])
            for issue in issues
        ]
        issue_ul = nodes.bullet_list("", *issue_nodes)
        release["nodelist"][0].append(issue_ul)

    result = nodes.paragraph("", "", *release["nodelist"])
    return result


def construct_nodes(releases):
    result = []
    for release in releases:
        result.extend(construct_release_nodes(release["release"], release["entries"]))
    return result


class BulletListVisitor(nodes.NodeVisitor):
    def __init__(self, document):
        nodes.NodeVisitor.__init__(self, document)

    def visit_bullet_list(self, node):
        releases = collect_releases(node.children)
        node.replace_self(construct_nodes(releases))

    def unknown_visit(self, node):
        pass


def generate_changelog(app, doctree, docname):
    if docname != "changelog":
        return
    # Replace the changelog bullet list with the formatted changelog
    changelog_visitor = BulletListVisitor(doctree)
    doctree.walk(changelog_visitor)


def setup(app):
    # Register intermediate roles
    for name in ISSUE_TYPES.keys():
        app.add_role(name, issues_role)
    app.add_role("release", release_role)
    # Hook in our changelog transmutation at appropriate step
    app.connect("doctree-resolved", generate_changelog)
