import datetime
import discord
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from pymongo import MongoClient
from db import modlog_collection

load_dotenv()


class ModLog(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.webhook_cache = {}

	async def send_modlog(self, guild_id, action_taker: discord.User, action, message):
		guild = self.bot.get_guild(guild_id)
		if not guild:
			print(f"Guild not found for ID: {guild_id}")
			return
		mod_logs = await modlog_collection.find_one({"guild_id": str(guild.id)})
		if mod_logs:
			log_channel = discord.utils.get(guild.channels, id=int(mod_logs["channel_id"]))
			if not log_channel:
				print(f"Log channel not found for ID: {mod_logs['channel_id']}")
				return
			embed = discord.Embed(
				title=f"{action}",
				description=f"<:modshield:1325613380945444864> {message}",
			)
			taker = self.bot.get_user(action_taker)
			if not taker:
				taker = await guild.fetch_user(action_taker)
			embed.add_field(
				name="Issued by", value=(taker.mention if taker else "None found")
			)
			embed.add_field(
				name="Issued at",
				value=discord.utils.format_dt(discord.utils.utcnow(), "F"),
			)
			if guild.icon:
				embed.set_thumbnail(url=guild.icon.url)
			embed.set_footer(text="Moderation Log")
			webhook = self.webhook_cache.get(log_channel.id)
			if webhook is None:
				try: webhooks = await log_channel.webhooks()
				except discord.Forbidden:
					webhooks = []
				webhook = discord.utils.get(
					[wh for wh in webhooks if wh.user.id == self.bot.user.id],
					name="Spectra Moderation Logs"
				)
				if webhook:
					self.webhook_cache[log_channel.id] = webhook
			bot_member = guild.me
			if bot_member is None:
				try:
					bot_member = await guild.fetch_member(self.bot.user.id)
				except discord.NotFound:
					bot_member = None
			if webhook is None and bot_member:
				perms = log_channel.permissions_for(bot_member)
				if perms.manage_webhooks:
					webhook = await log_channel.create_webhook(name="Spectra Moderation Logs")
			try:
				if webhook: await webhook.send(embed=embed, username="Spectra", avatar_url=self.bot.user.display_avatar.url)
				else:
					embed.add_field(name="Notice", value="Please give me `Manage Webhooks` permissions for modlogs.", inline=False)
					await log_channel.send(embed=embed)
			except discord.Forbidden:
				embed.add_field(name="Notice", value="Please give me `Manage Webhooks` permissions for modlogs.", inline=False)
				await log_channel.send(embed=embed)
		else:
			return


	@commands.Cog.listener()
	async def on_modlog(self, guild_id, action_taker, action, message):
		await self.send_modlog(guild_id, action_taker, action, message)

	@commands.hybrid_group(name="modlogs")
	async def modlogs(self, ctx):
		pass

	@modlogs.command(
		name="setup", description="Enable moderation logs related to Spectra"
	)
	@app_commands.default_permissions(manage_guild=True)
	@app_commands.describe(channel="The channel to send logs to")
	async def setup(self, ctx: commands.Context, channel: discord.TextChannel):
		guild_id = str(ctx.guild.id)
		if await modlog_collection.find_one({"guild_id": guild_id}):
			await ctx.send("Moderation logs are already enabled.", ephemeral=True)
			return
		try:
			try:
				await channel.send(".", delete_after=1)
			except:
				await ctx.send(
					"Failed to send a test message in the specified channel. Please ensure I have the correct permissions talk there.",
					ephemeral=True,
				)
				return
			await modlog_collection.insert_one(
				{"guild_id": guild_id, "channel_id": channel.id}
			)
			await ctx.send(
				f"<:switch_on:1326648555414224977> Moderation logs have been enabled and sent to <#{channel.id}>.",
				ephemeral=True,
			)
			embed = discord.Embed(
				title="Moderation Logs",
				description="Moderation logs have been enabled and set here.",
			)
			embed.add_field(name="Set by", value=ctx.author.mention)
			try:
				embed.set_thumbnail(url=ctx.guild.icon.url)
			except:
				pass
			await channel.send(embed=embed)
		except Exception as e:
			print(f"Error setting up mod log: {e}")
			await ctx.send(
				"An error occurred while setting up moderation logs.", ephemeral=True
			)

	@modlogs.command(
		name="disable", description="Disable moderation logs related to Spectra"
	)
	@app_commands.default_permissions(manage_guild=True)
	async def disable(self, ctx: commands.Context):
		guild_id = str(ctx.guild.id)
		if not await modlog_collection.find_one({"guild_id": guild_id}):
			await ctx.send("Moderation logs are already disabled.", ephemeral=True)
			return
		try:
			modlogs = await modlog_collection.find_one({"guild_id": guild_id})
			channel = discord.utils.get(ctx.guild.channels, id=modlogs["channel_id"])
			embed = discord.Embed(
				title="Moderation Logs",
				description=f"Moderation logs have been disabled by {ctx.author.mention}.",
			)
			try: await channel.send(embed=embed)
			except: pass
			await modlog_collection.delete_one({"guild_id": guild_id})
			await ctx.send(
				f"<:switch_off:1326648782393180282> Moderation logs have been disabled.",
				ephemeral=True,
			)
		except Exception as e:
			print(f"Error setting up mod log: {e}")
			await ctx.send(
				"An error occurred while disabling moderation logs.", ephemeral=True
			)


async def setup(bot):
	await bot.add_cog(ModLog(bot))
