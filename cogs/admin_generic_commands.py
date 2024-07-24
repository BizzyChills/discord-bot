"""[cog] A cog for managing generic commands such as moderation and bot shutdown
"""
from asyncio import sleep
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord.ext.commands import Context
from discord import app_commands, Object

from global_utils import global_utils

# pylint: disable=invalid-overridden-method
# pylint: disable=arguments-differ


class AdminGenericCommands(commands.Cog):
    """[cog] An admin cog for managing generic commands such as moderation and bot shutdown

    Parameters
    ----------
    bot : discord.ext.commands.bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """

    def __init__(self, bot: commands.bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """[event] Executes when the AdminMessageCommands cog is ready
        """
        # global_utils.log("AdminManage cog loaded")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """[app check] A global check for all app commands in this cog to ensure the user is an admin

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command

        Returns
        -------
        bool
            True if the user is an admin, False otherwise
        """
        return await global_utils.is_admin(interaction)

    async def cog_check(self, ctx: Context) -> bool:
        """[prefix check] A global check for all text commands in this cog to ensure the user is an admin

        Parameters
        ----------
        ctx : discord.ext.commands.Context
            The context object that initiated the command

        Returns
        -------
        bool
            True if the user is an admin, False otherwise
        """
        return await global_utils.is_admin(ctx)

    @app_commands.command(name="remind", description=global_utils.commands["remind"]["description"])
    @app_commands.choices(
        unit=[
            app_commands.Choice(name="hours", value="hours"),
            app_commands.Choice(name="minutes", value="minutes"),
            app_commands.Choice(name="seconds", value="seconds"),
        ]
    )
    @app_commands.describe(
        interval="The number of units to wait for the reminder",
        unit="The unit of time associated with the interval",
        message="The reminder message to send to the premier role"
    )
    async def remind(self, interaction: discord.Interaction,
                     interval: app_commands.Range[int, 1], unit: str,
                     *, message: str) -> None:
        """[app command] Sends a reminder to the premier role (and in the premier channel) after a specified interval

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        interval : int
            The number of units to wait for the reminder
        unit : str
            The unit of time associated with the interval (hours, minutes, seconds)
        message : str
            The reminder message to send to the premier role
        """
        message = message.strip()

        current_time = datetime.now()

        g = interaction.guild
        if g.id == global_utils.val_server_id:
            role_name = global_utils.prem_role_name
            reminder_channel = self.bot.get_channel(
                global_utils.prem_channel_id)
        else:
            role_name = global_utils.debug_role_name
            reminder_channel = self.bot.get_channel(
                global_utils.debug_channel_id)

        role = discord.utils.get(g.roles, name=role_name)

        message = f"(reminder) {role.mention} {message}"
        output = ""

        if unit == "seconds":
            output = f'(reminder) I will remind {role} in {interval} second(s) with the message: "{message}"'
            when = current_time + timedelta(seconds=interval)
        elif unit == "minutes":
            when = current_time + timedelta(minutes=interval)
            output = f'(reminder) I will remind {role} in {interval} minute(s) with the message: "{message}"'
            interval *= 60
        elif unit == "hours":
            when = current_time + timedelta(hours=interval)
            output = f'(reminder) I will remind {role} in {interval} hour(s) with the message: "{message}"'
            interval *= 3600

        await interaction.response.send_message(output, ephemeral=True)

        dt_when = datetime.fromtimestamp(when.timestamp()).isoformat()

        try:
            global_utils.reminders[dt_when].append((g.id, message))
        except KeyError:
            global_utils.reminders[dt_when] = [(g.id, message)]

        global_utils.save_reminders()

        global_utils.log(
            f"Saved a reminder from {interaction.user.display_name}: {output}")

        await sleep(interval)

        await reminder_channel.send(message)
        global_utils.log(
            f"Posted a reminder from {interaction.user.display_name} for {role.name}: {message}")

        global_utils.reminders[dt_when].remove((g.id, message))
        global_utils.save_reminders()

    @app_commands.command(name="pin", description=global_utils.commands["pin"]["description"])
    @app_commands.describe(
        message_id="The ID of the message to pin"
    )
    async def pin(self, interaction: discord.Interaction, message_id: str) -> None:
        """[app command] Pins a message by ID

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        message_id : str
            The ID of the message to pin
        """
        try:
            message = interaction.channel.get_partial_message(int(message_id))
            await message.pin()
        except (discord.HTTPException, discord.errors.NotFound):
            await interaction.response.send_message('Message not found.',
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        await interaction.response.send_message('Message pinned',
                                                ephemeral=True, delete_after=global_utils.delete_after_seconds)

        global_utils.log(
            f'{interaction.user.display_name} pinned message {message_id}')

    @app_commands.command(name="unpin", description=global_utils.commands["unpin"]["description"])
    @app_commands.describe(
        message_id="The ID of the message to unpin"
    )
    async def unpin(self, interaction: discord.Interaction, message_id: str) -> None:
        """[app command] Unpins a message by ID

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        message_id : str
            The ID of the message to unpin
        """
        try:
            message = interaction.channel.get_partial_message(int(message_id))
            await message.unpin()
        except (discord.HTTPException, discord.errors.NotFound):
            await interaction.response.send_message('Message not found.',
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        await interaction.response.send_message('Message unpinned',
                                                ephemeral=True, delete_after=global_utils.delete_after_seconds)

        global_utils.log(
            f'{interaction.user.display_name} unpinned message {message_id}')

    @app_commands.command(name="delete-message", description=global_utils.commands["delete-message"]["description"])
    @app_commands.describe(
        message_id="The ID of the message to delete"
    )
    async def deletemessage(self, interaction: discord.Interaction, message_id: str) -> None:
        """[app command] Deletes a message by ID

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        message_id : str
            The ID of the message to delete
        """
        try:
            await interaction.channel.get_partial_message(int(message_id)).delete()
        except (ValueError, discord.errors.NotFound):
            await interaction.response.send_message('Message not found.',
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        await interaction.response.send_message('Message deleted',
                                                ephemeral=True, delete_after=global_utils.delete_after_seconds)

        global_utils.log(
            f'{interaction.user.display_name} deleted message {message_id}')

    @commands.hybrid_command(name="kill", description=global_utils.commands["kill"]["description"])
    @app_commands.guilds(Object(id=global_utils.val_server_id), Object(global_utils.debug_server_id))
    async def kill(self, ctx: Context, *, reason: str = "no reason given") -> None:
        """[hybrid command] Kills the bot (shutdown)

        Parameters
        ----------
        ctx : discord.ext.commands.Context
            The context object that initiated the command
        reason : str, optional
            The reason for killing the bot, by default "no reason given"
        """
        await ctx.send('Goodbye cruel world!', ephemeral=True, delete_after=global_utils.delete_after_seconds)
        await ctx.message.delete(delay=global_utils.delete_after_seconds)

        global_utils.log(f"Bot killed. reason: {reason}")

        await self.bot.close()


async def setup(bot: commands.bot) -> None:
    """Adds the AdminPremierCommands and AdminMessageCommands cogs to the bot

    Parameters
    ----------
    bot : discord.ext.commands.Bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """
    guilds = [Object(global_utils.val_server_id), Object(global_utils.debug_server_id)]
    await bot.add_cog(AdminGenericCommands(bot), guilds=guilds)
