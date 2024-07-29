"""[cog] A cog for tasks that the bot needs to do on a regular basis
(like sending reminders for upcoming events, clearing old reminders, etc.)
"""
import sys
from copy import deepcopy
from asyncio import sleep
from datetime import datetime, time, timedelta
import asyncpg
import pytz

import discord
from discord.ext import commands, tasks

from global_utils import global_utils  # pylint: disable=wrong-import-order


class TasksCog(commands.Cog):
    """[cog] A cog for tasks that the bot needs to do on a regular basis
    (like sending reminders for upcoming events, clearing old reminders, etc.)

    Parameters
    ----------
    bot : discord.ext.commands.bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """

    def __init__(self, bot: commands.bot) -> None:
        self.bot = bot

        self.do_event_reminders = False
        self.premier_reminder_types = ["start", "prestart"]
        self.eventreminders.add_exception_type(asyncpg.PostgresConnectionError)  # pylint: disable=no-member

        self.tasks = [self.eventreminders,
                      self.clear_old_reminders,
                      self.remember_reminders,
                      self.latest_logs]

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """[event] Executes when the TasksCog cog is ready to start the tasks
        """
        # global_utils.log("Tasks cog loaded")
        # pylint: disable=no-member
        for task in self.tasks:
            if not task.is_running():
                task.start()
        # pylint: enable=no-member

    async def get_reminder_type(self, event: discord.ScheduledEvent) -> str:
        """Given an event, returns the type of reminder that needs to be sent
        Parameters
        ----------
        event : discord.Event
            The event to determine the reminder type for

        Returns
        -------
        str
            The type of reminder to send (from self.premier_reminder_types) or an empty string if no reminder is needed

        """
        time_remaining = (event.start_time -
                          datetime.now(pytz.utc)).total_seconds()

        reminder_type = ""
        if time_remaining <= 0:  # allow this reminder until 10 minutes after the event has already started
            if time_remaining >= -60 * 10:
                reminder_type = self.premier_reminder_types[0]
                if event.status == discord.EventStatus.scheduled:
                    await event.start()
            elif time_remaining <= -3600:  # remove the event
                if event.status == discord.EventStatus.active:
                    await event.end()
                elif event.status == discord.EventStatus.scheduled:
                    await event.cancel()
        elif time_remaining <= 3600:
            reminder_type = self.premier_reminder_types[1]

        return reminder_type

    async def get_all_events(self) -> list[discord.ScheduledEvent]:
        """Returns a list of all the events that need to be checked for reminders

        Returns
        -------
        list[discord.ScheduledEvent]
            The list of events to check for reminders
        """
        guild_ids = [global_utils.val_server_id, global_utils.debug_server_id]
        if not self.do_event_reminders:
            # only send the reminders in the debug server
            guild_ids.pop(0)

        events = []

        for g_id in guild_ids:
            guild = self.bot.get_guild(g_id)
            # send closest reminders last (so they are newest in the channel)
            new_events = [
                e for e in guild.scheduled_events if "premier" in e.name.lower()]
            events += sorted(new_events,
                             key=lambda x: x.start_time, reverse=True)

        return events

    def get_channel_role(self, guild_id: int) -> tuple[discord.TextChannel, discord.Role]:
        """Returns the channel and role to send reminders to for a given guild

        Parameters
        ----------
        guild_id : int
            The ID of the guild to get the channel and role for

        Returns
        -------
        tuple[discord.TextChannel, discord.Role]
            The channel and role to send reminders to
        """
        if guild_id == global_utils.val_server_id:
            channel = self.bot.get_channel(global_utils.prem_channel_id)
            role = discord.utils.get(
                channel.guild.roles, name=global_utils.prem_role_name)
        elif guild_id == global_utils.debug_server_id:
            channel = self.bot.get_channel(global_utils.debug_channel_id)
            role = discord.utils.get(
                channel.guild.roles, name=global_utils.debug_role_name)

        return channel, role

    @tasks.loop(time=global_utils.premier_reminder_times)
    async def eventreminders(self) -> None:  # pylint: disable=too-many-locals
        """[task] Sends reminders for upcoming events near starting times of West Coast premier events
        """
        global_utils.log("Checking for event reminders")

        events = await self.get_all_events()
        for event in events:
            reminder_type = await self.get_reminder_type(event)
            if reminder_type == "":  # there is no event reminder to send
                continue

            log_time = event.start_time.astimezone(global_utils.tz).strftime(
                "%Y-%m-%d %H:%M:%S")

            log_message = (f"Posted '{reminder_type}' reminder for event: {event.name} on {event.description}" +
                           f"starting at {log_time} EST")

            # if the reminder has already been posted, skip it
            if global_utils.already_logged(log_message):
                continue

            subbed_users = []
            async for user in event.users():
                subbed_users.append(user)

            channel, role = self.get_channel_role(event.guild_id)

            embed = await self.get_reminder_embed(event, reminder_type, len(subbed_users))

            prefix = "(reminder)"
            if reminder_type == self.premier_reminder_types[1]:
                message = f"{prefix} {role.mention}"

                button = discord.ui.Button(
                    style=discord.ButtonStyle.link, label="RSVP", url=event.url)
                view = discord.ui.View()
                view.add_item(button)
            else:
                header = global_utils.style_text('RSVP\'ed Users:', 'bu')
                message = f"{prefix}\n{header}\n- " + \
                    '\n- '.join([user.mention for user in subbed_users])

                view = None

            await channel.send(message, embed=embed, view=view)

            # mark the reminder as posted
            global_utils.log(log_message)

    async def get_reminder_embed(self, event: discord.ScheduledEvent, remind_type: str, sub_len: int) -> discord.Embed:
        """Generates an embed for a reminder message

        Parameters
        ----------
        event : discord.ScheduledEvent
            The event that the reminder is for
        remind_type : str
            The type of the reminder embed to generate, from self.premier_reminder_types
        sub_len : int
            The number of users who have subbed to the event

        Returns
        -------
        discord.Embed
            The embed to send
        """
        map_name = event.description.lower()
        map_url = global_utils.map_image_urls.get(map_name, "")
        map_display = global_utils.style_text(
            event.description.title(), 'i')

        event_type = "practice" if "practice" in event.name.lower() else "match"
        start_time = global_utils.discord_local_time(event.start_time)
        rsvp_hint = ("Please RSVP by clicking the button below and then clicking" +
                     f" {global_utils.style_text('interested', 'c')} (if you haven't already).")

        title = f"Premier {event_type} on {map_display}"
        if remind_type == self.premier_reminder_types[1]:
            desc = f"There is a premier {event_type} on {map_display} in 1 hour (at {start_time})! {rsvp_hint}"
        else:
            desc = f"The premier {event_type} on {map_display} is starting {global_utils.style_text('NOW', 'bu')}!"

        subbed_display = f"{sub_len} {('user', 'users')[sub_len != 1]}"

        embed = discord.Embed(title=title, description=desc,
                              color=discord.Color.blurple())
        (
            embed.set_image(url=map_url)
            .add_field(name="RSVP'ed", value=subbed_display, inline=True)
            .add_field(name="Map Weight", value=f"{global_utils.map_weights[map_name]}", inline=True)
        )

        return embed

    @tasks.loop(hours=1)
    async def clear_old_reminders(self) -> None:
        """[task] Clears old reminder messages from the premier and debug channels"""
        channels = global_utils.prem_channel_id, global_utils.debug_channel_id

        for channel_id in channels:
            channel = self.bot.get_channel(channel_id)
            now = datetime.now().astimezone(pytz.utc)
            before = now - timedelta(days=1)
            # bulk deletion only works for messages up to 14 days old. If the bot is offline for over 14 days, oh well
            after = now - timedelta(days=14)

            messages = [m async for m in channel.history(limit=None, before=before, after=after)
                        if m.author == self.bot.user
                        and m.content.startswith("(reminder)")  # bot prefixes all reminder messages with this
                        and now - m.created_at > timedelta(days=1)]

            if len(messages) == 0:
                continue

            await channel.delete_messages(messages)
            global_utils.log(
                f"Deleted {len(messages)} old reminder messages from {channel.name}")

    @tasks.loop(count=1)
    async def remember_reminders(self) -> None:
        """[task] Remembers reminder timers (made via /remind) in case the bot goes offline
        """
        reminder_iter = deepcopy(global_utils.reminders)
        sorted_keys = sorted(reminder_iter.keys())
        reminder_iter = {k: reminder_iter[k] for k in sorted_keys}

        for time_str, reminders in reminder_iter.items():
            reminder_time = datetime.fromisoformat(time_str)
            for reminder_info in reminders:
                server_id = reminder_info[0]
                reminder_message = reminder_info[1]

                channel = (
                    self.bot.get_channel(global_utils.prem_channel_id)
                    if server_id == global_utils.val_server_id
                    else self.bot.get_channel(global_utils.debug_channel_id))

                if reminder_time < datetime.now():
                    await channel.send(reminder_message + "\n(this reminder was supposed to go off at " +
                                       global_utils.discord_local_time(reminder_time) + ".")
                    global_utils.log(
                        "Bot missed a reminder during its downtime, but sent it now. Message: " + reminder_message)
                else:
                    await sleep((reminder_time - datetime.now()).total_seconds())
                    await channel.send(reminder_message)
                    global_utils.log("Posted reminder: " + reminder_message)

                global_utils.reminders[time_str] = [r for r in reminders if r != reminder_info]

                global_utils.save_reminders()

    # wait until a few seconds after midnight to start new log in case of some delay/desync issue
    @tasks.loop(time=global_utils.est_to_utc(time(hour=0, minute=0, second=5)))
    async def latest_logs(self) -> None:
        """[task] Creates a new log file at midnight and updates the logger to write to the new file"""
        new_date = datetime.now().strftime("%Y-%m-%d")

        if new_date != global_utils.log_date:
            global_utils.log("Starting new log file")
            global_utils.log_date = new_date
            global_utils.log_filepath = f"./logs/{global_utils.log_date}_stdout.log"
            sys.stdout.close()
            sys.stderr.close()

            sys.stdout = open(global_utils.log_filepath, 'a', encoding="utf-8")
            sys.stderr = open(f"./logs/{global_utils.log_date}_stderr.log", 'a', encoding="utf-8")


async def setup(bot: commands.bot) -> None:
    """Adds the TasksCog cog to the bot

    Parameters
    ----------
    bot : discord.ext.commands.bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """
    await bot.add_cog(TasksCog(bot), guilds=[
        discord.Object(global_utils.val_server_id),
        discord.Object(global_utils.debug_server_id)])
