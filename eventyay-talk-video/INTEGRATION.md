# Eventyay Talk Video plugin integration

This repository contains the `pretalx_venueless` plugin which integrates Pretalx (eventyay-talk) with the Eventyay video system:

- Adds an Eventyay video settings page under Orga → Event settings
- Pushes schedule updates to Eventyay video (`/schedule_update` endpoint) when a Pretalx schedule is released
- Optionally renders a "Join Eventyay video" button for speakers and generates JWT-based join links

## How it is wired in this workspace

This monorepo has three parts:

- eventyay-tickets (Django) — the ticketing/control app
- talk (Pretalx fork) — the talk/cfp/schedule app
- webapp — the video SPA served by eventyay-tickets at `/video`

Integration points:

1) Pretalx plugin (this folder)

- `talk/src/pretalx/settings.py` contains a local development fallback which adds this plugin to `INSTALLED_APPS` if the folder `eventyay-talk-video` exists next to the workspace root. This removes the need to install from Git during local dev.
- Pretalx auto-discovers plugin URLs in `pretalx/urls.py`. The plugin exposes:
  - Orga settings page: `/orga/event/<slug:event>/settings/p/eventyay-video/`
  - Health check: `/<slug:event>/p/eventyay-video/check`
  - Speaker join: `/<slug:event>/p/eventyay-video/join`

2) Ticketing app (eventyay-tickets)

- `app/eventyay/config/settings.py` includes `pretix_venueless` in `INSTALLED_APPS` so tickets-side templates and middleware can reference the plugin where needed.
- `app/eventyay/multidomain/maindomain_urlconf.py` includes a fallback to import and mount `pretix_venueless` URLs if present, ensuring they are reachable even when the plugin meta is missing.
- The video SPA is mounted under `/video` and injects `window.venueless` config dynamically based on the current event.

3) Webapp (video SPA)

- Built with Vite; assets are served by the ticketing app at `/video/assets/...` and the SPA shell at `/video` or `/video/<event_id_or_slug>`.
- The SPA consumes `window.venueless.api.base` and `window.venueless.api.socket` which the ticket app injects.

## Required configuration

For Pretalx → Eventyay video schedule push and speaker join links, the following must be configured on a per-event basis in the Pretalx orga settings page provided by the plugin:

- Eventyay video URL, e.g. `https://video.example.org/<world>/`
- Eventyay video API Token (with trait `world:api`)
- Optional Join link settings (if you want Pretalx to hand out speaker join links):
  - Join URL (public video URL)
  - Secret (HS256 JWT shared secret)
  - Issuer, Audience (JWT fields)
  - Optional access start time and intro text

On the Eventyay video side, configure an inbound `schedule_update` endpoint and token verification.

## Minimal local run

- Run the ticket app server task (Django) and the Pretalx app; ensure PostgreSQL and Redis are available as per their respective settings.
- Build the webapp under `app/eventyay/webapp` (Vite) and ensure `dist/` exists so `/video` can serve the built SPA.
- In Pretalx, enable the plugin for your event and configure the Eventyay video URL + token, then release a schedule to trigger a push.

## Troubleshooting

- If the settings page shows "Unable to reach Venueless", verify the Eventyay video URL, the `schedule_update` endpoint, and the API token.
- Ensure `window.venueless` is present on `/video` pages; if not, rebuild the webapp and check `maindomain_urlconf.py` wiring.
- For join link issues, verify that the JWT secret, issuer, audience, and join URL match the Eventyay video configuration.
