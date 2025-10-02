import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from db import bump_reminder_collection
from datetime import datetime, timedelta

class BumpReminder(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.reminder_tasks = {}
		self.cache = {}
		self.disboard_user_id = 302050872383242240
		self.interval_hours = timedelta(hours=2)

	async def load_guild_config(self, guild_id):
		config = await bump_reminder_collection.find_one({"guild_id": guild_id})
		if config:
			self.cache[guild_id] = config
		else:
			self.cache[guild_id] = {}

	async def schedule_reminder(self, guild_id, channel_id, role_id):
		await asyncio.sleep(self.interval_hours.total_seconds())
		embed = discord.Embed(
			title="Bump Reminder",
			description="It's time to bump the server! Use the command `/bump` to bump the server on Disboard.",
			color=discord.Color.pink()
		)
		guild = self.bot.get_guild(int(guild_id))
		if not guild:
			return
		channel = guild.get_channel(int(channel_id))
		if channel:
			role = f"<@&{role_id}>" if role_id else ""
			await channel.send(content=f"{role}", embed=embed)
		
		self.reminder_tasks.pop(guild_id, None)

	@commands.hybrid_group(name="bump-reminder", description="Commands for the bump reminder system")
	async def bump_reminder(self, ctx):
		pass

	@bump_reminder.command(
		name="enable", description="Enable the bump reminder system"
	)
	@commands.has_permissions(manage_guild=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(channel="The channel to send the bump reminder in", role="The role to ping in the bump reminder")
	async def enable(self, ctx: commands.Context, channel: discord.TextChannel, role: discord.Role = None):
		existing = await bump_reminder_collection.find_one({"guild_id": ctx.guild.id})
		if existing:
			await ctx.send("Bump reminder system is already enabled. Use the `update` command to change settings.", ephemeral=True)
			return
		await bump_reminder_collection.insert_one({
			"guild_id": ctx.guild.id,
			"channel_id": channel.id,
			"role_id": role.id if role else None
		})
		await self.load_guild_config(ctx.guild.id)
		self.bot.dispatch(
			"modlog",
			ctx.guild.id,
			ctx.author.id,
			"Enabled a System",
			f"The Bump Reminder system has been enabled in {channel.mention}."
		)
		await ctx.send(embed=discord.Embed(description=f"<:switch_on:1326648555414224977> Bump reminder system has been enabled in {channel.mention}."), ephemeral=True)

	@bump_reminder.command(
		name="disable", description="Disable the bump reminder system"
	)
	@commands.has_permissions(manage_guild=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def disable(self, ctx: commands.Context):
		existing = await bump_reminder_collection.find_one({"guild_id": ctx.guild.id})
		if not existing:
			await ctx.send("Bump reminder system is not enabled.", ephemeral=True)
			return
		await bump_reminder_collection.delete_one({"guild_id": ctx.guild.id})
		self.cache.pop(ctx.guild.id, None)
		self.bot.dispatch(
			"modlog",
			ctx.guild.id,
			ctx.author.id,
			"Disabled a System",
			"The Bump Reminder system has been disabled."
		)
		await ctx.send(embed=discord.Embed(description=f"<:switch_off:1326648553087984650> Bump reminder system has been disabled."), ephemeral=True)

	@bump_reminder.command(
		name="update", description="Update the bump reminder settings"
	)
	@commands.has_permissions(manage_guild=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	
	async def update(self, ctx: commands.Context, channel: discord.TextChannel = None, role: discord.Role = None):
		existing = await bump_reminder_collection.find_one({"guild_id": ctx.guild.id})
		if not existing:
			await ctx.send("Bump reminder system is not enabled. Use the `enable` command to set it up.", ephemeral=True)
			return
		if channel is None and role is None:
			await ctx.send("You must provide at least a channel or a role to update.", ephemeral=True)
			return
		await bump_reminder_collection.update_one(
			{"guild_id": ctx.guild.id},
			{"$set": {
				"channel_id": channel.id,
				"role_id": role.id if role else None
			}}
		)
		await self.load_guild_config(ctx.guild.id)
		self.bot.dispatch(
			"modlog",
			ctx.guild.id,
			ctx.author.id,
			"Updated a System",
			f"The Bump Reminder system has been updated to use {channel.mention}."
		)
		await ctx.send(embed=discord.Embed(description=f"<:check:1326648557690577920> Bump reminder settings have been updated to use {channel.mention}."), ephemeral=True)

	@commands.Cog.listener()
	async def on_message(self, message):
		if message.author.id != self.disboard_user_id:
			return
		if not message.guild:
			return
		guild_id = message.guild.id
		if guild_id not in self.cache: 
			return
		config = self.cache.get(guild_id)
		if not config:
			print("No config found for guild")
			return
		embed = message.embeds[0] if message.embeds else None
		if not embed:
			return
		if "bump done" not in embed.description.lower():
			return
		if guild_id in self.reminder_tasks:
			return
		channel_id = config.get("channel_id")
		role_id = config.get("role_id")
		if not channel_id:
			return
		task = self.bot.loop.create_task(self.schedule_reminder(guild_id, channel_id, role_id))
		self.reminder_tasks[guild_id] = task
		in_2_hours = datetime.now() + self.interval_hours
		unix_timestamp = int(in_2_hours.timestamp())
		embed = discord.Embed(
			title="Bump Acknowledged",
			description=f"Thank you for bumping the server! 💝\nThe next bump reminder will be sent <t:{unix_timestamp}:R>.",
			color=discord.Color.pink()
		)
		await message.channel.send(embed=embed, delete_after=self.interval_hours.total_seconds())

async def setup(bot):
	cog = BumpReminder(bot)
	configs = await bump_reminder_collection.find({}).to_list(length=None)
	await asyncio.gather(*(cog.load_guild_config(config["guild_id"]) for config in configs))
	await bot.add_cog(cog)