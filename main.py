# Imports

import asyncio
import discord
import datetime
import aiohttp
import os
import topgg
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
intents.message_content = True
intents.members = True
intents.reactions = True

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


def blacklist_check_decorator():
	async def predicate(ctx):
		return await blacklist_check(ctx)

	return commands.check(predicate)


async def get_prefix(Client, message):
	if not message.guild:
		return ">"

	prefix_data = await custom_prefix_collection.find_one({"guild_id": str(message.guild.id)})
	return prefix_data["prefix"] if prefix_data else ">"


# Bot

bot = commands.Bot(
	command_prefix=get_prefix,
	intents=intents,
	status=discord.Status.idle,
	activity=discord.CustomActivity(name=">help | spectrabot.pages.dev"),
	owner_ids=[856196104385986560, 998434044335374336],
	case_insensitive=True,
)

bot.remove_command("help")

# TopGG
bot.topgg_webhook = topgg.WebhookManager(bot).dbl_webhook(
	"/dblwebhook", "youshallnotpass"
)


@bot.event
async def setup_hook():
	token = os.environ.get("TOP_GG")
	if token:
		bot.topggpy = topgg.DBLClient(bot, token)


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

	@discord.ui.button(label="Support Server", style=discord.ButtonStyle.secondary)
	async def support(
		self, interaction: discord.Interaction, button: discord.ui.Button
	):
		embed = discord.Embed(
			title="Support Server",
			description="E-mail: spectra.official@protonmail.com\n[Click here to join the support server.](https://discord.gg/fcPF66DubA)",
			color=discord.Color.blue(),
		)
		embed.set_footer(
			text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
		)
		await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.before_invoke
async def before_any_command(ctx):
	if not await blacklist_check(ctx):
		raise commands.CheckFailure


# Bot Events


@bot.event
async def on_ready():
	if getattr(bot, "ready", False):
		return
	assert bot.user is not None
	# bot.topggpy.default_bot_id = bot.user.id
	"""
	try:
		await bot.topgg_webhook.run(5000)
	except:
		pass
	"""

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
	except Exception as e:
		print(e)
		return
	
	try: await bot.tree.sync()
	except Exception as e: return print(e)

	bot.ready = True


@bot.event
async def on_command_error(ctx, error):
	if isinstance(error, commands.CommandNotFound):
		await ctx.send(
			"I don't think that command exists! If you're using another bot, consider changing my prefix for this server!",
			ephemeral=True,
		)
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
			title="Error!", description="{}".format(error), color=discord.Color.red()
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
			title="Error!", description="{}".format(error), color=discord.Color.red()
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