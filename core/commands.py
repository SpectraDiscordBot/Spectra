import datetime
import discord
from discord.ext import commands
from db import custom_prefix_collection

class CommandPaginator(discord.ui.View):
	def __init__(self, commands, per_page=10):
		super().__init__(timeout=120)
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
			text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
		)
		start = self.current_page * self.per_page
		end = start + self.per_page
		for command in self.commands[start:end]:
			if command.hidden:
				continue
			if command.name == "help":
				continue
			if command.name == "refresh":
				continue
			if command.name == "verify":
				continue
			if command.name == "status":
				continue
			if command.name == "blacklist":
				continue
			if command.name == "unblacklist":
				continue
			if command.name == "jishaku":
				continue

			aliases = (
				", ".join(command.aliases)
				if hasattr(command, "aliases") and command.aliases
				else "None"
			)
			embed.add_field(
				name=f">{command.name}",
				value=command.description + f"\nAliases: {aliases}",
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
	def __init__(self, bot,	 *, timeout=120):
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
				"sync"
			]
		]
		paginator = CommandPaginator(commands)
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
			text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
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
			icon_url="https://i.ibb.co/cKqBfp1/spectra.gif",
		)
		embed.set_thumbnail(url="https://i.ibb.co/cKqBfp1/spectra.gif")
		prefix = await self.get_prefix(self.bot, ctx.message)
		embed.add_field(
			name="Prefix", value=f"`{prefix}`\n`/`", inline=False
		)
		await ctx.send(embed=embed, view=HelpButtons(self.bot), ephemeral=True)


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
		embed = discord.Embed(
			title="Want to support Spectra by voting? Click below!",
			description="[Click Me To Vote!](https://top.gg/bot/1279512390756470836/vote)",
			color=discord.Colour.blue(),
		)
		embed.set_footer(text="Support Spectra For Free!")
		await ctx.send(embed=embed)


	@commands.hybrid_command(name="ping", description="Check if the bot is online.")
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def ping(self, ctx: commands.Context):
		then = ctx.message.created_at.utcnow()
		msg = await ctx.send("Pinging...")
		
		now = datetime.datetime.utcnow()
		time_diff = (now - then).total_seconds() * 1000

		await msg.edit(
			content=f"Pong! 🏓 \nDiscord: `{round(ctx.bot.latency * 1000)}ms`\nBot Latency: `{round(time_diff)}ms`"
		)


	@commands.hybrid_command(name="invite", description="Invite Spectra to your server!")
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def invite(self, ctx: commands.Context):
		embed = discord.Embed(
			title="Invite Spectra to your server!",
			description="[Click Me To Invite!](https://discord.com/oauth2/authorize?client_id=1279512390756470836&permissions=939912256&integration_type=0&scope=bot+applications.commands)",
			color=discord.Colour.blue(),
		)
		embed.set_footer(text="Invite Spectra For Free!")
		await ctx.send(embed=embed)


	@commands.hybrid_command(name="support", description="Support server of the bot")
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def support(self, ctx: commands.Context):
		embed = discord.Embed(
			title="Support Server",
			description="E-mail: spectra.official@protonmail.com\n[Click here to join the support server.](https://discord.gg/fcPF66DubA)",
			color=discord.Color.pink(),
		)
		embed.set_footer(text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif")
		await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
	await bot.add_cog(Core(bot))
