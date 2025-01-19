Social Login Setup
--------------------------

To enable social login for providers, you first need to create an OAuth application on the provider's website.


I. Google OAuth Application
----------------------------
Create an OAuth application on https://console.developers.google.com/

Instructions:

- Follow the setup guide: https://medium.com/@tony.infisical/guide-to-using-oauth-2-0-to-access-google-apis-dead94d6866d

- Set the callback URL to: `{domain}/accounts/google/login/callback/`

- Add the client ID and client secret to admin settings


II. Github OAuth Application
-----------------------------
Create an OAuth application on https://github.com/settings/applications/new

Instructions:

- Set the callback URL to: `{domain}/accounts/github/login/callback/`

- Add the client ID and client secret to admin settings


III. MediaWiki OAuth Application
---------------------------------
To enable MediaWiki social login for your Eventyay instance, you need to register an OAuth application with MediaWiki.

Important Notes
~~~~~~~~~~~~~~~~

- The OAuth application must be approved by a MediaWiki administrator

- Until approved, only the application owner can log in

Registration Steps
~~~~~~~~~~~~~~~~~~~

1. Register your OAuth application at: 
   https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration/propose

2. Callback URL Configuration

   - Set the OAuth "callback" URL to: `{domain}/accounts/mediawiki/login/callback/`

   - Example: `http://localhost:8000/accounts/mediawiki/login/callback/`
   
3. Carefully read and follow the instructions on the registration page. Tick option: access private information.

4. The registered application will return:

   - One consumer key

   - One consumer secret

5. Add the consumer key and consumer secret to your Eventyay admin settings

After Approval
~~~~~~~~~~~~~~~
Once approved, other users can log in to your Eventyay instance using their MediaWiki account.
