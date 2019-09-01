# quaggagriff
Half zebra, half gryphon, Quaggagriff is a Discord Cog repo for naturalists.

**Please note, this repo is still in development so the installation instructions will not work yet as shown below.**

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

```
[p]repo add Quaggagriff https://github.com/synrg/quaggagriff
[p]cog install Quaggagriff <cog-name>
```

Where [p] is your prefix.

## TODO

- scheduled reports
- iNaturalist commands
- better doc (deferred until some of the above have been sorted out)
