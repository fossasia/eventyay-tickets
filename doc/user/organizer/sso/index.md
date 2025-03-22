# Single Sign-On (SSO)

This section explains how to configure and manage Single Sign-On providers for your pretix event or organization.

## What's in this section

* [SSO Configuration Guide](configuration.md) - Detailed setup instructions for popular providers including GitHub, Google, and Wikimedia

## What is Single Sign-On?

Single Sign-On (SSO) allows your users to log in using their existing accounts from trusted third-party providers. Instead of creating yet another username and password, attendees can use accounts they already have and trust.

This provides several important benefits:

1. **Improved security**: Leverages the security infrastructure of major providers
2. **Reduced friction**: No need for users to create and remember another set of credentials
3. **Higher conversion**: Simplified registration process leads to fewer abandoned signups
4. **Data quality**: More reliable user information from verified sources

## Supported Providers

pretix includes built-in support for any provider that implements the standard OAuth 2.0 or OpenID Connect protocols, including:

* GitHub
* Google
* Wikimedia
* Facebook
* Microsoft/Azure AD
* Apple
* Twitter/X
* LinkedIn
* And many others...

## Architecture Overview

When a user authenticates through SSO:

1. pretix redirects the user to the provider's login page
2. The user authenticates with the provider
3. The provider redirects back to pretix with a temporary code
4. pretix exchanges this code for tokens and user information
5. pretix creates or updates the user account and logs the user in

All sensitive data is exchanged securely through backend channels, not through the browser.

## Access Control

SSO can be enabled for:
- The entire pretix instance
- Specific organizers
- Specific events

This flexibility allows you to implement exactly the authentication strategy your organization needs.

## Limitations

* Users may need to re-authenticate if their session with the provider expires
* Provider outages can impact login functionality
* Some providers have rate limits that may affect high-volume events

## Getting Started

To begin setting up SSO, head over to the [Configuration Guide](configuration.md).

---

**Help us improve this documentation!** If you find issues or have suggestions, please open a ticket on our [GitHub repository](https://github.com/pretix/pretix). 