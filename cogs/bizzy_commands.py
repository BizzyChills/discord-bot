"""[cog] A cog for commands that only Bizzy can use
"""
from discord import Interaction, Object, app_commands
from discord.ext import commands
from discord.ext.commands import Context

from global_utils import global_utils


class BizzyCommands(commands.Cog):
    """[cog] A cog for commands that only Bizzy can use

    Parameters
    ----------
    bot : discord.ext.commands.bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """
    # pylint: disable=invalid-overridden-method
    # pylint: disable=arguments-differ

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def interaction_check(self, interaction: Interaction) -> bool:
        """[app check] Checks if the interaction is from Bizzy

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object to check

        Returns
        -------
        bool
            True if the interaction is from Bizzy, False otherwise
        """
        check = interaction.user.id == global_utils.my_id

        if not check:
            await interaction.response.send_message("You do not have permission to use this command",
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)

        return check

    async def cog_check(self, ctx: Context) -> bool:
        """[prefix check] A global check for all text commands in this cog to ensure they are only used by Bizzy

        Parameters
        ----------
        ctx : Context
            The context object to check

        Returns
        -------
        bool
            True if the context is from Bizzy, False otherwise
        """
        check = ctx.author.id == global_utils.my_id
        await ctx.message.delete(delay=0)

        if not check:
            await ctx.send("You do not have permission to use this command",
                           ephemeral=True, delete_after=global_utils.delete_after_seconds)

        return check

    async def sync_commands(self, guild_id: int = global_utils.debug_server_id) -> int:
        """Syncs the bot's app commands within the given guild

        Parameters
        ----------
        guild_id : int, optional
            The guild ID to sync the commands in, by default debug_server

        Returns
        -------
        int
            The number of commands synced
        """
        synced = await self.bot.tree.sync(guild=Object(id=guild_id))
        return synced

    # only available in the debug server
    @app_commands.command(name="clear", description=global_utils.commands["clear"]["description"])
    async def clear(self, interaction: Interaction) -> None:
        """[app command] Clears the calling channel in the debug server

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        """
        curr_guild_id = interaction.guild.id
        curr_channel_id = interaction.channel
        if curr_guild_id != global_utils.debug_server_id and curr_channel_id != global_utils.bot_channel_id:
            await interaction.response.send_message(
                "This command is not available here.", ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await interaction.channel.purge(limit=None, bulk=True)
        m = await interaction.followup.send("Cleared the entire channel", ephemeral=True)
        await m.delete(delay=global_utils.delete_after_seconds)

    @app_commands.command(name="feature", description=global_utils.commands["feature"]["description"])
    @app_commands.describe(
        feature_name="The new feature to promote",
        message="The promotion message"
    )
    async def feature(self, interaction: Interaction, feature_name: str, message: str) -> None:
        """[app command] Promotes a new feature in the current channel

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        feature : str
            The new feature to promote
        message : str
            The promotion message
        """
        feature_name = global_utils.style_text(feature_name.strip(), 'b')
        await interaction.response.send_message(f"New feature: {feature_name}\n\n{message}")

    @commands.hybrid_command(name="reload", description=global_utils.commands["reload"]["description"])
    @app_commands.guilds(Object(id=global_utils.val_server_id), Object(global_utils.debug_server_id))
    @app_commands.choices(
        sync=[
            app_commands.Choice(name="Yes", value=1),
        ]
    )
    @app_commands.describe(
        sync="Sync commands after reloading"
    )
    async def reload(self, ctx: Context, sync: int = 0) -> None:
        """[hybrid command] Reloads all cogs in the bot

        Parameters
        ----------
        ctx : discord.ext.commands.Context
            The context object that initiated the command
        sync : int, optional
            Treated as a boolean. Sync the commands after reloading, by default 0
        """
        async with ctx.typing(ephemeral=True):

            self.bot.dispatch("reload_cogs")
            await global_utils.load_cogs(self.bot)  # also *re*loads the cogs

            message = "All cogs reloaded"

            if sync:
                synced = await self.sync_commands(ctx.guild.id)
                message += f" and {len(synced)} commands synced in {ctx.guild.name}"

        await ctx.send(message, ephemeral=True, delete_after=global_utils.delete_after_seconds)
        await ctx.message.delete(delay=global_utils.delete_after_seconds)


async def setup(bot: commands.bot) -> None:
    """Adds the BizzyCommands cog to the bot

    Parameters
    ----------
    bot : discord.ext.commands.Bot
        The bot to add the cog to. Automatically passed in by the bot.load_extension method
    """
    guilds = [Object(global_utils.val_server_id), Object(global_utils.debug_server_id)]
    await bot.add_cog(BizzyCommands(bot), guilds=guilds)
