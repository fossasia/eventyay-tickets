.. _`paypal`:

PayPal
======

.. note::

   If you use eventyay Hosted, you do not longer need to go through this tedious process! You can
   just open the PayPal settings in the payment section of your event, click "Connect to PayPal"
   and log in to your PayPal account. The following guide is only required for self-hosted
   versions of eventyay.

To integrate PayPal with eventyay, you first need to have an active PayPal merchant account. If you do not already have a
PayPal account, you can create one on `paypal.com`_.
If you look into eventyay' settings, you are required to fill in two keys:

.. image:: img/paypal_pretix.png
   :class: screenshot

Unfortunately, it is not straightforward how to get those keys from PayPal's website. In order to do so, you
need to go to `developer.paypal.com`_ to link the account to your eventyay event.

.. warning::

   Unfortunately, PayPal tries to confuse you by having multiple APIs with different keys. You really need to
   go to https://developer.paypal.com for the API we use, not to your normal account settings!

Click on "Log In" in the top-right corner and log in with your PayPal account.

.. image:: img/paypal2.png
   :class: screenshot

Then, click on "Dashboard" in the top-right corner.

.. image:: img/paypal3.png
   :class: screenshot

In the dashboard, scroll down until you see the headline "REST API Apps". Click "Create App".

.. image:: img/paypal4.png
   :class: screenshot

Enter any name for the application that helps you to identify it later. Then confirm with "Create App".

.. image:: img/paypal5.png
   :class: screenshot

On the next page, before you do anything else, switch the mode on the right to "Live" to get the correct keys.
Then, copy the "Client ID" and the "Secret" and enter them into the appropriate fields in the payment settings in
eventyay.

.. image:: img/paypal6.png
   :class: screenshot

Finally, we need to create a webhook. The webhook tells PayPal to notify eventyay e.g. if a payment gets cancelled so
eventyay can cancel the ticket as well. If you have multiple events connected to your PayPal account, you need multiple
webhooks. To create one, scroll a bit down and click "Add Webhook".

.. image:: img/paypal7.png
   :class: screenshot

Then, enter the webhook URL that you find on the eventyay settings page. If you use eventyay Hosted, this is always ``https://eventyay.com/_paypal/webhook/``.
Tick the box "All events" and save.

.. image:: img/paypal8.png
   :class: screenshot

That's it, you are ready to go!

.. _paypal.com: https://www.paypal.com/webapps/mpp/account-selection
.. _developer.paypal.com: https://developer.paypal.com/
