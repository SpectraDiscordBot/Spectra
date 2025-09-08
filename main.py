# Imports

import asyncio
import discord
import datetime
import aiohttp
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
from db import *

# Load Dotenv

load_dotenv()

# Intents

intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True
intents.members = True
intents.reactions = True

"""
async def blacklist_check(ctx):
	user_blacklisted = await blacklist_collection.find_one({"_id": ctx.author.id})
	server_blacklisted = await blacklist_collection.find_one(
		{"_id": ctx.guild.id if ctx.guild else None}
	)

	if user_blacklisted:
		return False
	if server_blacklisted:
		await ctx.send("This server is blacklisted from using this bot.")
		return False
	return True
"""


async def get_prefix(Client, message):
	if not message.guild:
		return ">"

	prefix_data = await custom_prefix_collection.find_one({"guild_id": str(message.guild.id)})
	return prefix_data["prefix"] if prefix_data else ">"


# Bot

status_messages = itertools.cycle([
    ">help | spectrabot.pages.dev",
    "dynamic_guilds",
    "dynamic_users"
])

bot = commands.Bot(
	command_prefix=get_prefix,
	intents=intents,
	status=discord.Status.idle,
	owner_ids=[856196104385986560, 998434044335374336],
	case_insensitive=True,
)

bot.remove_command("help")


# Classes

class AutoRoleSetupButton(discord.ui.View):
	def __init__(self, *, timeout=120):
		super().__init__(timeout=timeout)

	@discord.ui.button(
		label="Remove AutoRole", emoji="⚠️", style=discord.ButtonStyle.danger
	)
	async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
		query = {"guild_id": str(interaction.guild.id)}
		await autorole_collection.delete_one(query, comment="Removed AutoRole")
		await interaction.response.send_message(
			"AutoRole has been removed.", ephemeral=True
		)


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
            url="https://spectrabot.pages.dev/mail.html"
        ))


# Bot Events


@bot.event
async def on_ready():
	if getattr(bot, "ready", False):
		return
	assert bot.user is not None

	print(f"✅ | {bot.user} Is Ready.")
	print(f"✅ | Bot ID: {bot.user.id}")
	try:
		await bot.load_extension("core.commands"); print("✅ | Loaded Core Commands")
		await bot.load_extension("autorole.commands"); print("✅ | Loaded AutoRole Commands")
		await bot.load_extension("reaction-roles.commands"); print("✅ | Loaded Reaction Role Commands")
		await bot.load_extension("welcomemessage.commands"); print("✅ | Loaded Welcome Message Commands")
		await bot.load_extension("manageroles.commands"); print("✅ | Loaded Manage Roles Commands")
		await bot.load_extension("moderation.commands"); print("✅ | Loaded Moderation Commands")
		await bot.load_extension("antispam.commands"); print("✅ | Loaded Anti-Spam Commands")
		await bot.load_extension("warning.commands"); print("✅ | Loaded Warning Commands")
		await bot.load_extension("notes.commands"); print("✅ | Loaded Notes Commands")
		await bot.load_extension("moderation-logs.commands"); print("✅ | Loaded Moderation Logs Commands")
		await bot.load_extension("anti-toxicity.commands"); print("✅ | Loaded Anti-Toxicity Commands")
		await bot.load_extension("reports.commands"); print("✅ | Loaded Reports Commands")
		await bot.load_extension("anti-ping.commands"); print("✅ | Loaded Anti-Ping Commands")
		await bot.load_extension("owner-stuff.commands"); print("✅ | Loaded Owner Commands")
		await bot.load_extension("TopGG.topgg"); print("✅ | Loaded TopGG Commands")
		await bot.load_extension("verification.commands"); print("✅ | Loaded Verification Commands")
		cycle_status.start(); print("✅ | Started Cycling Status")
	except Exception as e:
		print(e)
		return
	
	try: await bot.tree.sync()
	except Exception as e: return print(e)

	bot.ready = True

@tasks.loop(seconds=7)
async def cycle_status():
    status = next(status_messages)
    if status == "dynamic_guilds":
        status = f"Managing {len(bot.guilds)} servers"
    elif status == "dynamic_users":
        status = f"Serving {len(bot.users)} users"

    await bot.change_presence(activity=discord.CustomActivity(name=status))

@bot.event
async def on_command_error(ctx, error):
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
			text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
		)
		embed.set_thumbnail(
			url="https://media.discordapp.net/attachments/914579638792114190/1280203446825517239/error-icon-25239.png?ex=66d739de&is=66d5e85e&hm=83a98b27d14a3a19f4795d3fec58d1cd7306f6a940c45e49cd2dfef6edcdc96e&=&format=webp&quality=lossless&width=640&height=640SS"
		)
		await ctx.send(embed=embed, view=ErrorButtons(), ephemeral=True)
		print(error)


@bot.event
async def on_tree_error(
	interaction: discord.Interaction, error: app_commands.AppCommandError
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


bot.tree.on_error = on_tree_error

@bot.event
async def on_guild_join(guild):
	await asyncio.sleep(1.5)

	inviter = None
	async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.bot_add):
		if entry.target.id == bot.user.id:
			inviter = entry.user
			break

	if inviter:
		embed = discord.Embed(
			title="Thanks for adding me!",
			description=f"Hello! I'm Spectra, a multipurpose bot with moderation, auto-role, welcome messages, reaction roles, and much more!\n\nYou were the one who invited me to **{guild.name}**. If you need any help, feel free to join my [Support Server](https://discord.gg/fcPF66DubA) or check out my website at [spectrabot.pages.dev](https://spectrabot.pages.dev)!",
			color=discord.Color.pink(),
		)
		embed.set_thumbnail(url=bot.user.display_avatar.url)
		embed.set_footer(
			text="Made with ❤ by brutiv & tyler.hers",
			icon_url=bot.user.display_avatar.url,
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
	server_owner_embed.set_thumbnail(url=bot.user.display_avatar.url)
	server_owner_embed.set_footer(
		text="Made with ❤ by brutiv & tyler.hers",
		icon_url=bot.user.display_avatar.url,
	)
	server_owner_embed.set_author(name=guild.owner.name, icon_url=guild.owner.display_avatar.url)

	if not inviter or inviter.id != guild.owner_id:
		try:
			await guild.owner.send(embed=server_owner_embed)
		except discord.Forbidden:
			pass
		except Exception as e:
			print(e)

@bot.event
async def on_guild_remove(guild):
	guild_id = guild.id
	collections = await db.list_collection_names()
	for collection_name in collections:
		collection = db[collection_name]
		result = await collection.delete_many({"guild_id": guild_id})

	print(f"All data for guild {guild_id} has been removed from the database.")


@bot.event
async def on_message(message):
	if isinstance(message.channel, discord.channel.DMChannel):
		return

	await bot.process_commands(message)

	if bot.user.mentioned_in(message):
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


# Run Bot

bot.run(os.environ.get("TOKEN"))
