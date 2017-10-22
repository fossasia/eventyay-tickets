import datetime

import pytest

from pretalx.schedule.models import Availability


@pytest.mark.django_db
def test_availability_str_person(speaker):
    assert 'person=Jane Speaker' in str(Availability(
        start=datetime.datetime(2017, 1, 1, 0),
        end=datetime.datetime(2017, 1, 1, 5),
        person=speaker.profiles.first(),
    ))


@pytest.mark.django_db
def test_availability_str_room(room):
    assert 'room=Roomy' in str(Availability(
        start=datetime.datetime(2017, 1, 1, 0),
        end=datetime.datetime(2017, 1, 1, 5),
        room=room,
    ))


@pytest.mark.django_db
def test_availability_str_person_room(room, speaker):
    actual = str(Availability(
        start=datetime.datetime(2017, 1, 1, 0),
        end=datetime.datetime(2017, 1, 1, 5),
        person=speaker.profiles.first(),
        room=room,
    ))
    assert 'room=Roomy' in actual
    assert 'person=Jane Speaker' in actual


@pytest.mark.django_db
def test_availability_str_event(event):
    assert 'event=Event' in str(Availability(
        start=datetime.datetime(2017, 1, 1, 0),
        end=datetime.datetime(2017, 1, 1, 5),
        event=event
    ))


@pytest.mark.django_db
@pytest.mark.parametrize('one,two,expected_strict,expected', (
    (
        #    0000
        #    0000
        ((2017, 1, 1, 5), (2017, 1, 1, 9)),
        ((2017, 1, 1, 5), (2017, 1, 1, 9)),
        True, True,
    ),
    (
        #    0000
        #     000
        ((2017, 1, 1, 5), (2017, 1, 1, 9)),
        ((2017, 1, 1, 6), (2017, 1, 1, 9)),
        True, True,
    ),
    (
        #    0000
        #      000
        ((2017, 1, 1, 5), (2017, 1, 1, 9)),
        ((2017, 1, 1, 7), (2017, 1, 1, 10)),
        True, True,
    ),
    (
        #    0000
        # 000
        ((2017, 1, 1, 5), (2017, 1, 1, 9)),
        ((2017, 1, 1, 1), (2017, 1, 1, 5)),
        False, True,
    ),
    (
        #    0000
        # 00
        ((2017, 1, 1, 5), (2017, 1, 1, 9)),
        ((2017, 1, 1, 1), (2017, 1, 1, 4)),
        False, False,
    ),
    (
        #   0000000000
        #    00000000
        ((2017, 10, 5, 9), (2017, 10, 5, 16)),
        ((2017, 10, 5, 10), (2017, 10, 5, 15)),
        True, True,
    ),
))
def test_overlaps(one, two, expected_strict, expected):
    one = Availability(start=datetime.datetime(*one[0]), end=datetime.datetime(*one[1]))
    two = Availability(start=datetime.datetime(*two[0]), end=datetime.datetime(*two[1]))

    def test(strict, expected):
        nonlocal one, two
        actual1 = one.overlaps(two, strict)
        actual2 = two.overlaps(one, strict)
        assert expected == actual1
        assert expected == actual2

    test(True, expected_strict)
    test(False, expected)


@pytest.mark.django_db
@pytest.mark.parametrize('one,two,expected', (
    (
        # real overlap
        Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 7)),
        Availability(start=datetime.datetime(2017, 1, 1, 5), end=datetime.datetime(2017, 1, 1, 9)),
        Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 9)),
    ),
    (
        # just adjacent
        Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 7)),
        Availability(start=datetime.datetime(2017, 1, 1, 7), end=datetime.datetime(2017, 1, 1, 8)),
        Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 8)),
    ),
))
def test_merge_with(one, two, expected):
    actual1 = one.merge_with(two)
    actual2 = two.merge_with(one)
    actual1_magic = one | two
    actual2_magic = two | one
    assert expected.start == actual1.start
    assert expected.end == actual1.end
    assert expected.start == actual2.start
    assert expected.end == actual2.end
    assert actual1 == actual1_magic
    assert actual2 == actual2_magic


@pytest.mark.parametrize('method,args,expected', (
    (Availability.overlaps, ['i_am_no_availability', False], 'Availability object'),
    (Availability.merge_with, ['i_am_no_availability'], 'Availability object'),
    (Availability.merge_with, [Availability(start=datetime.datetime(2017, 1, 2), end=datetime.datetime(2017, 1, 2, 1))], 'overlap'),
    (Availability.intersect_with, ['i_am_no_availability'], 'Availability object'),
    (Availability.intersect_with, [Availability(start=datetime.datetime(2017, 1, 2), end=datetime.datetime(2017, 1, 2, 1))], 'overlap'),
))
def test_availability_fail(method, args, expected):
    avail = Availability(start=datetime.datetime(2017, 1, 1), end=datetime.datetime(2017, 1, 1, 1))

    with pytest.raises(Exception) as excinfo:
        method(avail, *args)

    assert expected in str(excinfo)


@pytest.mark.django_db
@pytest.mark.parametrize('avails,expected', (
    (
        [],
        [],
    ),
    (
        [Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 7))],
        [Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 7))],
    ),
    (
        [
            # 2 is after one 1, but with a gap. Do nothing.
            Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 5)),
            Availability(start=datetime.datetime(2017, 1, 1, 6), end=datetime.datetime(2017, 1, 1, 7)),
        ],
        [
            Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 5)),
            Availability(start=datetime.datetime(2017, 1, 1, 6), end=datetime.datetime(2017, 1, 1, 7)),
        ],
    ),
    (
        [
            # 2 is directly after one 1. Merge them.
            Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 5)),
            Availability(start=datetime.datetime(2017, 1, 1, 5), end=datetime.datetime(2017, 1, 1, 6)),
        ],
        [
            Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 6)),
        ],
    ),
    (
        [
            # 2 partly overlaps with 1. Merge them.
            Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 6)),
            Availability(start=datetime.datetime(2017, 1, 1, 5), end=datetime.datetime(2017, 1, 1, 7)),
        ],
        [
            Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 7)),
        ],
    ),
    (
        [
            # 2 partly overlaps with 1. Merge them.
            Availability(start=datetime.datetime(2017, 1, 1, 5), end=datetime.datetime(2017, 1, 1, 7)),
            Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 6)),
        ],
        [
            Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 7)),
        ],
    ),
    (
        [
            Availability(start=datetime.datetime(2017, 1, 1, 10), end=datetime.datetime(2017, 1, 1, 12)),
            Availability(start=datetime.datetime(2017, 1, 1, 12), end=datetime.datetime(2017, 1, 1, 14)),
            Availability(start=datetime.datetime(2017, 1, 1, 5), end=datetime.datetime(2017, 1, 1, 7)),
            Availability(start=datetime.datetime(2017, 1, 1, 6), end=datetime.datetime(2017, 1, 1, 8)),
            Availability(start=datetime.datetime(2017, 1, 1, 18), end=datetime.datetime(2017, 1, 1, 19)),
            Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 6)),
        ],
        [
            Availability(start=datetime.datetime(2017, 1, 1, 4), end=datetime.datetime(2017, 1, 1, 8)),
            Availability(start=datetime.datetime(2017, 1, 1, 10), end=datetime.datetime(2017, 1, 1, 14)),
            Availability(start=datetime.datetime(2017, 1, 1, 18), end=datetime.datetime(2017, 1, 1, 19)),
        ],
    ),
))
def test_union(avails, expected):
    actual = Availability.union(avails)

    assert len(actual) == len(expected)

    for act, exp in zip(actual, expected):
        assert act.start == exp.start
        assert act.end == exp.end


@pytest.mark.django_db
@pytest.mark.parametrize('availsets,expected', (
    (
        [],
        [],
    ),
    (
        [
            [Availability(start=datetime.datetime(2017, 1, 1, 5), end=datetime.datetime(2017, 1, 1, 7))],
            [],
        ],
        [],
    ),
    (
        #    0000
        #        0000
        # ==============
        #
        [
            [Availability(start=datetime.datetime(2017, 1, 1, 5), end=datetime.datetime(2017, 1, 1, 7))],
            [Availability(start=datetime.datetime(2017, 1, 1, 7), end=datetime.datetime(2017, 1, 1, 9))],
        ],
        [],
    ),
    (
        #    0000000
        #    0000000
        # ==============
        #    0000000
        [
            [Availability(start=datetime.datetime(2017, 1, 1, 5), end=datetime.datetime(2017, 1, 1, 7))],
            [Availability(start=datetime.datetime(2017, 1, 1, 5), end=datetime.datetime(2017, 1, 1, 7))],
        ],
        [Availability(start=datetime.datetime(2017, 1, 1, 5), end=datetime.datetime(2017, 1, 1, 7))],
    ),
    (
        #    0000000
        #       000000
        # ==============
        #       0000
        [
            [Availability(start=datetime.datetime(2017, 1, 1, 5), end=datetime.datetime(2017, 1, 1, 7))],
            [Availability(start=datetime.datetime(2017, 1, 1, 6), end=datetime.datetime(2017, 1, 1, 9))],
        ],
        [Availability(start=datetime.datetime(2017, 1, 1, 6), end=datetime.datetime(2017, 1, 1, 7))],
    ),
    (
        #    0000000
        #  0000   00000
        # ==============
        #    00   00
        [
            [Availability(start=datetime.datetime(2017, 1, 1, 2), end=datetime.datetime(2017, 1, 1, 7))],
            [
                Availability(start=datetime.datetime(2017, 1, 1, 0), end=datetime.datetime(2017, 1, 1, 3)),
                Availability(start=datetime.datetime(2017, 1, 1, 6), end=datetime.datetime(2017, 1, 1, 8)),
            ],
        ],
        [
            Availability(start=datetime.datetime(2017, 1, 1, 2), end=datetime.datetime(2017, 1, 1, 3)),
            Availability(start=datetime.datetime(2017, 1, 1, 6), end=datetime.datetime(2017, 1, 1, 7)),
        ],
    ),
    (
        #    0000000
        #  0000   00000
        #      00000
        # ==============
        #         00
        [
            [Availability(start=datetime.datetime(2017, 1, 1, 2), end=datetime.datetime(2017, 1, 1, 7))],
            [
                Availability(start=datetime.datetime(2017, 1, 1, 0), end=datetime.datetime(2017, 1, 1, 3)),
                Availability(start=datetime.datetime(2017, 1, 1, 6), end=datetime.datetime(2017, 1, 1, 8)),
            ],
            [Availability(start=datetime.datetime(2017, 1, 1, 9), end=datetime.datetime(2017, 1, 1, 7))],
        ],
        [
            Availability(start=datetime.datetime(2017, 1, 1, 9), end=datetime.datetime(2017, 1, 1, 7)),
        ],
    ),
    (
        #    0000000
        #  0000000
        # ==============
        #    00000
        [
            [Availability(start=datetime.datetime(2017, 1, 1, 2), end=datetime.datetime(2017, 1, 1, 7))],
            [
                Availability(start=datetime.datetime(2017, 1, 1, 0), end=datetime.datetime(2017, 1, 1, 3)),
                Availability(start=datetime.datetime(2017, 1, 1, 3), end=datetime.datetime(2017, 1, 1, 4)),
            ],
        ],
        [
            Availability(start=datetime.datetime(2017, 1, 1, 2), end=datetime.datetime(2017, 1, 1, 4)),
        ],
    ),
    (
        #    0000000      00000     0000
        #  0000   00000           000
        # ================================
        #    00   00              0
        [
            [
                Availability(start=datetime.datetime(2017, 1, 1, 2), end=datetime.datetime(2017, 1, 1, 7)),
                Availability(start=datetime.datetime(2017, 1, 1, 10), end=datetime.datetime(2017, 1, 1, 12)),
                Availability(start=datetime.datetime(2017, 1, 1, 14), end=datetime.datetime(2017, 1, 1, 19)),
            ],
            [
                Availability(start=datetime.datetime(2017, 1, 1, 0), end=datetime.datetime(2017, 1, 1, 3)),
                Availability(start=datetime.datetime(2017, 1, 1, 6), end=datetime.datetime(2017, 1, 1, 8)),
                Availability(start=datetime.datetime(2017, 1, 1, 13), end=datetime.datetime(2017, 1, 1, 15)),
            ],
        ],
        [
            Availability(start=datetime.datetime(2017, 1, 1, 2), end=datetime.datetime(2017, 1, 1, 3)),
            Availability(start=datetime.datetime(2017, 1, 1, 6), end=datetime.datetime(2017, 1, 1, 7)),
            Availability(start=datetime.datetime(2017, 1, 1, 14), end=datetime.datetime(2017, 1, 1, 15)),
        ],
    ),
))
def test_intersection(availsets, expected):
    actual1 = Availability.intersection(*availsets)
    actual2 = Availability.intersection(*reversed(availsets))

    assert len(actual1) == len(expected)
    assert len(actual2) == len(expected)

    for act1, act2, exp in zip(actual1, actual2, expected):
        assert act1.start == act2.start == exp.start
        assert act1.end == act2.end == exp.end
