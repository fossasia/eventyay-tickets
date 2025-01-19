=====================================================
Single Sign-On (SSO) Implementation with JWT and OAuth2
=====================================================

Overview
========
This document provides a step-by-step guide to implementing Single Sign-On (SSO) between the `ticket` and `talk` applications using JWT tokens and Django OAuth Toolkit. The configuration involves customizing the OAuth2 `AuthorizationView`, handling login processes to set JWT cookies, and ensuring a seamless SSO experience across applications.

Pre-requisites
==============
- Django >= 3.11
- Django OAuth Toolkit
- PyJWT
- HTTPS configuration for secure cookie handling

Step 1: Customize Authorization View
====================================
To bypass the OAuth2 consent screen for trusted applications and automatically set a JWT cookie upon successful authorization, we override the `AuthorizationView`.

src/pretix/control/views/auth.py


Step 2: Update URL Configuration
================================
Update the URL configuration to use the `CustomAuthorizationView`:

src/pretix/control/urls.py

Step 3: Modify Login View to Set JWT Cookie
===========================================
In the `ticket` application, modify the `login` view to set a JWT cookie after successful authentication.

Update `login` view in `src/pretix/control/views/auth.py`:


Step 4: Security and Configuration
==================================
Ensure that all configurations are secure and appropriate for your environment:

- Use `SECRET_KEY` in `settings.py` for JWT signing.

Conclusion
==========
By following these steps, you can implement SSO using JWT and Django OAuth Toolkit between the `ticket` and `talk` applications. This configuration allows for seamless user authentication while maintaining a secure environment. Ensure to review and follow security best practices to protect user data and session integrity.
