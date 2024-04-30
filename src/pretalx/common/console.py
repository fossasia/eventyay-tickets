import os
import textwrap
from contextlib import suppress
from itertools import repeat
from pathlib import Path
from sys import executable

BOLD = "\033[1m"
RESET = "\033[0m"
UD = "│"
LR = "─"
SEPARATORS = {
    (False, True, True, False): "┬",
    (True, False, False, True): "┴",
    (False, False, True, True): "┤",
    (True, True, False, False): "├",
    (False, True, False, True): "┼",
    (True, False, True, False): "┼",
}


def get_separator(*args):
    """(upright, downright, downleft, upleft): Tuple[bool] -> separator:

    str.
    """
    if sum(args) >= 3:
        return "┼"
    if sum(args) == 1:
        return ("└", "┌", "┐", "┘")[args.index(True)]
    return SEPARATORS[tuple(args)]


def start_box(size):
    try:
        print("┏" + "━" * size + "┓")
    except (UnicodeDecodeError, UnicodeEncodeError):  # pragma: no cover
        print("-" * (size + 2))


def end_box(size):
    try:
        print("┗" + "━" * size + "┛")
    except (UnicodeDecodeError, UnicodeEncodeError):  # pragma: no cover
        print("-" * (size + 2))


def print_line(string, box=False, bold=False, color=None, size=None):
    text_length = len(string)
    alt_string = string
    if bold:
        string = f"{BOLD}{string}{RESET}"
    if color:
        string = f"{color}{string}{RESET}"
    if box:
        if size:
            if text_length + 2 < size:
                string += " " * (size - text_length - 2)
                alt_string += " " * (size - text_length - 2)
        string = f"┃ {string} ┃"
        alt_string = f"| {alt_string} |"
    try:
        print(string)
    except (UnicodeDecodeError, UnicodeEncodeError):  # pragma: no cover
        try:
            print(alt_string)
        except (UnicodeDecodeError, UnicodeEncodeError):
            print("unprintable setting")


def log_initial(*, debug, config_files, db_name, db_backend, LOG_DIR, plugins):
    from pretalx import __version__

    with suppress(Exception):  # geteuid is not available on all OS
        if os.geteuid() == 0:
            print_line("You are running pretalx as root, why?", bold=True)

    lines = [
        (f"pretalx v{__version__}", True),
        (f'Settings:  {", ".join(config_files)}', False),
        (f"Database:  {db_name} ({db_backend})", False),
        (f"Logging:   {LOG_DIR}", False),
        (f"Root dir:  {Path(__file__).parent.parent.parent}", False),
        (f"Python:    {executable}", False),
    ]
    if plugins:
        plugin_lines = textwrap.wrap(", ".join(plugins), width=92)
        lines.append((f"Plugins:   {plugin_lines[0]}", False))
        lines += [(" " * 11 + line, False) for line in plugin_lines[1:]]
    if debug:
        lines += [("DEVELOPMENT MODE, DO NOT USE IN PRODUCTION!", True)]
    image = """
┏━━━━━━━━━━┓
┃  ┌─·──╮  ┃
┃  │  O │  ┃
┃  │ ┌──╯  ┃
┃  └─┘     ┃
┗━━━┯━┯━━━━┛
    ╰─╯
    """.strip().split(
        "\n"
    )
    img_width = len(image[0])
    image[-1] += " " * (img_width - len(image[-1]))
    image += [" " * img_width for _ in repeat(None, (len(lines) - len(image)))]

    lines = [(f"{image[n]}  {line[0]}", line[1]) for n, line in enumerate(lines)]

    size = max(len(line[0]) for line in lines) + 4
    start_box(size)
    for line in lines:
        print_line(line[0], box=True, bold=line[1], size=size)
    end_box(size)
