Webapp Configuration
====================

The webapp can be statically configured by defining :code:`window.venueless` before startup.
For example, add the following to the :code:`index.html` you are serving:

.. code-block:: html

	<script>window.venueless={"api": {"socket": "wss://sample.demo.venueless.org/ws/world/sample/"}, "features": []}</script>

Full configuration
------------------

.. code-block:: js

	{
		"api": {
			"socket": "wss://sample.demo.venueless.org/ws/world/sample/"
		},
		"features": [] // enable experimental features,
		"locale": "en",
		"theme": {
			"logo": {
				"url": "/venueless-logo-full-white.svg",
				"fitToWidth": false // optional
			}
			"colors": {
				"primary": '#673ab7', // hightlight color, should be high contrast on white background
				"sidebar": '#180044'
			},
			"streamOfflineImage": "/some-large-image.svg", // image shown instead of "Stream offline"
			// override texts in the ui
			// see webapp/src/locales for full list of keys
			// DO NOT use this to completely translate the ui
			"textOverwrites": {
				"ProfilePrompt:headline:text": "’ello Guv!"
			}
		}
	}


Experimental Features
---------------------

* event-admin
* questions-answers
* chat-moderation
* schedule-control
