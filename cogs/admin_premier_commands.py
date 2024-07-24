"""[cog] A cog for managing premier events, practices, and map pool
"""
from datetime import datetime, time, timedelta
from re import match
from pytz import utc

import discord
from discord.ext import commands
from discord.ext.commands import Context
from discord import app_commands, Object

from global_utils import global_utils

# pylint: disable=invalid-overridden-method
# pylint: disable=arguments-differ


class AdminPremierCommands(commands.Cog):
    """[cog] A cog for managing the premier events and practices`

    Parameters
    ----------
    bot : discord.ext.commands.bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """

    def __init__(self, bot: commands.bot) -> None:
        self.bot = bot
        self.debug_event_channel_id = 1217649405759324236  # debug voice channel
        self.event_channel_id = 1100632843174031476  # premier voice channel

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

    @app_commands.command(name="map-pool", description=global_utils.commands["map-pool"]["description"])
    async def map_pool(self, interaction: discord.Interaction) -> None:
        """[app command] Opens the map pool modification panel

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        """
        await interaction.response.defer(ephemeral=True)

        view = MapPoolPanel(sync_changes=self.sync_map_pool)
        embed = discord.Embed(title="Map Pool", description="- " + '\n- '.join([global_utils.style_text(
            m.title(), 'i') for m in global_utils.map_pool]), color=discord.Color.blurple())

        await interaction.followup.send("Map Pool (make sure you click out of the dropdown before hitting a button)",
                                        view=view, embed=embed, ephemeral=True)

    async def sync_map_pool(self, interaction: discord.Interaction) -> None:
        """Saves changes made to the map pool and the overall map list

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        """
        await global_utils.load_cogs(self.bot)
        await self.bot.tree.sync(guild=Object(id=interaction.guild.id))
        await interaction.followup.send(content="Map Pool changes applied", ephemeral=True)
        # don't delete this message. Since it can take a while to apply changes,
        # the user may miss this notification if it is deleted (ex. they afk)

    @app_commands.command(name="add-map", description=global_utils.commands["add-map"]["description"])
    @app_commands.describe(
        map_name="The name of the map that was added to the game"
    )
    async def add_map(self, interaction: discord.Interaction, map_name: str) -> None:
        """[app command] Adds a new map to the list of all maps in the game

        Parameters
        ----------
        map_name : str
            The map to add
        """
        # await interaction.response.defer(ephemeral=True)
        map_name = map_name.lower()
        map_display_name = global_utils.style_text(map_name.title(), 'i')

        if map_name in global_utils.map_preferences:
            await interaction.response.send_message(f'Map "{map_display_name}" is already in the game.',
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        global_utils.map_preferences = {
            map_name: {}} | global_utils.map_preferences
        global_utils.map_weights = {map_name: 0} | global_utils.map_weights

        # note: this function also calls save_weights
        global_utils.save_preferences()

        await interaction.response.defer()
        await self.sync_map_pool(interaction)

    @app_commands.command(name="remove-map", description=global_utils.commands["remove-map"]["description"])
    @app_commands.describe(
        map_name="The name of the map that was removed from the game"
    )
    @app_commands.choices(
        map_name=[
            app_commands.Choice(name=s.title(), value=s) for s in global_utils.map_preferences.keys()
        ],
        confirm=[app_commands.Choice(
            name="WARNING: This will remove the map and all of its data from the game (weights, votes, etc.)", value=1)]
    )
    async def remove_map(self, interaction: discord.Interaction, map_name: str, confirm: int) -> None:  # pylint: disable=unused-argument
        """[app command] Removes a new map to the list of all maps in the game

        Parameters
        ----------
        map_name : str
            The map to remove
        """
        # confirm is automatically chcecked by discord, so we just need to ensure it is a required argument to "confirm"

        map_name = map_name.lower()
        map_display_name = global_utils.style_text(map_name.title(), 'i')

        if map_name not in global_utils.map_preferences:
            await interaction.response.send_message(f'Map "{map_display_name}" is not in the game.',
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        # if it's in the map pool, remove it
        if map_name in global_utils.map_pool:
            global_utils.map_pool.remove(map_name)

        # if there are practice notes for it, remove the references
        global_utils.practice_notes.pop(map_name, None)
        global_utils.save_notes()

        global_utils.map_preferences.pop(map_name)
        global_utils.map_weights.pop(map_name)

        global_utils.save_pool()
        # note: this function also calls save_weights
        global_utils.save_preferences()

        await interaction.response.defer()
        await self.sync_map_pool(interaction)

    @app_commands.command(name="add-events", description=global_utils.commands["add-events"]["description"])
    @app_commands.describe(
        map_list="The map order separated by commas (whitespace between maps does not matter). Ex: 'map1, map2, map3'",
        date="The date (mm/dd/yy) of the Thursday that starts the first event (can be in the past)."
    )
    async def addevents(self, interaction: discord.Interaction, map_list: str, date: str) -> None:
        """[app command] Adds all premier events to the schedule at a rate of 5 events/minute

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        map_list : str
            The season's map order separated by commas (whitespace between maps does not matter). Ex: 'map1, map2, map3'
        date : str
            The date (mm/dd/yy) of the Thursday that starts the first event (can be in the past).
        """
        # THERE IS A RATELIMIT OF 5 EVENTS/MINUTE

        guild = interaction.guild

        # split by comma and remove extra whitespace
        new_maps = [m.strip().lower() for m in map_list.split(",")]

        for map_name in new_maps:
            if map_name not in global_utils.map_pool:
                map_display_name = global_utils.style_text(
                    map_name.title(), 'i')
                map_list = global_utils.style_text('map_list', 'c')
                map_pool = global_utils.style_text('/map-pool', 'c')
                hint = f"Ensure that {map_list} is formatted properly and that {map_pool} has been updated."
                await interaction.response.send_message(f"{map_display_name} is not in the map pool. {hint}",
                                                        ephemeral=True, delete_after=global_utils.delete_after_seconds)
                return

        regex = r"(0?[1-9]|1[0-2])/(0?[1-9]|[12][0-9]|3[01])/([0-9]{2})"
        matches = match(regex, date)
        if not matches or sum(len(g) for g in matches.groups()) != len(date) - 2:  # -2 for the slashes
            example = f"(ex. {global_utils.style_text('07/10/24 or 7/10/24', 'c')} for July 10th, 2024)"
            format_hint = f"Please provide a date in the format {global_utils.style_text('mm/dd/yy', 'c')}. {example}"
            await interaction.response.send_message(f'Invalid date format. {format_hint}',
                                                    ephemeral=True,
                                                    delete_after=global_utils.delete_after_seconds)
            return

        month, day, year = (str(int(g)) for g in matches.groups())  # this removes all leading 0s
        # we still need them for the datetime object, just don't want to duplicate them
        if len(month) == 1:
            month = "0" + month
        if len(day) == 1:
            day = "0" + day

        input_date = global_utils.tz.localize(datetime.strptime(
            f"{month}/{day}/{year}", "%m/%d/%y"))  # - for no leading 0s

        if input_date.weekday() != 3:
            await interaction.response.send_message('Input date is not a Thursday.',
                                                    ephemeral=True,
                                                    delete_after=global_utils.delete_after_seconds)
            return

        thur_time = datetime(year=input_date.year, month=input_date.month, day=input_date.day,
                             hour=22, minute=0, second=0)
        sat_time = (thur_time + timedelta(days=2)).replace(hour=23)
        sun_time = thur_time + timedelta(days=3)

        start_times = [global_utils.tz.localize(
            d) for d in [thur_time, sat_time, sun_time]]

        await interaction.response.defer(ephemeral=True, thinking=True)

        output = ""

        now = global_utils.tz.localize(datetime.now())

        if interaction.guild.id == global_utils.val_server_id:
            this_id = self.event_channel_id
        else:
            this_id = self.debug_event_channel_id

        voice_channel = discord.utils.get(
            guild.voice_channels, id=this_id)

        for i, map_name in enumerate(new_maps):
            for j, start_time in enumerate(start_times):
                if now > start_time:
                    output = "Detected that input date is in the past. Any maps that are in the past were skipped."
                    continue
                event_name = "Premier"
                event_desc = map_name.title()

                # last map and last day is playoffs
                if i == len(new_maps) - 1 and j == len(start_times) - 1:
                    event_name = "Premier Playoffs"
                    event_desc = "Playoffs"

                await guild.create_scheduled_event(name=event_name, description=event_desc, channel=voice_channel,
                                                   start_time=start_time, end_time=start_time + timedelta(hours=1),
                                                   entity_type=discord.EntityType.voice,
                                                   privacy_level=discord.PrivacyLevel.guild_only)

            start_times = [start_time + timedelta(days=7)
                           for start_time in start_times]

        new_maps = [global_utils.style_text(m, 'i')
                    for m in ", ".join(new_maps)]
        global_utils.log(
            f'{interaction.user.display_name} has posted the premier schedule starting on {date} with maps: {new_maps}')

        output += f'\nThe Premier schedule has been created starting on {date} with maps: {", ".join(new_maps)}'
        await interaction.followup.send(output, ephemeral=True)
        # don't delete the message. This command can take a while and the user may miss the notification

    @app_commands.command(name="cancel-event", description=global_utils.commands["cancel-event"]["description"])
    @app_commands.choices(
        map_name=[app_commands.Choice(name=s.title(), value=s) for s in global_utils.map_pool] +
        [app_commands.Choice(name="Playoffs", value="playoffs")],
        all_events=[
            app_commands.Choice(name="Yes", value=1),
        ],
        announce=[
            app_commands.Choice(name="Yes", value=1),
        ]
    )
    @app_commands.describe(
        map_name="The map to cancel the closest event for",
        all_events="Cancel all events for the specified map",
        announce="Announce the cancellation when used in the premier channel"
    )
    async def cancelevent(self, interaction: discord.Interaction, map_name: str,
                          all_events: int = 0, announce: int = 0) -> None:
        """[app command] Cancels the next premier event (or all events on a map).
        It's important to note that events are not practices.

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        map_name : str
            The map to cancel the closest event for
        all_events : int, optional
            Treated as a boolean. Cancel all events for the specified map, by default 0
        announce : int, optional
            Treated as a boolean. Announce the cancellation when used in the premier channel, by default 0
        """
        map_display_name = global_utils.style_text(map_name.title(), 'i')

        if map_name not in global_utils.map_pool and map_name != "playoffs":
            hint = f"Ensure that {global_utils.style_text('/map-pool', 'c')} is updated."
            await interaction.response.send_message(f'{map_display_name} is not in the map pool. {hint}',
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        ephem = interaction.channel.id != global_utils.prem_channel_id or not announce
        await interaction.response.defer(ephemeral=ephem, thinking=True)

        guild = interaction.guild
        events = guild.scheduled_events

        message = ""

        for event in events:
            if "Premier" in event.name and event.description.lower() == map_name:  # map is already lower
                if event.status == discord.EventStatus.scheduled:
                    await event.cancel()
                elif event.status == discord.EventStatus.active:
                    await event.end()
                else:
                    await event.delete()

                if not all_events:
                    e_name = event.name
                    e_desc = event.description
                    e_date = event.start_time
                    display_date = global_utils.discord_local_time(
                        e_date, with_date=True)
                    log_date = event.start_time.astimezone(
                        global_utils.tz).isoformat(sep=' ', timespec='seconds')
                    message = f'{e_name} on {e_desc} on {display_date} has been cancelled'
                    log_message = f'{e_name} on {e_desc} on {log_date} has been cancelled'
                    break
                else:
                    message = log_message = f'All events on {map_display_name} have been cancelled'

        if message == "":
            message = f"No events found for {map_display_name} in the schedule."
            ephem = True
        else:
            global_utils.log(
                f'{interaction.user.display_name} cancelled event - {log_message}')

        m = await interaction.followup.send(message, ephemeral=ephem)

        if ephem:
            await m.delete(delay=global_utils.delete_after_seconds)

    @app_commands.command(name="add-practices", description=global_utils.commands["add-practices"]["description"])
    async def addpractices(self, interaction: discord.Interaction) -> None:
        """[app command] Adds all premier practice events to the schedule at a rate of 5 practices/minute. 
        Ensure that the premier events have been added first using /addevents

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        """
        # THERE IS A RATELIMIT OF 5 EVENTS/MINUTE

        await interaction.response.defer(ephemeral=True, thinking=True)

        guild = interaction.guild
        events = guild.scheduled_events

        if len([event for event in events if event.name == "Premier" and event.description != "Playoffs"]) == 0:
            hint = global_utils.style_text('/addevents', 'c')
            m = await interaction.followup.send(f'Please add the premier events first ({hint})', ephemeral=True)
            await m.delete(delay=global_utils.delete_after_seconds)
            return

        wed_hour = global_utils.est_to_utc(time(hour=22)).hour
        fri_hour = wed_hour + 1

        for event in events:
            if event.start_time.astimezone(global_utils.tz).weekday() != 3 or "Premier" not in event.name:
                continue

            wed_time = fri_time = event.start_time.astimezone(utc)
            wed_time = wed_time.replace(hour=wed_hour) - timedelta(days=1)
            fri_time = fri_time.replace(hour=fri_hour) + timedelta(days=1)

            for start_time in [wed_time, fri_time]:
                if start_time < datetime.now().astimezone(utc):
                    continue

                event_name = "Premier Practice"
                event_desc = event.description

                await guild.create_scheduled_event(name=event_name, description=event_desc, channel=event.channel,
                                                   start_time=start_time, end_time=start_time + timedelta(hours=1),
                                                   entity_type=discord.EntityType.voice,
                                                   privacy_level=discord.PrivacyLevel.guild_only)

        global_utils.log(
            f'{interaction.user.display_name} has posted the premier practice schedule')

        m = await interaction.followup.send('Added premier practice events to the schedule', ephemeral=True)
        await m.delete(delay=global_utils.delete_after_seconds)

    @app_commands.command(name="cancel-practice", description=global_utils.commands["cancel-practice"]["description"])
    @app_commands.choices(
        map_name=[
            app_commands.Choice(name=s.title(), value=s) for s in global_utils.map_pool
        ],
        all_practices=[
            app_commands.Choice(name="Yes", value=1),
        ],
        announce=[
            app_commands.Choice(name="Yes", value=1),
        ]
    )
    @app_commands.describe(
        map_name="The map to cancel the next practice for",
        all_practices="Cancel all events for the specified map",
        announce="Announce the cancellation when used in the premier channel"
    )
    async def cancelpractice(self, interaction: discord.Interaction, map_name: str,
                             all_practices: int = 0, announce: int = 0) -> None:
        """[app command] Cancels the next premier practice event (or all practices on a map)

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        map_name : str
            The map to cancel the next practice for
        all_practices : int, optional
            Treated as a boolean. Cancel all practices for the specified map, by default 0
        announce : int, optional
            Treated as a boolean. Announce the cancellation when used in the premier channel, by default 0
        """
        map_display_name = global_utils.style_text(map_name.title(), 'i')

        if map_name not in global_utils.map_pool:
            hint = f"Ensure that {global_utils.style_text('/map-pool', 'c')} is updated."
            await interaction.response.send_message(f"{map_display_name} is not in the map pool. {hint}",
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        ephem = interaction.channel.id != global_utils.prem_channel_id or not announce
        await interaction.response.defer(ephemeral=ephem, thinking=True)

        guild = interaction.guild
        events = guild.scheduled_events

        message = f"No practices found for {map_display_name} in the schedule."

        for event in events:
            if event.name == "Premier Practice" and event.description.lower() == map_name:
                if event.status == discord.EventStatus.scheduled:
                    await event.cancel()
                elif event.status == discord.EventStatus.active:
                    await event.end()
                else:
                    await event.delete()

                if not all_practices:
                    e_name = event.name
                    e_date = event.start_time.date()
                    message = f'{e_name} on {map_display_name} for {e_date} has been cancelled'
                    break
                else:
                    message = f'All practices on {map_display_name} have been cancelled'

        if message != f"No practices found for {map_display_name} in the schedule.":
            global_utils.log(
                f'{interaction.user.display_name} cancelled practice: {message}')

        m = await interaction.followup.send(message, ephemeral=ephem)
        await m.delete(delay=global_utils.delete_after_seconds)

        global_utils.log(
            f"{interaction.user.display_name} cancelled practice(s) - {message}")

    @app_commands.command(name="clear-schedule", description=global_utils.commands["clear-schedule"]["description"])
    @app_commands.choices(
        confirm=[
            app_commands.Choice(
                name="I acknowledge all events with 'Premier' in the name will be deleted.", value="confirm"),
        ],
        announce=[
            app_commands.Choice(name="Yes", value=1),
        ]
    )
    @app_commands.describe(
        confirm='Confirm clear. Note: This will clear all events with "Premier" in the name.',
        announce="Announce that the schedule has been cleared when used in the premier channel"
    )
    async def clearschedule(self, interaction: discord.Interaction, confirm: str, announce: int = 0) -> None:  # pylint: disable=unused-argument
        """[app command] Clears the premier schedule (by deleting all events with "Premier" in the name)

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        confirm : str
            Confirms the schedule clear 
            (Discord automatically checks this since it is a required argument)
        announce : int, optional
            Treated as a boolean. Announce the schedule clear when used in the premier channel, by default 0
        """
        # confirm is automatically chcecked by discord, so we just need to ensure it is a required argument to "confirm"

        ephem = interaction.channel.id != global_utils.prem_channel_id or not announce

        await interaction.response.defer(ephemeral=ephem, thinking=True)

        guild = interaction.guild
        events = guild.scheduled_events

        for event in events:
            if "Premier" in event.name:
                if event.status == discord.EventStatus.scheduled:
                    await event.cancel()
                elif event.status == discord.EventStatus.active:
                    await event.end()
                else:
                    await event.delete()

        global_utils.log(
            f'{interaction.user.display_name} has cleared the premier schedule')

        await interaction.followup.send('Cleared the premier schedule', ephemeral=ephem)
        # don't delete the message. This command can take a while and the user may miss the notification

    @app_commands.command(name="add-note", description=global_utils.commands["add-note"]["description"])
    @app_commands.choices(
        map_name=[
            app_commands.Choice(name=s.title(), value=s) for s in global_utils.map_preferences.keys()
        ]
    )
    @app_commands.describe(
        map_name="The map to add a note for",
        note_id="The message ID of the note to add a reference to",
        description="Provide a short description of the note. Used to identify the note when using /notes"
    )
    async def addnote(self, interaction: discord.Interaction, map_name: str, note_id: str, description: str) -> None:
        """[app command] Creates a symbolic link/reference to a practice note for the specified map 
        (this does not store the note itself, only the reference to it)
        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        map_name : str
            The map to add a note for
        note_id : str
            The message ID of the note to add a reference to
        description : str
            The description of the note. Used to easily identify this note when using /notes
        """
        note_id = int(note_id)
        try:
            message = interaction.channel.get_partial_message(note_id)
        except (discord.HTTPException, discord.errors.NotFound):
            await interaction.response.send_message('Message not found',
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        if message.channel.id != global_utils.notes_channel_id:
            await interaction.response.send_message('Invalid message ID. The message must be in the notes channel.',
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        if map_name not in global_utils.practice_notes:
            global_utils.practice_notes[map_name] = {}

        global_utils.practice_notes[map_name][note_id] = description

        global_utils.save_notes()

        global_utils.log(
            f'{interaction.user.display_name} has added a practice note. Note ID: {note_id}')

        display_map_name = global_utils.style_text(map_name.title(), 'i')
        access_command = global_utils.style_text(
            f'/notes {map_name.title()}', 'c')

        await interaction.response.send_message(f'Note added for {display_map_name}. Access using {access_command}',
                                                ephemeral=True, delete_after=global_utils.delete_after_seconds)

    @app_commands.command(name="remove-note", description=global_utils.commands["remove-note"]["description"])
    @app_commands.choices(
        map_name=[
            app_commands.Choice(name=s.title(), value=s) for s in global_utils.map_preferences.keys()
        ]
    )
    @app_commands.describe(
        map_name="The map to remove the note reference from",
        note_number="The note number to remove (1-indexed). Leave empty to see options."
    )
    async def removenote(self, interaction: discord.Interaction, map_name: str, note_number: int = 0) -> None:
        """[app command] Removes a practice note reference for the specified map
        (this does not remove the original message)

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        map_name : str
            The map to remove the note reference from
        note_number : int, optional
            The note number to remove (1-indexed). Leave empty/0 to see options, by default 0
        """
        map_display_name = global_utils.style_text(map_name.title(), 'i')

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
            output = global_utils.style_text("Practice notes for ", 'b')
            output += global_utils.style_text(map_display_name, 'b') + ":\n"
            for i, note_id in enumerate(notes_list.keys()):
                note_number = f"Note {i+1}"
                note_number = global_utils.style_text(note_number, 'b')

                output += f"- {note_number}: {global_utils.style_text(notes_list[note_id], 'i')}\n"

            await interaction.response.send_message(output,
                                                    ephemeral=True, delete_after=global_utils.delete_after_seconds)
            return

        note_id = list(global_utils.practice_notes[map_name].keys())[
            note_number - 1]
        global_utils.practice_notes[map_name].pop(note_id)

        await interaction.response.send_message(f"Removed a practice note for {map_display_name}",
                                                ephemeral=True, delete_after=global_utils.delete_after_seconds)

        global_utils.save_notes()
        global_utils.log(
            f'{interaction.user.display_name} has removed a practice note. Note ID: {note_id}')


class MapPoolPanel(discord.ui.View):
    """[view] An admin panel (View) for managing the global map pool

    Parameters
    ----------
    timeout : float | None, optional
        The timeout for the panel, by default None
    sync_changes : callable
        The function to call to sync the changes made in the panel to discord
        This updates things like app_command choices.
    """
    # pylint: disable=unused-argument

    def __init__(self, *, timeout: float | None = None, sync_changes: callable) -> None:
        super().__init__(timeout=timeout)
        self.sync = sync_changes
        self.pool = global_utils.map_pool
        self.select = self.children[0]

    async def disable(self, interaction: discord.Interaction) -> None:
        """Disables the panel

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object linked to the panel
        """
        for child in self.children:
            child.disabled = True

        await self.resend(interaction)
        self.stop()

    async def resend(self, interaction: discord.Interaction) -> None:
        """Updates the map pool panel display

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object linked to the panel
        """
        self.pool.sort()

        for option in self.select.options:
            option.default = False if option.value not in self.pool else True

        pool_display = "\n- ".join([global_utils.style_text(m.title(), 'i') for m in self.pool])
        embed = discord.Embed(title="Map Pool", description=f"- {pool_display}", color=discord.Color.blurple())

        await interaction.response.edit_message(content="Map Pool", embed=embed, view=self)

    @discord.ui.select(custom_id="map_pool", placeholder="Maps", row=0,
                       min_values=1, max_values=len(global_utils.map_preferences),
                       options=[
                           discord.SelectOption(label=m.title(), value=m, default=m in global_utils.map_pool)
                           for m in global_utils.map_preferences
                       ])
    async def map_list(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
        """[select] Updates the map pool copy based on the selected maps

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        select : discord.ui.Select
            The select object that was interacted with
        """
        self.pool = self.select.values
        await self.resend(interaction)

    @discord.ui.button(custom_id="apply_changes", label="Apply Changes", row=1,
                       style=discord.ButtonStyle.success, emoji="✅")
    async def apply_changes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """[button] Applies the changes from the map pool copy to the global map pool

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        button : discord.ui.Button
            The button that was clicked
        """
        global_utils.map_pool = self.pool
        global_utils.save_pool()
        await self.disable(interaction)
        await self.sync(interaction)

    @discord.ui.button(custom_id="clear_map_pool", label="Clear", row=1,
                       style=discord.ButtonStyle.danger, emoji="🗑️")
    async def clear_map(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """[button] Clears the map pool copy

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        button : discord.ui.Button
            The button that was clicked
        """
        self.pool.clear()
        await self.resend(interaction)


async def setup(bot: commands.bot) -> None:
    """Adds the AdminPremierCommands and AdminMessageCommands cogs to the bot

    Parameters
    ----------
    bot : discord.ext.commands.Bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """
    guilds = [Object(global_utils.val_server_id), Object(global_utils.debug_server_id)]
    await bot.add_cog(AdminPremierCommands(bot), guilds=guilds)
