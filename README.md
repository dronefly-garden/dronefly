# quaggagriff
Quaggagriff is a Discord Cog collection for naturalists.

## Cogs:

- ebirdcog
    - Provides commands to access the eBird platform.
    - Note: you must apply for an eBird API key to use this cog.
    - Commands:
        - **ebird checkdays**
            - Checks days setting.
        - **ebird checkregion**
            - Checks region setting.
        - **ebird hybrids**
            - Reports recent hybrid observations.
        - **ebird setdays**
            - Sets days considered recent (1 through 30; default: 30).
        - **ebird setregion**
            - Sets region (default: CA-NS; e.g. US-MA, etc.).
- inatcog
    - Provides commands to access the iNat platform.
    - Read-only iNat commands (the only kind provided to date) do not require an API key.
    - Commands:
        - **inat taxon [terms...]**
            - Looks up the taxon by unique ID, code, or name.

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

Where [p] is your prefix.

## ebirdcog

After adding the repo as per Installation, install & load ebirdcog:

```
[p]cog install Quaggagriff ebirdcog
[p]load ebirdcog
```

The same goes for inatcog:

```
[p]cog install Quaggagriff inatcog
[p]load inatcog
```

### Configuration

Before you can access the eBird API, you must [generate an eBird API key](https://ebird.org/api/keygen) and set it in the [API key storage](https://docs.discord.red/en/stable/framework_apikeys.html) as follows (making sure to do this in DM so as to not expose the key to others!)

```
[p]set api ebird api_key,your-key-goes-here
```

Change default settings to values suitable for your bot, e.g.

```
[p]ebird setregion US-MA
[p]ebird setdays 7
```

### Examples

Set aliases for the server (as bot owner):

```
,load aliases
,set alias hybrids ebird hybrids
,set alias taxon inat taxon
```

Report hybrids observed recently on eBird:

```
,hybrids
```

> **Hybrids in US-MA from past 7 days** \
> **Mallard x American Black Duck** \
> · 12:25, 18 Sep: 2 at 210 Herring Creek Rd, Edgartown US-MA (41.3515,-70.5317)

Look up a taxon on iNat:

```
,taxon pare
```

> [Myioborus pictus (Painted Redstart)](https://www.inaturalist.org/taxa/9458) \
![Image of Myioborus pictus](https://static.inaturalist.org/photos/68547/square.jpg)


### Scheduled reports

See https://github.com/synrg/quaggagriff/issues/2#issuecomment-526963273 for advice on scheduled execution of an **ebird** subcommand, such as to alert channel users to new observations of hybrids found in the region.

## TODO

- add more useful / interesting commands
- ~~add some iNaturalist commands~~
- improve default permissions; document changing default permissions
- limit API calls using cached values where appropriate
- make a proper parser so that the command query language can be made richer (see taxon-pyparsing branch)
