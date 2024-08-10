"""This module contains the main bot var and event handlers
and is meant to be run directly to start the bot.
"""
import sys
import asyncio
from os import getenv

from discord import Interaction, Intents, app_commands, Message, Embed
from discord.ext import commands
from discord.ext.commands import Context

from global_utils import global_utils
from cogs.persist_commands import PersistentView


bot_token = getenv("DISCORD_BOT_TOKEN")
intents = Intents.default()
intents.typing = False
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!',
                   intents=intents, help_command=None)

if not bot_token:
    raise ValueError(
        "DISCORD_BOT_TOKEN is not set in the environment variables")


async def setup_hook() -> None:
    """Re-links/syncs the bot's persistent buttons"""
    bot.add_view(PersistentView())

    sys.stderr = open(f'./logs/{global_utils.log_date}_stderr.log', 'a', encoding="utf-8")


@bot.tree.error
async def on_app_command_error(interaction: Interaction, error: app_commands.AppCommandError) -> None:
    """[app error] Handles slash command errors

    Parameters
    ----------
    interaction : discord.Interaction
        The interaction object that initiated the command
    error : discord.app_commands.AppCommandError
        The error that occurred

    Raises
    ------
    error
        If the interaction is expired and cannot be responded to, simply raise the error
    """
    global_utils.debug_log(str(error))

    if interaction.is_expired():
        raise error

    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"{error}", ephemeral=True)
        return

    if interaction.user.id == global_utils.my_id:
        await interaction.response.send_message(f"{error}", ephemeral=True)
    else:
        err = "An unexpected error occurred. Please notify Bizzy."
        m = await interaction.response.send_message(err, ephemeral=True)
        await m.delete(delay=5)

        bizzy = await bot.fetch_user(global_utils.my_id)
        user_name = interaction.user.name
        await bizzy.send(f"Error in slash command by {user_name}: {error}")


@bot.event
async def on_command_error(ctx: Context, error: commands.CommandError) -> None:
    """[prefix error] Handles text command errors

    Parameters
    ----------
    ctx : discord.ext.commands.Context
        The context object that initiated the command
    error : discord.ext.commands.CommandError
        The error that occurred
    """
    global_utils.debug_log(str(error))

    if ctx.author.id == global_utils.my_id:
        await ctx.send(f"{error}")
    else:
        m = await ctx.send("An unexpected error occurred. Please notify Bizzy.")
        await m.delete(delay=5)
        await ctx.message.delete(delay=5)

        bizzy = await bot.fetch_user(global_utils.my_id)
        user_name = ctx.author.name
        await bizzy.send(f"Error in text command by {user_name}: {error}")


async def process_message(message: Message) -> None:
    """[helper] Handles any special processing for a message (such as emojifying)

    Parameters
    ----------
    message : Message
        The message object to process
    """
    emoji_dict = global_utils.emojify(message.content)
    if emoji_dict["output"] != message.content:
        await message.delete()
        await send_emojified(message, emoji_dict)


async def send_emojified(message: Message, emoji_dict: dict) -> None:
    """[helper] Sends a message for a user by proxy.
    This is mainly used for emojifying messages.

    Parameters
    ----------
    message : discord.Message
        The original message object
    emoji_dict : dict
        The dictionary containing the emojified message and a list of emojis names used
        emoji_dict has the following structure: {"output": emojified_message, "emojis": [emoji_names]}
    """
    author = {"name": message.author.display_name, "icon_url": message.author.display_avatar.url}
    description = emoji_dict["output"]
    image_url = None

    if len(emoji_dict["emojis"]) == 1:
        emoji = emoji_dict["emojis"][0]
        emoji = global_utils.custom_emojis[emoji]
        # if the message is just the emoji, make it an image and not a description
        if description == emoji["format"]:
            description = None
            image_url = emoji["link"]

    embed = (Embed(description=description, color=message.author.color)
             .set_author(name=author["name"], icon_url=author["icon_url"])
             .set_image(url=image_url))

    await message.channel.send(embed=embed)


@bot.event
async def on_message(message: Message) -> None:
    """[event] Executes when a message is sent

    Parameters
    ----------
    message : discord.Message
        The message object that was sent
    """
    if message.author == bot.user:
        return

    if (message.content.startswith(f"{bot.command_prefix}kill")
            or message.content.startswith(f"{bot.command_prefix}reload")):
        await bot.process_commands(message)

    # This channel is used for the persistent view and should not have any other messages
    # (unless they are from the bot or are slash commands)
    if message.channel.id == global_utils.bot_channel_id:
        await message.delete()
        return

    await process_message(message)


async def get_teammate_ids():
    """Gets the IDs of all teammates in the val server
    """
    val_server = bot.get_guild(global_utils.val_server_id)
    val_role = val_server.get_role(global_utils.val_role_id)
    return [member.id for member in val_role.members]


async def main() -> None:
    """[main] Loads all cogs and starts the bot
    """
    sys.stdout = open(global_utils.log_filepath, 'a', encoding="utf-8")
    bot.setup_hook = setup_hook
    await global_utils.load_cogs(bot)
    await bot.start(bot_token)

    global_utils.teammate_ids = await get_teammate_ids()

if __name__ == '__main__':
    try:
        # bot.run(bot_token)
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(bot.close())
else:
    print("This script is not meant to be imported. Please run it directly.")
    sys.exit(1)
