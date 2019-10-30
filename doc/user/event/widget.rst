Embeddable Widget
=================

If you want to show your schedule on your event website or blog, you can use
our JavaScript widget. This way, users will not need to leave your site to look
at the schedule in most cases. The widget will still open a new tab when the
user clicks on a talk to see the details.

To obtain the correct HTML code for embedding your event into your website, we
recommend that you go to the "Widget" tab of your event's settings. You can
specify some optional settings there (for example the language of the widget)
and then click "Generate widget code".

You will obtain two code snippets that look *roughly* like the following. The
first should be embedded into the ``<head>`` part of your website, if possible.
If this is inconvenient, you can put it in the ``<body>`` part as well::

    <link rel="stylesheet" type="text/css" href="https://pretalx.com/democon/schedule/widget/v1.css">
    <script type="text/javascript" src="https://pretalx.com/democon/schedule/widget/v1.en.js" async></script>

The second snippet should be embedded at the position where the widget should show up::

    <pretalx-schedule-widget event="https://pretalx.eu/democon/" height="500px"></pretalx-widget>
    <noscript>
       <div class="pretalx-widget">
            <div class="pretalx-widget-info-message">
                JavaScript is disabled in your browser. To access our schedule without JavaScript,
                please <a target="_blank" href="https://pretalx.com/democon/schedule/">click here</a>.
            </div>
        </div>
    </noscript>

.. note::

    Some website builders like Jimdo have trouble with our custom HTML tag. In
    that case, you can use
    ``<div class="pretalx-schedule-widget-compat" …></div>`` instead of
    ``<pretalx-schedule-widget …></pretalx-schedule-widget>``.

Example
-------

Your embedded widget could look like the following:

.. raw:: html

    <link rel="stylesheet" type="text/css" href="http://localhost:8000/35c3/schedule/widget/v1.css">
    <script type="text/javascript" src="http://localhost:8000/35c3/schedule/widget/v1.de.js" async></script>

    <pretalx-schedule-widget event="http://localhost:8000/35c3/" height="500px"></pretalx-schedule-widget>
    <noscript>
       <div class="pretalx-widget">
            <div class="pretalx-widget-info-message">
                JavaScript is disabled in your browser. To access our schedule without JavaScript,
                please <a target="_blank" href="https://pretalx.com/democon/schedule/">click here</a>.
            </div>
        </div>
    </noscript>


Styling
-------

If you want, you can customize the appearance of the widget to fit your website with CSS. If you inspect the rendered
HTML of the widget with your browser's developer tools, you will see that nearly every element has a custom class
and all classes are prefixed with ``pretalx-schedule``. You can override the styles as much as you want to and if
you want to go all custom, you don't even need to use the stylesheet provided by us at all.
