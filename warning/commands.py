import datetime
import discord
import os
import motor.motor_asyncio
from discord.ext import commands
from dotenv import load_dotenv
from db import *

load_dotenv()


class Warning_Commands(commands.Cog):
	async def _revoke_case(self, guild_id, case_id, revoker_id):
		doc = await cases_collection.find_one({"guild_id": str(guild_id)})
		if not doc:
			return False
		cases = doc.get("cases", [])
		for i, c in enumerate(cases):
			if c["case_id"] == case_id:
				c["revoked"] = {"by": revoker_id, "timestamp": datetime.datetime.utcnow().isoformat()}
				cases[i] = c
				await cases_collection.update_one({"guild_id": str(guild_id)}, {"$set": {"cases": cases}})
				return True
		return False
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

	def __init__(self, bot):
		self.bot = bot

	@commands.hybrid_group(name="warnings")
	async def warnings(self, ctx):
		pass

	@warnings.command(
		name="issue", description="Issue a warning.", aliases=["warn"]
	)
	@commands.cooldown(1, 5, type=commands.BucketType.user)
	@commands.has_permissions(moderate_members=True)
	async def issue_warning(
		self, ctx, user: discord.User, *, reason: str = "No Reason Provided"
	):
		if user.id in [ctx.author.id, self.bot.user.id]:
			await ctx.send("You cannot warn yourself or the bot.")
			return

		msg = await ctx.send("Loading, please wait...")

		member = discord.utils.get(ctx.guild.members, id=user.id)
		if not member or member.top_role >= ctx.author.top_role:
			await msg.edit(content="You cannot warn this user.")
			return

		data = await warning_collection.find_one({"guild_id": str(ctx.guild.id), "logs_channel": {"$exists": True}})
		if not data:
			await msg.edit(content="No warning system has been set up.")
			return

		case_id = await self._get_next_case_id(ctx.guild.id)
		case_obj = {
			"case_id": case_id,
			"type": "Warning",
			"target": f"{user} [{user.id}]",
			"moderator": f"{ctx.author} [{ctx.author.id}]",
			"reason": reason,
			"timestamp": datetime.datetime.utcnow().isoformat(),
			"edit_history": []
		}
		await self._add_case(ctx.guild.id, case_obj)

		logs_channel = ctx.guild.get_channel(int(data.get("logs_channel")))
		await warning_collection.insert_one(
			{
				"guild_id": str(ctx.guild.id),
				"user_id": str(user.id),
				"reason": reason,
				"issued_by": str(ctx.author.id),
				"issued_at": datetime.datetime.utcnow(),
				"case_number": case_id,
			}
		)
		warn_log = discord.Embed(
			title=f"Warning issued to {user.name}",
			description="",
			color=discord.Color.pink(),
		)
		warn_log.add_field(
			name="Case Number:", value=f"CASE #{case_id}", inline=False
		)
		warn_log.add_field(name="Reason:", value=reason, inline=False)
		warn_log.add_field(name="Issued By:", value=f"<@{ctx.author.id}>", inline=False)
		warn_log.add_field(
			name="Issued At:",
			value=discord.utils.format_dt(discord.utils.utcnow(), "F"),
			inline=False,
		)
		try:
			warn_log.set_thumbnail(url=user.avatar.url)
		except:
			pass
		warn_log.set_footer(text="Warning System")
		await msg.edit(
			content=f"<:Checkmark:1326642406086410317> `[CASE #{case_id}]` Warning issued to {user.mention} for `{reason}`."
		)
		try:
			await logs_channel.send(embed=warn_log)
		except:
			pass
		try:
			dm_embed = discord.Embed(title="Warned", description=f"You have been warned in **{ctx.guild.name}**", color=discord.Colour.pink())
			dm_embed.add_field(name="Reason:", value=reason, inline=False)
			dm_embed.add_field(name="Case Number:", value=f"CASE #{case_id}", inline=False)
			await user.send(
				embed=dm_embed
			)
		except:
			pass

	@warnings.command(
		name="revoke",
		description="Revoke a warning from a user.",
		aliases=["unwarn"],
	)
	@commands.cooldown(1, 5, type=commands.BucketType.user)
	@commands.has_permissions(moderate_members=True)
	async def revoke_warning(self, ctx, case_number: int):

		data = await warning_collection.find_one({"guild_id": str(ctx.guild.id), "logs_channel": {"$exists": True}})
		if not data:
			await ctx.send(content="No warning system has been set up.")
			return
		
		warning = await warning_collection.find_one(
			{"guild_id": str(ctx.guild.id), "case_number": case_number}
		)
		if not warning:
			await ctx.send("This warning does not exist.", ephemeral=True)
			return
		
		try:
			user = discord.utils.get(ctx.guild.members, id=int(warning["user_id"]))
		except:
			await ctx.send("Couldn't find the user in the warning.")
			return

		member = discord.utils.get(ctx.guild.members, id=user.id)
		if not member:
			await ctx.send("Couldn't find the user in the warning.")
			return
		if member.top_role >= ctx.author.top_role:
			await ctx.send("You cannot unwarn this user.")
			return

		if user.id == ctx.author.id:
			await ctx.send("You cannot revoke a warning from yourself.")
			return
		if user.id == self.bot.user.id:
			await ctx.send("I cannot revoke a warning from myself.")
			return

		await warning_collection.delete_one(
			{
				"guild_id": str(ctx.guild.id),
				"user_id": str(user.id),
				"case_number": case_number,
			}
		)
		await self._revoke_case(ctx.guild.id, case_number, ctx.author.id)
		warn_log = discord.Embed(
			title=f"Warning revoked from {user.name}",
			description="",
			color=discord.Color.pink(),
		)
		warn_log.add_field(
			name="Case Number:", value=f"CASE #{case_number}", inline=False
		)
		warn_log.add_field(
			name="Revoked By:", value=f"<@{ctx.author.id}>", inline=False
		)
		warn_log.add_field(
			name="Revoked At:",
			value=discord.utils.format_dt(discord.utils.utcnow(), "F"),
			inline=False,
		)

		try:
			warn_log.set_thumbnail(url=user.avatar.url)
		except:
			pass

		warn_log.set_footer(text="Warning System")
		await ctx.send(
			f"<:Checkmark:1326642406086410317> `[CASE #{case_number}]` Warning revoked from {user.mention}."
		)
		try:
			await ctx.guild.get_channel(int(data["logs_channel"])).send(embed=warn_log)
		except:
			pass

	@warnings.command(
		name="list",
		description="List all warnings of a user.",
		aliases=["warns", "warnings"],
	)
	@commands.cooldown(1, 5, type=commands.BucketType.user)
	@commands.has_permissions(moderate_members=True)
	async def list_warnings(self, ctx, user: discord.User = None):
		if user is None:
			user = ctx.author

		data = await warning_collection.find_one({"guild_id": str(ctx.guild.id), "logs_channel": {"$exists": True}})
		if not data:
			await ctx.send(content="No warning system has been set up.")
			return

		cursor = warning_collection.find(
			{"guild_id": str(ctx.guild.id), "user_id": str(user.id)}
		)
		embed = discord.Embed(
			title=f"<:Checkmark:1326642406086410317> Warnings of {user.name}",
			description="The following are the warnings of the user.",
			color=discord.Color.blue(),
		)
		embed.set_footer(text="Spectra")
		async for warning in cursor:
			issued_at = warning["issued_at"]
			if isinstance(issued_at, str):
				try:
					issued_at = datetime.datetime.fromisoformat(issued_at)
				except ValueError:
					try:
						issued_at = datetime.datetime.strptime(issued_at, "%Y-%m-%d %H:%M:%S.%f")
					except ValueError:
						issued_at = datetime.datetime.strptime(issued_at, "%Y-%m-%d %H:%M:%S")
			embed.add_field(
				name=f"Case #{warning['case_number']}",
				value=f"Reason: {warning['reason']}\nIssued by: <@{warning['issued_by']}>\nIssued at: {discord.utils.format_dt(issued_at)}",
				inline=False,
			)

		await ctx.send(embed=embed)

	@warnings.command(
		name="clear", description="Clear all warnings of a user."
	)
	@commands.has_permissions(moderate_members=True)
	async def clear(self, ctx, user: discord.User):
		if user.id == ctx.author.id:
			await ctx.send("You cannot clear your own warnings.")
			return
		if user.id == self.bot.user.id:
			await ctx.send("I cannot clear my own warnings.")
			return
		
		member = discord.utils.get(ctx.guild.members, id=user.id)
		if not member:
			await ctx.send("Couldn't find the user in the warning.")
			return
		if member.top_role >= ctx.author.top_role:
			await ctx.send("You cannot warn this user.")
			return
		

		data = await warning_collection.find_one({"guild_id": str(ctx.guild.id), "logs_channel": {"$exists": True}})
		if not data:
			await ctx.send(content="No warning system has been set up.")
			return

		await warning_collection.delete_many(
			{"guild_id": str(ctx.guild.id), "user_id": str(user.id)}
		)
		warn_log = discord.Embed(
			title=f"Warnings cleared from {user.name}",
			description="",
			color=discord.Color.pink(),
		)
		warn_log.add_field(
			name="Cleared By:", value=f"<@{ctx.author.id}>", inline=False
		)
		warn_log.add_field(
			name="Cleared At:",
			value=discord.utils.format_dt(discord.utils.utcnow(), "F"),
			inline=False,
		)

		try:
			warn_log.set_thumbnail(url=user.avatar.url)
		except:
			pass

		warn_log.set_footer(text="Warning System")
		await ctx.send(
			f"<:Checkmark:1326642406086410317> Warnings of {user.mention} have been cleared."
		)
		try:
			await ctx.guild.get_channel(int(data["logs_channel"])).send(embed=warn_log)
		except:
			pass

	@warnings.command(name="setup", description="Setup warning system.")
	@commands.has_permissions(manage_guild=True)
	async def setup(self, ctx, channel: discord.TextChannel):
		guild_id = str(ctx.guild.id)
		data = await warning_collection.find_one({"guild_id": str(ctx.guild.id), "logs_channel": {"$exists": True}})
		if data:
			await ctx.send(content="Warnings have already been setup.", ephemeral=True)
			return
		else:
			await warning_collection.insert_one(
				{"guild_id": str(guild_id), "logs_channel": str(channel.id)}
			)
			embed = discord.Embed(
				title="Warning System",
				description="Warning System has been set.",
				color=discord.Color.blue(),
			)
			embed.set_thumbnail(url=self.bot.user.avatar.url)
			embed.add_field(name="Set By:", value=ctx.author.mention, inline=False)
			await ctx.send(
				"<:switch_on:1326648555414224977> Warning System has been set."
			)
			try:
				self.bot.dispatch(
					"modlog",
					ctx.guild.id,
					ctx.author.id,
					"Enabled a System",
					f"The warning system has been successfully enabled.",
				)
			except Exception as e:
				print(e)
			try:
				await channel.send(embed=embed)
			except:
				pass

	@warnings.command(
		name="disable", description="Disable warning system."
	)
	@commands.has_permissions(manage_guild=True)
	async def disable(self, ctx):
		guild_id = str(ctx.guild.id)
		data = await warning_collection.find_one({"guild_id": str(ctx.guild.id), "logs_channel": {"$exists": True}})
		if not data:
			await ctx.send(content="No warning system has been set up.", ephemeral=True)
			return
		await warning_collection.delete_many({"guild_id": guild_id})
		await ctx.send(
			"<:switch_off:1326648782393180282> Warning System has been disabled.",
			ephemeral=True,
		)
		try:
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Disabled a System",
				f"The warning system has been successfully disabled.",
			)
		except Exception as e:
			print(e)


async def setup(bot):
	await bot.add_cog(Warning_Commands(bot))
