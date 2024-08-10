"""[cog] A cog for displaying general premier information
(that isn'tW provided by persist_commands.py).
"""
import asqlite

import discord
from discord.ext import commands
from discord import errors
from discord import app_commands

from global_utils import global_utils


class InfoCommands(commands.Cog):
    """[cog] A cog for displaying general premier information 
    (that isn't provided by the persistent view).
    This includes commands for displaying map weights, map votes, and practice notes.

    Parameters
    ----------
    bot : discord.ext.commands.Bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="map-weights", description=global_utils.commands["map-weights"]["description"])
    @app_commands.choices(
        announce=[
            discord.app_commands.Choice(name="Yes", value=1),
        ]
    )
    @app_commands.describe(
        announce="Show the output of the command to everyone (only in the premier channel)"
    )
    async def mapweights(self, interaction: discord.Interaction, announce: int = 0) -> None:
        """[app command] Displays the weights of each map in the map pool based on user preferences

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        announce : int, optional
            Treated as a boolean. Announce the output when used in the premier channel, by default 0
        """
        ephem = interaction.channel.id != global_utils.prem_channel_id or not announce

        output = ""

        for map_name in [m for m in global_utils.map_weights if m in global_utils.map_pool]:

            map_display_name = global_utils.style_text(map_name.title(), 'i')
            weight = global_utils.style_text(
                global_utils.map_weights[map_name], 'b')

            output += f'- {map_display_name}: {weight}\n'

        if output == "":
            output = "No weights to show for maps in the map pool."

        await interaction.response.send_message(output, ephemeral=ephem)

    @app_commands.command(name="map-votes", description=global_utils.commands["map-votes"]["description"])
    @app_commands.choices(
        announce=[
            discord.app_commands.Choice(name="Yes", value=1),
        ]
    )
    @app_commands.describe(
        announce="Show the output of the command to everyone when used in the premier channel"
    )
    async def mapvotes(self, interaction: discord.Interaction, announce: int = 0) -> None:  # pylint: disable=too-many-locals
        """[app command] Displays each user's preferences for each map in the map pool

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        announce : int, optional
            Treated as a boolean. Announce the output when used in the premier channel, by default 0
        """
        ephem = interaction.channel.id != global_utils.prem_channel_id or not announce

        is_prem = interaction.guild.id == global_utils.val_server_id

        role_name = global_utils.prem_role_name if is_prem else global_utils.debug_role_name
        premier_team = discord.utils.get(
            interaction.guild.roles, name=role_name).members

        output = ""

        # map_weights is sorted by weight already,
        for map_name in [m for m in global_utils.map_weights if m in global_utils.map_pool]:
            header = (f"- {global_utils.style_text(map_name.title(), 'i')}" +
                      f" ({global_utils.style_text(global_utils.map_weights[map_name], 'b')}):\n")
            body = ""

            for user in premier_team:
                if user.id not in global_utils.map_preferences[map_name]:
                    continue

                user_weight = global_utils.map_preferences[map_name][user.id]

                preference_decoder = {-1: "👎", 0: "🤷‍♀️", 1: "👍"}

                user_preference = preference_decoder.get(user_weight, "Preference Error")

                body += f" - {user.mention}: {global_utils.style_text(user_preference, 'c')}\n"

            if body == "":
                body = " - No votes for this map.\n"

            output += header + body

        if output == "":
            output = "No votes for any maps in the map pool."

        await interaction.response.send_message(output, ephemeral=ephem, silent=True)

    @app_commands.command(name="notes", description=global_utils.commands["notes"]["description"])
    @app_commands.choices(
        map_name=[
            app_commands.Choice(name=s.title(), value=s) for s in global_utils.map_preferences.keys()
        ],
        announce=[
            app_commands.Choice(name="Yes", value=1),
        ]
    )
    @app_commands.describe(
        map_name="The map to display the note for",
        note_number="The note number to display (1-indexed). Leave empty (or input 0) to see options.",
        announce="Return the note so that it is visible to everyone (only in notes channel)"
    )
    async def notes(self, interaction: discord.Interaction, map_name: str,
                    note_number: int = 0, announce: int = 0) -> None:
        """[app command] Displays practice notes for a map

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        map_name : str
            The map to display the note for
        note_number : int, optional
            The note number to display (1-indexed). Leaving this empty will show all options, by default 0
        announce : int, optional
            Treated as a boolean. Announce the output when used in the notes channel, by default 0
        """
        ephem = interaction.channel.id != global_utils.notes_channel_id or not announce

        map_display_name = global_utils.style_text(map_name, 'i').title()

        if map_name not in global_utils.practice_notes or len(global_utils.practice_notes[map_name]) == 0:
            await interaction.response.send_message(f'No notes found for {map_display_name}',
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        if note_number < 0 or note_number > len(global_utils.practice_notes[map_name]):
            await interaction.response.send_message('Invalid note number. Leave blank to see all options.',
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        if note_number == 0:
            notes_list = global_utils.practice_notes[map_name]
            output = f"{global_utils.style_text('Practice notes', 'b')} for {map_display_name}:\n"
            for i, note_id in enumerate(notes_list.keys()):
                note_number = f"Note {i+1}"
                note_number = global_utils.style_text(note_number, 'b')
                output += f"- {note_number}: {global_utils.style_text(notes_list[note_id], 'i')}\n"

            await interaction.response.send_message(output, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=ephem)

        note_id = list(global_utils.practice_notes[map_name].keys())[
            note_number - 1]
        try:
            note = await interaction.channel.fetch_message(int(note_id))
        except errors.NotFound:
            global_utils.practice_notes[map_name].pop(note_id)
            async with asqlite.connect("./local_storage/maps.db") as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
                await conn.commit()
            m = await interaction.followup.send('The original message has been deleted. Removing it from the list.',
                                                ephemeral=True)
            await m.delete(delay=global_utils.delete_after_seconds)
            return

        output = f'Practice note for {map_display_name} (created by {note.author.display_name}):\n\n{note.content}'

        await interaction.followup.send(output, ephemeral=ephem)


async def setup(bot: commands.bot) -> None:
    """Adds the InfoCommands cog to the bot

    Parameters
    ----------
    bot : discord.ext.commands.bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """
    guilds = [discord.Object(global_utils.val_server_id), discord.Object(global_utils.debug_server_id)]
    await bot.add_cog(InfoCommands(bot), guilds=guilds)
