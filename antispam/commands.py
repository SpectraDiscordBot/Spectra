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
antispam_collection = db['AntiSpam']

class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="spam-enable", description="Enable spam detection.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(channel='The channel to send logs to')
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def enable(self, ctx, channel: discord.TextChannel = None):
        if antispam_collection.find_one({'guild_id': ctx.guild.id}):
            await ctx.send("Spam detection is already enabled.", ephemeral=True)
            return
        try:
            if channel is None:
                antispam_collection.insert_one({'guild_id': ctx.guild.id}, {'$set': {'enabled': True}})
            if channel is not None:
                antispam_collection.insert_one({'guild_id': ctx.guild.id, 'channel_id': channel.id}, {'$set': {'enabled': True}})
            self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Enabled Anti-Spam", f"Enabled the Anti-Spam system.")
            await ctx.send("<:switch_on:1326648555414224977> Enabled spam detection.", ephemeral=True)
        except Exception as e:
            print(e)
            await ctx.send("An error occurred while enabling spam detection. Please try again later.", ephemeral=True)

    @commands.hybrid_command(name="spam-disable", description="Disable spam detection.")
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def disable(self, ctx):
        if not antispam_collection.find_one({'guild_id': ctx.guild.id}):
            await ctx.send("Spam detection is already disabled.", ephemeral=True)
            return
        try:
            antispam_collection.delete_one({'guild_id': ctx.guild.id})
            self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Disabled Anti-Spam", f"Disabled the Anti-Spam system.")
            await ctx.send("<:switch_off:1326648782393180282> Disabled spam detection.", ephemeral=True)
        except Exception as e:
            print(e)
            await ctx.send("An error occurred while disabling spam detection. Please try again later.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AntiSpam(bot))