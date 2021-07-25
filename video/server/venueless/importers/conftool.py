import copy
import hashlib
import time

import dateutil.parser
import pytz
import requests
from django.utils.timezone import make_aware
from lxml import etree


def escape_markdown(text):
    text = text.replace("*", "\\*")
    return text


def fetch_schedule_from_conftool(url, password):
    nonce = int(time.time())
    passhash = hashlib.sha256((str(nonce) + password).encode()).hexdigest()
    r = requests.get(
        f"{url}?nonce={nonce}&passhash={passhash}&page=adminExport&export_select=sessions&form_include_deleted=0"
        f"&form_export_format=xml&cmd_create_export=true&form_export_sessions_options[]=presentations"
        f"&form_export_sessions_options[]=presentations_abstracts&form_export_sessions_options[]=presentations_subpapers"
        f"&form_export_sessions_options[]=presentations_downloads"
        f"&export_form_export_sessions_options[]=presentations_authors_extended_firstname"
        f"&form_export_sessions_options[]=all"
    )
    r.encoding = "utf-8"
    root = etree.fromstring(r.text.encode())

    tzname = "Europe/Berlin"

    result = {
        "version": str(nonce),
        "timezone": tzname,
        "tracks": [],
        "rooms": [],
        "speakers": [],
        "talks": [],
    }
    tz = pytz.timezone(tzname)
    room_time_combos = set()

    def parse_date(date_in):
        return make_aware(dateutil.parser.parse(date_in), tz)

    def get_or_create_track(color):
        if not color:
            return None
        existing = [r for r in result["rooms"] if r["id"] == color]
        if existing:
            return existing[0]["id"]
        new_id = str(len(result["tracks"]) + 1)
        result["tracks"].append(
            {
                "id": new_id,
                "name": "",
                "color": color,
            }
        )
        return new_id

    def get_or_create_room(session, fold=0):
        if not session.xpath("session_room_ID")[0].text:
            return None
        rid = session.xpath("session_room_ID")[0].text + ("i" * fold)
        existing = [r for r in result["rooms"] if r["id"] == rid]
        if existing:
            return existing[0]["id"]
        result["rooms"].append(
            {
                "id": rid,
                "name": session.xpath("session_room")[0].text,
            }
        )
        return rid

    def get_or_create_speaker(sid, name, organization):
        existing = [r for r in result["speakers"] if r["code"] == sid]
        if existing:
            return existing[0]["code"]
        result["speakers"].append(
            {
                "code": sid,
                "name": f"{name} ({organization})",
                "avatar": None,
            }
        )
        return sid

    for session in root.xpath("session"):
        start = parse_date(session.xpath("session_start")[0].text).isoformat()
        end = parse_date(session.xpath("session_end")[0].text).isoformat()
        code = session.xpath("session_ID")[0].text
        speakers = []

        # Duplicate room if multiple sessions are scheduled at the same time
        fold = 0
        while True:
            room = get_or_create_room(session, fold=fold)
            if not room or (room, start) not in room_time_combos:
                if room:
                    room_time_combos.add((room, start))
                break
            fold += 1

        for i in range(1, 100):
            if session.xpath(f"chair{i}") and session.xpath(f"chair{i}")[0].text:
                speakers.append(
                    get_or_create_speaker(
                        session.xpath(f"chair{i}_ID")[0].text,
                        session.xpath(f"chair{i}_name")[0].text,
                        session.xpath(f"chair{i}_organisation")[0].text,
                    )
                )
            else:
                break

        title = ": ".join(
            [
                f
                for f in (
                    session.xpath("session_short")[0].text,
                    session.xpath("session_title")[0].text,
                )
                if f
            ]
        )

        abstract = [
            session.xpath("session_info")[0].text,
            session.xpath("session_abstract")[0].text,
        ]

        presentations = int(session.xpath("presentations")[0].text or 0)
        for i in range(presentations):
            abstract += [
                "## " + escape_markdown(session.xpath(f"p{i + 1}_title")[0].text),
                "**"
                + escape_markdown(session.xpath(f"p{i + 1}_authors")[0].text)
                + "** \n"
                + "<em>"
                + escape_markdown(session.xpath(f"p{i + 1}_organisations")[0].text)
                + "</em> ",
                escape_markdown(session.xpath(f"p{i + 1}_abstract")[0].text),
            ]
            for j in ("A", "B", "C"):
                if session.xpath(f"p{i + 1}_download_{j}")[0].text:
                    abstract += ["* " + session.xpath(f"p{i + 1}_download_{j}")[0].text]
        abstract = "\n\n".join([a for a in abstract if a])

        talk = {
            "code": code if speakers or abstract else None,
            "title": title,
            "abstract": abstract,
            "start": start,
            "end": end,
            "room": room,
            "speakers": speakers,
            "track": get_or_create_track(session.xpath("session_colour_vivid")[0].text),
        }
        result["talks"].append(talk)

    for talk in result["talks"][:]:
        if not talk.get("code"):
            # Move breaks to all rooms
            for r in result["rooms"]:
                if (r["id"], talk["start"]) not in room_time_combos:
                    t = copy.copy(talk)
                    t["room"] = r["id"]
                    result["talks"].append(t)
            result["talks"].remove(talk)
        else:
            # Move talks without room to first room
            if not talk["room"]:
                talk["room"] = result["rooms"][0]["id"]

    return result
