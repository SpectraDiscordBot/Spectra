import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from db import anti_ping_collection

class AntiPing(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.cache = {}
		
	async def load_guild_roles(self, guild_id):
		data = await anti_ping_collection.find({"guild_id": str(guild_id)}).to_list(length=None)
		self.cache[str(guild_id)] = data

	@commands.Cog.listener()
	async def on_message(self, message: discord.Message):
		if message.author.bot or not message.guild:
			return

		guild_id = str(message.guild.id)
		data = self.cache.get(guild_id, [])

		for entry in data:
			role_id = int(entry["role"])
			bypass_role_id = entry.get("bypass_role")

			role = message.guild.get_role(role_id)
			bypass_role = message.guild.get_role(int(bypass_role_id)) if bypass_role_id else None

			if bypass_role and bypass_role in message.author.roles:
				continue

			blocked = False
			for user in message.mentions:
				if user == message.author:
					continue
				if role in user.roles:
					blocked = True
					break

			if role in message.role_mentions and role not in message.author.roles:
				blocked = True

			if message.mention_everyone:
				blocked = True

			if blocked:
				delete_message = bool(entry.get("delete_message", True))
				if delete_message:
					await message.delete()
				embed = discord.Embed(
					title="Anti-Ping",
					description=f"You are not allowed to ping members with the role **{role.name}**." if not message.mention_everyone else "You are not allowed to use @everyone/@here.",
					color=discord.Color.pink()
				)
				try:
					embed.set_thumbnail(url=message.guild.icon.url)
				except:
					pass
				embed.set_footer(text="Powered By Spectra", icon_url=self.bot.user.display_avatar.url)
				await message.channel.send(
					content=f"{message.author.mention}",
					embed=embed,
					delete_after=10
				)
				break
			
	@commands.Cog.listener()
	async def on_guild_role_delete(self, role: discord.Role):
		guild_id = str(role.guild.id)
		role_id = str(role.id)
		deleted_role = await anti_ping_collection.find_one(
			{"guild_id": guild_id, "role": role_id}
		)
		if deleted_role:
			await anti_ping_collection.delete_one(
				{"guild_id": guild_id, "role": role_id}
			)
			self.bot.dispatch(
				"modlog",
				role.guild.id,
				self.bot.user.id,
				"Removed an Anti-Ping role",
				f"Removed <@&{role_id}> as an Anti-Ping role because it was deleted.",
			)
			await self.load_guild_roles(role.guild.id)
		
	
	@commands.Cog.listener()
	async def on_message_edit(self, before: discord.Message, after: discord.Message):
		if before.author.bot or not before.guild:
			return
		if before.content == after.content:
			return

		guild_id = str(before.guild.id)
		data = self.cache.get(guild_id, [])

		for entry in data:
			role_id = int(entry["role"])
			bypass_role_id = entry.get("bypass_role")

			role = before.guild.get_role(role_id)
			bypass_role = before.guild.get_role(int(bypass_role_id)) if bypass_role_id else None

			if bypass_role and bypass_role in before.author.roles:
				continue

			blocked = False
			for user in after.mentions:
				if user == after.author:
					continue
				if role in user.roles:
					blocked = True
					break

			if role in after.role_mentions and role not in after.author.roles:
				blocked = True

			if after.mention_everyone:
				blocked = True

			if blocked:
				delete_message = bool(entry.get("delete_message", True))
				if delete_message:
					await after.delete()
				embed = discord.Embed(
					title="Anti-Ping",
					description=f"You are not allowed to ping members with the role **{role.name}**." if not after.mention_everyone else "You are not allowed to use @everyone/@here.",
					color=discord.Color.pink()
				)
				try:
					embed.set_thumbnail(url=before.guild.icon.url)
				except:
					pass
				embed.set_footer(text="Powered By Spectra", icon_url=self.bot.user.display_avatar.url)
				await before.channel.send(
					content=f"{before.author.mention}",
					embed=embed,
					delete_after=10
				)
				break
			
	@commands.hybrid_group(name="anti-ping")
	async def anti_ping(self, ctx):
		pass
	
	@anti_ping.command(name="add", description="Add a role to the anti-ping list")
	@commands.has_permissions(manage_roles=True)
	@app_commands.describe(role="The role for anti-ping", bypass_role="They will be able to ping the role", delete_message="Delete the message if it has the role pinged")
	async def anti_ping_add(self, ctx: commands.Context, role: discord.Role, bypass_role: discord.Role = None, delete_message: bool = True):
		role_id = str(role.id)
		bypass_role_id = None
		if bypass_role is not None: bypass_role_id = str(bypass_role.id)
		guild_id = str(ctx.guild.id)
		existing_anti_ping_role = await anti_ping_collection.find_one(
			{"guild_id": guild_id, "role": role_id}
		)
		count = await anti_ping_collection.count_documents({"guild_id": guild_id})

		if count >= 5:
			await ctx.send(
				"You have reached the maximum limit of 5 Anti-Ping roles. Please remove one first.",
				delete_after=10,
			)
			return
		if existing_anti_ping_role:
			await ctx.send("That Anti-Ping has already been set.", delete_after=10)
			return
		else:
			await anti_ping_collection.insert_one({"guild_id": guild_id, "role": role_id, "bypass_role": bypass_role_id, "delete_message": delete_message})
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Added an Anti-Ping Role",
				f"Added {role.mention} as an Anti-Ping role.\nBypass Role: {bypass_role.mention if bypass_role is not None else "None"}",
			)
			await ctx.send(
				f"<:Checkmark:1326642406086410317> {role.name} has been successfully added.",
				ephemeral=True
			)
			await self.load_guild_roles(ctx.guild.id)

	@anti_ping.command(name="remove", description="Remove a role from the anti-ping list")
	@commands.has_permissions(manage_roles=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(role="The role to remove from anti-ping")
	async def anti_ping_remove(self, ctx, role: discord.Role):
		guild_id = str(ctx.guild.id)
		anti_ping_role = await anti_ping_collection.find_one(
			{"guild_id": guild_id, "role": str(role.id)}
		)

		if anti_ping_role:
			await anti_ping_collection.delete_one(
				{"guild_id": guild_id, "role": str(role.id)}
			)
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Removed an Anti-Ping role",
				f'Removed <@&{anti_ping_role["role"]}> as an Anti-Ping role.',
			)
			await ctx.send(
				f"<:Checkmark:1326642406086410317> {role.name} has been successfully removed.",
				ephemeral=True,
			)
			await self.load_guild_roles(ctx.guild.id)
		else:
			await ctx.send("That Anti-Ping role has not been set.", delete_after=10)

async def setup(bot):
	cog = AntiPing(bot)
	configs = await anti_ping_collection.find().to_list(length=None)
	await asyncio.gather(*[cog.load_guild_roles(int(c["guild_id"])) for c in configs])
	await bot.add_cog(cog)