# quaggagriff
Half zebra, half gryphon, Quaggagriff is a Discord Cog repo for naturalists.

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
$ git clone https://github.com/synrg/quaggagriff

[p]addpath quaggagriff
[p]load <cog-name>
```

## TODO

- scheduled reports
- iNaturalist commands
- better doc (deferred until some of the above have been sorted out)
