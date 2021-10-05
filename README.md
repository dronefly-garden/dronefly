[![Red cogs](https://img.shields.io/badge/Red--DiscordBot-cogs-red.svg)](https://github.com/Cog-Creators/Red-DiscordBot/tree/V3/develop)
[![discord.py](https://img.shields.io/badge/discord-py-blue.svg)](https://github.com/Rapptz/discord.py)
[![ReadTheDocs](https://img.shields.io/readthedocs/dronefly/latest?label=documentation)](https://dronefly.readthedocs.io)

# Dronefly bot

Dronefly is a bot for naturalists that gives users access to
[iNaturalist](https://www.inaturalist.org) on [Discord](https://discord.com)
chat.

Dronefly was made by and for members of the iNaturalist Discord server. You
are welcome to join our community using this invite link:
https://discord.gg/uskv2yx

Join the Dronefly support Discord server with this invite
https://discord.gg/pUbZFDbDdD if:

- you own a Discord server and want Dronefly on it
- you already use Dronefly and need support
- you want to be involved with Dronefly development

## Dronefly cog repository

Dronefly bot is based on [Red Discord
Bot](https://github.com/Cog-Creators/Red-DiscordBot) but it is also the name
of the Red cog repository for the bot on GitHub. The latter
provides the components that interact with sites of interest to its users,
such as iNaturalist.

While some developers and some users may have an interest in the repository,
most will find it simplest to just use the bot on Discord. You don't need to
download anything from this site to do that.

If you do want to run your own bot with the cogs from Dronefly repository on
it, see the Installation instructions below.

## Cogs:

### inatcog

Use iNat in Discord: search for species, automatic observation preview,
compare observations/species per user & place, and more.

A selection of the principal commands are listed below. Use `[p]help iNat`
for more commands &amp; details.

#### Query Commands:

##### taxon

`[p]taxon [query]` looks up the taxon best matching the query (where `[p]` is the bot prefix). It will:

- Match the taxon with the given iNat id#.
- Match words that start with the terms typed.
- Exactly match words enclosed in double-quotes.
- Match a taxon 'in' an ancestor taxon.
- List # of observations &amp; species 'by' a user.
- List # of observations &amp; species 'from' a place.
- Filter matches by rank keywords before or after other terms.
- Match the AOU 4-letter bird code (if it's in iNat's Taxonomy).

Example `[p]taxon` queries:

```
[p]taxon bear family          -> Ursidae (Bears)
[p]taxon prunella             -> Prunella (self-heals)
[p]taxon prunella in animals  -> Prunella
[p]taxon wtsp                 -> Zonotrichia albicollis (White-throated Sparrow)
```

For each successful response, the scientific name, followed by the preferred common name (if any) is output as a link to the corresponding www.inaturalist.org taxon page, and a small thumbnail of the default image for the taxon (if any) is output beside it, similar in appearance to the following:

```
[p]taxon pare
```
<span align="top">
    <blockquote>
        <span style="float: left"><a href="https://www.inaturalist.org/taxa/9458">Myioborus pictus (Painted Redstart)</a></span>
        <img align="top" style="float: right" width="30" height="30" alt="Image of Myioborus pictus" src="https://static.inaturalist.org/photos/20389/square.jpg?1545366901"></br>
        <b style="clear: both">Matched:</b><br>
        PARE
    </blockquote>
</span>

If the matched term was neither in the scientific name, nor the preferred common name, the term that matched is shown as well.

##### map

`[p]map [taxon query 1, taxon query 2, ...]` looks up one or more taxa (see [taxon](#taxon)) and displays a link to a range map for all matching taxa. For example:

```
[p]map boreal chorus frog, spring peeper
```

<span align="top">
    <blockquote>
        <a href="https://www.inaturalist.org/taxa/map?taxa=24255,24268#4/44.15997297735885/269.0876447595656">Range map for Pseudacris maculata (Boreal Chorus Frog), Pseudacris crucifer (Spring Peeper)</a>
    </blockquote>
</span>

##### obs

`[p]obs [link|#]` looks up the observation and displays a summary. See also [Auto Commands](#auto-commands). With `autoobs` turned on (either for the channel or whole server), this command is automatically performed every time a link to the observation is mentioned by a user.

If there are sounds for the observation, the first sound will be included in the summary. On the Discord webapp or desktop client, Discord embeds a player for sounds.

##### link

`[p]link [<link>|#]` looks up an iNat link and displays a preview & summary. See also [Auto Commands](#auto-commands).

The command is subtly different from `[p]obs` in that it is intended to preview any link, including any image on the page, thereby providing a functional replacement for Discord's own automatic preview. Therefore, to suppress Discord's preview, enclose the link in angle-brackets.

To date, only observation link previews are supported. Previews for different iNat link types may be added in future releases.

```
[p]link <https://inaturalist.org/observations/2>
```

##### last

Lookup maps, taxa, or ranks for recently mentioned observations or taxa, e.g.

```
[p]last obs          -> The last observation
[p]last obs map      -> Range map for last observation
[p]last obs taxon    -> Taxon of the last observation
[p]last obs family   -> Family of the last observation
[p]last taxon order  -> The order of the last taxon
```

#### Auto Commands:

##### inat show autoobs

`[p]inat show autoobs`

Shows the automatic observation summary settings for the server & channel. Example output:

```
Dronefly: Server observation auto-preview is on.
Dronefly: Channel observation auto-preview is inherited from server (on).
```

##### inat set autoobs server

`[p]inat set autoobs server [on|off]`

Turn on or off automatic summaries of observation links mentioned in any channel on the server. **Requires Admin or Manage Messages permission**.

##### inat set autoobs

`[p]inat set autoobs [on|off|inherit]`

Turn on, off, or inherit from the `autoobs server` setting automatic summaries of observation links pasted to the current channel. **Requires Admin or Manage Messages permission**.

The default is `[p]inat set autoobs inherit`. Specify `on` or `off` to override the server setting per channel.

#### User commands:

##### user add

```
[p]user add [discord-user] [inat-user]
```

Add the Discord user with the specified iNat user id#, login, or profile link to the User config store. **Requires Admin or Manage Roles permission.**

*Note: discord-user is used here, not discord-member to improve comprehension of guild channel history & contributions from those users emeritus on the iNat platform.*

##### user remove

```
[p]user remove [discord-user]
```

Remove the user from the User config store. **Requires Admin or Manage Roles permission.**

##### user

```
[p]user [discord-user]
```

Show the user if present in the User config store.

### ebirdcog

Provides commands to access the eBird platform. *Note: you must apply for an eBird API key to use this cog.*

#### Commands:

The following commands are supported (where `[p]` is the bot prefix).

```
[p]ebird checkdays            Checks days setting.
[p]ebird checkregion          Checks region setting.
[p]ebird hybrids              Reports recent hybrid observations.
[p]ebird setdays              Sets days considered recent (1 through 30; default: 30).
[p]ebird setregion            Sets region (default: CA-NS; e.g. US-MA, etc.).
```

## Prerequisites

These Cogs provide commands for Red Bot V3. If you don't have that already, go get it, following the installation guide for your platform here: https://red-discordbot.readthedocs.io/en/latest/index.html

Any other python package dependencies of the cogs you install are automatically satisfied by the installation. See the next section.

## Installation

If you have not already, load the Red V3 downloader cog:

```
[p]load downloader
```

Then add the Dronefly repo and install the desired cog(s) as per:

```
[p]repo add Dronefly https://github.com/dronefly-garden/dronefly
[p]cog install Dronefly [cog-name]
```

### inatcog

After adding the repo as per Installation, install & load inatcog:

```
[p]cog install Dronefly inatcog
[p]load inatcog
```

### ebirdcog

After adding the repo as per Installation, install & load ebirdcog:

```
[p]cog install Dronefly ebirdcog
[p]load ebirdcog
```

## Configuration

### ebirdcog

Before you can access the eBird API, you must [generate an eBird API key](https://ebird.org/api/keygen) and set it in the [API key storage](https://docs.discord.red/en/stable/framework_apikeys.html) as follows (making sure to do this in DM so as to not expose the key to others!)

```
[p]set api ebird api_key,your-key-goes-here
```

Change default settings to values suitable for your bot, e.g.

```
[p]ebird setregion US-MA
[p]ebird setdays 7
```

Set a `[p]hybrids` global alias (as bot owner):

```
[p]load alias
[p]set global alias hybrids ebird hybrids
```

An example command to verify the alias works:

```
[p]hybrids US-MA 7
```

> **Hybrids in US-MA from past 7 days** \
> **Mallard x American Black Duck** \
> · 12:25, 18 Sep: 2 at 210 Herring Creek Rd, Edgartown US-MA (41.3515,-70.5317)

*Tip: Hybrids are uncommon in some regions & some times of year. Try a larger # of days (up to 30) and/or a more interesting part of the world with greater hybrid activity year-round (e.g. BR for Brazil)*

```
[p]hybrids BR 30
```

> **Hybrids in BR from past 30 days** \
> **Red-capped x Crimson-fronted Cardinal** \
> · 14:47, 05 Oct: 1 at PE do Cantão--sede \
> **White-barred x Ochre-collared Piculet** \
> · 07:04, 04 Oct: 1 at Ponto De Escuta 01 - Parque Municipal Arthur Thomas, Londrina, Paraná, BR (-23,345, -51,137) \
> **White-barred x White-wedged Piculet** \
> · 07:10, 15 Sep: 1 at Ipeúna--Mata do vira-folha

*Tip: For scheduling execution of the hybrids command, use a scheduled command execution cog. We recommend `fifo` by Bobloy from the https://github.com/bobloy/Fox-V3 repository.*

## TODO

Check the [Issues](https://github.com/dronefly-garden/dronefly/issues) for a comprehensive list of TODO items that are either already actionable, or on their way to becoming so.
