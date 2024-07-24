"""[cog] A cog that creates/stores the predefined trivia questions
"""
from asyncio import sleep, TimeoutError as AsyncTimeoutError
from random import sample, randint

import discord
from discord import app_commands
from discord.ext import commands

from global_utils import global_utils


class TriviaCommands(commands.Cog):
    """[cog] A cog that creates/stores some predefined trivia questions

        Parameters
        ----------
        bot : discord.ext.commands.Bot
            The bot to add the cog to. Automatically passed with the bot.load_extension method
        """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        self.trivia_questions = self.get_questions()

    def get_questions(self) -> dict:
        """Sets up the trivia questions for the trivia game

        Returns
        -------
        dict
            a dictionary grouped by easy/medium/hard with the following structure:

            {difficulty: [{question: answer}, ...]}
        """
        questions = {
            "easy": [
                {
                    "question": "How many agents are currently (05/25/24) in Valorant? (hint: some are hidden)",
                    "answer": "25"
                },
                {
                    "question": "How many multiplayer maps are currently (05/25/24) in Valorant?",
                    "answer": "14"
                },
                {
                    "question": 'What nationality is the agent "Gekko"?',
                    "answer": "American"
                },
                {
                    "question": 'What agent has the ability "Curveball"?',
                    "answer": "Phoenix"
                },
                {
                    "question": "What is Bizzy's cat's name?",
                    "answer": "Luna"
                },
            ],
            "medium": [
                {
                    "question": 'What is the internal codename for the agent "Killjoy"?',
                    "answer": "Killjoy"
                },
                {
                    "question": 'What is the internal codename for Raze\'s ability "Paint Shells"?',
                    "answer": "Default__Clay_4_ClusterGrenade_Gungame_DataAsset_C"
                },
                {
                    "question": "What is the internal codename for the tutorial?",
                    "answer": "Onboarding"
                },
                {
                    "question": "How many ceremonies are there in Valorant?",
                    "answer": "6"
                },
            ],
            "hard": [
                {
                    "question": ("What is Bizzy's favorite 2D effect, notably implemented in his Flappy Bird clone?"
                                 "(hint: It gets Bizzy very excited and is related to background elements)"),
                    "answer": "Parallax"
                },
                {
                    "question": "What month and year did Bizzy first meet Sam, Fiona, and Dylan (in mm/yyyy format)?",
                    "answer": "02/2023"
                },
                {
                    "question": 'What map started "The Adventures of Sam and Bizzy"?',
                    "answer": "Ascent"
                },
                {
                    "question": "What is the food known to give Bizzy a buff?",
                    "answer": "chicken alfredo"
                },
                {
                    "question": "How many non-multiplayer maps are there in Valorant (hint: some are hidden)?",
                    "answer": "2"
                },
            ]
        }

        return questions

    async def delayed_gratification(self, user: discord.User) -> None:
        """Sends the prize message to the user after 5 minutes 
        while taunting them with messages every minute until then

        Parameters
        ----------
        user : discord.User
            The user who has completed the trivia game
        """
        pat = fr"\*{global_utils.style_text('gives you a pat on the back', 'i')}\*"
        await user.send(f"Congratulations, you win! Here is your prize: {pat}", delete_after=60)

        taunts = [
            "Are you mad at me? Good.",
            "You went through all of that just for a pat on the back. How does that make you feel?",
            "You know, I kind of feel bad for you. Just kidding, I don't.",
            ("Actually, now I do kind of feel bad for you. I apologize for my rudeness."
             "Give me a minute to think about what I've done and I'll make it up to you.")
        ]

        for taunt in taunts:
            await sleep(60)
            await user.send(taunt, delete_after=60)

        await user.send(("Alright, I've thought long and hard (giggity) about my actions and I've decided to "
                         f"give you an actual prize. Here it is: {pat}. Congratulations!"), delete_after=5)

        await sleep(5)
        await user.send((f"Just kidding. Here is your actual prize, no foolin': "
                         f"{global_utils.style_text('https://cs.indstate.edu/~cs60901/final/', 'c')}"))

    async def trivia(self, user: discord.User) -> None:
        """Plays a game of trivia with the user in their DMs

        Parameters
        ----------
        user : discord.User
            The user to play trivia with
        """
        await user.send(("Welcome to trivia!"
                         f"You will have {global_utils.style_text('10 seconds', 'c')} to answer each question.\n\n"
                         "Since I'm nice, I'll let you know that almost every answer can be found in the server",
                         "(or with a simple Google search). Good luck!"
                         ), delete_after=10)

        await sleep(10)  # give the user time to read the message

        questions = self.trivia_questions["easy"] + \
            self.trivia_questions["medium"] + self.trivia_questions["hard"]

        if randint(1, 4) == 3:  # The prize for trivia is my name. 25% chance to troll the user by asking them my name
            questions.append({
                "question": "What is Bizzy's name?",
                "answer": "Isaiah"
            })

        questions = sample(questions, len(questions))  # shuffle the questions

        for i, question in enumerate(questions):
            question_header = global_utils.style_text(
                f"Question {i + 1}:\n", 'b')
            question_body = global_utils.style_text(
                questions[i]['question'], 'i')
            q = await user.send(f"{question_header}{question_body}")

            trivia_command = global_utils.style_text('/trivia', 'c')

            go_back = (f"Go back to the server and use {trivia_command} to try again"
                       "(yes this is intentionally tedious).")

            try:
                answer = await self.bot.wait_for("message", check=lambda m: m.author == user, timeout=10)
            except AsyncTimeoutError:
                await q.delete()

                await user.send(f"You took too long to answer. {go_back}", delete_after=5)
                return

            await q.delete()

            if answer.content.lower() == question['answer'].lower():
                await user.send("Correct!", delete_after=2)
                await sleep(2)
            else:
                if question["question"] == "What is Bizzy's name?":
                    await user.send(f"Lol, nt gamer. {go_back}", delete_after=global_utils.delete_after_seconds)
                else:
                    await user.send(f"Incorrect. {go_back}", delete_after=global_utils.delete_after_seconds)

                return

        await self.delayed_gratification(user)

    @app_commands.command(name="trivia", description=global_utils.commands["trivia"]["description"])
    async def trivia_help(self, interaction: discord.Interaction) -> None:
        """[app command] Starts a game of trivia with the user in their DMs

        Parameters
        ----------
        interaction : discord.Interaction
            The interaction object that initiated the command
        """
        user = interaction.user
        await interaction.response.send_message(("Please open the DM with the bot to play trivia."
                                                "It may take a some time to start."),
                                                ephemeral=True, delete_after=global_utils.delete_after_seconds)
        # give the user time to read the message and move to the DMs
        await sleep(global_utils.delete_after_seconds)
        await self.trivia(user)


async def setup(bot: commands.bot) -> None:
    """Adds the TriviaCommands cog to the bot

    Parameters
    ----------
    bot : discord.ext.commands.bot
        The bot to add the cog to. Automatically passed with the bot.load_extension method
    """
    guilds = [discord.Object(global_utils.val_server_id), discord.Object(global_utils.debug_server_id)]
    await bot.add_cog(TriviaCommands(bot), guilds=guilds)
