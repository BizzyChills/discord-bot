"""This module contains the global utility class, which contains various 
utility functions and global variables for the bot

Exports
-------
global_utils
    An instance of the Utils class, which contains all the global variables and utility functions
"""
# pylint: disable=wrong-import-order
import os
import json
from datetime import datetime, time, timedelta
import pytz
from asyncio import run
import re

# reduce bloat, only for type hints
from discord import Interaction
from discord.ext import commands

import asqlite


class Utils:
    """The global utility class, which contains various utility functions and global variables for the bot
    """

    def __init__(self) -> None:
        # ensure the working directory is the same as the script
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        if not os.path.exists('logs'):
            os.makedirs('logs')

        self.source_code = "https://github.com/BizzyChills/discord-bot"

        self.log_date = datetime.now().strftime("%Y-%m-%d")
        self.log_filepath = f'./logs/{self.log_date}_stdout.log'

        self.debug_server_id = 1217649405759324232
        self.debug_role_name = "southern"
        self.debug_channel_id = 1217649405759324235

        self.val_server_id = 1100632842528096330
        self.prem_role_name = "The Valorats"
        self.val_role_id = 1131273362786750516
        self.bot_channel_id = 1218420817394925668
        self.prem_channel_id = 1193661647752003614
        self.notes_channel_id = 1237971459461218376

        self.my_id = 461265370813038633
        sam_id = 180107711806046208
        self.admin_ids = [self.my_id, sam_id]
        self.teammate_ids = []

        # delete messages after n seconds.
        # When using delete_after argument, the message will not be deleted if
        # the bot goes offline before the time is up (so be careful setting this too high)
        self.delete_after_seconds = 5

        self.tz = pytz.timezone("US/Eastern")

        right_now = (datetime.now().replace(
            microsecond=0) + timedelta(seconds=5)).time()
        self.premier_reminder_times = [  # add 2 seconds to each time to ensure time_remaining logic works
            right_now,  # debug,

            # 1 hr before for thur and sun
            time(hour=21, second=2),

            # right on time for thur and sun (and 1 hr before for sat)
            time(hour=22, second=2),

            time(hour=23, second=2)  # right on time for sat
        ]

        self.premier_reminder_times = [self.est_to_utc(
            t) for t in self.premier_reminder_times]

        self.commands = run(self.get_commands())
        self.custom_emojis = run(self.get_custom_emojis())

        map_info = run(self.get_map_info())

        self.map_preferences = run(self.get_map_preferences())
        self.map_weights = {m: map_info[m]["weight"] for m in self.map_preferences}
        self.map_weights = dict(sorted(self.map_weights.items(), key=lambda item: item[1], reverse=True))
        self.map_preferences = {m: self.map_preferences[m] for m in self.map_weights}

        self.map_pool = sorted([m for m in map_info if map_info[m]["in_pool"]])
        self.map_image_urls = {m: map_info[m]["url"] for m in self.map_preferences}

        self.practice_notes = run(self.get_map_notes())

        self.reminders = self.get_reminders()


    def get_pool(self) -> list[str]:
        """Extracts the map pool from ./local_storage/map_pool.txt

        Returns
        -------
        list
            A list of strings containing the maps in the current map pool
        """
        with open("./local_storage/map_pool.txt", "r", encoding="utf-8") as file:
            return file.read().splitlines()

    def save_pool(self) -> None:
        """Saves any changes made to the map pool during runtime to ./local_storage/map_pool.txt
        """
        self.map_pool.sort()
        with open("./local_storage/map_pool.txt", "w", encoding="utf-8") as file:
            file.write("\n".join(self.map_pool))

    def get_preferences(self) -> dict:
        """Extracts the map preferences from ./local_storage/map_preferences.json

        Returns
        -------
        dict
            A 2D dictionary containing with the following structure: {map: {user_id: weight}}
        """
        with open("./local_storage/map_preferences.json", "r", encoding="utf-8") as file:
            prefs = json.load(file)
            if prefs == {}:
                try:
                    prefs = {map_name: {} for map_name in self.map_pool}
                except AttributeError:
                    self.map_pool = self.get_pool()
                    prefs = {map_name: {} for map_name in self.map_pool}

            return prefs

    def save_preferences(self) -> None:
        """Saves any changes made to the map preferences during runtime to 
        ./local_storage/map_preferences.json and also saves the map weights
        """
        self.map_preferences = {
            k: self.map_preferences[k] for k in sorted(self.map_preferences)}

        # filter out old teammates' preferences, but we need to be careful not to accidentally remove all preferences
        # so just don't do any filtering if the roster is empty
        if self.teammate_ids:
            for map_name in self.map_preferences.keys():
                prefs = self.map_preferences[map_name]
                self.map_preferences[map_name] = {
                    u_id: prefs[u_id] for u_id in prefs if int(u_id) in self.teammate_ids}

        with open("./local_storage/map_preferences.json", "w", encoding="utf-8") as file:
            json.dump(self.map_preferences, file)

        self.save_weights()

    def get_weights(self) -> dict:
        """Extracts the map weights from ./local_storage/map_weights.json

        Returns
        -------
        dict
            A dictionary containing the weights for each map in the current map pool
        """
        with open("./local_storage/map_weights.json", "r", encoding="utf-8") as file:
            weights = json.load(file)
            if weights == {}:
                weights = {map_name: 0 for map_name in self.map_preferences}

            return weights

    def save_weights(self) -> None:
        """Saves any changes made to the map weights during runtime to ./local_storage/map_weights.json
        """
        for map_name, user_weights in self.map_preferences.items():
            self.map_weights[map_name] = sum(user_weights.values())

        self.map_weights = dict(sorted(self.map_weights.items(), key=lambda item: item[1], reverse=True))

        with open("./local_storage/map_weights.json", "w", encoding="utf-8") as file:
            json.dump(self.map_weights, file)

    def get_reminders(self) -> dict:
        """Extracts the reminders from ./local_storage/reminders.json

        Returns
        -------
        dict
            A 2D dictionary containing with the following structure: {guild_id: {reminder_time: reminder_message}}
        """
        with open("./local_storage/reminders.json", "r", encoding="utf-8") as file:
            return json.load(file)

    def save_reminders(self) -> None:
        """Saves any changes made to the reminders during runtime to ./local_storage/reminders.json
        """
        with open("./local_storage/reminders.json", "w", encoding="utf-8") as file:
            json.dump(self.reminders, file)

    def get_notes(self) -> dict:
        """Extracts the practice notes from ./local_storage/notes.json file.
        This does not actually contain the notes, but rather the message IDs of the notes in the notes channel.

        Returns
        -------
        dict
            A 2D dictionary containing with the following structure: {map: {note_message_id: note_description}}
        """
        with open("./local_storage/notes.json", "r", encoding="utf-8") as file:
            return json.load(file)

    def save_notes(self) -> None:
        """Saves any changes made to the practice notes during runtime to ./local_storage/notes.json
        """
        if not isinstance(self.practice_notes, dict):
            self.practice_notes = {}
        with open("./local_storage/notes.json", "w", encoding="utf-8") as file:
            json.dump(self.practice_notes, file)

    async def get_commands(self) -> dict:
        """Retrieves command names, ids, and descriptions from the commands database

        Returns
        -------
        dict
            A dictionary containing the command names and descriptions
        """
        async with asqlite.connect("./local_storage/commands.db") as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM commands")
                rows = await cur.fetchall()

        return {row[0]: {"id": row[1], "description": row[2], "emoji": row[3]} for row in rows}

    async def get_custom_emojis(self) -> dict:
        """Retrieves custom emoji names, ids, and string formats from the custom emojis database

        Returns
        -------
        dict
            A dictionary containing the custom emoji names and formats
        """
        async with asqlite.connect("./local_storage/custom_emojis.db") as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM custom_emojis")
                rows = await cur.fetchall()

        return {row[0]: {"id": row[1], "format": row[2], "link": row[3]} for row in rows}

    async def get_map_preferences(self) -> dict:
        """Retrieves the map preferences from the map preferences database

        Returns
        -------
        dict
            A dictionary containing the map preferences for each user
            grouped by map name
        """
        ret = {}
        async with asqlite.connect("./local_storage/maps.db") as conn:
            async with conn.cursor() as cur:
                await cur.execute("PRAGMA table_info(preferences)")
                columns = await cur.fetchall()

                for c in columns:
                    if c[1] == "user_id":
                        continue

                    await cur.execute(f"SELECT user_id, {c[1]} FROM preferences")
                    rows = await cur.fetchall()

                    ret.update({c[1]: {row[0]: row[1] for row in rows}})

        return ret

    async def get_map_info(self) -> dict:
        """Retrieves the map info from the map info database

        Returns
        -------
        dict
            A dictionary containing the map info for each map
        """
        ret = {}
        async with asqlite.connect("./local_storage/maps.db") as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM info")
                rows = await cur.fetchall()

                for row in rows:
                    ret[row[0]] = {
                        "in_pool": row[1],
                        "weight": row[2],
                        "url": row[3]
                    }

        return ret

    async def get_map_notes(self) -> dict:
        """Retrieves the practice notes from the practice notes database

        Returns
        -------
        dict
            A dictionary containing the practice notes for each map
            grouped by map name and containing the message ID and description
        """
        ret = {}
        async with asqlite.connect("./local_storage/maps.db") as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM notes")
                rows = await cur.fetchall()

                for row in rows:
                    ret[row[0]] = {row["message_id"]: row["description"]}

        return ret

    def log(self, message: str) -> None:
        """Logs a message to the current stdout log file

        Parameters
        ----------
        message : str
            The message to log
        """
        with open(self.log_filepath, 'a+', encoding="utf-8") as file:
            if "connected to Discord" in message:
                prefix = "\n" if file.readline() != "" else ""
                file.write(f"{prefix}{'-' * 50}\n")

            file.write(
                f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {message}\n')

    def debug_log(self, message: str) -> None:
        """Logs a message to the debug log file

        Parameters
        ----------
        message : str
            The debug message to log
        """
        with open("./local_storage/debug_log.txt", 'a', encoding="utf-8") as file:
            file.write(
                f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {message}\n')

    def est_to_utc(self, t: time) -> time:
        """Converts an EST time to a UTC time

        Parameters
        ----------
        t : time
            The EST time to convert

        Returns
        -------
        datetime.time
            The converted, UTC time
        """
        d = datetime.combine(datetime.today(), t)
        return self.tz.localize(d).astimezone(pytz.utc).time()

    def discord_local_time(self, date_time: datetime, with_date=False) -> str:
        """Converts a datetime object to a Discord-formatted local time string 
        (shows the time in the user's local time zone)
        If the datetime object is naive, it will be assumed to be in the bot's local time zone (EST)

        Parameters
        ----------
        date_time : datetime
            The datetime object to convert
        with_date : bool, optional
            Include the date in the formatted string, by default False

        Returns
        -------
        str
            The Discord-formatted local time string
        """
        epoch_time = date_time.timestamp()
        style = "F" if with_date else "t"  # F for full date and time
        style = "R"
        formatted = f"<t:{str(int(epoch_time))}:{style}>"
        return formatted

    def style_text(self, text: str, style: str) -> str:
        """Formats text to a specified style in Discord

        Parameters
        ----------
        text : str
            The text to format
        style : str
            The style string to apply to the text. Options are (i)talics, (u)nderline, (b)old, or (c)ode. 

            Just use the first letter of the desired style (case-insensitive and spaces are ignored). 
            If a style character is not recognized, it will be ignored.

        Example:
        ```python
        style_text("Hello, World!", 'ib')  # returns "**_Hello, World!_**"
        ```

        Returns
        -------
        str
            The formatted text
        """
        style = style.replace(" ", "").lower()  # easier to parse the style
        style = set(style)

        output = text

        all_styles = {'i': '_', 'u': '__', 'b': '**', 'c': '`'}

        for s in style:
            if s not in all_styles:
                continue

            s = all_styles[s]
            output = f"{s}{output}{s}"

        return output

    def mention_slash(self, command_name: str) -> str | None:
        """Formats text to mention a slash command in Discord

        Parameters
        ----------
        command_name : str
            The name of the command to mention. Any prefixing slashes are ignored.

        Returns
        -------
        str | None
            The formatted text, or None if the command name is not recognized
            or the command does not have an ID
        """
        command_name = command_name.lstrip("/")
        if command_name not in self.commands:
            return None

        command_id = self.commands[command_name]["id"]

        return f"</{command_name}:{command_id}>" if command_id else None

    def emojify(self, text: str) -> dict:
        """Formats the input string to include the bot's custom emojis in Discord.
        In order to use an emoji, the emoji name must be surrounded by semicolons in the text.
        Example: "Hello, ;mc_pig;!" will be formatted to "Hello, <:mc_pig:1266232717339656192>!"

        Parameters
        ----------
        text : str
            The formatted text to emojify

        Returns
        -------
        dict
            A dictionary containing the modified text and a dictionary of the names of the inserted emojis
        """
        if ";" not in text:
            return {"output": text, "emojis": []}

        inserted_emojis = []
        matches = re.findall(";([A-Za-z_]+);", text)
        for match in matches:
            if match in self.custom_emojis:
                text = text.replace(f";{match};", self.custom_emojis[match]["format"])
                inserted_emojis.append(match)

        text = "".join(text)

        return {"output": text, "emojis": inserted_emojis}

    async def load_cogs(self, bot: commands.Bot) -> None:
        """Load/reload all cogs in the cogs directory

        Parameters
        ----------
        bot : discord.ext.commands.Bot
            The bot object that the cogs will be loaded into
        """
        dirs = ["cogs", "ignore_but_use"]
        for d in dirs:
            for file in os.listdir(f'./{d}'):
                if file.endswith('.py'):
                    f = f'{d}.{file[:-3]}'
                    try:
                        # reload them if they're already loaded
                        await bot.reload_extension(f)
                    except commands.ExtensionNotLoaded:  # otherwise
                        await bot.load_extension(f)  # load them

    def already_logged(self, log_message: str) -> bool:
        """Checks if a log message has already been logged in the current stdout log file.

        This is useful for functions that use the log to track state 
        (ex. eventreminders task to avoid sending duplicate reminders after a restart)

        Parameters
        ----------
        log_message : str
            The message to check for in the log file

        Returns
        -------
        bool
            Whether the message has already been logged
        """
        if log_message == "":
            return False

        with open(self.log_filepath, "r", encoding="utf-8") as file:
            log_contents = file.read()

        return log_message in log_contents if log_contents != "" else False

    async def is_admin(self, ctx: commands.Context | Interaction, respond: bool = True) -> bool:
        """Determines if the user is either Sam or Bizzy for use in admin commands

        Parameters
        ----------
        ctx : discord.ext.commands.Context | discord.Interaction
            The context object that initiated the command. Can be either a text command or a slash command
        respond : bool, optional
            Respond to the user with a invalid permissions message, by default True

        Returns
        -------
        bool
            Whether the user has permission to use the command
        """
        message = "You do not have permission to use this command"

        if isinstance(ctx, commands.Context):
            responder = ctx.send
            command = ctx.invoked_with
            user_id = ctx.author.id
        else:
            responder = ctx.response.send_message
            command = ctx.command.name
            user_id = ctx.user.id

        if user_id in self.admin_ids:
            return True

        if respond:
            await responder(message, ephemeral=True)

        self.log(
            f"User with id {user_id} attempted to use the admin command '{command}'")
        return False


global_utils = Utils()
