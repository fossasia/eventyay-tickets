import re

# banlist based on http://www.bannedwordlist.com/lists/swearWords.txt
banlist = [
    "anal",
    "anus",
    "arse",
    "ass",
    "balls",
    "bastard",
    "bitch",
    "biatch",
    "bloody",
    "blowjob",
    "bollock",
    "bollok",
    "boner",
    "boob",
    "bugger",
    "bum",
    "butt",
    "clitoris",
    "cock",
    "coon",
    "crap",
    "cunt",
    "damn",
    "dick",
    "dildo",
    "dyke",
    "fag",
    "feck",
    "fellate",
    "fellatio",
    "felching",
    "fuck",
    "fudgepacker",
    "flange",
    "goddamn",
    "hell",
    "homo",
    "jerk",
    "jizz",
    "knobend",
    "labia",
    "lmao",
    "lmfao",
    "muff",
    "nigger",
    "nigga",
    "omg",
    "penis",
    "piss",
    "poop",
    "prick",
    "pube",
    "pussy",
    "queer",
    "scrotum",
    "sex",
    "shit",
    "sh1t",
    "slut",
    "smegma",
    "spunk",
    "tit",
    "tosser",
    "turd",
    "twat",
    "vagina",
    "wank",
    "whore",
    "wtf",
]

banlist_regex = re.compile("(" + "|".join(banlist) + ")")


def banned(string):
    return bool(banlist_regex.search(string.lower()))
