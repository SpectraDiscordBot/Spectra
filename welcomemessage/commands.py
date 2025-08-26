import discord
import os
from discord.ext import commands
from discord import app_commands
from discord.ui import Modal, TextInput
from dotenv import load_dotenv
from db import welcome_messages_collection

load_dotenv()


class WelcomeEmbedSetupModal(Modal, title="Setup Welcome Embed"):
	title_input = TextInput(label="Title", max_length=256, required=False)
	description_input = TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=2048, required=False)
	color_input = TextInput(label="Color (hex, e.g. #2F3136)", max_length=7, required=False, placeholder="#2F3136")
	image_url_input = TextInput(label="Image URL", max_length=2000, required=False)
	thumbnail_url_input = TextInput(label="Thumbnail URL", max_length=2000, required=False)

	def __init__(self, bot, ctx):
		super().__init__()
		self.bot = bot
		self.ctx = ctx

	async def on_submit(self, interaction: discord.Interaction):
		color_str = self.color_input.value.strip() or "#2F3136"
		if color_str.startswith("#"):
			color_str = color_str[1:]
		try:
			color_int = int(color_str, 16)
			if color_int < 0 or color_int > 0xFFFFFF:
				raise ValueError
		except:
			await interaction.response.send_message("Invalid color hex code. Use format like `#2F3136`.", ephemeral=True)
			return

		embed_data = {
			"title": self.title_input.value.strip(),
			"description": self.description_input.value.strip(),
			"color": f"0x{color_str.upper()}",
			"image": self.image_url_input.value.strip(),
			"thumbnail": self.thumbnail_url_input.value.strip(),
			"fields": [],
			"footer": {},
			"author": {"name": "", "icon_url": "", "url": ""}
		}

		guild_id = str(self.ctx.guild.id)
		channel_id = str(self.ctx.channel.id)

		await welcome_messages_collection.update_one(
			{"guild_id": guild_id},
			{"$set": {"embed": embed_data, "channel": channel_id}},
			upsert=True,
		)

		await self.ctx.cog.load_guild_welcome(self.ctx.guild.id)

		self.bot.dispatch(
			"modlog",
			self.ctx.guild.id,
			self.ctx.author.id,
			"Updated welcome embed",
			f"Welcome embed set in {self.ctx.channel.mention}"
		)

		await interaction.response.send_message(
			"<:switch_on:1326648555414224977> Welcome embed has been set successfully.", ephemeral=True
		)

class WelcomeEmbedSetupButtonView(discord.ui.View):
	def __init__(self, bot, ctx):
		super().__init__(timeout=180)
		self.bot = bot
		self.ctx = ctx

	@discord.ui.button(label="Setup Welcome Embed", style=discord.ButtonStyle.green)
	async def setup_embed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
		modal = WelcomeEmbedSetupModal(self.bot, self.ctx)
		await interaction.response.send_modal(modal)

class WelcomeMessage_Commands(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.cache = {}

	async def load_guild_welcome(self, guild_id):
		data = await welcome_messages_collection.find_one({"guild_id": str(guild_id)})
		self.cache[str(guild_id)] = data
		
	def build_embed(self, data, member):
		def replace_vars(text):
			return (
				(text or "")
				.replace("{user}", member.mention)
				.replace("{username}", member.name)
				.replace("{guild}", member.guild.name)
				.replace("{membercount}", str(member.guild.member_count))
				.replace("{mention}", member.mention)
				.replace("{discriminator}", member.discriminator)
			)

		color = (
			int(data.get("color", "0x2F3136"), 16) if data.get("color") else 0x2F3136
		)
		embed = discord.Embed(
			title=replace_vars(data.get("title", "")),
			description=replace_vars(data.get("description", "")),
			color=color,
		)
		for field in data.get("fields", []):
			embed.add_field(
				name=replace_vars(field.get("name", "")),
				value=replace_vars(field.get("value", "")),
				inline=field.get("inline", False),
			)
		footer = data.get("footer")
		if footer and footer.get("text"):
			embed.set_footer(text=replace_vars(footer["text"]))
		thumbnail = data.get("thumbnail")
		if thumbnail:
			embed.set_thumbnail(url=thumbnail)
		author = data.get("author")
		if author:
			name = replace_vars(author.get("name", ""))
			icon_url = author.get("icon_url")
			url = author.get("url")
			embed.set_author(name=name, icon_url=icon_url, url=url)
		image = data.get("image")
		if image:
			embed.set_image(url=image)
		return embed

	async def send_welcome(self, member: discord.Member):
		guild_id = str(member.guild.id)
		data = self.cache.get(guild_id)
		if not data:
			return
		channel_id = data.get("channel")
		if channel_id:
			channel = member.guild.get_channel(int(channel_id))
			if channel:
				msg_content = data.get("message") or ""
				msg_content = (
					msg_content.replace("{user}", member.mention)
					.replace("{username}", member.name)
					.replace("{guild}", member.guild.name)
					.replace("{membercount}", str(member.guild.member_count))
					.replace("{mention}", member.mention)
					.replace("{discriminator}", member.discriminator)
				)
				embed_data = data.get("embed")
				embeds = []
				if embed_data:
					embeds.append(self.build_embed(embed_data, member))
				try:
					if embeds:
						await channel.send(
							content=msg_content, embeds=embeds
						)
					else:
						await channel.send(content=msg_content)
				except:
					pass
		if data.get("dm_enabled", False):
			dm_msg = data.get("dm_message") or ""
			dm_msg = (
				dm_msg.replace("{user}", member.mention)
				.replace("{username}", member.name)
				.replace("{guild}", member.guild.name)
				.replace("{membercount}", str(member.guild.member_count))
				.replace("{mention}", member.mention)
				.replace("{discriminator}", member.discriminator)
			)
			dm_embed_data = data.get("dm_embed")
			embeds = []
			if dm_embed_data:
				embeds.append(self.build_embed(dm_embed_data, member))
			try:
				if embeds:
					await member.send(
						content=member.mention + " " + dm_msg, embeds=embeds
					)
				else:
					await member.send(content=dm_msg)
			except:
				pass

	@commands.Cog.listener()
	async def on_member_join(self, member):
		await self.send_welcome(member)
		
	@commands.hybrid_group(name="welcome")
	async def welcome(self, ctx):
		pass

	@welcome.command(
		name="help", description="Learn how to setup welcome messages"
	)
	@commands.has_permissions(manage_guild=True)
	async def welcome_help(self, ctx: commands.Context):
		embed = discord.Embed(
			title="Welcome Message Setup Help",
			color=discord.Color.pink(),
			description=(
				"Use the following variables in your welcome messages to personalize them:\n\n"
				"`{user}` - Mentions the user\n"
				"`{username}` - User's name\n"
				"`{guild}` - Server name\n"
				"`{membercount}` - Server member count\n"
				"`{mention}` - Mentions the user\n"
				"`{discriminator}` - User's discriminator (the 4-digit tag)\n\n"
				"**To create an embed:** Use the `/welcome-embed-setup` command.\n\n"
				"**Example plain message:**\n"
				"`Welcome {mention} to {guild}! You are member #{membercount}!`\n\n"
				"**Example embed:**\n"
				"Title: Welcome {username}!\n"
				"Description: Glad to have you at {guild}.\n"
				"Fields: Name: Member Count, Value: {membercount}\n"
				"Footer: Enjoy your stay!"
			),
		)
		embed.set_footer(
			text="Use /welcome-setup or /welcome-embed-setup to set your message."
		)
		await ctx.send(embed=embed)

	@welcome.command(
		name="setup", description="Setup the welcome message (plain text)."
	)
	@commands.has_permissions(manage_guild=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(
		message="The message you want to send when someone joins.",
		channel="The channel you want to send the message to.",
	)
	async def welcome_setup(self, ctx, message: str, channel: discord.TextChannel):
		guild_id = str(ctx.guild.id)
		if await welcome_messages_collection.find_one({"guild_id": guild_id}):
			await ctx.send(
				"Welcome Message has already been set. Use `/welcome-remove` to remove it first.",
				ephemeral=True,
			)
		else:
			await welcome_messages_collection.insert_one(
				{
					"guild_id": str(guild_id),
					"message": str(message),
					"channel": str(channel.id),
				}
			)
			await self.load_guild_welcome(ctx.guild.id)
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Set the welcome message",
				f"Added `{message}` as a welcome message in {channel.mention}",
			)
			await ctx.send(
				"<:switch_on:1326648555414224977> Welcome Message has been set.",
				ephemeral=True,
			)

	@welcome.command(
		name="embed-setup",
		description="Setup a fully customizable embed welcome message.",
	)
	@commands.has_permissions(manage_guild=True)
	@commands.cooldown(1, 30, commands.BucketType.user)
	async def welcome_embed_setup(self, ctx: commands.Context):
		view = WelcomeEmbedSetupButtonView(self.bot, ctx)
		await ctx.send("Click the button below to setup the welcome embed message.", view=view, ephemeral=True)

	@welcome.command(
		name="dm-setup",
		description="Set a DM welcome message, sent to a user's DMs when they join",
	)
	@commands.has_permissions(manage_guild=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(message="The message to send in their DMs")
	async def welcome_dm_setup(self, ctx: commands.Context, message: str):
		guild_id = str(ctx.guild.id)
		await welcome_messages_collection.update_one(
			{"guild_id": guild_id},
			{"$set": {"dm_message": message, "dm_enabled": True}},
			upsert=True,
		)
		await self.load_guild_welcome(ctx.guild.id)
		self.bot.dispatch(
			"modlog",
			ctx.guild.id,
			ctx.author.id,
			"Set the welcome DM",
			f"Added `{message}` as DM welcome message.",
		)
		if ctx.interaction:
			await ctx.interaction.response.send_message(
				"<:switch_on:1326648555414224977> DM Welcome Message has been set.",
				ephemeral=True,
			)
		else:
			await ctx.send(
				"<:switch_on:1326648555414224977> DM Welcome Message has been set."
			)

	@welcome.command(
		name="dm-remove", description="Remove the DM welcome message."
	)
	@commands.has_permissions(manage_guild=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def welcome_dm_remove(self, ctx):
		guild_id = str(ctx.guild.id)
		data = await welcome_messages_collection.find_one(
			{"guild_id": guild_id, "dm_enabled": True}
		)
		if data:
			query = {"guild_id": guild_id}
			await welcome_messages_collection.update_one(
				query, {"$unset": {"dm_message": "", "dm_enabled": ""}}
			)
			await self.load_guild_welcome(ctx.guild.id)
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Removed the DM welcome message",
				f"Removed DM welcome message.",
			)
			if ctx.interaction:
				await ctx.interaction.response.send_message(
					"<:switch_off:1326648782393180282> DM Welcome Message has been removed.",
					ephemeral=True,
				)
			else:
				await ctx.send(
					"<:switch_off:1326648782393180282> DM Welcome Message has been removed."
				)
		else:
			if ctx.interaction:
				await ctx.interaction.response.send_message(
					"DM Welcome Message is not set.", ephemeral=True
				)
			else:
				await ctx.send("DM Welcome Message is not set.")

	@welcome.command(
		name="remove", description="Remove the welcome message."
	)
	@commands.has_permissions(manage_guild=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def welcome_remove(self, ctx):
		guild_id = str(ctx.guild.id)
		if await welcome_messages_collection.find_one({"guild_id": guild_id}):
			query = {"guild_id": str(ctx.guild.id)}
			await welcome_messages_collection.delete_one(
				query, comment="Removed Welcome Message"
			)
			await self.load_guild_welcome(ctx.guild.id)
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Removed the welcome message",
				f"Removed welcome message.",
			)
			await ctx.send(
				"<:switch_off:1326648782393180282> Welcome Message has been removed.",
				ephemeral=True,
			)
		else:
			return await ctx.send("Welcome Message is not set.", ephemeral=True)


async def setup(bot):
	cog = WelcomeMessage_Commands(bot)
	for guild in bot.guilds:
		await cog.load_guild_welcome(guild.id)
	await bot.add_cog(cog)