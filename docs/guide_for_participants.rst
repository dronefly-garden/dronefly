.. iNaturalist Discord Server Guide for Participants

=================================================
iNaturalist Discord Server Guide for Participants
=================================================


Discord Basics
--------------

Discord is a proprietary freeware VoIP application and digital
distribution platform that specializes in text, image, video and audio
communication between users in a chat channel. Discord runs on Windows,
macOS, Android, iOS, Linux, and in web browsers.

Get Discord
^^^^^^^^^^^

Browser URL:
`https://discordapp.com/ <https://discordapp.com/channels/@me>`__

Software: https://discordapp.com/download

You can also find the Discord app in the Apple App Store or on Google
Play.

Once you have Discord, you’ll need an invitation to the iNaturalist
Discord server. A permanent standing invitation exists here:

https://discord.gg/eCD4WvT (opens in #introductions)

Discord Layout and Functions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Discord will look different depending on platform, but in general, you
can expect something like this:

|image1|

Let’s take a look at each of those features in more detail:

|image2|

You can change your status by clicking on your avatar in the lower left,
and using the pop-up menu.

|image3|

|image4|

The home button will take you to your Home Screen, from which you can
Direct Message other users, see your Friends and start video or voice
calls with them.

Each of the servers (a.k.a. guilds) you belong to are shown. In this
case, we’ll focus on the iNaturalist Discord server, but there’s also
Dronefly (related to bot development) where you can find many of the
same participants.

Allows you to add other servers

Allows you to look for other servers

|image5|

Selecting the down arrow next to the Server name in the upper left
allows you to take a variety of actions, including:

|image6|

Inviting friends and other naturalist professionals to join us (if you
use this, create from #introductions)

Adjusting your notification settings (see Appendix A)

Allowing or prohibiting direct messages from other users

Changing your nickname (for instance, to add your location to your
nickname, e.g. michaelpirrello \|\| Pennsylvania)

Leaving (Hopefully you’ll never want to, but sometimes life gets in the
way.)

Beneath the iNaturalist header bar is the channel list. Channels are
organized by the categories shown. You may have categories or channels
of particular interest, and others you have no interest in. You can
collapse categories as shown, or expand them to see all the channels. If
you collapse the categories, only those channels with new content will
be shown.

|image7|

If you want to mute a channel, the easiest way is to use the bell icon
in the upper right corner once you’re in a channel (|image8|).

|image9|

When you first join the server, visit the #introductions channel (under
the Important heading), where the Dronefly bot (and hopefully some
active users) will welcome you.

If you want to participate in the server’s iNaturalist projects, or use
the Dronefly bot, post your profile (https://www.inaturalist.org/people/
followed by your username or user number, e.g.
https://www.inaturalist.org/people/1276353).

You can find your profile using the menu in the upper right corner when
you’re using iNaturalist in a browser.

Pinned messages are posts that have occurred in a channel that
moderators have decided are either particularly important, or equally as
likely, particularly funny. You’ll find both useful information and
humorous items in pinned messages.

|image10|

For instance, in the #bot-stuff channel, you’ll find information about
commands you can use with bots as pinned items.

Other pinned items may be...less useful.

|image11|

The member list button (|image12|) at the upper right toggles the member
list visibility on and off (good if you need more screen space, or if
you need to contact an Admin or a Moderator and want to know who is
available.) Right clicking on users in the member list allows you to see
their profile (which can be helpful when temporary nickname changes
occur).

Get Set Up using the #role-menus Channel
----------------------------------------

The #role-menus channel (under the Important heading) is one of the
first channels every new user should visit. Configuring details about
your appearance on the server and the roles you want is as easy as
pressing some buttons. Roles primarily allow you to be notified when
someone is seeking information on a topic you’re interested in, or
something is happening you may want to participate in (e.g. a voice
chat).

|image13|

Other roles can only be assigned by moderators (some by request, and
some based on achievement. For instance, talking with people on the
server will earn you the Naturalist role.

Using the Discord Bots
----------------------

Access to the Discord bots is one of the great benefits of being on the
server. Bots are primarily for obtaining information.

There are several bots, which are instances of `Red Discord
Bot <https://github.com/Cog-Creators/Red-DiscordBot>`__, each with a
different function. You can access the functions of the bots using the
prefix specific to the bot:

`Dronefly <https://github.com/synrg/dronefly/>`__ (,) - Accesses
iNaturalist and other naturalist-related web platforms.

Dumbo (-) - For general purpose admin & info functions, not strictly
nature-related (e.g. Twitter and Wikipedia).

Pickerel ($) - Plays audio (e.g. music) from SoundCloud, Spotify, and
YouTube in the Music channel.

(CuckooBee (/ or c.) is the development version of Dronefly, so if
you’re not interested in bot development, you won’t need it. If you
indicate that you’re interested in helping with bot testing, you may
occasionally receive an invite to participate in testing features.)

|image14|

Notes on reading the online bot help:

-  If there is no punctuation, type it exactly as shown (literal)
-  If there are <angle brackets>, it is representative of what should be
   typed
-  If there are [square brackets,] it is an optional input

Dronefly
^^^^^^^^

(access help using *,help*)

A guide to using the Dronefly bot is available on the iNaturalist Forum
here:

https://forum.inaturalist.org/t/how-to-use-dronefly-a-discord-chat-bot/9770

Syntax: *,inat -*\ Access the iNaturalist platform. See the help topics
for each subcommand for details.

Commands
""""""""

*,image* (*,img*) - Show default iNaturalist image for taxon
query.

|image16| \ |image15| 

Note that you can press the buttons below the image to generate
reactions with information (shown above the image on the right) as
follows:

|image17| \ Will indicate the number of observations you’ve made

|image18| \ Will indicate the number of observations made by a user you
specify

|image19| \ Will indicate the number of observations from your home place
(see\ *,user* below)

|image20| \ Will indicate the number of observations made from a place
you specify

|image21|

*,last* - Show info for recently mentioned iNaturalist page. (operators
are *obs* or *taxon*). Can be further expanded using *<rank>*, *img*,
*map* or *taxon*.

*,link* - Show summary for iNaturalist link.

|image22|

*,map* - Show iNaturalist range map for a list of one or more taxa
(comma delimited)

|image23|

*,obs* - Show observation summary for iNaturalist link or number, or
taxa.

(supports *by <user>* and *from <place>*)

|image24|

*,place* - Show a place by number, name, or abbreviation defined with
*,place add* (operators are\ *add*\ or *remove*)

A list of place abbreviations can be generated with *,place list*.

|image25|

*,project <query> -* Show iNat project or abbreviation, with <query>
containing ID# of the iNat project, words in the iNat project name, or
abbreviation defined with\ *,project add <abbrev> <project_number>*)

A list of project abbreviations can be generated with *,project list*.

*,project stats* (*,rank*) - Show project stats for the named user.
(*,rank <project> <user>*)

(*,my* is an alias for\ *,rank <project> me* and will show you your own
project statistics, e.g.\ *,my 2020*)

|image26|

*,related* - Relatedness of a list of taxa (taxa can be iNaturalist
taxon ID numbers, common names, or scientific names)

|image27|

*,search* (*,s*) - Search iNat.

Search subcommands
""""""""""""""""""

*inactive* - Search iNat taxa (includes inactive - exact match only)

*obs*- Search iNat observations.

*places* - Search iNat places.

*projects* - Search iNat projects.

*taxa* - Search iNat taxa (does not include inactive)

*users* - Search iNat users.

Arrow keys allow paging through pages of results. See `Appendix
C <#_4whij4v6yazk>`__ for icons.

*,taxon* (*,t*) - Show taxon best matching the query. Query may
contain:

|image28|

   - id# of the iNaturalist taxon

..

   - initial letters of scientific or common names

   - double-quotes around exact words in the name

..

   - rank keywords filter by ranks (sp, family, etc.)

   - `AOU 4-letter code <https://www.birdpop.org/pages/birdSpeciesCodes.php>`__ for birds

..

   - taxon in an ancestor taxon

   Note: Dronefly also supports *,species*.

,user - Show user if their iNaturalist ID is known.

|image29|

(*,me* is an alias for ,user me and will show you your own statistics)

(Compare against *-userinfo*)

(,user set home <#> - Allows the user to specify a home location. To
obtain a place number, go to the iNaturalist place page for your
location (https://www.inaturalist.org/places/\ <place>) and either
append .json to the end of the URL, or click on Embed Place Widget. The
number for the place will be shown in the URL.

|image30|

↓

|image31|\ →\ |image32|

|image33|

(,user set known - Allows the user to be known/unknown to instances of
Dronefly running on, as of the time of this writing, 14 other servers.
Operators are *True* and *False*.)

|image34|

Type *,help <command>* for more info on a command (e.g.\ *,help taxon*).
You can also type *,help <category>* for more info on a category
(e.g.\ *,help inat*).

An exception to the rule about using the comma prefix for Dronefly is
the *,dot_taxon*\ command. Surrounding text with periods will trigger
one lookup per message (which is useful when using AOU codes, for
example). Spaces are required before and after, although the command can
be used at the start of a line, if needed. The lookup can also utilize
the “by user” and “from place” conventions.

|image36| \ |image35|

Dronefly also utilizes custom commands that can be used to draw data
from other nature-related sites:

Custom commands
"""""""""""""""

*,bhl*-
`https://www.biodiversitylibrary.org/search?searchTerm={0:query}#/titles <https://www.biodiversitylibrary.org/search?searchTerm=lygaeus+kalmii#/titles>`__

*,bold3* -
https://v3.boldsystems.org/index.php/Public_SearchTerms?query=%7B0:query}
(put genus or binomial after command)

*,bold4* -
http://www.boldsystems.org/index.php/Public_BINSearch?searchtype=records&query=%7B0:query}
(see
http://www.boldsystems.org/index.php/Public_BINSearch?searchtype=records
for support of quotes, exclusions, and bracketed clarifications: [geo],
[ids], [inst], [researcher], [tax])

*,bonap* - http://bonap.net/NAPA/TaxonMaps/Genus/County/%7B0:query} (put
capitalized plant Genus after command)

*,bonapgen* -
`http://bonap.net/MapGallery/County/Genus/{0:query}.png <http://bonap.net/MapGallery/County/Genus/lonicera.png>`__
(put plant genus after command)

*,bonapsp* - http://bonap.net/MapGallery/County/%7B0:query%7D%7B1:query}
(put plant binomial after command)

*,bug* - https://www.insectimages.org/search/action.cfm?q=%7B0:query}
(put search term after command)

*,gbif* - https://www.gbif.org/search?q=%7B0:query} (put search term
after command)

*,hostplant* -
https://www.nhm.ac.uk/our-science/data/hostplants/search/list.dsml?searchPageURL=index.dsml&PGenus=%7B0:query}
(put lepidopteran host plant genus after command)

*,hostplantsp* -
https://www.nhm.ac.uk/our-science/data/hostplants/search/list.dsml?searchPageURL=index.dsml&PGenus=%7B0:query%7D&PSpecies=%7B1:query}
(put lepidopteran host plant binomial after command)

*,hosts* -
https://www.nhm.ac.uk/our-science/data/hostplants/search/list.dsml?searchPageURL=index.dsml&Genus=%7B0:query}
(put lepidoptera genus after command)

*,hostsp* -
https://www.nhm.ac.uk/our-science/data/hostplants/search/list.dsml?searchPageURL=index.dsml&Genus=%7B0:query%7D&Species=%7B1:query}
(put lepidoptera binomial after command)

*,ilwild* -
https://illinoiswildflowers.info/plant_insects/plants/%7B0:query%7D_spp.html
(put plant genus after command)

,ilwildsp -
https://illinoiswildflowers.info/plant_insects/plants/%7B0:query%7D_%7B1:query%7D.html
(put plant binomial after command)

*,lichen
-*\ https://lichenportal.org/cnalh/taxa/index.php?taxon=%7B0:query%7D&formsubmit=Search+Terms
(put lichen genus or binomial after command)

*,maverick* -
https://www.inaturalist.org/identifications?category=maverick&user_id=%7B0:query}
(put iNaturalist username after command)

*,miflora* - https://michiganflora.net/genus.aspx?id=%7B0:query} (put
plant genus after command)

*,millibase* -
http://www.millibase.org/aphia.php?tName=%7B0:query%7D&p=taxlist (put
diplopod taxa of interest after command)

*,moobs* -
https://mushroomobserver.org/observer/observation_search?pattern=%7B0:query}
(put fungi genus or binomial after command)

*,paflora* -
http://paflora.org/original/sp-page.php?submitted=true&criteria=%7B0:query}
(put plant binomial after command)

*,pfaf* - https://pfaf.org/user/Plant.aspx?LatinName=%7B0:query} (put
plant genus or binomial after command)

*,powo* - http://www.plantsoftheworldonline.org/?q=%7B0:query} (put
plant taxa of interest after command)

*,rfwo* -
<https://www.robberfliesoftheworld.com/TaxonPages/TaxonSearch.php?taxonsearch=%7B0:query}>
(put capitalized robber fly Genus after command)

*,sitetopic
-*\ `https://www.google.com/search?q=site%3A{0:query}+{1:query} <https://www.google.com/search?q=site%3A%7B0:query%7D+%7B1:query%7D+%7B2:query>`__
(put site in format domain.tld and search term(s) after command)

*,smith* -
https://www.si.edu/search/collection-images?edan_q=%7B0:query%7D&edan_fq=media_usage%3ACC0
(put search term after command)

*,stats* - https://www.inaturalist.org/stats/%7B0:query%7D/%7B1:query}
(put year and iNaturalist username after command)

*,tol* - http://tolweb.org/%7B0:query} (put taxon at family level or
above after command)

*,ts* - <https://www.inaturalist.org/taxa/search?q=%7B0:query}> (search
iNaturalist taxa, whole words only)

*,wildflower*-
https://www.wildflower.org/plants/search.php?search_field=%7B0:query%7D&newsearch=true\ (put
plant genus or binomial after command)

*,worms* -
http://www.marinespecies.org/aphia.php?p=taxlist&action=search&tName=%7B0:query}
(put marine species taxa of interest after command)

*,xc* - https://www.xeno-canto.org/explore?query=%7B0:query} (put bird
taxa of interest after command)

*,xcsp* - https://www.xeno-canto.org/species/%7B0:query%7D-%7B1:query}
(put bird species of interest after command)

*,xcssp* -
https://www.xeno-canto.org/species/%7B0:query%7D-%7B1:query%7D?query=ssp:%22%7B2:query%7D%22
(put bird subspecies of interest after command)

Dumbo
^^^^^

(access help using *-help*)

*-conv* - Convert a value

Conv Subcommands
""""""""""""""""

celsius (c) Convert degree Celsius to Fahrenheit or Kelvin.

fahrenheit (f) Convert Fahrenheit degree to Celsius or Kelvin.

kelvin (k) Convert Kelvin degree to Celsius or Fahrenheit.

kg Convert kilograms to pounds.

|image37|

km Convert kilometers to miles.

lb Convert pounds to kilograms.

mi Convert miles to kilometers.

todate Convert a unix timestamp to a readable datetime.

tounix Convert a date to a unix timestamp.

*-antonym* - Displays antonyms for a given word.

*-define* - Displays definitions of a given word.

*-synonym* - Displays synonyms for a given word.

|image38|

*-time* - Checks the time.

For the list of supported timezones, see here:
https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

Time subcommands
""""""""""""""""

compare Compare your saved timezone with another user's timezone.

iso Looks up ISO3166 country codes and gives you a supported timezone

me Sets your timezone.

tz Gets the time in any timezone. (e.g.\ *-time tz America/New_York*)

user Shows the current time for user.

*-tweets* - Gets information from Twitter's API

|image39|

Tweets subcommands
""""""""""""""""""

gettweets Display a users tweets as a scrollable message

getuser Get info about the specified user

trends Gets trends for a given location

|image40|

*-userinfo* - Show Discord info about a user.

|image41|

*-weather (-we)* - Display weather for a location

Syntax: *-weather <location>* (location must take the form of city,
Country Code, for example: *-weather New York,US*)

Weather subcommands
"""""""""""""""""""

cityid Display weather in a given location

co Display weather in a given location

zip Display weather in a given location

See:https://bulk.openweathermap.org/sample/city.list.json.gz)

|image42|

*-wikipedia* (-wiki) - Get information from Wikipedia.

Dumbo also uses custom commands:

Custom commands
"""""""""""""""

*-abbrev* - https://www.abbreviations.com/%7B0:query%7D

*-dict* - https://www.merriam-webster.com/dictionary/%7B0:query%7D

*-down* - https://downforeveryoneorjustme.com/inaturalist.org (nothing
entered after)

-radar -
https://weatherstreet.com/ridge/%7B0:query%7D-%7B1:query%7D-%7B2:query%7D-radar.htm
(enter capitalized City ST Zip)

-rloop - https://radar.weather.gov/ridge/lite/N0R/%7B0:query%7D_loop.gif
(enter 3 character Site ID from
https://www.roc.noaa.gov/WSR88D/Program/SiteID.aspx)

*-wiktionary*- https://en.wiktionary.org/wiki/%7B0:query%7D

Pickerel
^^^^^^^^

(access help using $help)

Syntax: $play <query>

*Commands:* (Note: Please use in #music channel, listen in |image43|)

$autoplay - Starts auto play. (DJ role required if enabled)

$bump - Bump a track number to the top of the queue.

$bumpplay - Force play a URL or search for a track.

$eq - Equalizer management.

$genre - Pick a Spotify playlist from a list of categories to star...

$local - Local playback commands.

$now - Now playing.

|image44|

$pause - Pause or resume a playing track.

$percent - Queue percentage.

$play - Play a URL or search for a track. (DJ role required if enabled)

$playlist - Playlist configuration options.

$prev - Skip to the start of the previously played track.

$queue - List the songs in the queue.

$remove - Remove a specific track number from the queue.

$repeat - Toggle repeat.

$search - Pick a track with a search.

$seek - Seek ahead or behind on a track by seconds

$shuffle - Toggle shuffle.

$sing - Make Red sing one of her songs. (DJ role required if enabled)

$skip - Skip to the next track, or to a given track number.

$stop - Stop playback and clear the queue.

$volume - Set the volume, 1% - 150%.

Participating - #chat (under General)

Follow the rules for communicating with others in the #welcome channel.

#chat and #chat-2-electric-bugaloo are both general nature-oriented chat
channels. If one is busy with an ongoing discussion, and you want to
start a new topic, use the other.

Basic functions
"""""""""""""""

Typing\ *@username* will “ping” the user.

Typing *#channel* will create a link to that channel.

The emoji menu (|image45|) next to each message provides numerous ways
to react.

|image46|\ on the left of the message bar allows for uploading files and
images to the chat.

Let a moderator know if you think a file is important enough to be
pinned.

Participating - #suggestions (under Important)
----------------------------------------------

Anyone can make a suggestion to improve the server in this channel.

Participating - #inat-questions and #inat-curation (under iNat Stuff)
---------------------------------------------------------------------

Ask and answer user and curator questions about iNaturalist and how it
works in these channels. Don’t forget to check pinned messages and use
the search function to see if your question has been asked/answered
before. If you can’t get an answer here, the iNaturalist Forum is
another good place to post questions: https://forum.inaturalist.org/

Participating - #id-confirmation and #work-party (under Identify)
-----------------------------------------------------------------

Use the #id-confirmation channel for:

-  Posting an observation where you’ve made an ID and are looking for a
   confirmation.
-  Posting an observation where you’re looking for a more specific
   identification (or, post in a taxa-specific channel - both are
   appropriate)

Use the #work-party channel for:

Posting tasks for the general good of iNaturalist that server
participants can help with.

Examples include:

-  Posting Unknowns that need coarse ID’s
-  Correcting misidentifications (where a misidentification is firmly
   embedded with many confirmations, you can also ping the @work-party
   role)
-  https://forum.inaturalist.org/t/state-of-matter-life-clean-up/3556
-  https://forum.inaturalist.org/t/computer-vision-clean-up-wiki/7281
-  https://forum.inaturalist.org/t/ways-to-help-out-on-inat-wiki/1983

Participating - |image47|\ General and #vc-general (under Voice Channels)
-------------------------------------------------------------------------

Voice channels (like |image48|) allow you to talk and listen to other
iNaturalist Discord Server participants in real time.
Presentations/Entertainment may take place here as well. #vc-general is
used for text chat in support of the General voice channel (e.g. sharing
pictures as you talk.)

The Go Live! Feature (|image49|) allows for screen sharing (only in the
Discord software, not available in the browser version). Once a
presenter goes live, you will need to select “Join Stream” to see the
screen they’re sharing.

|image50|

Please don’t forget to mute yourself (|image51|) if someone else is
presenting.

Appendix A - Notification Settings
----------------------------------

Suggested starting point for Notification Settings:|image52|

|image53|

Scroll down a bit further, and you can adjust notification settings for
each channel (example shown is not a recommendation).

Appendix B - Text Formatting
----------------------------

|image54|

Highlighting text before submitting will bring up a formatting menu.

|image55|

Right clicking that same highlighted text brings up a spellcheck
function.

Preceding and following text with \*\* (e.g. \**stuff**) will bold the
text: **stuff**

Preceding and following text with \* (e.g. \*stuff*) will italicize the
text: *stuff*

Preceding and following text with ~~ (e.g. ~~stuff~~) will strikethrough
the text: [STRIKEOUT:stuff]

Preceding and following text with \|\| (e.g. \||stuff||) will hide the
text until readers click it.

Preceding and following text with \` (e.g. \`stuff`) will quote text
(good for displaying command text when you don’t want it to execute).

A double quote function is also available from the formatting menu, that
precedes the word with a line and space to represent quoted text. (also
available from the ellipsis menu (|image56|) next to each message for
quoting previous posts with attribution)

|image57|

There are also text commands that you can be put in front of text (e.g.
*/shrug* Oh well!)

Appendix C - Search Result Icons
--------------------------------

Dronefly search results are accompanied by icons as follows:

========= ====================================
|image58| Photo(s) associated with observation
|image59| Sound(s) associated with observation
|image60| Observation is Research Grade
|image61| Observation Needs ID
|image62| Observation is Casual Grade
|image63| Observation is favorited
|image64| Observation has identification
|image65| Observation has comment
\         
========= ====================================

.. |image1| image:: ./Pictures/100000000000077A000004076AFB08886503F74E.jpg
   :width: 6.5in
   :height: 3.5in
.. |image2| image:: ./Pictures/10000201000000F0000001434F32C3C13C3E72C3.png
   :width: 2.5in
   :height: 3.3646in
.. |image3| image:: ./Pictures/100002010000005A0000019360ADD80972C8EEE6.png
   :width: 0.9374in
   :height: 4.198in
.. |image4| image:: ./Pictures/1000020100000050000000472C9E00C3AA81D7C8.png
   :width: 0.8335in
   :height: 0.7398in
.. |image5| image:: ./Pictures/100002010000011F0000003216D33AF1B3D61D46.png
   :width: 2.0035in
   :height: 0.3484in
.. |image6| image:: ./Pictures/10000201000001110000017A0F43164E2CE8E238.png
   :width: 1.9819in
   :height: 2.7453in
.. |image7| image:: ./Pictures/10000201000001320000026A99731C47D04BB7F0.png
   :width: 1.9819in
   :height: 4.0047in
.. |image8| image:: ./Pictures/1000020100000029000000262823531D29C7DD9A.png
   :width: 0.4272in
   :height: 0.3957in
.. |image9| image:: ./Pictures/10000201000002F400000297C8ECDD52253957FB.png
   :width: 3.4638in
   :height: 3.0366in
.. |image10| image:: ./Pictures/100002010000014800000256510E40EA74BD26CD.png
   :width: 3.4165in
   :height: 6.2291in
.. |image11| image:: ./Pictures/10000201000001AD000001A71721D3688D65BE7A.png
   :width: 2.8902in
   :height: 2.8693in
.. |image12| image:: ./Pictures/100002010000002D0000002C98B36B1C092470C9.png
   :width: 0.4689in
   :height: 0.4583in
.. |image13| image:: ./Pictures/100002010000041D000003190B51C9BC5E795518.png
   :width: 6.5in
   :height: 4.889in
.. |image14| image:: ./Pictures/10000201000001130000008B6AF6654BB1A42C7D.png
   :width: 2.3335in
   :height: 1.1811in
.. |image15| image:: ./Pictures/10000201000002810000029F5458DEAE73669FAF.png
   :width: 2.4307in
   :height: 2.5417in
.. |image16| image:: ./Pictures/1000020100000285000002685FD7FC876BEFD905.png
   :width: 2.6583in
   :height: 2.5417in
.. |image17| image:: ./Pictures/10000201000000210000001F4AB7933E2A4F1722.png
   :width: 0.3437in
   :height: 0.3228in
.. |image18| image:: ./Pictures/100002010000002100000020FF4EF22C23D7F5B6.png
   :width: 0.3437in
   :height: 0.3335in
.. |image19| image:: ./Pictures/100002010000002400000025EF2D49C687F8E627.png
   :width: 0.3484in
   :height: 0.3583in
.. |image20| image:: ./Pictures/1000020100000026000000212E24246F193494CE.png
   :width: 0.3598in
   :height: 0.3098in
.. |image21| image:: ./Pictures/100002010000020800000258EB656E6526D9BD11.png
   :width: 3in
   :height: 3.4634in
.. |image22| image:: ./Pictures/10000201000002C0000000DD3DDA345EE14A8D95.png
   :width: 3in
   :height: 0.9429in
.. |image23| image:: ./Pictures/10000201000001D000000119C73D8ECFE4573FC2.png
   :width: 3in
   :height: 1.8165in
.. |image24| image:: ./Pictures/10000201000001F3000001D5F04D480E7BCC3535.png
   :width: 3in
   :height: 2.8283in
.. |image25| image:: ./Pictures/10000201000001E1000001D1B0D96A8BEE6D7047.png
   :width: 3in
   :height: 2.9008in
.. |image26| image:: ./Pictures/10000201000001CF000000F4CCF4BB5A6896A7CF.png
   :width: 3in
   :height: 1.5839in
.. |image27| image:: ./Pictures/100002010000024A000001E1A1677C8E37D4E4C9.png
   :width: 3in
   :height: 2.4701in
.. |image28| image:: ./Pictures/10000201000002C00000016F875D7653A349ED74.png
   :width: 2.9992in
   :height: 1.5575in
.. |image29| image:: ./Pictures/1000020100000284000000FAB2C0427E13B6FC17.png
   :width: 3.5173in
   :height: 1.3693in
.. |image30| image:: ./Pictures/100002010000022B00000031ABFED1C8B2F24AFE.png
   :width: 5.7811in
   :height: 0.5102in
.. |image31| image:: ./Pictures/100002010000009800000022AB3C7761A61A6539.png
   :width: 1.5835in
   :height: 0.3543in
.. |image32| image:: ./Pictures/10000201000001B90000002A24F9084D2D5236AB.png
   :width: 4.1819in
   :height: 0.3984in
.. |image33| image:: ./Pictures/10000201000002EB000000BCB083D5A39481F5DE.png
   :width: 4.9953in
   :height: 1.2583in
.. |image34| image:: ./Pictures/100002010000028A000000B5A33BFADBBD3BE1CD.png
   :width: 4.9744in
   :height: 1.3772in
.. |image35| image:: ./Pictures/10000201000001E00000011E4D5DA932EC03E6C0.png
   :width: 2.9791in
   :height: 1.7756in
.. |image36| image:: ./Pictures/10000201000002B8000001770AD72CC54041BD01.png
   :width: 3.2673in
   :height: 1.7709in
.. |image37| image:: ./Pictures/10000201000001D40000009C9F0962AC9C0D2E3E.png
   :width: 3.4744in
   :height: 1.1701in
.. |image38| image:: ./Pictures/10000201000002E50000009729AC90737CC41BC4.png
   :width: 4.5083in
   :height: 0.922in
.. |image39| image:: ./Pictures/10000201000001D5000000C6B2AEF1A25BA94725.png
   :width: 3in
   :height: 1.2709in
.. |image40| image:: ./Pictures/10000201000002E500000166ED910A3A86D21D56.png
   :width: 3.0209in
   :height: 1.4571in
.. |image41| image:: ./Pictures/100002010000020C00000162D806B84E7E9DB2ED.png
   :width: 2.9953in
   :height: 2.0307in
.. |image42| image:: ./Pictures/10000201000002AF0000010951D4D9B934D2DCF7.png
   :width: 3.0209in
   :height: 1.1638in
.. |image43| image:: ./Pictures/10000201000000640000002B2A657DA24D965E10.png
   :width: 1.0417in
   :height: 0.448in
.. |image44| image:: ./Pictures/100002010000029900000165ECD4DE3FC63800C2.png
   :width: 4.7339in
   :height: 2.5453in
.. |image45| image:: ./Pictures/10000201000000220000001FB9D9ACF1EF1482A3.png
   :width: 0.3543in
   :height: 0.3228in
.. |image46| image:: ./Pictures/100002010000003100000028EEDA160002369D4E.png
   :width: 0.422in
   :height: 0.3445in
.. |image47| image:: ./Pictures/100002010000025800000258247DEE2DD1751D78.png
   :width: 0.2201in
   :height: 0.2201in
.. |image48| image:: ./Pictures/1000020100000070000000246A7043DFA53E0C76.png
   :width: 1.1665in
   :height: 0.3752in
.. |image49| image:: ./Pictures/10000201000000290000002850EF6815787F2825.png
   :width: 0.4272in
   :height: 0.4165in
.. |image50| image:: ./Pictures/10000201000002720000014A3EA906AB828506AE.png
   :width: 6.5in
   :height: 3.4307in
.. |image51| image:: ./Pictures/10000201000000270000002CAF1826D3E67AA112.png
   :width: 0.4063in
   :height: 0.4583in
.. |image52| image:: ./Pictures/10000201000002D9000002EFA49A2F5F28B2B69C.png
   :width: 3.2193in
   :height: 3.3181in
.. |image53| image:: ./Pictures/10000201000002DC00000239412E96CD73B2CB77.png
   :width: 3.2311in
   :height: 2.5161in
.. |image54| image:: ./Pictures/10000201000000AA00000044BC7CBE61952CC595.png
   :width: 1.7709in
   :height: 0.7083in
.. |image55| image:: ./Pictures/10000201000000B7000000A34B2F652C2A04428B.png
   :width: 1.9063in
   :height: 1.698in
.. |image56| image:: ./Pictures/100002010000001A00000018CA021E5F74E6375A.png
   :width: 0.2709in
   :height: 0.25in
.. |image57| image:: ./Pictures/10000201000001E600000155B79D05061B1B7F0E.png
   :width: 4.0256in
   :height: 2.8252in
.. |image58| image:: ./Pictures/100002010000003300000024C5AF4A8E8E194B51.png
   :width: 0.3957in
   :height: 0.278in
.. |image59| image:: ./Pictures/1000020100000021000000266B1570BDC2C4E14F.png
   :width: 0.2756in
   :height: 0.3181in
.. |image60| image:: ./Pictures/100002010000002600000021F635F2874D7D1007.png
   :width: 0.2945in
   :height: 0.2547in
.. |image61| image:: ./Pictures/1000020100000025000000255785BECC80465026.png
   :width: 0.2756in
   :height: 0.2756in
.. |image62| image:: ./Pictures/1000020100000024000000223A22C38615232C9D.png
   :width: 0.2756in
   :height: 0.2602in
.. |image63| image:: ./Pictures/1000020100000021000000205588538839AF7821.png
   :width: 0.2866in
   :height: 0.2756in
.. |image64| image:: ./Pictures/100002010000002900000024E26922CA5DABE4EB.png
   :width: 0.3299in
   :height: 0.2866in
.. |image65| image:: ./Pictures/10000201000000240000002471171A76353C85E1.png
   :width: 0.3075in
   :height: 0.3075in
