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

    <script type="text/javascript" src="https://pretalx.com/democon/schedule/widget/v2.en.js"></script>

The second snippet should be embedded at the position where the widget should show up::

    <pretalx-schedule event-url="https://pretalx.com/democon/" locale="en" style="--pretalx-clr-primary: #3aa57c"></pretalx-schedule>
    <noscript>
       <div class="pretalx-widget">
            <div class="pretalx-widget-info-message">
                JavaScript is disabled in your browser. To access our schedule without JavaScript,
                please <a target="_blank" href="https://pretalx.com/democon/schedule/">click here</a>.
            </div>
        </div>
    </noscript>

.. note::

    You can of course embed multiple widgets of multiple events on your page.
    In this case, please add the first snippet only *once* and the second
    snippets once *for each event*.

Example
-------

Your embedded widget could look like the following:

.. raw:: html

    <script type="text/javascript" src="https://pretalx.com/democon/schedule/widget/v2.en.js" async></script>

    <pretalx-schedule event="https://pretalx.com/democon/" locale="en" style="--pretalx-clr-primary: #3aa57c"></pretalx-schedule>
    <noscript>
       <div class="pretalx-widget">
            <div class="pretalx-widget-info-message">
                JavaScript is disabled in your browser. To access our schedule without JavaScript,
                please <a target="_blank" href="https://pretalx.com/democon/schedule/">click here</a>.
            </div>
        </div>
    </noscript>
