import datetime
import discord
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ.get('MONGO_URI'))
db = client['Spectra']
modlog_collection = db["ModLogs"]

class ModLog(commands.Cog):

	@commands.hybrid_command(name="setup-modlogs", description="Enable moderation logs related to Spectra")
	@app_commands.default_permissions(manage_guild=True)
	@app_commands.describe(channel="The channel to send logs to")
	async def setup(self, ctx: commands.Context, channel: discord.TextChannel):
		guild_id = str(ctx.guild.id)
		if modlog_collection.find_one({"guild_id": guild_id}):
			await ctx.send("Moderation logs are already enabled.", ephemeral=True)
			return
		try:
			try:
				await channel.send(".", delete_after=1)
			except:
				await ctx.send("Failed to send a test message in the specified channel. Please ensure I have the correct permissions talk there.", ephemeral=True)
				return
			modlog_collection.insert_one({'guild_id': guild_id, 'channel_id': channel.id})
			await ctx.send(f"<:switch_on:1326648555414224977> Moderation logs have been enabled and sent to <#{channel.id}>.", ephemeral=True)
			embed = discord.Embed(title="Moderation Logs", description="Moderation logs have been enabled and set here.", color=discord.Colour.pink())
			embed.add_field(name="Set by", value=ctx.author.mention)
			try:
				embed.set_thumbnail(url=ctx.guild.icon.url)
			except:
				pass
			await channel.send(embed=embed)
		except Exception as e:
			print(f"Error setting up mod log: {e}")
			await ctx.send("An error occurred while setting up moderation logs.", ephemeral=True)

	@commands.hybrid_command(name="disable-modlogs", description="Disable moderation logs related to Spectra")
	@app_commands.default_permissions(manage_guild=True)
	async def disable(self, ctx: commands.Context):
		guild_id = str(ctx.guild.id)
		if not modlog_collection.find_one({"guild_id": guild_id}):
			await ctx.send("Moderation logs are already disabled.", ephemeral=True)
			return
		try:
			modlogs = modlog_collection.find_one({"guild_id": guild_id})
			channel = discord.utils.get(ctx.guild.channels, id=modlogs["channel_id"])
			modlog_collection.delete_one({'guild_id': guild_id})
			embed = discord.Embed(title="Moderation Logs", description="Moderation logs have been disabled.", color=discord.Colour.pink())
			await channel.send(embed=embed)
			await ctx.send(f"<:switch_off:1326648782393180282> Moderation logs have been disabled.", ephemeral=True)
		except Exception as e:
			print(f"Error setting up mod log: {e}")
			await ctx.send("An error occurred while disabling moderation logs.", ephemeral=True)

async def setup(bot):
	await bot.add_cog(ModLog(bot))