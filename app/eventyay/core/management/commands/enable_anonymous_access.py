from django.core.management.base import BaseCommand

from eventyay.base.models import Event
from eventyay.core.permissions import Permission


class Command(BaseCommand):
    help = (
        "Enable or disable implicit anonymous (client_id) EVENT_VIEW access for an event by assigning "
        "a role grant with empty trait requirements. This allows visitors without a token to connect "
        "via the websocket using a generated client_id."
    )

    def add_arguments(self, parser):
        parser.add_argument("event_id", type=str, help="Primary key/UUID of the event")
        parser.add_argument(
            "--role",
            type=str,
            default="viewer",
            help="Role name to use / create for granting EVENT_VIEW (default: viewer)",
        )
        parser.add_argument(
            "--remove",
            action="store_true",
            default=False,
            help="Remove anonymous grant instead of adding it",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show intended changes without saving",
        )

    def handle(self, *args, **opts):
        event_id = opts["event_id"]
        role = opts["role"]
        remove = opts["remove"]
        dry = opts["dry_run"]

        event = Event.objects.get(id=event_id)

        roles = dict(event.roles or {})
        trait_grants = dict(event.trait_grants or {})

        changed = False

        if remove:
            # Remove empty trait grant for chosen role if it exactly matches []
            if role in trait_grants and trait_grants[role] == []:
                self.stdout.write(f"Removing empty trait grant for role '{role}'")
                del trait_grants[role]
                changed = True
            # Optionally remove EVENT_VIEW from role if no other grants depend on it
            if role in roles and Permission.EVENT_VIEW.value in roles[role]:
                self.stdout.write(
                    f"(Note) Role '{role}' still has EVENT_VIEW; leaving permissions unchanged. Use manual edit if needed."
                )
        else:
            # Ensure permission present
            ev_perm = Permission.EVENT_VIEW.value
            current_perms = set(roles.get(role, []))
            if ev_perm not in current_perms:
                current_perms.add(ev_perm)
                roles[role] = sorted(current_perms)
                self.stdout.write(f"Added EVENT_VIEW permission to role '{role}'")
                changed = True
            else:
                self.stdout.write(f"Role '{role}' already has EVENT_VIEW permission")
            # Ensure empty trait grant in trait_grants (implicit grant) => []
            if trait_grants.get(role) != []:
                trait_grants[role] = []
                self.stdout.write(
                    f"Set trait_grants['{role}'] = [] (anonymous users allowed to assume role implicitly)"
                )
                changed = True
            else:
                self.stdout.write(
                    f"trait_grants already contains empty list for role '{role}' (anonymous already enabled)"
                )

        if not changed:
            self.stdout.write("No changes required.")
            return

        if dry:
            self.stdout.write("Dry run: not saving changes.")
            return

        event.roles = roles
        event.trait_grants = trait_grants
        event.save(update_fields=["roles", "trait_grants"])
        self.stdout.write(
            self.style.SUCCESS(
                ("Anonymous access enabled." if not remove else "Anonymous access removed.")
            )
        )
