Cloudflare Turnstile Anti-Abuse Protection
==========================================

Eventyay supports `Cloudflare Turnstile <https://developers.cloudflare.com/turnstile/>`_ as a privacy-preserving, CAPTCHA-style anti-abuse mechanism for public forms and entry points.

Turnstile protects against automated spam registrations, credential stuffing, brute force logins, and abuse of public forms while maintaining a low-friction experience for human users.

Overview & Supported Entry Points
---------------------------------

Turnstile can be enabled globally and selectively configured for the following entry points:

* **User Registration / Signup:** Protects public account registration (`/accounts/signup/` and team invite registration).
* **User Login:** Supports two protection modes:
  * *Always require:* Every login attempt requires a Turnstile challenge.
  * *Only after repeated failed attempts:* Challenges are presented only after a configurable number of consecutive failed login attempts (default: 3) from a given client IP address.
* **Password Reset Request:** Protects `/forgot/` password recovery requests from automated enumeration and spam.
* **Organizer Creation:** Protects the organizer setup form.
* **Contact & Inquiry Forms:** Protects public messaging and contact submission forms.

Configuration
-------------

Platform administrators can configure Turnstile from the admin dashboard:

1. Navigate to **Admin Settings** > **Global Settings** > **Security & Anti-Abuse** tab.
2. Select **Cloudflare Turnstile** under *Anti-Abuse / CAPTCHA Provider*.
3. Enter your **Cloudflare Turnstile Site Key** and **Secret Key** generated in the `Cloudflare Dashboard <https://dash.cloudflare.com/>`_.
4. Configure the form-level protection toggles:
   * Check **Require Turnstile on user registration / signup** to protect signups.
   * Choose the **Turnstile on user login** mode (*Always* or *Only after repeated failed login attempts*).
   * Specify the **Failed login attempt threshold** if *failed attempts only* mode is selected.
   * Check **Require Turnstile on password reset requests**.
   * Check **Require Turnstile on organizer creation**.
   * Check **Require Turnstile on public contact and inquiry forms**.
5. Click **Save**.

Development & Testing Keys
--------------------------

For local development and testing, Cloudflare provides dummy site keys and secret keys that simulate various challenge outcomes without contacting real users:

* **Always passes (Visible):**
  * Site Key: ``1x00000000000000000000AA``
  * Secret Key: ``1x0000000000000000000000000000000AA``

* **Always blocks / fails:**
  * Site Key: ``2x00000000000000000000AB``
  * Secret Key: ``2x0000000000000000000000000000000AB``

* **Always passes (Interactive):**
  * Site Key: ``3x00000000000000000000AA``
  * Secret Key: ``3x0000000000000000000000000000000AA``

Security & Failure Handling
---------------------------

* **Server-side Verification:** The client submission includes the ``cf-turnstile-response`` token, which is verified server-side against Cloudflare's verification endpoint (``https://challenges.cloudflare.com/turnstile/v0/siteverify``).
* **Safe Fallbacks:** If Turnstile is enabled but the secret key is missing or misconfigured, form submission is blocked with an informative configuration error to prevent security bypasses.
* **State Preservation:** When a verification fails, existing form inputs (such as email) are preserved to prevent user frustration.
