import textwrap
from itertools import repeat

from dateutil import rrule
from django.utils.translation import gettext_lazy as _

from pretalx.common.console import LR, UD, get_separator


def draw_schedule_list(data):
    result = ""
    for date in data:
        talk_list = sorted(
            (talk for room in date["rooms"] for talk in room.get("talks", [])),
            key=lambda x: x.start,
        )
        if talk_list:
            result += "\n\033[33m{:%Y-%m-%d}\033[0m\n".format(date["start"])
            result += "".join(
                "* \033[33m{:%H:%M}\033[0m ".format(talk.start)
                + (
                    "{}, {} ({}); in {}\n".format(
                        talk.submission.title,
                        talk.submission.display_speaker_names or _("No speakers"),
                        talk.submission.content_locale,
                        talk.room.name,
                    )
                    if talk.submission
                    else "{} in {}\n".format(talk.description, talk.room.name)
                )
                for talk in talk_list
            )
    return result


def talk_card(talk, col_width):
    empty_line = " " * col_width
    text_width = col_width - 4
    titlelines = textwrap.wrap(
        talk.submission.title if talk.submission else str(talk.description),
        text_width,
    )
    height = talk.duration // 5 - 1
    yielded_lines = 0

    max_title_lines = 1 if height <= 5 else height - 4
    if len(titlelines) > max_title_lines:
        titlelines, remainder = (
            titlelines[:max_title_lines],
            titlelines[max_title_lines:],
        )
        last_line = titlelines[-1] + " " + " ".join(remainder)
        titlelines[-1] = last_line[: text_width - 1] + "…"

    height_after_title = height - len(titlelines)
    join_speaker_and_locale = height_after_title <= 3 and talk.submission
    speaker_str = talk.submission.display_speaker_names if talk.submission else ""
    cutoff = (text_width - 4) if join_speaker_and_locale else text_width
    speaker_str = (
        speaker_str[: cutoff - 1] + "…" if len(speaker_str) > cutoff else speaker_str
    )

    if height > 4:
        yield empty_line
        yielded_lines += 1
    for line in titlelines:
        yield f"  \033[1m{line:<{text_width}}\033[0m  "
        yielded_lines += 1
    if height_after_title > 2:
        yield empty_line
        yielded_lines += 1
    if speaker_str:
        if join_speaker_and_locale:
            yield (
                f"  \033[33m{speaker_str:<{text_width-4}}\033[0m"
                f"  \033[38;5;246m{talk.submission.content_locale:<2}\033[0m  "
            )
            yielded_lines += 1
        else:
            yield f"  \033[33m{speaker_str:<{text_width}}\033[0m  "
            yielded_lines += 1
            if height_after_title > 4:
                yield empty_line
                yielded_lines += 1
            yield " " * (
                text_width - 2
            ) + f"  \033[38;5;246m{talk.submission.content_locale}\033[0m  "
            yielded_lines += 1
    elif talk.submission:
        yield " " * (
            text_width - 2
        ) + f"  \033[38;5;246m{talk.submission.content_locale}\033[0m  "
        yielded_lines += 1
    for __ in repeat(None, height - yielded_lines + 1):
        yield empty_line


def get_line_parts(start1, start2, end1, end2, run1, run2, fill_char):
    start_end = [end2, start2, start1, end1]
    result = []
    if run1 and (start2 or end2):
        result.append("├")
    elif run2 and (start1 or end1):
        result.append("┤")
    elif any(start_end):
        result.append(get_separator(*map(bool, start_end)))
    elif run1 or run2:
        result.append(UD)
    else:
        result.append(fill_char)
    return result


def draw_dt_line(
    dt,
    is_tick,
    starting_events,
    running_events,
    ending_events,
    rooms,
    col_width,
    cards_by_id,
):
    line_parts = [f"{dt:%H:%M} --" if is_tick else " " * 8]
    fill_char = "-" if is_tick else " "

    room = rooms[0]
    start, run, end = (
        starting_events[room],
        running_events[room],
        ending_events[room],
    )

    if start or end:
        line_parts.append(
            get_separator(bool(end), bool(start), False, False) + LR * col_width
        )
    elif run:
        line_parts.append(UD + next(cards_by_id[run.pk]))
    else:
        line_parts.append(fill_char * (col_width + 1))

    for loc1, loc2 in zip(rooms[:-1], rooms[1:]):
        start1, run1, end1 = (
            starting_events[loc1],
            running_events[loc1],
            ending_events[loc1],
        )
        start2, run2, end2 = (
            starting_events[loc2],
            running_events[loc2],
            ending_events[loc2],
        )
        line_parts += get_line_parts(
            start1, start2, end1, end2, run1, run2, fill_char=fill_char
        )
        if run2:
            line_parts.append(next(cards_by_id[run2.pk]))
        elif start2 or end2:
            line_parts.append(LR * col_width)
        else:
            line_parts.append(fill_char * col_width)

    room = rooms[-1]
    start, run, end = (
        starting_events[room],
        running_events[room],
        ending_events[room],
    )

    if start or end:
        line_parts.append(get_separator(False, False, bool(start), bool(end)))
    elif run:
        line_parts.append(UD)
    else:
        line_parts.append(fill_char)
    return "".join(line_parts)


def draw_grid_for_day(day, col_width=20):
    talk_list = sorted(
        (talk for room in day["rooms"] for talk in room.get("talks", [])),
        key=lambda x: x.start,
    )
    if not talk_list:
        return None

    global_start = day.get("first_start", min(talk.start for talk in talk_list))
    global_end = day.get("last_end", max(talk.end for talk in talk_list))
    talks_by_room = {str(r["name"]): r["talks"] for r in day["rooms"]}
    cards_by_id = {talk.pk: talk_card(talk, col_width) for talk in talk_list}
    rooms = list(talks_by_room.keys())
    lines = ["        | " + " | ".join(f"{room:<{col_width-2}}" for room in rooms)]
    tick_times = rrule.rrule(
        rrule.HOURLY,
        byminute=(0, 30),
        dtstart=global_start,
        until=global_end,
    )

    for hour in rrule.rrule(
        rrule.HOURLY,
        byminute=range(0, 60, 5),
        dtstart=global_start,
        until=global_end,
    ):
        starting_events = {
            room: next((e for e in talks_by_room[room] if e.start == hour), None)
            for room in rooms
        }
        running_events = {
            room: next(
                (e for e in talks_by_room[room] if e.start < hour < e.real_end),
                None,
            )
            for room in rooms
        }
        ending_events = {
            room: next((e for e in talks_by_room[room] if e.real_end == hour), None)
            for room in rooms
        }
        lines.append(
            draw_dt_line(
                hour,
                hour in tick_times,
                starting_events,
                running_events,
                ending_events,
                rooms,
                col_width,
                cards_by_id,
            )
        )
    return "\n".join(lines)


def draw_schedule_grid(data, col_width=20):
    result = ""
    for date in data:
        result += "\n\033[33m{:%Y-%m-%d}\033[0m\n".format(date["start"])
        table = draw_grid_for_day(date, col_width=col_width)
        if table:
            result += table
        else:
            result += "No talks on this day.\n"
    return result


def draw_ascii_schedule(data, output_format="table"):
    if output_format == "list":
        return draw_schedule_list(data)
    return draw_schedule_grid(data, col_width=20)
