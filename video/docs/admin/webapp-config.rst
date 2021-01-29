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
		"dateLocale": "en-ie",
		"timetravelTo": "2020-08-26T06:49:28.975Z", // forces local time to always be this (for schedule demo purposes ONLY)
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
		},
		"videoPlayer": {
			"hls.js": {} // https://github.com/video-dev/hls.js/blob/master/docs/API.md#fine-tuning
		}
	}


Presentation Mode
-----------------

To enter presentation mode, append `/presentation` to a room url.
This shows ONLY the content of the currently pinned question (and updates if anything changes).

You can style presenation mode via custom css:

.. code-block:: css

	// add a background
	#presentation-mode {
		background: url('YOUR_URL_HERE');
		background-size: cover;
		color: A_COLOR_THAT_MATCHES_YOUR_BACKGROUND;
	}

Experimental Features
---------------------

* schedule-control
* roulette
* muxdata