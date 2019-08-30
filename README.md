# quaggagriff
Half zebra, half gryphon, Quaggagriff is a Discord bot for naturalists.

eBird commands:

- hybrids
    - starts daily reporting of hybrids seen on eBird recently for the configured region

iNaturalist commands:

- coming soon

Development is early alpha. The code is likely to change considerably
over the next little while. The biggest change will be to convert it
from a bot to a collection of Discord Cogs, running on Red Discord Bot
instead (see Issues: #1, #2, #3, #4, #5, etc.). This bot requires:

- python >= 3.5
- a discord.py bot token
- an eBird API key (for eBird commands)

## Install

```
pip install quaggagriff
```

## Usage

- obtain a bot token for discord.py
- obtain An API key for eBird API 2.0
- create qgriff.ini and configure as follows

```
[discord]
key = your-bot-token-goes-here

[ebird]
key = your-ebird-api-key-goes-here

[bot]
command_prefix = ,

[hybrids]
days = 30
region = CA-NS
run_hr = 5
run_min = 0
```

The above values, which are also the defaults if none are specified in qgriff.ini,
will:

- set the bot command prefix to comma (",")
- set the 'hybrids' command defaults to report hybrids from eBird:
    - seen within the past 30 days
    - in CA-NS (Nova Scotia, Canada, where the author lives)
    - at 05:00 daily

```
python -m qgriff.qgriff
```

Note: One or more qgriff.ini files can be located in the working directory
for the above command, in your user config dir, or your site config dir.

If you want to keep it simple, just put qgriff.ini in the working directory.
Otherwise, where the user & site config dirs are depends on which OS/platform
you are on, as determined by:

```python
dirs = AppDirs('qgriff', 'Quaggagriff')
user_config_dir = dirs.user_config_dir
site_config_dir = dirs.site_config_dir
```

See https://github.com/ActiveState/appdirs for details. A future release will
support writing configuration values to this directory, and then the user
will not normally need to know where the configuration is stored.

## Commands

.hybrids

Reports daily at the configured *run_hr*:*run_min* which hybrids have been
observed at ebird.org (with or without confirmation) within the last
configured *days* in the configured *region*.

After reporting has started, re-triggering the command only reports when the
reporting period started & how many reports have been issued since then.

## TODO

- permissions (restrict command usage to specific roles)
- commands (start & stop reporting task(s), status, etc.)
- iNaturalist commands
- better doc (deferred until some of the above have been sorted out)
