"""
This is a radically pared-down and partially rewritten version of the `releases` Sphinx extension
by Jeff 'bitprophet' Forcier. I stripped out all the good features relating to versioning and kept
only a linear changelog. Since it's not a package anymore, I also hardcoded the settings.

The original code is released under the BSD license, and so is this:

Copyright (c) 2020, Jeff Forcier & 2023, Tobias Kunze
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice,
      this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice,
      this list of conditions and the following disclaimer in the documentation
      and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
from collections import defaultdict
import re

from docutils import nodes, utils


ISSUE_TYPES = {"bug": "A04040", "feature": "40A056", "support": "4070A0"}
DEBUG = True


class Issue(nodes.Element):
    @property
    def type(self):
        return self["type_"]

    @property
    def number(self):
        return self.get("number", None)

    def __repr__(self):
        return f"<{self.type} #{self.number}>"


class Release(nodes.Element):
    @property
    def number(self):
        return self["number"]

    def __repr__(self):
        return "<release {}>".format(self.number)


def issues_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    parts = utils.unescape(text).split()
    issue_no = parts.pop(0)
    # Lol @ access back to Sphinx
    if issue_no not in ("-", "0"):
        ref = f"https://github.com/pretalx/pretalx/issues/{issue_no}"
        identifier = nodes.reference(rawtext, "#" + issue_no, refuri=ref, **options)
    else:
        identifier = None
        issue_no = None

    type_label_str = (
        f'[<span style="color: #{ISSUE_TYPES[name]};">{name.capitalize()}</span>]'
    )
    type_label = [nodes.raw(text=type_label_str, format="html")]
    github_link = [nodes.inline(text=" "), identifier] if identifier else []
    final_space = [] if identifier else [nodes.inline(text=" ")]
    nodelist = type_label + github_link + [nodes.inline(text=":")] + final_space

    node = Issue(number=issue_no, type_=name, nodelist=nodelist)
    return [node], []


year_arg_re = re.compile(r"^(.+?)\s*(?<!\x00)<(.*?)>$", re.DOTALL)


def release_role(name, rawtext, text, lineno, inliner, options={}, content=[]):
    match = year_arg_re.match(text)
    if not match:
        msg = inliner.reporter.error("Must specify release date!")
        return [inliner.problematic(rawtext, rawtext, msg)], [msg]
    number, date = match.group(1), match.group(2)

    if number == "unreleased":
        text = "Next Release"
        uri = "https://github.com/pretalx/pretalx/commits/main"
        date = None
    else:
        text = number
        uri = f"https://pypi.org/project/pretalx/{number.strip('v')}/"

    datespan = f' <span style="font-size: 75%;">{date}</span>' if date else ""
    link = f'<a class="reference external" href="{uri}">{text}</a>'
    header = f'<h2 style="margin-bottom: 0.3em;">{link}{datespan}</h2>'
    node = nodes.section(
        "", nodes.raw(rawtext="", text=header, format="html"), ids=[text]
    )

    release_node = Release(number=number, date=date, nodelist=[node])
    return [release_node], []


def collect_releases(entries):
    releases = defaultdict(list)
    current_release = None

    for entry in entries:
        # Issue object is always found in obj (LI) index 0 (first, often only
        # P) and is the 1st item within that (index 0 again).
        # Preserve all other contents of 'obj'.
        obj = entry[0].pop(0)
        rest = entry
        if isinstance(obj, Release):
            current_release = obj.number
            releases[obj.number] = {
                "release": obj,
                "version": obj.number,
                "entries": [],
            }
        else:
            if not current_release:
                raise ValueError("Found issue node before release node!")
            if not isinstance(obj, Issue):
                msg = f"Found issue node ({obj}) which is not an Issue! Please double-check your ReST syntax!"
                msg += f"Context: {str(obj.parent)}"
                raise ValueError(msg)

            releases[current_release]["entries"].append(
                {
                    "issue": obj,
                    "description": rest,
                    "number": obj.number,
                    "type": obj.type,
                }
            )

    order = {"feature": 0, "bug": 1, "support": 2}
    for release in releases.values():
        release["entries"] = sorted(release["entries"], key=lambda x: order[x["type"]])
    return releases


def construct_nodes(releases):
    result = []
    for d in releases.values():
        if not d["entries"]:
            continue
        obj = d["release"]
        entries = []
        for entry in d["entries"]:
            desc = entry["description"].deepcopy()
            # Expand any other issue roles found in the description - sometimes we refer to related issues inline.
            # (They can't be left as issue() objects at render time since that's undefined.)
            # Use [:] slicing (even under modern Python; the objects here are docutils Nodes whose .copy() is weird)
            # to avoid mutation during the loops.
            for index, node in enumerate(desc[:]):
                for subindex, subnode in enumerate(node[:]):
                    if isinstance(subnode, Issue):
                        lst = subnode["nodelist"]
                        desc[index][subindex : subindex + 1] = lst
            for node in reversed(entry["issue"]["nodelist"]):
                desc[0].insert(0, node)
            entries.append(desc)
        ul = nodes.bullet_list("", *entries)
        obj["nodelist"][0].append(ul)
        header = nodes.paragraph("", "", *obj["nodelist"])
        result.extend(header)
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
    for name in list(ISSUE_TYPES):
        app.add_role(name, issues_role)
    app.add_role("release", release_role)
    # Hook in our changelog transmutation at appropriate step
    app.connect("doctree-resolved", generate_changelog)
