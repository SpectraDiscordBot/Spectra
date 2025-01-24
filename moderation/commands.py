import asyncio
import datetime
from email import utils
import discord
import os
from discord.ext import commands
from discord import app_commands, utils
from dotenv import load_dotenv
from pymongo import MongoClient
from humanfriendly import parse_timespan, InvalidTimespan

load_dotenv()

client = MongoClient(os.environ.get('MONGO_URI'))
db = client['Spectra']
autorole_collection = db['AutoRole']
cases_collection = db['Cases']
welcome_messages_collection = db['WelcomeMessages']

class Moderation(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.hybrid_command(name="purge", description="Purges messages from the channel.")
	@commands.has_permissions(manage_messages=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def purge(self, ctx, limit: int = 5, *, reason: str = None):
		await ctx.defer(ephemeral=True)
		if limit > 100:
			await ctx.send("Currently, you can only delete up to 100 messages.", ephemeral=True)
			return
		if limit < 1:
			await ctx.send("Please specify a number between 1 and 100.", ephemeral=True)
			return
		
		try:
			await ctx.message.delete()
		except discord.HTTPException:
			pass

		skipped = []

		def check(message):
			if message.created_at < discord.utils.utcnow() - datetime.timedelta(days=14):
				skipped.append(message)
				return False
			return True

		deleted = await ctx.channel.purge(limit=limit, check=check)

		embed = discord.Embed(
			title="Purge Summary",
			description=f"Purged {len(deleted)} messages from {ctx.channel.mention}",
			color=discord.Color.green(),
			timestamp=datetime.datetime.utcnow()
		)
		embed.add_field(name="Deleted by", value=ctx.author.mention, inline=True)
		embed.add_field(name="Reason", value=reason or "No reason provided.", inline=False)

		if skipped:
			skipped_preview = '\n'.join([f"**{msg.author}**: {msg.content}" for msg in skipped[:5] if msg.content])
			embed.add_field(name="Skipped Messages (Older than 14 days)", value=skipped_preview or "No skipped messages.", inline=False)
		
		self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Purge", f"Purged {len(deleted)} messages in {ctx.channel.mention}\nReason: {reason}")

		try:
			await ctx.send(embed=embed, ephemeral=True, delete_after=5)
		except discord.HTTPException:
			pass


	@commands.hybrid_command(name="mute", description="Mute a user.")
	@commands.has_permissions(moderate_members=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def mute(self, ctx, user: discord.Member, time: str, *, reason: str):
		if user.id == ctx.author.id:
			await ctx.send("You cannot mute yourself.")
			return
		if user.id == self.bot.user.id:
			await ctx.send("I cannot mute myself.")
			return
		try:
			duration = parse_timespan(time)
		except InvalidTimespan:
			await ctx.send("Invalid time.")
			return
		if user.is_timed_out():
			await ctx.send(f"{user.mention} is already muted.")
			return
		try:
			cases = cases_collection.find_one({"guild_id": str(ctx.guild.id)})
			if not cases:
				cases_collection.insert_one({"guild_id": str(ctx.guild.id), "cases": 0})
			
			cases_collection.update_one({"guild_id": str(ctx.guild.id)}, {"$set": {"cases": cases["cases"] +1}})

			case = cases_collection.find_one({'guild_id': str(ctx.guild.id)})
			case_number = case["cases"]
			await user.timeout(utils.utcnow() + datetime.timedelta(seconds=duration), reason=f"[#{case_number}] Moderator: {ctx.author.name}\nReason: {reason}")
			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Mute", f"[#{case_number}] Muted {user.mention} with reason: {reason}")
			await ctx.send(f"[#{case_number}] Muted {user.mention} for `{time}`.")
			try:
				await user.send(f"[#{case_number}] You have been muted in **{ctx.guild.name}** for: `{reason}`.")
			except:
				pass
		except Exception as e:
			await ctx.send("I do not have permission to mute users.")
			print(e)

	@commands.hybrid_command(name="unmute", description="Unmute a user.")
	@commands.has_permissions(moderate_members=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def unmute(self, ctx, user: discord.Member):
		if user.id == ctx.author.id:
			await ctx.send("You cannot unmute yourself.")
			return
		if user.id == self.bot.user.id:
			await ctx.send("I cannot unmute myself.")
			return
		if not user.is_timed_out():
			await ctx.send(f"{user.mention} is not muted.")
			return
		try:
			await user.timeout(None)
			cases = cases_collection.find_one({"guild_id": str(ctx.guild.id)})
			if not cases:
				cases_collection.insert_one({"guild_id": str(ctx.guild.id), "cases": 0})
			
			cases_collection.update_one({"guild_id": str(ctx.guild.id)}, {"$set": {"cases": cases["cases"] +1}})
			case = cases_collection.find_one({'guild_id': str(ctx.guild.id)}) 
			case_number = case["cases"]

			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Unmute", f"[#{case_number}]Unmuted {user.mention}")
			await ctx.send(f"[#{case_number}] Unmuted {user.mention}.")
		except Exception as e:
			await ctx.send("I do not have permission to unmute users.")
			print(e)

	@commands.hybrid_command(name="ban", description="Ban a user.")
	@commands.has_permissions(ban_members=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def ban(self, ctx, user: discord.User, delete_message_days : int = 0, *, reason: str = "No Reason Provided"):
		if user.id == ctx.author.id:
			await ctx.send("You cannot ban yourself.")
			return
		if user.id == self.bot.user.id:
			await ctx.send("I cannot ban myself.")
			return
		try:
			if user.top_role > ctx.author.top_role:
				await ctx.send("You cannot ban this user.")
				return
		except:
			pass
		if delete_message_days > 7:
			await ctx.send("Number of days to delete messages cannot be more than 7, or a week.")
			return
		try:
			cases = cases_collection.find_one({"guild_id": str(ctx.guild.id)})
			if not cases:
				cases_collection.insert_one({"guild_id": str(ctx.guild.id), "cases": 0})
			
			cases_collection.update_one({"guild_id": str(ctx.guild.id)}, {"$set": {"cases": cases["cases"] +1}})

			case = cases_collection.find_one({'guild_id': str(ctx.guild.id)})
			case_number = case["cases"]
			await ctx.guild.ban(user, reason=f"[#{case_number}]Moderator: {ctx.author.name}\nReason: {reason}", delete_message_days=delete_message_days)
			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Ban", f"[#{case_number}]Banned {user.mention} with reason: {reason}")
			await ctx.send(f"[#{case_number}] Banned {user.mention}.")
		except Exception as e:
			await ctx.send("I do not have permission to ban users.")
			print(e)

	@commands.hybrid_command(name="kick", description="Kick a user.")
	@commands.has_permissions(kick_members=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def kick(self, ctx, user: discord.Member, *, reason: str = "No Reason Provided"):
		if user.id == ctx.author.id:
			await ctx.send("You cannot kick yourself.")
			return
		if user.id == self.bot.user.id:
			await ctx.send("I cannot kick myself.")
			return
		if user.top_role > ctx.author.top_role:
			await ctx.send("You cannot kick this user.")
			return
		try:
			cases = cases_collection.find_one({"guild_id": str(ctx.guild.id)})
			if not cases:
				cases_collection.insert_one({"guild_id": str(ctx.guild.id), "cases": 0})
			
			cases_collection.update_one({"guild_id": str(ctx.guild.id)}, {"$set": {"cases": cases["cases"] +1}})

			case = cases_collection.find_one({'guild_id': str(ctx.guild.id)})
			case_number = case["cases"]
			await user.kick(reason=f"[#{case_number}] Moderator: {ctx.author.name}\nReason: {reason}")
			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Kick", f"[#{case_number}] Kicked {user.mention} with reason: {reason}")
			await ctx.send(f"[#{case_number}] Kicked {user.mention}.")
		except Exception as e:
			await ctx.send("I do not have permission to kick users.")
			print(e)

	@commands.hybrid_command(name="unban", description="Unban a user.")
	@commands.has_permissions(ban_members=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def unban(self, ctx, user: discord.User):
		try:
			await ctx.guild.unban(discord.Object(id=user.id), reason=f"Moderator: {ctx.author.name}")
			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Unban", f"Unbanned `{user.name} [{user.id}]`")
			await ctx.send(f"Unbanned user `{user.name}`.")
		except Exception as e:
			await ctx.send("I do not have permission to unban users.")
			print(e)

	@commands.hybrid_command(name="slowmode", description="Set the slowmode in a channel")
	@commands.has_permissions(manage_channels=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def slowmode(self, ctx, seconds: int, channel: discord.TextChannel = None):
		if not channel:
			channel = ctx.channel
		try:
			await channel.edit(slowmode_delay=seconds)
			await ctx.send(f"Set slowmode in {channel.mention} to {seconds} seconds.")
			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Slowmode", f"Set slowmode in #{channel.name} to {seconds} seconds")
		except:
			await ctx.send("It seems I do not have permission to set slowmode.")
			return

async def setup(bot):
	await bot.add_cog(Moderation(bot))