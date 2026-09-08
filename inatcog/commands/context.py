"""Module for context command group."""

import re

import discord

from redbot.core import app_commands

from dronefly.core.parsers.url import (
    PAT_OBS_LINK,
    PAT_TAXON_LINK,
)

from ..constants import COG_NAME
from ..partials import PartialContext
from ..embeds.inat import INatEmbed


@app_commands.context_menu(name="Show taxon")
async def show_taxon(interaction: discord.Interaction, message: discord.Message):
    """Show a taxon for either a bot display or user message."""

    async def maybe_get_taxon_id_from_match(matched):
        taxon_id = None
        obs_id = matched["obs_id"]
        if obs_id:
            obs = await anext(
                aiter(cog.inat_client.observations.from_ids(int(obs_id))), None
            )
            if obs:
                taxon = obs.taxon
                if taxon:
                    taxon_id = taxon.id
        return taxon_id

    async def maybe_get_taxon_id_from_obs(content: str):
        taxon_id = None
        mat_obs = re.search(PAT_OBS_LINK, content)
        if mat_obs:
            taxon_id = await maybe_get_taxon_id_from_match(mat_obs)
        return taxon_id

    taxon_id = None
    await interaction.response.defer()
    bot = interaction.client
    cog = bot.get_cog(COG_NAME)
    ctx = PartialContext(
        bot=bot,
        guild=message.guild,
        channel=message.channel,
        author=interaction.user,
        message=message,
        command="Show taxon",
        interaction=interaction,
        inat_client=cog.inat_client,
    )
    if message.embeds:
        inat_embed = INatEmbed.from_discord_embed(message.embeds[0])
        if inat_embed:
            # Prioritize taxon for multi observations as that will be
            # the topic of that sort of display (obs search)
            if inat_embed.has_observations():
                url = inat_embed.obs_url
                taxon_id = await maybe_get_taxon_id_from_obs(url)
            else:
                # i.e. either the id from a /taxa link or if absent,
                # taxon_id from URL params
                # - single obs display will also have a taxon link
                #   already obtained from looking up the obs
                # - otherwise this works for other sorts of display
                #   for single or multiple taxa or a search that
                #   has taxon_id in it
                params = inat_embed.get_params()
                taxon_id = params.get("taxon_id")
    if not taxon_id and message.content:
        content = message.content
        # Prioritize taxon link over obs for non-embed displays because
        # user messages may contain both, and the taxon is the more obvious one
        # to show.
        mat_taxon = re.search(PAT_TAXON_LINK, content)
        if mat_taxon:
            taxon_id = mat_taxon["taxon_id"]
        else:
            taxon_id = await maybe_get_taxon_id_from_obs(content)
        if not taxon_id and not message.author.bot:
            content = content.lower().replace(r"[^a-z]+", "")
            words = content.split()[0:2]
            # look for taxon in first 2 words
            if all(len(word) > 1 for word in words):
                if len(words) == 2 and words[1] in ["sp", "spp"]:
                    content = words[0]
                else:
                    content = " ".join(words)
                paginator = cog.inat_client.taxa.autocomplete(q=content, limit=1)
                taxa = await paginator.async_all()
                if len(taxa):
                    taxon_id = taxa[0].id
    if taxon_id:
        taxon_command = bot.get_command("taxon")
        await taxon_command(ctx, query=str(taxon_id))
        return
    await interaction.followup.send(
        "I can't find a taxon in that message.",
    )
