# quaggagriff
Quaggagriff is a Discord Cog collection for naturalists.

## Cogs:

- ebirdcog
    - provides access to the eBird platform
    - note: you must apply for an eBird API key to use this cog
    - commands:
        - **ebird hybrids**
            - reports hybrids seen recently
        - **ebird setregion**
            - sets the region (e.g. US-MA, CA-NS)
        - **ebird setdays**
            - sets days to consider "recent" (default: 30, maximum: 30)

## Prerequisites

These Cogs provide commands for Red Bot V3. If you don't have that already, go get it, following the installation guide for your platform here: https://red-discordbot.readthedocs.io/en/latest/index.html

## Installation

If you have not already, load the V3 downloader:

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

Report hybrids observed recently:

```
[p]ebird hybrids
[8:52 AM] BOT CuckooBee: Mallard x American Black Duck (hybrid) (Anas platyrhynchos x rubripes); 1 observed at 09:04, 27 Aug, from Hartlen Point West Beach (44.5926,-63.4546)
```

### Scheduled reports

See https://github.com/synrg/quaggagriff/issues/2#issuecomment-526963273 for advice on scheduled execution of an ebird subcommand, such as to alert channel users to new observations of hybrids found in the region.

## TODO

- add more useful / interesting commands
- add some iNaturalist commands
- improve default permissions; document changing default permissions
- limit API calls using cached values where appropriate
