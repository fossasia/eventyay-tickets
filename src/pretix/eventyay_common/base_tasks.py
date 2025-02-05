import logging
from importlib import import_module
from importlib.util import find_spec
from typing import Any

from celery import Task
from django_scopes import scopes_disabled
from pretix_venueless.views import VenuelessSettingsForm

from ..base.models import Event
from .utils import EventCreatedFor

logger = logging.getLogger(__name__)


class CreateWorldTask(Task):
    """
    A base class for handling video platform creation tasks for events.

    This class is responsible for:
    - Setting up video plugins for events
    - Managing plugin attachments
    - Configuring video settings and JWT authentication
    - Handling post-task success operations

    Raises:
        ValueError: When event doesn't exist or validation fails
        ConfigurationError: When plugin setup fails
    """

    def add_plugin(self, event: Event, plugin_name: str) -> str:
        """
        Add a plugin to an event's plugin list.

        Args:
            event: The event instance to add the plugin to
            plugin_name: Name of the plugin to add

        Returns:
            str: Comma-separated string of all plugins including the new one
        """
        if not event.plugins:
            return plugin_name
        plugins = set(event.plugins.split(','))
        plugins.add(plugin_name)
        return ','.join(plugins)

    def attach_plugin_to_event(self, plugin_name: str, event_slug: str) -> None:
        """
        Attach a plugin to an event by updating its plugins list.

        Args:
            plugin_name: Name of the plugin to attach
            event_slug: Unique slug identifier of the event

        Raises:
            ValueError: If the event does not exist
        """
        try:
            with scopes_disabled():
                event = Event.objects.get(slug=event_slug)
                event.plugins = self.add_plugin(event, plugin_name)
                event.save()
        except Event.DoesNotExist:
            logger.error('Event does not exist: %s', event_slug)
            raise ValueError(f"Event with slug '{event_slug}' does not exist")

    def save_video_settings_information(self, event_id: str, video_settings: dict) -> None:
        """
        Save video configuration settings for an event.

        Args:
            event_id: The event identifier
            video_settings: Dictionary containing video configuration parameters

        Raises:
            ValueError: If event doesn't exist or settings validation fails
        """
        try:
            with scopes_disabled():
                event_instance = Event.objects.get(slug=event_id)
                video_config_form = VenuelessSettingsForm(data=video_settings, obj=event_instance)
                if video_config_form.is_valid():
                    video_config_form.save()
                else:
                    errors = video_config_form.errors
                    logger.error(
                        'Video integration configuration failed - Validation errors: %s',
                        errors,
                    )
                    raise ValueError(f'Failed to validate video integration settings: {errors}')
        except Event.DoesNotExist:
            logger.error('Event does not exist: %s', event_id)
            raise ValueError(f"Event with ID '{event_id}' does not exist")

    def check_installed_plugin(self, plugin_name: str) -> bool:
        """
        Check if a plugin is installed.

        Args:
            plugin_name: Name of the plugin to check

        Returns:
            Boolean: True if installed, False otherwise
        """
        try:
            if find_spec(plugin_name) is not None:
                import_module(plugin_name)
                return True
            return False
        except ImportError:
            logger.warning('Failed to import plugin: %s', plugin_name)
            return False

    def extract_jwt_config(self, world_data: dict) -> dict:
        """
        Extract JWT configuration from world data.

        Args:
            world_data: Dictionary containing world configuration data

        Returns:
            dict: JWT configuration with secret, issuer, and audience
        """
        try:
            config = world_data.get('config', {})
            jwt_secrets = config.get('JWT_secrets', [])
            jwt_config = jwt_secrets[0] if jwt_secrets else {}

            return {
                'secret': jwt_config.get('secret', ''),
                'issuer': jwt_config.get('issuer', ''),
                'audience': jwt_config.get('audience', ''),
            }
        except (KeyError, IndexError) as e:
            logger.warning('Failed to extract JWT config: %s', e)
            return {'secret': '', 'issuer': '', 'audience': ''}

    def setup_video_plugin(self, world_data: dict) -> None:
        """
        Setup and configure the video plugin for an event.

        Args:
            world_data: Dictionary containing world configuration data

        Raises:
            ValueError: If plugin is not installed or configuration fails
        """
        plugin_name = 'pretix_venueless'
        if not self.check_installed_plugin(plugin_name):
            logger.error('Video integration configuration failed - Plugin not installed')
            raise ValueError(f"Plugin '{plugin_name}' is not installed")

        event_id = world_data.get('id')
        if not event_id:
            raise ValueError('World data missing event ID')

        # Setup plugin
        self.attach_plugin_to_event(plugin_name, event_id)

        # Configure video settings
        jwt_config = self.extract_jwt_config(world_data)
        video_settings = {
            'venueless_url': world_data.get('domain', ''),
            'venueless_secret': jwt_config['secret'],
            'venueless_issuer': jwt_config['issuer'],
            'venueless_audience': jwt_config['audience'],
            'venueless_all_items': True,
            'venueless_items': [],
            'venueless_questions': [],
        }

        self.save_video_settings_information(event_id, video_settings)

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> Any:
        """
        Handle successful task completion by setting up the video plugin.
        Enable video plugin for the event

        Args:
            retval: Task return value containing world data
            task_id: ID of the completed task
            args: Original task arguments
            kwargs: Original task keyword arguments

        Returns:
            Any: Result from parent class on_success method
        """
        if isinstance(retval, dict):
            try:
                self.setup_video_plugin(retval)
            except ValueError as e:
                logger.error('Video integration configuration failed: %s', e)
        return super().on_success(retval, task_id, args, kwargs)


class SendEventTask(Task):
    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> Any:
        """
        Handle successful task completion by updating event settings.
        Set the event settings to "create_for" both:
        indicate that the event is created for both tickets and talk

        Args:
            retval: Task return value
            task_id: ID of the completed task
            args: Original task arguments
            kwargs: Original task keyword arguments

        Returns:
            Any: Result from parent class on_success method
        """
        event = kwargs.get('event', {}).get('slug', '')
        try:
            event = Event.objects.get(slug=event)
            event.settings.set('create_for', EventCreatedFor.BOTH.value)
            event.save()
        except Event.DoesNotExist:
            logger.error('Event with slug %s does not exist', event)
        return super().on_success(retval, task_id, args, kwargs)
