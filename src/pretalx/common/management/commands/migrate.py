"""Django tries to be helpful by suggesting to run "makemigrations" in
alarmingly red font on every "migrate" run.

Since pretalx migrations are most often run by pretalx users, that is –
administrators, this is dangerous advice. Running "makemigrations" on a
project that you intend to continue to install from PyPI will lead to no
end of headaches, so by this very dirty hack, we're removing the
warnigns from user-facing output.
"""

import sys

from django.core.management.base import OutputWrapper
from django.core.management.commands.migrate import Command as Parent


class OutputFilter(OutputWrapper):
    banlist = (
        "Your models have changes that are not yet reflected",
        "Run 'manage.py makemigrations' to make new ",
    )

    def write(self, msg, style_func=None, ending=None):
        if any(b in msg for b in self.banlist):
            return
        super().write(msg, style_func, ending)


class Command(Parent):
    def __init__(self, stdout=None, stderr=None, no_color=False, force_color=False):
        super().__init__(stdout, stderr, no_color, force_color)
        self.stdout = OutputFilter(stdout or sys.stdout)
