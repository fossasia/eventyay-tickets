from pretalx.event.models import Organiser, Team


def create_organiser_with_team(*, name, slug, users=None):

    organiser = Organiser.objects.create(name=name, slug=slug)
    team = Team.objects.create(
        organiser=organiser,
        name=f'Team {name}',
        can_create_events=True,
        can_change_teams=True,
        can_change_organiser_settings=True,
    )
    for user in users:
        team.members.add(user)
    return organiser, team
