import logging
from datetime import datetime

from celery import shared_task
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django_scopes import scopes_disabled

from pretalx.event.forms import TeamForm
from pretalx.event.models import Event, Organiser, Team

logger = logging.getLogger(__name__)


class Action:
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@shared_task
def process_organiser_webhook(organiser_data):
    try:
        action = organiser_data.get("action")
        if action == Action.CREATE:
            organiser = Organiser(
                name=organiser_data.get("name"), slug=organiser_data.get("slug")
            )
            organiser.full_clean()
            organiser.save()
            logger.info(f"Organiser {organiser.name} created successfully.")
            # Create an Administrator team for new organiser
            team = TeamForm(
                organiser=organiser,
                data={
                    "name": "Administrators",
                    "all_events": True,
                    "can_create_events": True,
                    "can_change_teams": True,
                    "can_change_organiser_settings": True,
                    "can_change_event_settings": True,
                    "can_change_submissions": True,
                },
            )
            if team.is_valid():
                team.save()
                logger.info(
                    f"Administrator team for organiser {organiser.name} created "
                    f"successfully."
                )
            else:
                logger.error(
                    f"Error creating Administrator team for organiser {organiser.name}: {team.errors}"
                )

        elif action == Action.UPDATE:
            organiser = Organiser.objects.get(slug=organiser_data.get("slug"))
            organiser.name = organiser_data.get("name")
            organiser.full_clean()
            organiser.save()
            logger.info(f"Organiser {organiser.name} updated successfully.")

        elif action == Action.DELETE:
            # Implement delete logic here
            logger.info("Organiser delete not implemented yet.")
            pass

        else:
            logger.error(f"Unknown action: {action}")
    except ValidationError as e:
        logger.error("Validation error:", e.message_dict)
    except Exception as e:
        logger.error("Error saving organiser:", e)


@shared_task
def process_team_webhook(team_data):
    try:
        action = team_data.get("action")
        organiser = get_object_or_404(Organiser, slug=team_data.get("organiser_slug"))
        if action == Action.CREATE:
            team = TeamForm(organiser=organiser, data=team_data)
            if team.is_valid():
                team.save()
                logger.info(
                    f"Team for organiser {organiser.name} created successfully."
                )
            else:
                logger.error(
                    f"Error creating Administrator team for organiser {organiser.name}: {team.errors}"
                )

        elif action == Action.UPDATE:
            team = Team.objects.filter(
                organiser=organiser, name=team_data.get("old_name")
            ).first()
            if not team:
                raise Http404("No Team matches the given query.")
            # Update the team object with new data from team_data
            for field, value in team_data.items():
                setattr(team, field, value)
            team.save()
            logger.info(f"Team for organiser {organiser.name} created successfully.")

        elif action == Action.DELETE:
            team = Team.objects.filter(
                organiser=organiser, name=team_data.get("name")
            ).first()
            if not team:
                raise Http404("No Team matches the given query.")
            team.delete()
            logger.info(f"Team for organiser {organiser.name} deleted successfully.")

        else:
            logger.error(f"Unknown action: {action}")
    except ValidationError as e:
        logger.error("Validation error:", e.message_dict)
    except Exception as e:
        logger.error("Error saving organiser:", e)


@shared_task
def process_event_webhook(event_data):
    try:
        action = event_data.get("action")
        organiser = get_object_or_404(Organiser, slug=event_data.get("organiser_slug"))
        if action == Action.CREATE:
            with scopes_disabled():
                event = Event.objects.create(
                    organiser=organiser,
                    locale_array=",".join(event_data.get("locales")),
                    content_locale_array=",".join(event_data.get("locales")),
                    name=event_data.get("name"),
                    slug=event_data.get("slug"),
                    timezone=event_data.get("timezone"),
                    email=event_data.get("user_email"),
                    locale=event_data.get("locale"),
                    date_from=datetime.fromisoformat(event_data.get("date_from")),
                    date_to=datetime.fromisoformat(event_data.get("date_to")),
                )
                event.save()
        elif action == Action.UPDATE:
            event = Event.objects.filter(
                organiser=organiser, slug=event_data.get("slug")
            ).first()
            if not event:
                raise Http404("No Event matches the given query.")
            # Update the team object with new data from team_data
            event.name = event_data.get("name")
            event.date_from = datetime.fromisoformat(event_data["date_from"])
            event.date_to = datetime.fromisoformat(event_data["date_to"])
            event.locale_array = ",".join(event_data.get("locales"))
            event.content_locale_array = ",".join(event_data.get("locales"))
            event.timezone = event_data.get("timezone")
            event.locale = event_data.get("locale")
            event.save()
            logger.info(f"Event for organiser {organiser.name} created successfully.")

        elif action == Action.DELETE:
            pass

        else:
            logger.error(f"Unknown action: {action}")
    except ValidationError as e:
        logger.error("Validation error:", e.message_dict)
    except Exception as e:
        logger.error("Error saving organiser:", e)
