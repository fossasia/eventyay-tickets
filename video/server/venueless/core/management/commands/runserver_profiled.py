import logging
import signal

import yappi
from channels.management.commands.runserver import Command as RunserverCommand

logger = logging.getLogger(__name__)

yappi.set_clock_type("CPU")


class Command(RunserverCommand):
    def run(self, **options):
        options["use_reloader"] = False
        return super().run(**options)

    def print(self, *args, **kwargs):
        s = yappi.get_func_stats()
        s.sort("ttot")
        s.print_all(
            columns={
                0: ("name", 80),
                1: ("ncall", 8),
                2: ("tsub", 8),
                3: ("ttot", 8),
                4: ("tavg", 8),
            }
        )

    def inner_run(self, *args, **options):
        signal.signal(signal.SIGUSR1, self.print)
        try:
            with yappi.run():
                return super().inner_run(*args, **options)
        finally:
            self.print()
