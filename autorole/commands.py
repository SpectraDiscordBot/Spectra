import discord
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from db import *

load_dotenv()

class AutoRole_Commands(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.cache = {} # {guild_id: [role_ids...]}

	async def load_guild_roles(self, guild_id):
		data = await autorole_collection.find({"guild_id": str(guild_id)}).to_list(length=None)
		self.cache[str(guild_id)] = [int(d["role"]) for d in data]

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

	@commands.hybrid_command(name="autorole-add", description="Add an auto role.")
	@commands.has_permissions(manage_roles=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(auto_role="The role you want to set as auto role.")
	async def autorole_add(self, ctx, auto_role: discord.Role):
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
			await autorole_collection.insert_one({"guild_id": guild_id, "role": role_id})
			await self.load_guild_roles(ctx.guild.id)
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Added an Auto-Role",
				f"Added {auto_role.mention} as an Auto-Role.",
			)
			await ctx.send(
				f"<:Checkmark:1326642406086410317> **{auto_role.name}** has been successfully added.", ephemeral=True
			)

	@commands.hybrid_command(name="autorole-remove", description="Remove an auto role.")
	@commands.has_permissions(manage_roles=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
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

	@commands.Cog.listener()
	async def on_member_join(self, member):
		roles = self.cache.get(str(member.guild.id), [])

		if roles:
			for r_id in roles:
				role_obj = member.guild.get_role(r_id)
				if not role_obj:
					print(f"Role ID {r_id} not found in guild {member.guild.id}")
			roles_to_add = [member.guild.get_role(r) for r in roles if member.guild.get_role(r)]
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
	for guild in bot.guilds:
		await cog.load_guild_roles(guild.id)
	await bot.add_cog(cog)