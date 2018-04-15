from pretalx.event.models import Organiser, Team


def create_organiser_with_user(*, name, slug, user):

    organiser = Organiser.objects.create(name=name, slug=slug)
    team = Team.objects.create(
        organiser=organiser, name=f'Team {name}',
        can_create_events=True, can_change_teams=True,
        can_change_organiser_settings=True,
    )
    team.members.add(user)
    return organiser, team
