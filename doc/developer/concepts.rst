Concepts and Terminology
========================

The Components
--------------

pretalx is split into a range of components (also called “apps”, following the
Django terminology). These are the most important ones:

**common**
    Templates, models, and utility methods used in all areas of pretalx live here.

**event**
    This component contains all models and methods regarding events, organisers,
    teams, and their relationships with each other.

**mail**
    Everything concerning email sending and templating takes place here.

**person**
    The custom pretalx user model, as well as speaker profiles.

**schedule**
    All matters regarding schedules, scheduling, talk slots, conflict resolution,
    etc, come from here.

**submission**
    This component contains the submission model and all other models that are
    tied directly to it, such as tracks, submission types, questions and answers,
    the submission state machine, etc.

**agenda**
    In this frontend component you can find all templates and views for the
    public schedule pages.

**cfp**
    This frontend component contains all templates and views for the submission
    workflow and the private speaker area.

**orga**
    This frontend component holds all templates and views for the organiser backend.

**api**
    All matters regarding the RESTful pretalx API live here.


The Concepts
------------

This is how pretalx sees the world – so if anything here strikes you as very
wrong, chances are pretalx will not work well for you. If this happens, please
let us know by `opening an issue`_!

Persons
~~~~~~~

pretalx tries to treat its users as the persons they actually are. This
involves allowing people to be both organisers and speakers at one or multiple
events. Even submitting proposals to an event and then reviewing other
proposals is something pretalx allows (although the submitter will never be
able to see the reviews their own submission received).

It is expected that people can take part in as many events as they like, in any
role they like. Naturally, a non-bounded number of people can present any talk.

Events and organisers
~~~~~~~~~~~~~~~~~~~~~

**Events** take place once, over the course of one or multiple days. Events
belong to an **organiser**, which is an entity that can take on one or multiple
events.

**Teams** run events or certain parts of events for an organiser. A team is
defined as a number of people who share the same rights and responsibilities
with regards to one or multiple events. People can be in multiple teams. A team
can run multiple events, and most events will have multiple teams associated
with them.

Submissions and Reviews
~~~~~~~~~~~~~~~~~~~~~~~

**Submissions** (or: proposals) are a cornerstone of how pretalx's
understanding of the world. A submission will have at least a title and as many
other fields as the organisers have specified, either by requiring or removing
the built-in fields, or by adding questions of their own. A submission will
probably have one or multiple speakers.

Submissions have a **state**. They start out as *submitted*. While they are
submitted, they can be *deleted* or *withdrawn*. Organisers can then change the
submission state to *accepted* or *rejected* (typically after the CfP has
closed and the review phase is over). An *accepted* proposal can then be
*confirmed* by any of their speakers (or the organisers, who can set any
submission to any state, if need be).

Both *accepted* and *confirmed* submissions can be *canceled* to indicate that
a planned presentation will not take place after all.

Schedules and Slots
~~~~~~~~~~~~~~~~~~~

A **schedule** is a versioned programme of an event. Any event will have at
least one schedule – the unreleased, work-in-progress schedule. At any time,
organisers can “freeze” this schedule to a released **version**, that will go
by a name organisers can choose. Speakers will receive updates if their
presentations have been moved, and attendees can look at the changelog to see
differences between versions.

**Slots** are the scheduled instances of a submission. Regularly, a submission
will have one slot per schedule, but submissions can also have more than that,
for example if a workshop will be held twice.

.. _opening an issue: https://github.com/pretalx/pretalx/issues/new
