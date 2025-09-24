# Imports

import asyncio
import discord
import datetime
import os
import topgg
import itertools
from discord.ext import commands
from discord import Button, app_commands
from discord.ui import View
from datetime import time
from dotenv import load_dotenv
from googleapiclient import discovery
from humanfriendly import parse_timespan
from discord.ext import tasks
from db import db, custom_prefix_collection

# Load Dotenv

load_dotenv()

# Intents

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True
intents.members = True
intents.reactions = True
intents.presences = True


async def get_prefix(client, message):
	if not hasattr(client, "prefix_cache"):
		client.prefix_cache = {}
	if not message.guild:
		return ">"
	gid = str(message.guild.id)
	if gid in client.prefix_cache:
		return client.prefix_cache[gid]
	data = await custom_prefix_collection.find_one({"guild_id": gid})
	prefix = data["prefix"] if data else ">"
	client.prefix_cache[gid] = prefix
	return prefix


# Bot

status_messages = itertools.cycle([
	">help | spectrabot.pages.dev",
	"dynamic_guilds",
	"dynamic_users"
])

class Bot(commands.AutoShardedBot):
	def __init__(self):
		super().__init__(
			command_prefix=get_prefix,
			intents=intents,
			owner_ids=[856196104385986560, 998434044335374336, 1362053982444454119],
			case_insensitive=True,
		)
		self.remove_command("help")
		self.prefix_cache = {}
		
		self.start_time = datetime.datetime.now(datetime.timezone.utc)
		self.ready = False
		
	async def setup_hook(self):
		try:
			self.prefix_cache.clear()
			async for doc in custom_prefix_collection.find({}, {"guild_id": 1, "prefix": 1}):
				self.prefix_cache[doc["guild_id"]] = doc["prefix"]
			await self.load_extension("jishaku"); print("✅ | Loaded Jishaku")
			await self.load_extension("Cogs.core.commands"); print("✅ | Loaded Core Commands")
			await self.load_extension("Cogs.autorole.commands"); print("✅ | Loaded AutoRole Commands")
			await self.load_extension("Cogs.reaction-roles.commands"); print("✅ | Loaded Reaction Role Commands")
			await self.load_extension("Cogs.welcomemessage.commands"); print("✅ | Loaded Welcome Message Commands")
			await self.load_extension("Cogs.server-stats.commands"); print("✅ | Loaded Server Stats Commands")
			await self.load_extension("Cogs.manageroles.commands"); print("✅ | Loaded Manage Roles Commands")
			await self.load_extension("Cogs.moderation.commands"); print("✅ | Loaded Moderation Commands")
			await self.load_extension("Cogs.antispam.commands"); print("✅ | Loaded Anti-Spam Commands")
			await self.load_extension("Cogs.warning.commands"); print("✅ | Loaded Warning Commands")
			await self.load_extension("Cogs.notes.commands"); print("✅ | Loaded Notes Commands")
			await self.load_extension("Cogs.moderation-logs.commands"); print("✅ | Loaded Moderation Logs Commands")
			await self.load_extension("Cogs.anti-toxicity.commands"); print("✅ | Loaded Anti-Toxicity Commands")
			await self.load_extension("Cogs.reports.commands"); print("✅ | Loaded Reports Commands")
			await self.load_extension("Cogs.anti-ping.commands"); print("✅ | Loaded Anti-Ping Commands")
			await self.load_extension("Cogs.owner-stuff.commands"); print("✅ | Loaded Owner Commands")
			await self.load_extension("Cogs.TopGG.topgg"); print("✅ | Loaded TopGG Commands")
			await self.load_extension("Cogs.verification.commands"); print("✅ | Loaded Verification Commands")
			cycle_status.start(); print("✅ | Started Cycling Status")
		except Exception as e:
			print(e)
			return
		
	async def on_ready(self):
		if not self.ready:
			print(f"✅ | {self.user} Is Ready.")
			print(f"✅ | Bot ID: {self.user.id}")
			
			try: await self.tree.sync()
			except Exception as e: return print(e)

			self.tree.on_error = self.on_tree_error
			
			self.ready = True

	async def on_command_error(self, ctx, error):
		if isinstance(error, commands.CommandNotFound):
			pass
		elif isinstance(error, commands.NotOwner):
			pass
		elif isinstance(error, commands.CommandOnCooldown):
			msg = "**Still On Cooldown!** You may retry after {:.2f}s".format(
				error.retry_after
			)
			await ctx.send(msg, ephemeral=True)
		elif isinstance(error, commands.MissingRequiredArgument):
			required_params = [
				param
				for param in ctx.command.params
				if ctx.command.params[param].default == ctx.command.params[param].empty
			]

			usage = f"/{ctx.command} " + " ".join(f"<{param}>" for param in required_params)
			await ctx.send(
				f"Error: Missing required argument `{error.param.name}`.\nUsage: `{usage}`",
				ephemeral=True,
			)
		else:
			embed = discord.Embed(
				title="Error!", description="{}".format(error), color=0x2f3136
			)
			embed.set_footer(
				text="Spectra", icon_url=self.user.display_avatar.url
			)
			embed.set_thumbnail(
				url="https://media.discordapp.net/attachments/914579638792114190/1280203446825517239/error-icon-25239.png?ex=66d739de&is=66d5e85e&hm=83a98b27d14a3a19f4795d3fec58d1cd7306f6a940c45e49cd2dfef6edcdc96e&=&format=webp&quality=lossless&width=640&height=640SS"
			)
			await ctx.send(embed=embed, view=ErrorButtons(), ephemeral=True)
			print(error)

	async def on_tree_error(
		self, interaction: discord.Interaction, error: app_commands.AppCommandError
	):
		if isinstance(error, app_commands.CommandOnCooldown):
			msg = "**Still On Cooldown!** You may retry after {:.2f}s".format(
				error.retry_after
			)
			try:
				await interaction.response.send_message(msg, ephemeral=True)
			except:
				await interaction.channel.send(
					interaction.user.mention, msg, delete_after=5
				)
		elif isinstance(error, commands.CommandOnCooldown):
			msg = "**Still On Cooldown!** You may retry after {:.2f}s".format(
				error.retry_after
			)
			try:
				await interaction.response.send_message(msg, ephemeral=True)
			except:
				await interaction.channel.send(
					interaction.user.mention, msg, delete_after=5
				)
		elif isinstance(error, app_commands.MissingPermissions):
			msg = "You are missing the following permissions: {}".format(
				", ".join(error.missing_permissions)
			)
			try:
				await interaction.response.send_message(msg, ephemeral=True)
			except:
				await interaction.channel.send(
					interaction.user.mention, msg, delete_after=5
				)
		elif isinstance(error, commands.MissingPermissions):
			msg = "You are missing the following permissions: {}".format(
				", ".join(error.missing_permissions)
			)
			try:
				await interaction.response.send_message(msg, ephemeral=True)
			except:
				await interaction.channel.send(
					interaction.user.mention, msg, delete_after=5
				)
		else:
			embed = discord.Embed(
				title="Error!", description="{}".format(error), color=0x2f3136
			)
			embed.set_footer(
				text="Spectra",
			)
			embed.set_thumbnail(
				url="https://media.discordapp.net/attachments/914579638792114190/1280203446825517239/error-icon-25239.png?ex=66d739de&is=66d5e85e&hm=83a98b27d14a3a19f4795d3fec58d1cd7306f6a940c45e49cd2dfef6edcdc96e&=&format=webp&quality=lossless&width=640&height=640"
			)
			try:
				await interaction.response.send_message(
					embed=embed, view=ErrorButtons(), delete_after=10, ephemeral=True
				)
			except:
				try:
					await interaction.followup.send(
						embed=embed, view=ErrorButtons(), delete_after=10, ephemeral=True
					)
				except:
					pass
			print(error)

	async def on_guild_join(self, guild):
		await asyncio.sleep(1.5)

		inviter = None
		async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
			if entry.target.id == self.user.id:
				inviter = entry.user
				break

		if inviter:
			embed = discord.Embed(
				title="Thanks for adding me!",
				description=f"Hello! I'm Spectra, a multipurpose bot with moderation, auto-role, welcome messages, reaction roles, and much more!\n\nYou were the one who invited me to **{guild.name}**. If you need any help, feel free to join my [Support Server](https://discord.gg/fcPF66DubA) or check out my website at [spectrabot.pages.dev](https://spectrabot.pages.dev)!",
				color=discord.Color.pink(),
			)
			embed.set_thumbnail(url=self.user.display_avatar.url)
			embed.set_footer(
				text="Made with ❤ by brutiv & tyler.hers",
				icon_url=self.user.display_avatar.url,
			)
			embed.set_author(name=inviter.name, icon_url=inviter.display_avatar.url)
			try:
				await inviter.send(embed=embed)
			except discord.Forbidden:
				pass
			except Exception as e:
				print(e)

		server_owner_embed = discord.Embed(
			title="Spectra",
			description=f"Hello! I'm Spectra, a multipurpose bot with moderation, auto-role, welcome messages, reaction roles, and much more!\n\nThanks for adding me to **{guild.name}**! If you need any help, feel free to join my [Support Server](https://discord.gg/fcPF66DubA) or check out my website at [spectrabot.pages.dev](https://spectrabot.pages.dev)!",
			color=discord.Color.pink(),
		)
		server_owner_embed.set_thumbnail(url=self.user.display_avatar.url)
		server_owner_embed.set_footer(
			text="Made with ❤ by brutiv & tyler.hers",
			icon_url=self.user.display_avatar.url,
		)
		server_owner_embed.set_author(name=guild.owner.name, icon_url=guild.owner.display_avatar.url)

		if not inviter or inviter.id != guild.owner_id:
			try:
				await guild.owner.send(embed=server_owner_embed)
			except discord.Forbidden:
				pass
			except Exception as e:
				print(e)

	async def on_guild_remove(self, guild):
		guild_id = guild.id
		collections = await db.list_collection_names()
		for collection_name in collections:
			collection = db[collection_name]
			await collection.delete_many({"guild_id": guild_id})


	async def on_message(self, message):
		if isinstance(message.channel, discord.channel.DMChannel):
			return

		await self.process_commands(message)

		if self.user.mentioned_in(message):
			if message.author.id == 856196104385986560:
				await message.reply(
					"<:Checkmark:1326642406086410317> Owner of Spectra Verified"
				)
			elif message.author.id == 998434044335374336:
				await message.reply(
					"<:Checkmark:1326642406086410317> Co Owner of Spectra Verified"
				)
			else:
				pass
		

bot = Bot()


# Classes

class ErrorButtons(discord.ui.View):
	def __init__(self, *, timeout=120):
		super().__init__(timeout=timeout)
		self.add_item(discord.ui.Button(
			label="Support Server",
			style=discord.ButtonStyle.link,
			url="https://discord.gg/fcPF66DubA"
		))
		self.add_item(discord.ui.Button(
			label="E-Mail",
			style=discord.ButtonStyle.link,
			url="https://spectrabot.pages.dev/mail"
		))

@tasks.loop(seconds=10)
async def cycle_status():
	status = next(status_messages)
	if status == "dynamic_guilds":
		status = f">help | Managing {len(bot.guilds)} servers"
	elif status == "dynamic_users":
		status = f">help | Serving {len(bot.users)} users"

	await bot.change_presence(activity=discord.CustomActivity(name=status))


# Run Bot

bot.run(os.environ.get("TOKEN"))
