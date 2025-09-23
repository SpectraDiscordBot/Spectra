import asyncio
import datetime
import discord
import os
from discord.ext import commands
from discord import app_commands, utils
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from humanfriendly import parse_timespan, InvalidTimespan
from db import cases_collection

load_dotenv()

class Moderation(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@staticmethod
	def discord_timestamp(val, style="F"):
		if isinstance(val, str):
			dt = datetime.datetime.fromisoformat(val)
		else:
			dt = val
		return f"<t:{int(dt.timestamp())}:{style}>"

	@commands.hybrid_command(name="purge", description="Purges messages from the channel.")
	@commands.has_permissions(manage_messages=True)
	@commands.bot_has_permissions(manage_messages=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(limit="Number of messages to purge (1-250)", reason="Reason for purging messages")
	async def purge(self, ctx, limit: int = 5, *, reason: str = None):
		await ctx.defer(ephemeral=True)
		if limit > 250:
			await ctx.send(embed=discord.Embed(description="You can only delete up to 250 messages."), ephemeral=True)
			return
		if limit < 1:
			await ctx.send(embed=discord.Embed(description="Please specify a number between 1 and 250."), ephemeral=True)
			return
		try:
			await ctx.message.delete()
		except discord.HTTPException:
			pass

		messages = [msg async for msg in ctx.channel.history(limit=limit)]
		messages_to_delete = [m for m in messages if m.created_at > discord.utils.utcnow() - datetime.timedelta(days=14)]
		skipped = [m for m in messages if m.created_at <= discord.utils.utcnow() - datetime.timedelta(days=14)]

		if messages_to_delete and len(messages_to_delete) <= 100:
			await ctx.channel.delete_messages(messages_to_delete, reason=f"Purged by {ctx.author} | Reason: {reason if reason else 'No reason provided'}")
		elif len(messages_to_delete) > 100:
			await ctx.channel.purge(limit=len(messages_to_delete), check=lambda m: m in messages_to_delete, reason=f"Purged by {ctx.author} | Reason: {reason if reason else 'No reason provided'}")
		deleted_count = len(messages_to_delete)
		embed = discord.Embed(
			title="Purge Summary",
			description=f"Purged {deleted_count} messages from {ctx.channel.mention}",
			timestamp=datetime.datetime.utcnow(),
		)
		embed.add_field(name="Purged by", value=ctx.author.mention, inline=True)
		embed.add_field(name="Reason", value=reason or "No reason provided.", inline=False)
		if skipped:
			skipped_preview = "\n".join([f"**{msg.author}**: {discord.utils.escape_markdown((msg.content[:50] + "...") if len(msg.content) > 50 else msg.content)}" for msg in skipped[:5] if msg.content])
			embed.add_field(name="Skipped Messages (Older than 14 days)", value=skipped_preview or "No skipped messages.", inline=False)
		self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Purge", f"Purged {deleted_count} messages in {ctx.channel.mention}\nReason: {reason}")
		try:
			await ctx.send(embed=embed, ephemeral=True, delete_after=5)
		except discord.HTTPException:
			pass

	async def _get_next_case_id(self, guild_id):
		doc = await cases_collection.find_one({"guild_id": str(guild_id)})
		if not doc:
			await cases_collection.insert_one({"guild_id": str(guild_id), "cases": [], "last_case_id": 0})
			return 1
		return doc.get("last_case_id", 0) + 1

	async def _add_case(self, guild_id, case):
		await cases_collection.update_one(
			{"guild_id": str(guild_id)},
			{"$push": {"cases": case}, "$set": {"last_case_id": case["case_id"]}},
			upsert=True
		)

	async def _edit_case(self, guild_id, case_id, editor_id, new_data):
		doc = await cases_collection.find_one({"guild_id": str(guild_id)})
		if not doc:
			return False
		cases = doc.get("cases", [])
		for i, c in enumerate(cases):
			if c["case_id"] == case_id:
				history = c.get("edit_history", [])
				history.append({"editor_id": editor_id, "timestamp": datetime.datetime.utcnow().isoformat(), "old_data": {k: c[k] for k in new_data}})
				for k, v in new_data.items():
					c[k] = v
				c["edit_history"] = history
				cases[i] = c
				await cases_collection.update_one({"guild_id": str(guild_id)}, {"$set": {"cases": cases}})
				return True
		return False
		
	@commands.hybrid_command(name="case", description="View a moderation case.")
	@commands.has_permissions(moderate_members=True)
	@app_commands.describe(case_id="The ID of the case to view")
	async def case(self, ctx, case_id: int):
		doc = await cases_collection.find_one({"guild_id": str(ctx.guild.id)})
		if not doc or not doc.get("cases"):
			await ctx.send(embed=discord.Embed(description="No cases found."), ephemeral=True)
			return

		case = next((c for c in doc["cases"] if c["case_id"] == case_id), None)
		if not case:
			await ctx.send(embed=discord.Embed(description="Case not found."), ephemeral=True)
			return

		embed = discord.Embed(title=f"Case #{case['case_id']}")
		embed.add_field(name="Type", value=case["type"], inline=True)
		embed.add_field(name="Target", value=case["target"], inline=False)
		embed.add_field(name="Moderator", value=case["moderator"], inline=False)
		embed.add_field(name="Reason", value=case["reason"], inline=False)
		embed.add_field(name="Timestamp", value=self.discord_timestamp(case["timestamp"], style="F"), inline=False)

		if case.get("revoked"):
			r = case["revoked"]
			embed.add_field(
				name="Revoked",
				value=f"By <@{r['by']}> at {self.discord_timestamp(r['timestamp'], style='F')}",
				inline=False
			)

		if case.get("edit_history"):
			edits = "\n".join(
				[f"By <@{h['editor_id']}> at {self.discord_timestamp(h['timestamp'], style='F')}" for h in case["edit_history"]]
			)
			embed.add_field(name="Edit History", value=edits, inline=False)

		await ctx.send(embed=embed, ephemeral=True)

	@commands.hybrid_command(name="editcase", description="Edit a moderation case.")
	@commands.has_permissions(moderate_members=True)
	@app_commands.describe(case_id="The ID of the case to edit", reason="The new reason for the case")
	async def editcase(self, ctx, case_id: int, *, reason: str):
		ok = await self._edit_case(ctx.guild.id, case_id, ctx.author.id, {"reason": reason})
		if ok:
			await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> Case #{case_id} updated."), ephemeral=True)
		else:
			await ctx.send(embed=discord.Embed(description="Case not found.", ephemeral=True))

	@commands.hybrid_command(name="mute", description="Mute a user.", aliases=["timeout"])
	@commands.has_permissions(moderate_members=True)
	@commands.bot_has_permissions(moderate_members=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(user="The user to mute", time="Duration of the mute (e.g., 10m, 1h, 1d)", reason="Reason for the mute")
	async def mute(self, ctx, user: discord.Member, time: str, *, reason: str):
		if user.id == ctx.author.id:
			await ctx.send(embed=discord.Embed(description="You cannot mute yourself."), ephemeral=True)
			return
		if user.id == self.bot.user.id:
			await ctx.send(embed=discord.Embed(description="I cannot mute myself."), ephemeral=True)
			return
		try:
			if user.top_role.position >= ctx.author.top_role.position:
				await ctx.send(embed=discord.Embed(description="You cannot mute this user."), ephemeral=True)
				return
			if user.top_role.position >= ctx.guild.me.top_role.position:
				await ctx.send(embed=discord.Embed(description="I cannot mute this user."), ephemeral=True)
				return
		except:
			pass
		try:
			duration = parse_timespan(time)
		except InvalidTimespan:
			await ctx.send(embed=discord.Embed(description="Invalid time."), ephemeral=True)
			return
		if user.is_timed_out():
			await ctx.send(embed=discord.Embed(description=f"{user.mention} is already muted."), ephemeral=True)
			return
		try:
			case_id = await self._get_next_case_id(ctx.guild.id)
			await user.timeout(utils.utcnow() + datetime.timedelta(seconds=duration), reason=f"[#{case_id}] Moderator: {ctx.author.name}\nReason: {reason}")
			case_obj = {
				"case_id": case_id,
				"type": "Mute",
				"target": f"{user} [{user.id}]",
				"moderator": f"{ctx.author} [{ctx.author.id}]",
				"reason": reason,
				"timestamp": datetime.datetime.utcnow().isoformat(),
				"edit_history": []
			}
			await self._add_case(ctx.guild.id, case_obj)
			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Mute", f"[#{case_id}] Muted {user.mention} with reason: {reason}")
			await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> [#{case_id}] Muted {user.mention} for `{time}`."), ephemeral=True)
			try:
				await user.send(embed=discord.Embed(description=f"[#{case_id}] You have been muted in **{ctx.guild.name}** for: `{reason}`.", color=discord.Color.red()))
			except:
				pass
		except Exception as e:
			await ctx.send(embed=discord.Embed(description="I do not have permission to mute that user."), ephemeral=True)
			print(e)

	@commands.hybrid_command(name="unmute", description="Unmute a user.", aliases=["untimeout"])
	@commands.has_permissions(moderate_members=True)
	@commands.bot_has_permissions(moderate_members=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(user="The user to unmute")
	async def unmute(self, ctx, user: discord.Member):
		if user.id == ctx.author.id:
			await ctx.send(embed=discord.Embed(description="You cannot unmute yourself."), ephemeral=True)
			return
		if user.id == self.bot.user.id:
			await ctx.send(embed=discord.Embed(description="I cannot unmute myself."), ephemeral=True)
			return
		if not user.is_timed_out():
			await ctx.send(embed=discord.Embed(description=f"{user.mention} is not muted."), ephemeral=True)
			return
		try:
			if user.top_role.position >= ctx.author.top_role.position:
				await ctx.send(embed=discord.Embed(description="You cannot unmute this user."), ephemeral=True)
				return
			if user.top_role.position >= ctx.guild.me.top_role.position:
				await ctx.send(embed=discord.Embed(description="I cannot unmute this user."), ephemeral=True)
				return
		except:
			pass
		try:
			await user.timeout(None)
			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Unmute", f"Unmuted {user.mention}")
			await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> Unmuted {user.mention}."), ephemeral=True)
		except Exception as e:
			await ctx.send(embed=discord.Embed(description="I do not have permission to unmute that user."))
			print(e)

	@commands.hybrid_command(name="ban", description="Ban a user.")
	@commands.has_permissions(ban_members=True)
	@commands.bot_has_permissions(ban_members=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(user="The user to ban", delete_message_days="Number of days to delete messages", reason="Reason for the ban")
	async def ban(self, ctx, user: discord.User, delete_message_days: int, *, reason: str = "No Reason Provided"):
		if user.id == ctx.author.id:
			await ctx.send(embed=discord.Embed(description="You cannot ban yourself."), ephemeral=True)
			return
		if user.id == self.bot.user.id:
			await ctx.send(embed=discord.Embed(description="I cannot ban myself."), ephemeral=True)
			return
		try:
			if user.top_role.position >= ctx.author.top_role.position:
				await ctx.send(embed=discord.Embed(description="You cannot ban this user."), ephemeral=True)
				return
			if user.top_role.position >= ctx.guild.me.top_role.position:
				await ctx.send(embed=discord.Embed(description="I cannot ban this user."), ephemeral=True)
				return
		except:
			pass
		if delete_message_days > 7:
			await ctx.send(embed=discord.Embed(description="Number of days to delete messages cannot be more than 7, or a week."), ephemeral=True)
			return
		try:
			case_id = await self._get_next_case_id(ctx.guild.id)
			await ctx.guild.ban(user, reason=f"[#{case_id}]Moderator: {ctx.author.name}\nReason: {reason}", delete_message_days=delete_message_days)
			case_obj = {
				"case_id": case_id,
				"type": "Ban",
				"target": f"{user} [{user.id}]",
				"moderator": f"{ctx.author} [{ctx.author.id}]",
				"reason": reason,
				"timestamp": datetime.datetime.utcnow().isoformat(),
				"edit_history": []
			}
			await self._add_case(ctx.guild.id, case_obj)
			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Ban", f"[#{case_id}]Banned {user.mention} with reason: {reason}")
			await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> [#{case_id}] Banned {user.mention}."), ephemeral=True)
			try:
				await user.send(embed=discord.Embed(description=f"[#{case_id}] You have been banned from **{ctx.guild.name}** for: `{reason}`.", color=discord.Color.red()))
			except:
				pass
		except Exception as e:
			await ctx.send(embed=discord.Embed(description="I do not have permission to ban that user."), ephemeral=True)
			print(e)

	@commands.hybrid_command(name="kick", description="Kick a user.")
	@commands.has_permissions(kick_members=True)
	@commands.bot_has_permissions(kick_members=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(user="The user to kick", reason="Reason for the kick")
	async def kick(self, ctx, user: discord.Member, *, reason: str = "No Reason Provided"):
		if user.id == ctx.author.id:
			await ctx.send(embed=discord.Embed(description="You cannot kick yourself."), ephemeral=True)
			return
		if user.id == self.bot.user.id:
			await ctx.send(embed=discord.Embed(description="I cannot kick myself."), ephemeral=True)
			return
		if user.top_role.position >= ctx.author.top_role.position:
			await ctx.send(embed=discord.Embed(description="You cannot kick this user."), ephemeral=True)
			return
		if user.top_role.position >= ctx.guild.me.top_role.position:
			await ctx.send(embed=discord.Embed(description="I cannot kick this user."), ephemeral=True)
			return
		try:
			case_id = await self._get_next_case_id(ctx.guild.id)
			await user.kick(reason=f"[#{case_id}] Moderator: {ctx.author.name}\nReason: {reason}")
			case_obj = {
				"case_id": case_id,
				"type": "Kick",
				"target": f"{user} [{user.id}]",
				"moderator": f"{ctx.author} [{ctx.author.id}]",
				"reason": reason,
				"timestamp": datetime.datetime.utcnow().isoformat(),
				"edit_history": []
			}
			await self._add_case(ctx.guild.id, case_obj)
			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Kick", f"[#{case_id}] Kicked {user.mention} with reason: {reason}")
			await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> [#{case_id}] Kicked {user.mention}."), ephemeral=True)
			try:
				await user.send(embed=discord.Embed(description=f"[#{case_id}] You have been kicked from **{ctx.guild.name}** for: `{reason}`.", color=discord.Color.red()))
			except:
				pass
		except Exception as e:
			await ctx.send("I do not have permission to kick users.", ephemeral=True)
			print(e)

	@commands.hybrid_command(name="unban", description="Unban a user.")
	@commands.has_permissions(ban_members=True)
	@commands.bot_has_permissions(ban_members=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(user="The user to unban")
	async def unban(self, ctx, user: discord.User):
		try:
			await ctx.guild.unban(
				discord.Object(id=user.id), reason=f"Moderator: {ctx.author.name}"
			)
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Unban",
				f"Unbanned `{user.name} [{user.id}]`",
			)
			await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> Unbanned user `{user.name}`."), ephemeral=True)
		except Exception as e:
			await ctx.send(embed=discord.Embed(description="I do not have permission to unban users."), ephemeral=True)
			print(e)

	@commands.hybrid_command(
		name="slowmode", description="Set the slowmode in a channel"
	)
	@commands.has_permissions(manage_channels=True)
	@commands.bot_has_permissions(manage_channels=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(seconds="The slowmode delay in seconds", channel="The channel to set slowmode in (defaults to current channel)")
	async def slowmode(self, ctx, seconds: int, channel: discord.TextChannel = None):
		if not channel:
			channel = ctx.channel
		try:
			await channel.edit(slowmode_delay=seconds)
			await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> Set slowmode in {channel.mention} to {seconds} seconds."), ephemeral=True)
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Slowmode",
				f"Set slowmode in #{channel.name} to {seconds} seconds",
			)
		except:
			await ctx.send(embed=discord.Embed(description="It seems I do not have permission to set slowmode."), ephemeral=True)
			return

async def setup(bot):
	await bot.add_cog(Moderation(bot))