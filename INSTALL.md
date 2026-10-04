# Dronefly cog repository

**Dronefly** bot is based on [Red Discord
Bot](https://github.com/Cog-Creators/Red-DiscordBot). Its iNaturalist and
eBird commands are provided from two cogs, `inatcog` and `ebirdcog`
respectively.

While some developers and some users may have an interest in running their
own Dronefly instance, most will find it simplest to just use Dronefly
bot on Discord. You don't need to download anything from this site to do
that.

Otherwise, if you do want to run your own bot, follow the instructions
below.

# Installing Dronefly cogs

## Prerequisites

1. Install Red Bot V3: https://red-discordbot.readthedocs.io/en/latest/index.html
2. Create a bot instance and start it.
3. Load the Red V3 downloader cog:
```
[p]load downloader
```
4. Add the Dronefly repo and install one or both cogs with:
```
[p]repo add Dronefly https://github.com/dronefly-garden/dronefly
[p]cog install Dronefly inatcog
[p]cog install Dronefly ebirdcog
```

## inatcog

After adding the repo, install & load inatcog:

```
[p]cog install Dronefly inatcog
[p]load inatcog
```

### Taxon name autocompletion

Taxon name autocompletion in some `inatcog` commands
is supported via a database that must be built
separately. See:

https://github.com/dronefly-garden/dronefly-miner

If the database is absent, users of slash commands
with a `taxon` parameter, such as `/taxon show`
will show an empty autocompletion select list. The
command will still work, though, returning a
"best match" for the text that was typed.

## ebirdcog

*Note: This cog is no longer being actively developed. It is still supported, but no new features will be added.*

After adding the repo as per Installation, install & load ebirdcog:

```
[p]cog install Dronefly ebirdcog
[p]load ebirdcog
```

# Configuration

## inatcog

To configure `inatcog`, follow the [server owner guide](https://github.com/dronefly-garden/dronefly/wiki/Server-owner-guide)

## ebirdcog

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

