import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from db import autorole_collection

load_dotenv()

class AutoRole_Commands(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.cache = {}

	async def load_guild_roles(self, guild_id):
		data = await autorole_collection.find({"guild_id": str(guild_id)}).to_list(length=None)
		self.cache[str(guild_id)] = [
			{"role_id": int(d["role"]), "ignore_bots": d.get("ignore_bots", False)} for d in data
		]

	@commands.Cog.listener()
	async def on_guild_role_delete(self, role):
		existing = await autorole_collection.find_one({"guild_id": str(role.guild.id), "role": str(role.id)})
		if existing:
			try: 
				await autorole_collection.delete_one({"guild_id": str(role.guild.id), "role": str(role.id)})
				await self.load_guild_roles(role.guild.id)
				self.bot.dispatch(
					"modlog",
					role.guild.id,
					self.bot.user.id,
					"Removed an Auto-Role",
					f"Automatically removed **{role.name}** `{role.id}` as an Auto-Role due to it being deleted.",
				)
			except Exception as e:
				print(e)

	@commands.hybrid_group(name="autorole")
	async def autorole(self, ctx):
		pass
	
	@autorole.command(name="add", description="Add an auto role.")
	@commands.has_permissions(manage_roles=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(auto_role="The role you want to set as auto role.", ignore_bots="Whether to ignore bots when assigning this role.")
	async def autorole_add(self, ctx, auto_role: discord.Role, ignore_bots: bool = False):
		role_id = str(auto_role.id)
		guild_id = str(ctx.guild.id)
		existing_autorole = await autorole_collection.find_one(
			{"guild_id": guild_id, "role": role_id}
		)
		count = await autorole_collection.count_documents({"guild_id": guild_id})

		if count >= 5:
			await ctx.send(
				"You have reached the maximum limit of 5 auto roles. Please remove one first.",
				delete_after=10,
				ephemeral=True
			)
			return
		if existing_autorole:
			await ctx.send("That AutoRole has already been set.", delete_after=10, ephemeral=True)
			return
		else:
			await autorole_collection.insert_one({"guild_id": guild_id, "role": role_id, "ignore_bots": ignore_bots})
			await self.load_guild_roles(ctx.guild.id)
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Added an Auto-Role",
				f"Added {auto_role.mention} as an Auto-Role.\nIgnore Bots: {ignore_bots}",
			)
			await ctx.send(
				f"<:Checkmark:1326642406086410317> **{auto_role.name}** has been successfully added.", ephemeral=True
			)

	@autorole.command(name="remove", description="Remove an auto role.")
	@commands.has_permissions(manage_roles=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(auto_role="The role you want to remove from auto roles.")
	async def autorole_remove(self, ctx, auto_role: discord.Role):
		guild_id = str(ctx.guild.id)
		autorole = await autorole_collection.find_one(
			{"guild_id": guild_id, "role": str(auto_role.id)}
		)

		if autorole:
			await autorole_collection.delete_one(
				{"guild_id": guild_id, "role": str(auto_role.id)}
			)
			await self.load_guild_roles(ctx.guild.id)
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Removed an Auto-Role",
				f"Removed {auto_role.mention} as an Auto-Role.",
			)
			await ctx.send(
				f"<:Checkmark:1326642406086410317> **{auto_role.name}** has been successfully removed.",
				ephemeral=True,
			)
		else:
			await ctx.send("That AutoRole has not been set.", delete_after=10)

	@autorole.command(name="list", description="List all auto roles in the server.")
	async def autorole_list(self, ctx):
		roles = self.cache.get(str(ctx.guild.id), [])
		if roles:
			embed = discord.Embed(
				title="Auto Roles",
				description="\n".join(
					[ctx.guild.get_role(r["role_id"]).mention for r in roles if ctx.guild.get_role(r["role_id"])]
				)
			)
			await ctx.send(embed=embed, ephemeral=True)
		else:
			await ctx.send("No auto roles have been set.", ephemeral=True)

	@commands.Cog.listener()
	async def on_member_join(self, member):
		roles_data = self.cache.get(str(member.guild.id), [])
		roles_to_add = []
		for r in roles_data:
			if r.get("ignore_bots", False) and member.bot:
				continue
			role = member.guild.get_role(r["role_id"])
			if role:
				roles_to_add.append(role)

		if roles_to_add:
			try:
				await member.add_roles(*roles_to_add, reason="Spectra AutoRole")
			except discord.Forbidden:
				pass
			except Exception as e:
				print(f"Failed to add auto roles: {e}")
				await member.send("❌ An error occurred while assigning your auto roles. Please contact the server admin.")

async def setup(bot):
	cog = AutoRole_Commands(bot)
	configs = await autorole_collection.find().to_list(length=None)
	await asyncio.gather(*(cog.load_guild_roles(int(c["guild_id"])) for c in configs))
	await bot.add_cog(cog)