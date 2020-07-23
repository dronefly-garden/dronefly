.. Design Goals

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

- https://github.com/synrg/dronefly/issues/27 is an example issue to help with this goal

----------------------------------------------------------------------
Make use of context from the conversation to avoid needless repetition
----------------------------------------------------------------------

It is tedious to have to tell the bot again what has already been established
as context for the current discussion. It should recognize from patterns in the
conversation key elements that can help provide default context for queries.

- https://github.com/synrg/dronefly/issues/25 is an example issue to help with this goal

-----------------------------------------------------------------------------------------
Provide additional context from who the user is or where the conversation is taking place
-----------------------------------------------------------------------------------------

Some context should be configurable for a user or channel to avoid having to
provide that information over and over again, e.g.

- Remember who the Discord user is & where they are, supporting queries that
  are filtered by preferred location, preferred taxa, etc.
- Similarly, on channels devoted to discussion of certain taxa, some queries
  might default to be specific to those taxa.
- https://github.com/synrg/dronefly/issues/14 and
  https://github.com/synrg/dronefly/issues/15 are example issues to help with
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
https://github.com/synrg/dronefly/issues/19 and
https://github.com/synrg/dronefly/issues/18 to provide at-a-glance overviews of
where taxa are found with maps, without a time-consuming & more bandwidth-heavy
trip out to the web.
