# quaggagriff
Half zebra, half gryphon, the quaggagriff is a Discord bot for
naturalists. This legendary beast circles the globe, scanning for
interesting life & reporting its findings.

Development is early alpha. The code is likely to change considerably
over the next little while. This bot requires:

- python >= 3.5
- ebird-api
- discord.py


## Usage

An API key for eBird API 2.0 & bot token for discord.py are required
in order to run the bot. Once both are obtained & placed in ebird.key
and discord.key files, respectively, in the directory where the bot is
run, edit qgriff.py to change any parameters (e.g.  command prefix,
get_observations region which is 'CA-NS'), and start the bot with:

```
python qgriff.py
```

## Commands

.hybrids

Reports daily at 05:00 which hybrids have been observed at ebird.org
(with or without confirmation) within the last 30 days in the CA-NS
region (Nova Scotia, Canada).

## TODO

- permissions (restrict command usage to specific roles)
- configuration (.ini file for region, task schedule, etc.)
- commands (start & stop reporting task(s), status, etc.)
- iNaturalist commands
- better doc (deferred until some of the above have been sorted out)

