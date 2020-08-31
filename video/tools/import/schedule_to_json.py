#!/usr/bin/env python3
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import pandas


def load_sheet(fname):
    if not Path(fname).exists():
        print("Could not find the file you want to import, aborting!")
        sys.exit(-1)

    sheets = {
        "Talks": {"usecols": "A:H,K", "parse_dates": [5, 6],},
        "Rooms": {"usecols": "A:C",},
        "Speakers": {"usecols": "A:B",},
        "Tracks": {"usecols": "A:C",},
    }
    return {
        title: pandas.read_excel(fname, sheet_name=title, header=0, **config)
        for title, config in sheets.items()
    }


def to_iso(value):
    return value.isoformat()


def to_list(value):
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


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


def transform_data(data, field_mapping, mandatory_fields, methods=None):
    result = []
    transformers = defaultdict(lambda: serializable)
    if methods:
        transformers.update(**methods)

    for _, row in data.iterrows():
        if not all(truthy(row.get(key)) for key in mandatory_fields):
            continue
        result.append(
            {
                field: transformers[field](row.get(excel))
                for field, excel in field_mapping.items()
            }
        )
    return result


def main():
    fname = sys.argv[-1]
    if fname == "schedule_to_json.py":
        print("Please call this script with the xlsx file you want to import!")
        return

    data = load_sheet(fname)

    result = {"version": data["Talks"].iat[4, 8]}
    result["rooms"] = transform_data(
        data["Rooms"],
        field_mapping={"id": "ID", "name": "Name"},
        mandatory_fields=["ID", "Name"],
    )
    result["tracks"] = transform_data(
        data["Tracks"],
        field_mapping={"id": "ID", "name": "Name", "color": "Colour"},
        mandatory_fields=["ID", "Name"],
    )
    result["speakers"] = transform_data(
        data["Speakers"],
        field_mapping={"code": "ID", "name": "Name", "avatar": "Avatar"},
        mandatory_fields=["ID", "Name"],
    )
    result["talks"] = transform_data(
        data["Talks"],
        field_mapping={
            "code": "ID",
            "title": "Title",
            "abstract": "Abstract",
            "speakers": "Speakers",
            "track": "Track ID",
            "room": "Room ID",
            "start": "Start",
            "end": "End",
        },
        mandatory_fields=["ID", "Title", "Start", "End", "Room ID"],
        methods={"start": to_iso, "end": to_iso, "speakers": to_list},
    )
    with open("schedule.json", "w") as fp:
        json.dump(result, fp, indent=4)


if __name__ == "__main__":
    main()
