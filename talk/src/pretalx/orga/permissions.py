import rules

from pretalx.event.rules import can_change_event_settings

# Legacy for plugins. TODO remove after v2025.1.0
rules.add_perm("orga.change_settings", can_change_event_settings)
