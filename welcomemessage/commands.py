import discord
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ.get('MONGO_URI'))
db = client['Spectra']
autorole_collection = db['AutoRole']
welcome_messages_collection = db['WelcomeMessages']

class WelcomeMessageSetupButton(discord.ui.View):
    def __init__(self, *, timeout=120):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Remove Welcome Message", style=discord.ButtonStyle.danger)
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        query = {"guild_id": str(interaction.guild.id)}
        if not welcome_messages_collection.find_one(query):
            return await interaction.response.send_message("Welcome Messaging has not been set.", ephemeral=True)
        else:
            welcome_messages_collection.delete_one(query, comment="Removed Welcome Message")
            await interaction.response.send_message("<:switch_off:1326648782393180282> Welcome Message has been removed.", ephemeral=True)

class WelcomeMessage_Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="welcome-setup", description="Setup the welcome message.")
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @app_commands.describe(message="The message you want to send when someone joins.", channel="The channel you want to send the message to.")
    async def welcome_setup(self, ctx, message: str, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        if welcome_messages_collection.find_one({"guild_id": guild_id}):
            await ctx.send("Welcome Message has already been set.", ephemeral=True)
        else:
            welcome_messages_collection.insert_one({"guild_id": str(guild_id), "message": str(message), "channel": str(channel.id)})
            self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Set the welcome message", f"Added `{message}` as a welcome message in {channel.mention}")
            await ctx.send("<:switch_on:1326648555414224977> Welcome Message has been set.", ephemeral=True)

    @commands.hybrid_command(name="welcome-remove", description="Remove the welcome message.")
    @commands.has_permissions(administrator=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def welcome_remove(self, ctx):
        guild_id = str(ctx.guild.id)
        if welcome_messages_collection.find_one({"guild_id": guild_id}):
            query = {"guild_id": str(ctx.guild.id)}
            if not query:
                return await ctx.send("Welcome Messaging has not been set.", ephemeral=True)
            else:
                welcome_messages_collection.delete_one(query, comment="Removed Welcome Message")
                self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Removed the welcome message", f"Removed welcome message.")
                await ctx.send("<:switch_off:1326648782393180282> Welcome Message has been removed.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(WelcomeMessage_Commands(bot))