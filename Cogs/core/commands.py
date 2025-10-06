import datetime
import discord
import time
import psutil
from discord.ext import commands
from db import custom_prefix_collection, db

class CommandPaginator(discord.ui.View):
	def __init__(self, bot, commands, per_page=10):
		super().__init__(timeout=120)
		self.bot = bot
		self.commands = commands
		self.per_page = per_page
		self.current_page = 0
		
	def update_buttons(self):
		self.previous_page.disabled = self.current_page == 0
		self.next_page.disabled = (self.current_page + 1) * self.per_page >= len(self.commands)

	def get_embed(self):
		embed = discord.Embed(
			title="List of Commands", description="", color=discord.Color.pink()
		)
		embed.set_footer(
			text="Spectra", icon_url=self.bot.user.display_avatar.url
		)
		start = self.current_page * self.per_page
		end = start + self.per_page
		def iter_commands(commands_list):
			commands_list = sorted(commands_list, key=lambda c: c.name.lower())
			for cmd in commands_list:
				if cmd.hidden:
					continue
				if cmd.name in ["help", "refresh", "verify", "status", "blacklist", "unblacklist", "jishaku", "restart"]:
					continue

				if isinstance(cmd, discord.ext.commands.Group):
					yield from iter_commands(cmd.commands)
				else:
					yield cmd

		all_commands = list(iter_commands(self.commands))

		for command in all_commands[start:end]:
			parts = []

			if getattr(command, "aliases", None):
				parts.append(f"Aliases: {', '.join(command.aliases)}")

			if command.clean_params:
				args = []
				for name, param in command.clean_params.items():
					if param.default is param.empty:
						args.append(f"<{name}>")
					else:
						args.append(f"[{name}={param.default}]")
				parts.append(f"Arguments: {' '.join(args)}")

			desc = command.description or "No description"
			value = desc + ("\n" + "\n".join(parts) if parts else "")

			embed.add_field(
				name=f">{command.qualified_name}",
				value=value,
				inline=False,
			)
		return embed

	@discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
	async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
		if self.current_page > 0:
			self.current_page -= 1
		self.update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)

	@discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
	async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
		if (self.current_page + 1) * self.per_page < len(self.commands):
			self.current_page += 1
		self.update_buttons()
		await interaction.response.edit_message(embed=self.get_embed(), view=self)
			

class HelpButtons(discord.ui.View):
	def __init__(self, bot,	 *, timeout=300):
		super().__init__(timeout=timeout)
		self.bot = bot
		self.add_item(discord.ui.Button(
			label="Support Server",
			style=discord.ButtonStyle.link,
			url="https://discord.gg/fcPF66DubA"
		))
		self.add_item(discord.ui.Button(
			label="Documentation",
			style=discord.ButtonStyle.link,
			url="https://www.notion.so/spectra-docs/Introduction-17f36833aca1806bbd11cd5faa438fef"
		))
		
	async def on_timeout(self):
		for child in self.children:
			if isinstance(child, discord.ui.Button) and child.style != discord.ButtonStyle.link:
				child.disabled = True
		await self.message.edit(view=self)

	@discord.ui.button(label="List of Commands", style=discord.ButtonStyle.primary)
	async def first_page(
		self, interaction: discord.Interaction, button: discord.ui.Button
	):
		commands = [
			command
			for command in self.bot.commands
			if command.name
			not in [
				"help",
				"refresh",
				"verify",
				"load",
				"unload",
				"biggest_server",
				"shutdown",
				"blacklist",
				"unblacklist",
				"servers",
				"sync",
				"botteds"
			]
		]
		paginator = CommandPaginator(self.bot, commands)
		await interaction.response.send_message(
			embed=paginator.get_embed(), view=paginator, ephemeral=True
		)

	@discord.ui.button(label="Uptime", style=discord.ButtonStyle.primary) 
	async def uptime(self, interaction: discord.Interaction, button: discord.ui.Button):
		startTime = getattr(self.bot, "start_time", None)
		if not startTime:
			await interaction.response.send_message("Start time not set yet.", ephemeral=True)
			return

		now = datetime.datetime.now(datetime.timezone.utc)
		uptime_seconds = int((now - startTime).total_seconds())
		start_unix = int(startTime.timestamp())

		# >24h = full time <24h = full date should be formatted this time.
		if uptime_seconds < 86400:
			timestamp = f"<t:{start_unix}:R>"
		else:
			timestamp = f"<t:{start_unix}:F>"

		embed = discord.Embed(
			title="Uptime",
			description=f"The bot has been online since {timestamp}",
			color=discord.Color.pink()
		)
		embed.set_footer(
			text="Spectra", icon_url=self.bot.user.display_avatar.url
		)
		await interaction.response.send_message(embed=embed, ephemeral=True)

class Core(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.bot.start_time = datetime.datetime.now(datetime.timezone.utc)

	async def get_prefix(self, Client, message):
		if not message.guild:
			return ">"

		prefix_data = await custom_prefix_collection.find_one({"guild_id": str(message.guild.id)})
		return prefix_data["prefix"] if prefix_data else ">"
	
	@commands.Cog.listener()
	async def on_ready(self):
		if not hasattr(self.bot, "start_time"):
			self.bot.start_time = datetime.datetime.now(datetime.timezone.utc)

	@commands.hybrid_command(name="help", description="Get help with the bot.")
	@commands.cooldown(1, 15, commands.BucketType.user)
	async def help(self, ctx: commands.Context):
		embed = discord.Embed(
			title="Help Menu", description="Get assistance or information about Spectra.\n\n> List of Commands - View All of Spectra's Commands and Features.\n> Uptime - See How Long Spectra Has Been Up For.\n> Support Server - Spectra's Support Server If You Need Help\n> Documentation - View All of Spectra's Features and Uses", color=discord.Color.pink(), timestamp=datetime.datetime.now(datetime.timezone.utc)
		)
		embed.set_author(
			name=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url
		)
		embed.set_footer(
			text="Made with ❤ by brutiv & tyler.hers",
			icon_url=self.bot.user.display_avatar.url,
		)
		embed.set_thumbnail(url=self.bot.user.display_avatar.url)
		prefix = await self.get_prefix(self.bot, ctx.message)
		embed.add_field(
			name="Prefix", value=f"`{prefix}`\n`/`", inline=False
		)
		view = HelpButtons(self.bot)
		msg = await ctx.send(embed=embed, view=view, ephemeral=True)
		view.message = msg


	@commands.hybrid_command(
		name="set-prefix", description="Set a custom prefix for the server."
	)
	@commands.has_permissions(manage_guild=True)
	@commands.cooldown(1, 5)
	async def set_prefix(self, ctx: commands.Context, prefix: str):
		if not 1 <= len(prefix) <= 3:
			await ctx.send("Prefix must be 1–3 characters.", ephemeral=True)
			return

		gid = str(ctx.guild.id)

		await custom_prefix_collection.update_one(
			{"guild_id": gid},
			{"$set": {"prefix": prefix}},
			upsert=True
		)

		ctx.bot.prefix_cache[gid] = prefix

		try:
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Set a new prefix",
				f"Set prefix to {prefix} for this server.",
			)
		except Exception as e:
			print(e)

		await ctx.send(f"Prefix set to `{prefix}` for this server.")


	@commands.hybrid_command(name="vote", description="Vote for Spectra!")
	@commands.cooldown(1, 15, commands.BucketType.user)
	async def vote(self, ctx: commands.Context):
		class VoteView(discord.ui.View):
			def __init__(self):
				super().__init__(timeout=None)
				self.add_item(discord.ui.Button(
					label="Click Me To Vote!",
					style=discord.ButtonStyle.link,
					url="https://top.gg/bot/1279512390756470836/vote"
				))

		embed = discord.Embed(
			title="Want to support Spectra by voting?",
			description="Click the button below to vote for Spectra!",
			color=discord.Color.pink(),
		)
		await ctx.send(embed=embed, view=VoteView())


	@commands.hybrid_command(name="ping", description="Check if the bot is online.")
	@commands.cooldown(1, 10, commands.BucketType.user)
	async def ping(self, ctx: commands.Context):
		start = time.perf_counter()
		msg = await ctx.send("Pinging...", ephemeral=True)

		discord_latency = round(ctx.bot.latency * 1000)
		bot_latency = round((time.perf_counter() - start) * 1000)

		try:
			db_start = time.perf_counter()
			await db.command("ping")
			db_latency = round((time.perf_counter() - db_start) * 1000)
		except Exception:
			db_latency = "Not operational"
		
		embed = discord.Embed(
			title="Pong! 🏓",
		)
		embed.add_field(name="Discord API Latency", value=f"{discord_latency}ms")
		embed.add_field(name="Database Latency", value=f"{db_latency}ms")
		embed.add_field(name="Bot Latency", value=f"{bot_latency}ms")
		process = psutil.Process()
		memory_info = process.memory_info()
		memory_usage_mb = memory_info.rss / (1024 * 1024)
		embed.add_field(name="Memory Usage", value=f"{memory_usage_mb:.2f} MB")
		cpu_usage = psutil.cpu_percent(interval=0.0)
		embed.add_field(name="CPU Usage", value=f"{cpu_usage}%")
		embed.set_footer(text=f"Developed by Brutiv")
		embed.set_author(
			name=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url
		)
		embed.set_thumbnail(url=self.bot.user.display_avatar.url)
		await msg.edit(content="", embed=embed)


	@commands.hybrid_command(name="invite", description="Invite Spectra to your server!")
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def invite(self, ctx: commands.Context):
		class InviteView(discord.ui.View):
			def __init__(self):
				super().__init__(timeout=None)
				self.add_item(discord.ui.Button(label="Invite", url="https://discord.com/oauth2/authorize?client_id=1279512390756470836&permissions=939912256&integration_type=0&scope=bot+applications.commands"))
				self.add_item(discord.ui.Button(label="Website", url="https://spectrabot.pages.dev"))
				self.add_item(discord.ui.Button(label="Support Server", url="https://discord.gg/fcPF66DubA"))

		embed = discord.Embed(
			title="Invite Spectra",
			description="Powerful moderation, role management, and server stats all in one place. 100% free and open source."
		)
		embed.add_field(
			name="Why should I invite Spectra?",
			value="• All-in-one server management: Powerful moderation, role management, and server stats in one place.\n\n• Complete moderation suite: warnings, bans, anti-spam, anti-toxicity, and anti-ping protection with moderation logs.\n\n• Advanced role management: auto-roles, reaction roles, and customizable role attributes.\n\n• Server stats: dynamic counters for members, bots, boosts, channels, roles, emojis, stickers, and threads.\n\n• Easy & flexible: designed to be simple to use even for large servers.\n\n• Free & open source - add to Discord or learn more by clicking below or [visiting our website](https://spectrabot.pages.dev).",
			inline=False
		)
		embed.set_thumbnail(url=self.bot.user.display_avatar.url)
		embed.set_footer(text="Spectra", icon_url=self.bot.user.display_avatar.url)
		await ctx.send(embed=embed, view=InviteView(), ephemeral=True)


	@commands.hybrid_command(name="botteds", description="Check newest joined guild for botting.")
	@commands.is_owner()
	async def botteds(self, ctx: commands.Context):
		if not self.bot.guilds:
			await ctx.send("The bot is not in any guilds.", ephemeral=True)
			return

		g = max(self.bot.guilds, key=lambda g: g.me.joined_at)
		member_count = len(g.members)
		bot_count = sum(1 for m in g.members if m.bot)
		human_count = member_count - bot_count
		bot_ratio = (bot_count / member_count) if member_count else 0
		is_bot_farm = bot_ratio > 0.5

		status = "⚠️ Likely a bot farm" if is_bot_farm else "✅ Normal server"
		joined_at = g.me.joined_at
		embed = discord.Embed(color=discord.Color.pink())
		embed.title = "Newest Guild Bot-Ratio Check"
		embed.description = (
			f"Newest guild: {g.name} ({g.id})\n"
			f"Joined at: {joined_at}\n"
			f"Members: {member_count}\n"
			f"Humans: {human_count}, Bots: {bot_count}\n"
			f"Bot ratio: {bot_ratio:.2%}\n\n"
			f"{status}"
		)
		await ctx.send(embed=embed, ephemeral=True)


	@commands.hybrid_command(name="support", description="Support server of the bot")
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def support(self, ctx: commands.Context):
		embed = discord.Embed(
			title="Support Server",
			description="E-mail: spectra.official@protonmail.com\n[Click here to join the support server.](https://discord.gg/fcPF66DubA)",
			color=discord.Color.pink(),
		)
		embed.set_footer(text="Spectra", icon_url=self.bot.user.display_avatar.url)
		await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
	await bot.add_cog(Core(bot))
