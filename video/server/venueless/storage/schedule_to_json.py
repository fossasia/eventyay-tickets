import datetime as dt
import json
import math
from collections import defaultdict

import pandas
from dateutil.parser import parse
from django.core.exceptions import ValidationError


def load_sheet(io):
    sheets = {
        "Talks": {
            "usecols": "A:I,K",
            "parse_dates": [5, 6],
        },
        "Rooms": {
            "usecols": "A:C",
        },
        "Speakers": {
            "usecols": "A:D",
        },
        "Tracks": {
            "usecols": "A:C",
        },
    }
    return {
        title: pandas.read_excel(io, sheet_name=title, header=0, **config)
        for title, config in sheets.items()
    }


def to_iso(value):
    if not isinstance(value, dt.datetime):
        raise Exception("Not a valid date and time.")
    return value.isoformat()


def to_list(value):
    if not value or str(value) == "nan":
        return []
    value = str(value)
    return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]


def truthy(value):
    if isinstance(value, (list, dict, str, int, pandas.Timestamp)):
        return bool(value)
    if not value or pandas.isnull(value) or math.isnan(value):
        return False
    return True


def serializable(value):
    if isinstance(value, (list, dict, str)):
        return value

    if not truthy(value):
        return None

    if isinstance(value, (int, float)):
        if int(value) == value:
            return int(value)
        return value

    if not truthy(value):
        return None

    return value


def transform_data(data, table_name, field_mapping, mandatory_fields, methods=None):
    data = data[table_name]
    result = []
    transformers = defaultdict(lambda: serializable)
    if methods:
        transformers.update(**methods)

    for _, row in data.iterrows():
        truthy_fields = {key: truthy(row.get(key)) for key in mandatory_fields}
        if not any(truthy_fields.values()):
            continue  # empty row, probably
        if not all(truthy_fields.values()):
            missing = [key for key, value in truthy_fields.items() if not value]
            raise ValidationError(
                f"Missing key(s) in sheet {table_name}, row {_ + 1}: {missing}"
            )
        row_result = {}
        for field, excel in field_mapping.items():
            try:
                row_result[field] = transformers[field](row.get(excel))
            except Exception as e:
                raise ValidationError(
                    f"Error in sheet {table_name}, row {_ + 1} when importing column {excel}: {e}"
                )
        result.append(row_result)
    return result


def validate_data(data):
    room_ids = [room["id"] for room in data["rooms"]]
    track_ids = [track["id"] for track in data["tracks"]]
    speaker_ids = [speaker["code"] for speaker in data["speakers"]]
    for talk in data["talks"]:
        if not talk["start"]:
            raise ValidationError(
                f"Talk {talk['code']} ({talk['title']}) has no valid start datetime."
            )
        if not talk["end"]:
            raise ValidationError(
                f"Talk {talk['code']} ({talk['title']}) has no valid start datetime."
            )
        start = parse(talk["start"])
        end = parse(talk["end"])
        if start > end:
            raise ValidationError(
                f"Talk {talk['code']} ({talk['title']}) has a start that is later than its end."
            )
        if talk["track"] and not talk["track"] in track_ids:
            raise ValidationError(
                f"Talk {talk['code']} ({talk['title']}) has an invalid track ID."
            )
        if not talk["room"] in room_ids:
            raise ValidationError(
                f"Talk {talk['code']} ({talk['title']}) has an invalid room ID."
            )
        for speaker in talk.get("speakers", []):
            if speaker not in speaker_ids:
                raise ValidationError(
                    f"Talk {talk['code']} ({talk['title']}) has an unknown speaker ID: {speaker}."
                )


def convert(io):
    data = load_sheet(io)

    result = {"version": dt.datetime.now().isoformat()}
    result["rooms"] = transform_data(
        data,
        "Rooms",
        field_mapping={"id": "ID", "name": "Name"},
        mandatory_fields=["ID", "Name"],
    )
    result["tracks"] = transform_data(
        data,
        "Tracks",
        field_mapping={"id": "ID", "name": "Name", "color": "Colour"},
        mandatory_fields=["ID", "Name"],
    )
    result["speakers"] = transform_data(
        data,
        "Speakers",
        field_mapping={
            "code": "ID",
            "name": "Name",
            "avatar": "Avatar",
            "biography": "Biography",
        },
        mandatory_fields=["ID", "Name"],
        methods={"code": str},
    )
    result["talks"] = transform_data(
        data,
        "Talks",
        field_mapping={
            "code": "ID",
            "title": "Title",
            "abstract": "Abstract",
            "speakers": "Speaker IDs",
            "track": "Track ID",
            "room": "Room ID",
            "start": "Start",
            "end": "End",
            "url": "URL",
        },
        mandatory_fields=["Title", "Start", "End", "Room ID"],
        methods={"start": to_iso, "end": to_iso, "speakers": to_list},
    )
    validate_data(result)
    return json.dumps(result, indent=4)
