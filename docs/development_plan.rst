.. Development Plan

.. role:: python(code)
    :language: python

============
Design Goals
============

------------------------------------------------------------------------------
Support requests in natural language using terms familiar within the community
------------------------------------------------------------------------------

Names & syntax of commands and keywords should be intuitive & natural, so that
once a user has familiarized themselves with basic operation of the commands,
more advanced use of the commands will come easily.

To this end:

- The [p]taxon command supports a query language.
- Queries can be phrased with English-like structure, like [p]taxon genus
  prunella in animals to match the genus Prunella in the taxon Animalia. This
  complex query actually performs two queries: first, with the query after in
  and second, provided that succeeded, the query before in, passing the
  taxon_id matched by the first query as a filter.

------------------------------------------------------
Don't clutter up conversations with unnecessary output
------------------------------------------------------

Chat sessions can get very busy, so output from most bot commands, especially
those which are used more frequently, should provide the least distraction
from what is said by humans, just showing the essential information required
at the moment, and linking to www.inaturalist.org for the rest.

- https://github.com/dronefly-garden/dronefly/issues/27 is an example issue to help with this goal

----------------------------------------------------------------------
Make use of context from the conversation to avoid needless repetition
----------------------------------------------------------------------

It is tedious to have to tell the bot again what has already been established
as context for the current discussion. It should recognize from patterns in the
conversation key elements that can help provide default context for queries.

- https://github.com/dronefly-garden/dronefly/issues/25 is an example issue to help with this goal

-----------------------------------------------------------------------------------------
Provide additional context from who the user is or where the conversation is taking place
-----------------------------------------------------------------------------------------

Some context should be configurable for a user or channel to avoid having to
provide that information over and over again, e.g.

- Remember who the Discord user is & where they are, supporting queries that
  are filtered by preferred location, preferred taxa, etc.
- Similarly, on channels devoted to discussion of certain taxa, some queries
  might default to be specific to those taxa.
- https://github.com/dronefly-garden/dronefly/issues/14 and
  https://github.com/dronefly-garden/dronefly/issues/15 are example issues to help with
  this goal, and the following goal "Support making & improving social
  connections"

---------------------------------------------
Support making & improving social connections
---------------------------------------------

The bot should facilitate making & improving social connections within
naturalist communities. For example, it could facilitate users browsing &
identifying each other's observations using their user_id on iNaturalist if
they have volunteered that information.

---------------------------------------------
Support collaborative efforts to improve data
---------------------------------------------

An example of an enhancement that would support this goal might be to provide
visible indicators of progress to work parties, such as the ongoing work to
resolve Unknown observations, state by state and province by province in the US
and Canada currently underway on channel #work-party on the unofficial iNat
Discord.

------------------------------------------------------------------------
Improve comprehension of the subject matter being discussed with visuals
------------------------------------------------------------------------

Example issues supporting this goal are
https://github.com/dronefly-garden/dronefly/issues/19 and
https://github.com/dronefly-garden/dronefly/issues/18 to provide at-a-glance overviews of
where taxa are found with maps, without a time-consuming & more bandwidth-heavy
trip out to the web.

==================================
iNaturalist Platform Main Concepts
==================================

-----------------------
Overview: The Big Seven
-----------------------

We refer to these sometimes as the "big seven" concepts of iNaturalist. There
are numerous other entities, such as flags, comments, photos, and sounds, but
these seven are primary areas of focus for most Dronefly bot development.
They are:

- Taxon
- Observation
- User
- Place
- Project
- Time
- Identification

-----
Taxon
-----
Taxon is the first concept we implemented, and therefore is the best
supported of the big seven. We support natural language queries for taxa.
This is a distinctive feature of Dronefly arising from the text-oriented
nature of chat. The usual gui device for narrowing down potential matches,
incremental search, is not an option here. Therefore, some care has been
put into allowing users to refer to taxa in text-based queries without
accidentally retrieving the wrong one (e.g. via the `in` qualifier to
filter matches using a matching ancestor taxon).

-----------
Observation
-----------
The second to be implemented. Access is primarily through `autoobs` feature
(i.e. an observation summary is shown when the user pastes a link to an
observation, as when they share it from the app or web). Additionally,
a growing set of qualifiers are being added to the query language to bring
observation searches in Discord up to par with all of the various search
options on iNaturalist website. For example, `by` a user, `from` a place,
and `with` an annotation are currently supported, and more along these
lines are planned.

----
User
----
We extend the iNaturalist concept of User by linking it to the Discord user
identity. Members are registered by the mods of each server as they join
and indicate assent to this registration by sharing their profile links.
Access to user data is primarily through `my` search qualifier and :hash:
reaction which adds a member's observation & species counts to a taxon
display, linked to those observations on the web. These displays can
handle counts from several members at once, allowing to gain insight
and inspiration through comparison, as well as to assist each other in
identifying what they've found.

-----
Place
-----
Places in iNat can be somewhat awkward to access. We support server member
defined place abbreviations for places found via `[p]search place` as a
convenient way to refer to them. Subsequently, the most common way to
access place data is through the `from` qualifier in a command, or by
pressing the :house: place reaction to add the member's "home place" to a
taxon display.

-------
Project
-------
Projects in iNat need the same sort of help, so abbreviations for projects
can be defined by members similarly. At time of writing, support for project
in bot commands is not as well developed as places, but better support is
coming soon.

----
Time
----
The iNaturalist API includes a number of search options, largely relating to
observation searches, to limit results to specific time periods. As of
writing, we are still planning support, but aim to start adding qualifiers
such as `on` a particular relative or absolute date, as well as `since`,
`before`, and `between`. Tabulation of search results per month or per time
of day are more distant future plans for the time concept.

--------------
Identification
--------------
Finally, identifications round out the seven. They are weakly supported to
date, only showing up as a grand total & link to one's own identifications in
the `[p]me` command. We feel that to handle identifications effectively, all
of the first six concepts need to be more solidly supported, and besides,
that identification itself is best accomplished on the web. That said, we
would like to see some support for search & tabulation of one's own
identifications that would aid in an individual identifier gaining insight,
such as understanding which taxa they have yet to learn how to ID accurately.
