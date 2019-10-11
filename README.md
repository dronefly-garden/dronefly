# quaggagriff
Quaggagriff is a Discord Cog collection for naturalists.

## Cogs:

### inatcog

Provides commands to access the iNat platform.

#### Commands:

`[p]inat taxon <query>` looks up the taxon best matching the query (where `[p]` is the bot prefix). It will:

- Match the taxon with the given iNat id#.
- Match words that start with the terms typed.
- Exactly match words enclosed in double-quotes.
- Match a taxon 'in' an ancestor taxon.
- Filter matches by rank keywords before or after other terms.
- Match the AOU 4-letter code (if it's in iNat's Taxonomy).

*Note: It is recommended that `[p]taxon` itself and individual ranks be set up as shortcuts for the corresponding commands the bot owner has created those aliases with the `alias` cog.*

Example `[p]inat taxon` queries using aliases:

```
[p]taxon bear family          -> Ursidae (Bears)
[p]family bear                -> Ursidae (Bears)
[p]taxon prunella             -> Prunella (self-heals)
[p]taxon prunella in animals  -> Prunella
[p]taxon wtsp                 -> Zonotrichia albicollis (White-throated Sparrow)
```

For each successful response, the scientific name, followed by the preferred common name (if any) is output as a link to the corresponding www.inaturalist.org taxon page, and a small thumbnail of the default image for the taxon (if any) is output beside it, similar in appearance to the following:

```
[p]taxon pare
```

> [Myioborus pictus (Painted Redstart)](https://www.inaturalist.org/taxa/9458) \
![Image of Myioborus pictus](https://static.inaturalist.org/photos/68547/square.jpg)

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

## Installation

If you have not already, load the Red V3 downloader cog:

```
[p]load downloader
```

Then add the Quaggagriff repo and install the desired cog(s) as per:

```
[p]repo add Quaggagriff https://github.com/synrg/quaggagriff
[p]cog install Quaggagriff <cog-name>
```

### inatcog

After adding the repo as per Installation, install & load inatcog:

```
[p]cog install Quaggagriff inatcog
[p]load inatcog
```

### ebirdcog

After adding the repo as per Installation, install & load ebirdcog:

```
[p]cog install Quaggagriff ebirdcog
[p]load ebirdcog
```

## Configuration

### inatcog

Set aliases for the server (as bot owner):

```
[p]load alias
[p]set global alias taxon inat taxon
[p]set global alias kingdom inat taxon kingdom
... etc. for all ranks, including common abbreviations (see Note below)
```

*Note: The keywords sp, ssp, & var are accepted as abbreviations for species, subspecies, and variety, respectively. Set aliases for those keywords as well as spelled out.*

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

*Tip: See https://github.com/synrg/quaggagriff/issues/2#issuecomment-526963273 for advice on scheduled execution of an **ebird** subcommand, such as to alert channel users to new observations of hybrids found in the region.*

## TODO

- add more useful / interesting commands
- provide helper commands to:
    - add / remove all of the recommended `inat taxon` aliases automatically
    - schedule an `ebird hybrids` report for a channel more conveniently
- improve default permissions; document changing default permissions
- ~~make a proper parser so that the command query language can be made richer (see taxon-pyparsing branch)~~
