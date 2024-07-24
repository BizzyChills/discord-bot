"""[cog] A cog for commands that are just for "fun" (miscellaneous commands)
"""
from discord import app_commands, Interaction, Object
from discord.ext import commands

from global_utils import global_utils


class MiscCommands(commands.Cog):
    """[cog] A cog for commands that are just for "fun" (miscellaneous commands)

    Parameters
    ----------
    bot : discord.ext.commands.bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """

    def __init__(self, bot: commands.bot) -> None:
        self.bot = bot

    @app_commands.command(name="hello", description=global_utils.commands["hello"]["description"])
    async def hello(self, interaction: Interaction) -> None:
        """[app command] Says hello to the bot

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        """
        await interaction.response.send_message(f'Hello {interaction.user.mention}!',
                                                ephemeral=True, delete_after=global_utils.delete_after_seconds)


async def setup(bot: commands.bot) -> None:
    """Adds the MiscCommands cog to the bot

    Parameters
    ----------
    bot : discord.ext.commands.bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """
    guilds = [Object(global_utils.val_server_id), Object(global_utils.debug_server_id)]
    await bot.add_cog(MiscCommands(bot), guilds=guilds)
