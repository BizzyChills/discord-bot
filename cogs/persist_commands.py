"""A cog that handles sending the persistent buttons for the bot
and processing the commands that are sent through them
"""
from datetime import datetime
import asqlite

import discord
from discord import app_commands
from discord.ext import commands


from global_utils import global_utils


class PersistCommands(commands.Cog):
    """A cog that handles sending the persistent buttons for the bot
    and processing the commands that are sent through them

        Parameters
        ----------
        bot : discord.ext.commands.Bot
            The bot to add the cog to. Automatically passed with the bot.load_extension method
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """[event] Executes when the BotCog cog is ready
        """
        # global_utils.log("Bot cog loaded")

    @app_commands.command(name="persist", description=global_utils.commands["persist"]["description"])
    async def persist(self, interaction: discord.Interaction) -> None:
        """[app command] Sends the persistent buttons view

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        """
        view = PersistentView()
        await interaction.response.send_message(global_utils.style_text("HELP:", 'b'), view=view)


class PersistentView(discord.ui.View):
    """A view that handles the persistent buttons for the bot
    """
    # pylint: disable=unused-argument

    def __init__(self, *_) -> None:
        super().__init__(timeout=None)

        emojis = global_utils.commands
        emojis = {k: emojis[k]["emoji"] for k in emojis}

        desc_hint = "(start typing the command to see its description)"
        self.commands_header = f"{global_utils.style_text('Commands', 'b')} {desc_hint}:"

        self.basic_commands = [f"- {global_utils.style_text('INFO', 'b')}:",
                               f" - {emojis['map-weights']} {global_utils.mention_slash('map-weights')}",
                               f" - {emojis['map-votes']} {global_utils.mention_slash('map-votes')}",
                               f" - {emojis['notes']} {global_utils.mention_slash('notes')}",]

        self.admin_commands = [f"- {global_utils.style_text('ADMIN ONLY', 'b')}:",
                               f" - {emojis['map-pool']} {global_utils.mention_slash('map-pool')}",
                               f" - {emojis['add-map']} {global_utils.mention_slash('add-map')}",
                               f" - {emojis['remove-map']} {global_utils.mention_slash('remove-map')}",
                               f" - {emojis['add-events']} {global_utils.mention_slash('add-events')}",
                               f" - {emojis['cancel-event']} {global_utils.mention_slash('cancel-event')}",
                               f" - {emojis['add-practices']} {global_utils.mention_slash('add-practices')}",
                               f" - {emojis['cancel-practice']} {global_utils.mention_slash('cancel-practice')}",
                               f" - {emojis['clear-schedule']} {global_utils.mention_slash('clear-schedule')}",
                               f" - {emojis['add-note']} {global_utils.mention_slash('add-note')}",
                               f" - {emojis['remove-note']} {global_utils.mention_slash('remove-note')}",
                               f" - {emojis['remind']} {global_utils.mention_slash('remind')}",
                               f" - {emojis['pin']} {global_utils.mention_slash('pin')}",
                               f" - {emojis['unpin']} {global_utils.mention_slash('unpin')}",
                               f" - {emojis['delete-message']} {global_utils.mention_slash('delete-message')}",
                               (f" - {emojis['kill']} {global_utils.mention_slash('kill')} or " +
                                f"{global_utils.style_text('!kill', 'c')}"),]

        self.bizzy_commands = [f"- {global_utils.style_text('BIZZY ONLY', 'b')}:",
                               f" - {emojis['persist']} {global_utils.mention_slash('persist')}",
                               (f" - {emojis['reload']} {global_utils.mention_slash('reload')} or " +
                                f" {global_utils.style_text('!reload', 'c')}"),
                               f" - {emojis['feature']} {global_utils.mention_slash('feature')}",]

        self.misc_commands = [f"- {global_utils.style_text('MISC', 'b')}:",
                              f" - {emojis['hello']} {global_utils.mention_slash('hello')}",
                              f" - {emojis['trivia']} {global_utils.mention_slash('trivia')}",
                              f" - {emojis['emojis']} {global_utils.mention_slash('emojis')}",]

        self.output_message = None

    async def remove_old_output(self) -> None:
        """Removes the old output message
        """
        if self.output_message is not None:
            try:
                await self.output_message.delete()
            except discord.NotFound:
                pass

    @discord.ui.select(placeholder=f"{global_utils.commands['commands']['emoji']} Commands List",
                       custom_id="commands_list_type", min_values=0,
                       options=[discord.SelectOption(label="Minimum commands", value="basic", emoji="💾"),
                                discord.SelectOption(label="User commands", value="user", emoji="💿"),
                                discord.SelectOption(label="Admin commands", value="admin", emoji="📀"),
                                discord.SelectOption(label="Minimum + Admin", value="basic_admin", emoji="💽"),
                                discord.SelectOption(label="User + Admin", value="user_admin", emoji="👥"),
                                discord.SelectOption(label="All commands", value="all", emoji="🌎")], )
    async def commands_list_select(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
        """[select] Sends the selected list of commands

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object from the select menu
        select : discord.ui.Select
            The select menu object that was used
        """
        await self.remove_old_output()

        if len(select.values) == 0:
            await interaction.response.defer()
            return

        list_type = select.values[0]

        await interaction.response.defer(ephemeral=True, thinking=True)

        user_commands = self.basic_commands + self.misc_commands
        basic_admin_commands = self.basic_commands + self.admin_commands
        user_admin_commands = user_commands + self.admin_commands
        all_commands = user_admin_commands + self.bizzy_commands

        match list_type:
            case "basic":
                output = self.basic_commands
            case "user":
                output = user_commands
            case "basic_admin":
                output = basic_admin_commands
            case "admin":
                output = self.admin_commands
                if interaction.user.id == global_utils.my_id:
                    output += self.bizzy_commands
            case "user_admin":
                output = user_admin_commands
            case _:
                output = all_commands

        embed = discord.Embed(title=self.commands_header, description='\n'.join(
            output), color=discord.Color.blurple())

        self.output_message = await interaction.followup.send(embed=embed, ephemeral=True, silent=True)

    @discord.ui.button(custom_id="schedule_button", label="Schedule", row=1,
                       style=discord.ButtonStyle.primary,  emoji=global_utils.commands['schedule']['emoji'])
    async def schedule_button(self, interaction: discord.Object, button: discord.ui.Button) -> None:
        """[button] Sends the premier schedule for the current server

        Parameters
        ----------
        interaction : discord.Object
            The interaction object from the button click
        button : discord.ui.Button
            The button object that was clicked
        """
        await self.remove_old_output()

        await interaction.response.defer(ephemeral=True, thinking=True)

        guild = interaction.guild
        events = guild.scheduled_events

        event_header = f"{global_utils.style_text('Upcoming Premier Events:', 'b')}"
        practice_header = f"\n\n{global_utils.style_text('Upcoming Premier Practices:', 'b')}"
        event_message = []
        practice_message = []

        for event in events:
            map_name = event.description

            if "premier practice" in event.name.lower():
                practice_message.append(
                    f"{global_utils.discord_local_time(event.start_time, with_date=True)}", event.start_time, map_name)
            elif "premier" in event.name.lower():
                event_message.append(
                    f"{global_utils.discord_local_time(event.start_time, with_date=True)}", event.start_time, map_name)

        if not event_message:
            event_message = f"{global_utils.style_text('No premier events scheduled', 'b')}"
        else:
            event_message = self.format_schedule(event_message, event_header)

        if not practice_message:
            practice_message = f"\n\n{global_utils.style_text('No premier practices scheduled', 'b')}"
        else:
            practice_message = self.format_schedule(
                practice_message, practice_header)

        message = event_message + practice_message

        header = f"{global_utils.style_text('Premier Schedule:', 'b')}"

        embed = discord.Embed(
            title=header, description=message, color=discord.Color.blurple())

        self.output_message = await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(custom_id="map_pool_button", label="Map Pool", row=1,
                       style=discord.ButtonStyle.primary, emoji=global_utils.commands['map-pool']['emoji'])
    async def map_pool_button(self, interaction: discord.Object, button: discord.ui.Button) -> None:
        """[button] Sends the current map pool for the server

        Parameters
        ----------
        interaction : discord.Object
            The interaction object from the button click
        button : discord.ui.Button
            The button object that was clicked
        """
        await self.remove_old_output()

        await interaction.response.defer(ephemeral=True, thinking=True)

        map_list = '\n- '.join([global_utils.style_text(
            m.title(), 'i') for m in global_utils.map_pool])
        embed = discord.Embed(
            title="Map Pool", description=f"- {map_list}", color=discord.Color.blurple())
        self.output_message = await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(custom_id="map_weights_button", label="Map Weights", row=2,
                       style=discord.ButtonStyle.primary,  emoji=global_utils.commands['map-weights']['emoji'])
    async def map_weights_button(self, interaction: discord.Object, button: discord.ui.Button) -> None:
        """[button] Sends the current map weights for the server

        Parameters
        ----------
        interaction : discord.Object
            The interaction object from the button click
        button : discord.ui.Button
            The button object that was clicked
        """
        await self.remove_old_output()

        await interaction.response.defer(ephemeral=True, thinking=True)

        output = ""

        # don't just iterate over the map pool, the weights are sorted by weight and pool is not.
        for map_name in [m for m in global_utils.map_weights if m in global_utils.map_pool]:
            map_display_name = global_utils.style_text(map_name.title(), 'i')
            weight = global_utils.style_text(
                global_utils.map_weights[map_name], 'b')

            output += f'- {map_display_name}: {weight}\n'

        if output == "":
            output = "No weights to show for maps in the map pool."

        embed = discord.Embed(
            title="Map Weights", description=output, color=discord.Color.blurple())

        self.output_message = await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(custom_id="vote_map_button", label="Map Voting", row=2,
                       style=discord.ButtonStyle.primary, emoji=global_utils.commands['map-votes']['emoji'])
    async def vote_map_button(self, interaction: discord.Object, button: discord.ui.Button) -> None:
        """[button] Allows the user to mark their map preferences

        Parameters
        ----------
        interaction : discord.Object
            The interaction object from the button click
        button : discord.ui.Button
            The button object that was clicked
        """
        await self.remove_old_output()

        await interaction.response.defer(thinking=True, ephemeral=True)
        view = VotingButtons(
            timeout=None, interaction=interaction)
        await view.respond()

        self.output_message = None

    def format_schedule(self, schedule: list[tuple[str, datetime, str]], header: str = None) -> str:
        """Formats the schedule for display in Discord

        Parameters
        ----------
        schedule : list[tuple[str, datetime, str]]
            The schedule to format. This should be a list of tuples with the following structure: 

            [(event_display_string, event_datetime, event_map), ...]
        header : str, optional
            The header to display at the top of the schedule, by default None

        Returns
        -------
        str
            The formatted schedule as a string to display in Discord
        """
        schedule = sorted(schedule, key=lambda x: x[1])

        subsections = {entry[2]: [] for entry in schedule}

        for m in schedule:
            map_name = m[2]
            event_display = m[0]  # just use variables for readability

            subsections[map_name].append(event_display)

        output = ""
        for map_name, event_displays in subsections.items():
            subheader = f"- {global_utils.style_text(map_name, 'iu')}:"
            event_displays = " - " + '\n - '.join(event_displays)

            output += f"{subheader}\n{event_displays}\n"

        return f"{header}\n{output}" if header else output


class VotingButtons(discord.ui.View):
    """A view that handles the map voting process

    Parameters
    ----------
    timeout : float | None, optional
        The number of seconds to listen for an interaction before timing out, by default None (no timeout)
    interaction : discord.Interaction
        The interaction object from the command generating this view
    """
    # pylint: disable=unused-argument

    def __init__(self, *, timeout: float | None = None, interaction: discord.Interaction) -> None:
        super().__init__(timeout=timeout)

        self.question_interaction = interaction
        self.user_id = interaction.user.id

        self.maps_left = global_utils.map_pool.copy()

        self.emojis = {1: "👍", 0: "✊", -1: "👎", -2: "❔"}

        self.started = False

    async def exit(self) -> None:
        """Disables the view and sends the exit message
        """
        self.stop()
        for button in self.children:
            button.disabled = True

        embed = discord.Embed(
            title="Map Voting", description="Preferences saved. Thank you!", color=discord.Color.blurple())

        if not self.started:
            await self.question_interaction.followup.send(embed=embed, view=self, ephemeral=True)
        else:
            await self.question_interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Like", row=0,
                       style=discord.ButtonStyle.success, emoji="👍")
    async def like(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """[button] Saves the user's preference for the current map as a like

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object from the button click
        button : discord.ui.Button
            The button object that was clicked
        """
        await interaction.response.defer()
        await self.save_preference(1)
        await self.respond()

    @discord.ui.button(label="Neutral", row=0,
                       style=discord.ButtonStyle.secondary, emoji="🤷‍♀️")
    async def neutral(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """[button] Saves the user's preference for the current map as neutral

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object from the button click
        button : discord.ui.Button
            The button object that was clicked
        """
        await interaction.response.defer()
        await self.save_preference(0)
        await self.respond()

    @discord.ui.button(label="Dislike", row=0,
                       style=discord.ButtonStyle.danger, emoji="👎")
    async def dislike(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """[button] Saves the user's preference for the current map as a dislike

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object from the button click
        button : discord.ui.Button
            The button object that was clicked
        """
        await interaction.response.defer()
        await self.save_preference(-1)
        await self.respond()

    @discord.ui.button(label="Skip", row=1,
                       style=discord.ButtonStyle.secondary, emoji="⏭")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """[button] Skips the current map and moves to the next one

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object from the button click
        button : discord.ui.Button
            The button object that was clicked
        """
        await interaction.response.defer()
        self.maps_left.pop(0)
        await self.respond()

    @discord.ui.button(label="Exit", row=1,
                       style=discord.ButtonStyle.danger, emoji="✖")
    async def exit_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """[button] Exits the map voting process without saving any more preferences

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object from the button click
        button : discord.ui.Button
            The button object that was clicked
        """
        await interaction.response.defer()
        await self.exit()

    async def save_preference(self, preference: int) -> None:
        """Saves the user's preference for the current map from self.map_names

        Parameters
        ----------
        preference : int
        """
        map_name = self.maps_left.pop(0)
        user_id = self.question_interaction.user.id
        if global_utils.map_preferences[map_name].get(user_id, -2) == preference:
            return

        global_utils.map_preferences[map_name][user_id] = preference
        global_utils.map_weights[map_name] += preference

        async with asqlite.connect("./local_storage/maps.db") as conn:
            async with conn.cursor() as cur:
                await cur.execute("Start TRANSACTION")
                await cur.execute("""
                    INSERT INTO map_preferences (user_id, map_name)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET map_name = ?
                """, (user_id, preference, preference))

                await cur.execute("UPDATE info SET weight = ? WHERE map_name = ?",
                                  (global_utils.map_weights[map_name], map_name))
            await conn.commit()

    async def respond(self) -> None:
        """Responds to the user after they click a button by either asking the next question or disabling the buttons
        """
        if len(self.maps_left) <= 0:
            return await self.exit()

        map_name = self.maps_left[0]
        map_display_name = global_utils.style_text(map_name.title(), 'i')
        map_url = global_utils.map_image_urls.get(map_name, None)

        user_weight = global_utils.map_preferences[map_name].get(
            self.user_id, -2)
        user_preference = self.emojis[user_weight]

        embed = discord.Embed(
            title="Map Voting", description=f"What do you think of {map_display_name}?", color=discord.Color.blurple())
        if map_url:
            embed.set_image(url=map_url)
        (
            embed.add_field(name="Map's Current Weight",
                            value=global_utils.map_weights[map_name])
            .add_field(name="Your Current Preference", value=user_preference)
        )

        if not self.started:
            await self.question_interaction.followup.send(embed=embed, view=self, ephemeral=True)
            self.started = True
        else:
            await self.question_interaction.edit_original_response(embed=embed, view=self)


async def setup(bot: commands.bot) -> None:
    """Adds the BotCog cog to the bot

    Parameters
    ----------
    bot : discord.ext.commands.bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """
    guilds = [discord.Object(global_utils.val_server_id), discord.Object(global_utils.debug_server_id)]
    await bot.add_cog(PersistCommands(bot), guilds=guilds)
