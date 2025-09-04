from eventyay.base.models import Organizer, Team


def create_organizer_with_team(*, name, slug, users=None):
    organizer = Organizer.objects.create(name=name, slug=slug)
    team = Team.objects.create(
        organizer=organizer,
        name=f"Team {name}",
        can_create_events=True,
        can_change_teams=True,
        can_change_organizer_settings=True,
    )
    for user in users:
        team.members.add(user)
    return organizer, team
