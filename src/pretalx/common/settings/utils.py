def log_initial(DEBUG, config_files, db_name, db_backend, LOG_DIR):
    from pretalx.common.console import start_box, end_box, print_line
    mode = 'development' if DEBUG else 'production'
    lines = [
        (f'This is pretalx calling, running in {mode} mode.', True),
        ('', False),
        (f'Settings:', True),
        (f'Read from: {config_files}', False),
        (f'Database: {db_name} ({db_backend})', False),
        (f'Logging:  {LOG_DIR}', False),
        ('', False),
    ]
    image = '''
┏━━━━━━━━━━┓
┃  ┌─·──╮  ┃
┃  │  O │  ┃
┃  │ ┌──╯  ┃
┃  └─┘     ┃
┗━━━┯━┯━━━━┛
    ╰─╯
    '''.strip().split('\n')

    lines = [(f'{image[n]}  {lines[n][0]}', lines[n][1]) for n in range(len(lines))]

    size = max(len(line[0]) for line in lines) + 4
    start_box(size)
    for line in lines:
        print_line(line[0], box=True, bold=line[1], size=size)
    end_box(size)


def reduce_dict(data):
    return {
        section_name: {
            key: value
            for key, value in section_content.items()
            if value is not None
        }
        for section_name, section_content in data.items()
    }
