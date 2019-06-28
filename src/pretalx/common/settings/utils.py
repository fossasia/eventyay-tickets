from itertools import repeat
from pathlib import Path
from sys import executable


def log_initial(*, debug, config_files, db_name, db_backend, LOG_DIR, plugins):
    from pretalx.common.console import start_box, end_box, print_line
    from pretalx import __version__

    lines = [
        (f'pretalx v{__version__}', True),
        (f'Settings:  {", ".join(config_files)}', False),
        (f'Database:  {db_name} ({db_backend})', False),
        (f'Logging:   {LOG_DIR}', False),
        (f'Root dir:  {Path(__file__).parent.parent.parent}', False),
        (f'Python:    {executable}', False),
    ]
    if plugins:
        lines += [(f'Plugins:   {",".join(plugins)}', False)]
    if debug:
        lines += [('DEVELOPMENT MODE, DO NOT USE IN PRODUCTION!', True)]
    image = '''
┏━━━━━━━━━━┓
┃  ┌─·──╮  ┃
┃  │  O │  ┃
┃  │ ┌──╯  ┃
┃  └─┘     ┃
┗━━━┯━┯━━━━┛
    ╰─╯
    '''.strip().split(
        '\n'
    )
    img_width = len(image[0])
    image[-1] += ' ' * (img_width - len(image[-1]))
    image += [' ' * img_width for _ in repeat(None, (len(lines) - len(image)))]

    lines = [(f'{image[n]}  {line[0]}', line[1]) for n, line in enumerate(lines)]

    size = max(len(line[0]) for line in lines) + 4
    start_box(size)
    for line in lines:
        print_line(line[0], box=True, bold=line[1], size=size)
    end_box(size)


def reduce_dict(data):
    return {
        section_name: {
            key: value for key, value in section_content.items() if value is not None
        }
        for section_name, section_content in data.items()
    }
