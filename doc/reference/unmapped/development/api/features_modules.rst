.. highlight:: python
   :linenothreshold: 5

Features & Integrations
=======================

This section documents the advanced features and integrations in the unified eventyay system.

Live Features (Video Component)
-------------------------------

WebSocket Consumers
~~~~~~~~~~~~~~~~~~~

The live features WebSocket consumers are located in ``eventyay.features.live.consumers``.

Live Modules
~~~~~~~~~~~~

Live module handlers are in ``eventyay.features.live.modules`` package:

- ``room.py`` - Room management
- ``chat.py`` - Chat handling
- ``poll.py`` - Poll functionality
- ``bbb.py`` - BigBlueButton integration
- ``question.py`` - Q&A management
- ``roulette.py`` - Speed networking
- ``zoom.py`` - Zoom integration
- ``januscall.py`` - Janus WebRTC calls


Analytics
---------

Analytics Graphs
~~~~~~~~~~~~~~~~

.. automodule:: eventyay.features.analytics.graphs.report
   :members:

.. automodule:: eventyay.features.analytics.graphs.utils
   :members:

Analytics Tasks
~~~~~~~~~~~~~~~

.. automodule:: eventyay.features.analytics.graphs.tasks
   :members:

Importers
---------

ConfTool Import
~~~~~~~~~~~~~~~

.. automodule:: eventyay.features.importers.conftool
   :members:

Import Tasks
~~~~~~~~~~~~

.. automodule:: eventyay.features.importers.tasks
   :members:

Integrations
------------

Zoom Integration
~~~~~~~~~~~~~~~~

.. automodule:: eventyay.features.integrations.zoom.views
   :members:

Storage Integrations
~~~~~~~~~~~~~~~~~~~~

.. automodule:: eventyay.features.integrations.platforms.storage.nanocdn
   :members:



