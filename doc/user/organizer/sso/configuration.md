# Single Sign-On (SSO) Configuration

This guide explains how to configure SSO providers in pretix to allow users to log in using their existing accounts from popular platforms.

## General SSO Setup

Before setting up specific providers, navigate to your Organizer Settings > SSO Providers and click "Create a new SSO provider". You'll see the following screen:

![SSO Provider Creation Screen](../../_static/img/sso/provider_create.png)

> **NOTE:** The SSO feature requires at least pretix 4.2.0 or higher. If you're using an older version, please upgrade first.

## GitHub SSO Configuration

GitHub's implementation is generally the most reliable due to their stable OAuth API. To set up GitHub as an SSO provider:

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "New OAuth App"
3. Fill in the following details:
   - **Application name**: Your event name or organization name
   - **Homepage URL**: Your event homepage or organization website
   - **Authorization callback URL**: Enter the Redirection URL shown in your pretix SSO provider settings page (something like `https://yourdomain.com/control/organizer/myorganizer/sso/providers/callback/`)
4. Click "Register application"
5. GitHub will generate a Client ID and Client Secret
6. In pretix, configure your SSO provider as follows:
   - **Name**: GitHub
   - **Button label**: Login with GitHub
   - **Method**: OpenID Connect (Only one is availabel)
   - **Base URL**: https://github.com/login/oauth
   - **Client ID**: `your-client-id` (e.g., `a1b2c3d4e5f6g7h8i9j0`)
   - **Client secret**: `your-client-secret` (keep this confidential!)
   - **Scope**: `user:email`
   - **User ID field**: `id`
   - **Email field**: `email`
   - **First name field**: `name`

> **WARNING:** If GitHub returns an error about redirect URL mismatch, double-check that the URL you entered in GitHub *exactly* matches the one shown in pretix, including trailing slashes.

### GitHub Limitations

GitHub's API only provides a combined name field, not separate first/last name fields, so you'll need to configure name splitting in pretix if this is important for your use case. We're currently tracking this limitation in [GitHub issue #876](https://example.com/issue/876).

## Google SSO Configuration

Google's SSO requires more setup but provides better user profile information. To set up Google as an SSO provider:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to APIs & Services > Credentials
4. Click "Create Credentials" > "OAuth client ID"
5. Configure the consent screen if prompted
   - For most users, an "External" consent screen is sufficient
   - You **must** add the email scope to your consent screen configuration
6. Select "Web application" as the application type
7. Fill in the following details:
   - **Name**: Your event or organization name
   - **Authorized JavaScript origins**: Your pretix domain (e.g., `https://yourdomain.com`)
   - **Authorized redirect URIs**: Enter the Redirection URL shown in your pretix SSO provider settings page
8. Click "Create"
9. Google will generate a Client ID and Client Secret
10. In pretix, configure your SSO provider as follows:
    - **Name**: Google
    - **Button label**: Login with Google
    - **Method**: OpenID Connect (Only one is availabel)
    - **Base URL**: https://accounts.google.com
    - **Client ID**: `your-google-client-id` (e.g., `123456789012-abcdefghijklmnopqrstuvwxyz123456.apps.googleusercontent.com`)
    - **Client secret**: `your-google-client-secret` (keep this confidential!)
    - **Scope**: `openid email profile`
    - **User ID field**: `sub`
    - **Email field**: `email`
    - **First name field**: `given_name`
    - **Last name field**: `family_name`

> **TIP:** Google provides excellent name field separation, making it ideal if you need accurate first/last name data for your events.

## Wikimedia SSO Configuration

Wikimedia's SSO can be a bit tricky to set up and occasionally experiences downtime during high-traffic periods. To set up Wikimedia as an SSO provider:

1. Go to [Wikimedia Developer Portal](https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/propose)
2. Click "Propose a consumer"
3. Fill in the following details:
   - **Application name**: Your event or organization name
   - **Application description**: Brief description of your event/organization
   - **OAuth callback URL**: Enter the Redirection URL shown in your pretix SSO provider settings page
   - **Allow consumer to specify a callback in requests**: Yes
   - **Types of grants being requested**: Authorization only (no API access)
4. Submit the application
5. **IMPORTANT:** Wikimedia approval is manual and can take 1-3 business days. Plan accordingly!
6. Once approved, you'll receive a Consumer Key and Secret
7. In pretix, configure your SSO provider as follows:
   - **Name**: Wikimedia
   - **Button label**: Login with Wikimedia
   - **Method**: OpenID Connect  (Only one is availabel)
   - **Base URL**: https://meta.wikimedia.org/w/rest.php/oauth2
   - **Client ID**: `your-wikimedia-consumer-key`
   - **Client secret**: `your-wikimedia-consumer-secret`
   - **Scope**: `openid profile email`
   - **User ID field**: `sub`
   - **Email field**: `email`
   - **Name field**: `username` (may vary based on Wikimedia's implementation)

We've had reports that sometimes Wikimedia's API returns incomplete user profiles. If you encounter this issue, try enabling the "Fall back to user identification by email" setting. This is documented in our issue tracker ([ticket #724](https://example.com/issue/724)).

## Testing Your Configuration

After setting up your SSO provider, test it immediately:

1. Enable the provider by toggling the "Is active" switch to "Enable" (not "Enabled" as shown in older versions)
2. Open an incognito/private browser window (to avoid session conflicts)
3. Go to your event's public page and attempt to log in using the SSO option
4. Verify that you're correctly redirected to the provider's login page
5. After logging in, you should be redirected back to your event page

If things don't work immediately, don't panic! SSO configurations often need small adjustments.

## Common Errors and Troubleshooting

### "Invalid client_id" or "Unknown client"
- Double-check your client ID for typos
- Verify that your application is approved (especially for Wikimedia)
- Check if your OAuth app is in a sandbox/development mode that limits access

### "Invalid redirect URI"
- The most common SSO error!
- The redirect URI must match **exactly** what you configured with the provider
- Check for:
  - HTTP vs HTTPS mismatch
  - Missing or extra trailing slashes
  - Subdomains (www vs non-www)

### "User profile missing required fields"
- Try requesting additional scopes
- Check field mapping configuration
- Some providers (especially GitHub) don't provide all profile fields

### "Access token validation failed"
- Your client secret might be incorrect
- The token endpoint URL could be wrong
- Check if your OAuth credentials have expired

## Advanced Configuration

For complex integrations, pretix supports additional configuration options:

```python
# Example of advanced configuration parameters
{
  "additional_query_params": "hd=yourdomain.com&prompt=select_account",
  "additional_headers": {"X-Custom-Header": "value"},
  "token_endpoint_auth_method": "client_secret_post"
}
```

This advanced configuration is available by editing the provider's JSON configuration directly. Use with caution!

<!-- TODO: Add screenshots for each provider's configuration screen in a future documentation update. Currently tracked as issue #982 -->

## Limitations and Known Issues

- The SSO email verification logic assumes emails from providers are verified. Using unverified emails could create security issues.
- Only one active session per provider/user combination is currently supported.
- If a user changes their email with the provider, they'll need to contact you to update their account.
- Token refresh mechanisms vary between providers and may require occasional re-authentication.

*Last updated: June 2023 – Please report any errors or outdated information in our [GitHub repository](https://github.com/pretix/pretix/issues).* 