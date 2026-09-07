Architecture overview
=====================

.. _unified_architecture:

Overview
--------

Eventyay is a unified, open-source event management platform that integrates three major components:

* **Tickets Component** - Ticket sales, registration, payment processing, and attendee management
* **Talk Component** - Call for Papers (CfP), submission management, schedule building, and speaker coordination  
* **Video Component** - Virtual event platform with video streaming, interactive rooms, and networking features

All components are now integrated into a single codebase under the ``app/eventyay`` directory, sharing a unified data model, authentication system, and user interface.

Architecture Principles
-----------------------

Unified Data Model
~~~~~~~~~~~~~~~~~~

All components share a common Django-based data model located in ``app/eventyay/base/models/``. Key shared entities include:

* **Event** - The central model representing both physical and virtual events
* **Organizer** - Organizations managing events
* **User** - Unified authentication across all components
* **Team** - Permission and access control

Component-Specific Models
~~~~~~~~~~~~~~~~~~~~~~~~~

Each component extends the base models with specialized functionality:

**Tickets Component Models:**

* Product, ProductCategory, ProductVariation
* Order, OrderPosition, OrderPayment
* Quota, Voucher, Invoice
* CheckinList, Checkin

**Talk Component Models:**

* Submission, SubmissionType, SubmissionStates
* SpeakerProfile, Review, ReviewPhase
* Schedule, TalkSlot, Track
* CfP (Call for Papers)

**Video Component Models:**

* Room, RoomView, Channel
* BBBServer, JanusServer, JitsiServer, TurnServer
* Poll
* RouletteRequest (networking)

Shared Services
~~~~~~~~~~~~~~~

All components utilize shared services from ``app/eventyay/base/services/``:

* Email delivery and templating
* File storage and uploads
* Payment processing
* Logging and audit trails
* Caching and performance optimization

Directory Structure
-------------------

The unified codebase is organized as follows::

    app/eventyay/
    ├── base/           # Core models, shared services
    ├── control/        # Organizer/admin interface
    ├── presale/        # Public ticket shop
    ├── orga/           # Talk organizer interface
    ├── agenda/         # Public talk schedule
    ├── cfp/            # Call for papers interface
    ├── features/       # Video and advanced features
    │   ├── live/       # Live streaming
    │   ├── integrations/
    │   └── social/
    ├── api/            # REST API
    ├── plugins/        # Plugin system
    └── config/         # Django settings

Authentication & Permissions
----------------------------

Eventyay uses a unified authentication system:

* Single sign-on across all components
* Role-based access control (RBAC)
* Team-based permissions
* OAuth2 support for third-party integrations

Users can have different roles:

* **Superuser** - Full system access
* **Organizer** - Can create and manage events
* **Team Member** - Limited access based on team permissions
* **Speaker/Presenter** - Can submit and manage talks
* **Attendee** - Can purchase tickets and attend events

Database Schema
---------------

The unified database schema uses PostgreSQL (recommended) with the following key relationships:

.. code-block:: text

    Organizer (1) ──── (N) Event
        │                   │
        │                   ├── (N) Product (Tickets)
        │                   ├── (N) Submission (Talks)
        │                   ├── (N) Room (Video)
        │                   └── (N) Order
        │
        └── (N) Team ─── (N) User

API Architecture
----------------

The unified REST API (``/api/v1/``) provides access to all components:

* **GET /api/v1/organizers/** - List organizers
* **GET /api/v1/organizers/{org}/events/** - List events
* **GET /api/v1/organizers/{org}/events/{event}/products/** - Tickets
* **GET /api/v1/organizers/{org}/events/{event}/submissions/** - Talks
* **GET /api/v1/organizers/{org}/events/{event}/rooms/** - Video rooms

All API endpoints support:

* Token authentication
* OAuth2 authentication
* Pagination
* Filtering and searching
* Webhooks for real-time updates

Plugin System
-------------

Eventyay supports plugins that can extend all components:

.. code-block:: python

    from eventyay.base.plugins import PluginConfig
    
    class MyPluginApp(PluginConfig):
        name = 'eventyay_myplugin'
        
        class EventyayPluginMeta:
            name = 'My Plugin'
            category = 'FEATURE'
            description = 'Extends eventyay functionality'

Plugins can:

* Add new models and database fields
* Register signal handlers
* Provide custom views and URLs
* Extend the API
* Add payment providers
* Create custom exporters

Frontend Architecture
---------------------

The unified frontend uses:

* **Django Templates** - Server-side rendering for main interfaces
* **Vue.js 3** - Interactive components (schedule editor, live features)
* **Bootstrap 5** - Responsive CSS framework
* **WebSockets** - Real-time updates for video and chat

Key frontend modules:

* ``app/eventyay/static/`` - Shared static assets
* ``app/eventyay/webapp/`` - Frontend applications and shared component libraries
* ``app/eventyay/webapp/video/`` - Video Vue 3 SPA

Deployment Options
------------------

Eventyay can be deployed in several configurations:

**All-in-One (Recommended for small to medium events):**

* Single server running all components
* Docker Compose setup available
* Suitable for events up to 10,000 attendees

**Microservices (For large scale):**

* Separate containers for tickets, talk, video
* Shared database and Redis
* Load balancing and auto-scaling
* Suitable for events with 10,000+ attendees

**Hybrid:**

* Tickets and Talk on one server
* Video on dedicated streaming infrastructure
* Cost-effective for mostly physical events

Environment Variables
---------------------

Unified environment variables (replacing component-specific ones):

* ``EVENTYAY_DB_URL`` - Database connection
* ``EVENTYAY_REDIS_URL`` - Redis connection
* ``EVENTYAY_CONFIG_FILE`` - Configuration file path
* ``EVENTYAY_DATA_DIR`` - Data directory
* ``EVENTYAY_DEBUG`` - Debug mode (development only)

Migration from Legacy Systems
-----------------------------

If migrating from standalone Pretix, Pretalx, or Venueless:

1. **Database Migration:** Use the provided migration scripts in ``app/eventyay/base/migrations/``
2. **Configuration:** Update environment variables to use ``EVENTYAY_`` prefix
3. **Plugins:** Update plugin entry points to use ``eventyay.plugin``
4. **Custom Code:** Update imports from ``pretix.*`` to ``eventyay.*``

For more details on the unified architecture, see the sections above.

Development Setup
-----------------

To set up a local development environment:

.. code-block:: bash

    # Clone the repository
    git clone https://github.com/fossasia/eventyay.git
    cd eventyay
    
    # Set up the app directory
    cd app
    python -m venv venv
    source venv/bin/activate
    
    # Install dependencies
    pip install -e .
    
    # Run migrations
    python manage.py migrate
    
    # Create superuser
    python manage.py createsuperuser
    
    # Run development server
    python manage.py runserver

The unified interface will be available at:

* Admin: http://localhost:8000/control/
* Tickets: http://localhost:8000/
* Talk: http://localhost:8000/orga/
* Video: http://localhost:8000/features/

For more details, see :ref:`devsetup`.

Testing
-------

Run the unified test suite:

.. code-block:: bash

    cd app
    pytest
    
    # Run specific component tests
    pytest eventyay/base/tests/
    pytest eventyay/orga/tests/  # Talk tests
    pytest eventyay/presale/tests/  # Tickets tests
    pytest eventyay/features/tests/  # Video tests

Performance Considerations
--------------------------

The unified architecture provides several performance benefits:

* **Shared Connection Pooling** - All components use the same database connections
* **Unified Caching** - Redis cache shared across components
* **Asset Optimization** - Single build process for all static assets
* **Reduced Memory Footprint** - No duplicate services or processes

For high-traffic events:

* Use PostgreSQL with connection pooling (PgBouncer)
* Enable Redis caching for sessions and data
* Use CDN for static assets and media files
* Configure Celery for background tasks
* Scale horizontally with load balancing

Security
--------

The unified platform implements comprehensive security measures:

* **CSRF Protection** - Django CSRF tokens on all forms
* **XSS Prevention** - Content Security Policy headers
* **SQL Injection Prevention** - Django ORM with parameterized queries
* **Rate Limiting** - API rate limits and throttling
* **Secure Sessions** - HTTPOnly, Secure cookies
* **2FA Support** - Two-factor authentication for organizers

See Also
--------

* :ref:`devsetup` - Setting up your development environment
* :ref:`pluginsetup` - Creating plugins
* :doc:`../api/index` - API documentation
* :ref:`admindocs` - Administrator documentation

