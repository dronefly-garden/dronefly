"""Module for context command group."""

import re

import discord

from redbot.core import app_commands

from dronefly.core.parsers.url import PAT_OBS_LINK, PAT_TAXON_LINK

from ..constants import COG_NAME
from ..partials import PartialContext
from ..embeds.inat import INatEmbed


@app_commands.context_menu(name="Show taxon")
async def show_taxon(interaction: discord.Interaction, message: discord.Message):
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
            params = inat_embed.get_params()
            taxon_id = params.get("taxon_id")
    if not taxon_id and message.content:
        mat_taxon = re.search(PAT_TAXON_LINK, message.content)
        if mat_taxon:
            taxon_id = mat_taxon["taxon_id"]
        else:
            obs_id = None
            mat_obs = re.search(PAT_OBS_LINK, message.content)
            if mat_obs:
                obs_id = mat_obs["obs_id"]
            if obs_id:
                obs = await anext(
                    aiter(cog.inat_client.observations.from_ids(int(obs_id))), None
                )
                if obs:
                    taxon = obs.taxon
                    if taxon:
                        taxon_id = taxon.id
    if taxon_id:
        taxon_command = bot.get_command("taxon")
        await taxon_command(ctx, query=str(taxon_id))
        return
    await interaction.followup.send(
        "I can't find a taxon in that message.",
    )
