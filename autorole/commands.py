import discord
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ.get('MONGO_URI'))
db = client['Spectra']
autorole_collection = db['AutoRole']
welcome_messages_collection = db['WelcomeMessages']


class AutoRole_Commands(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.hybrid_command(name="autorole-add", description="Add an auto role.")
	@commands.has_permissions(administrator=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(auto_role="The role you want to set as auto role.")
	async def autorole_add(self, ctx, auto_role: discord.Role):
		role_id = str(auto_role.id)
		guild_id = str(ctx.guild.id)
		existing_autorole = autorole_collection.find_one({"guild_id": guild_id, "role": role_id})
		count = autorole_collection.count_documents({"guild_id": guild_id})

		if count >= 3:
			await ctx.send("You have reached the maximum limit of 3 auto roles. Please remove one first.", delete_after=10)
			return
		if existing_autorole:
			await ctx.send("That AutoRole has already been set.", delete_after=10)
			return
		else:
			autorole_collection.insert_one({"guild_id": guild_id, "role": role_id})
			channel = ctx.guild.system_channel
			embed = discord.Embed(
				title="Auto Role",
				description=f"Added {auto_role.mention} as an autorole.",
				color=discord.Color.blue()
			)
			try: embed.set_thumbnail(url=ctx.guild.icon.url)
			except: pass
			embed.set_footer(text="Spectra")
			embed.add_field(name="Set By:", value=ctx.author.mention, inline=False)
			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Added an Auto-Role", f"Added {auto_role.mention} as an Auto-Role.")
			await ctx.send(f"<:Checkmark:1326642406086410317> {auto_role.mention} has been successfully added.")
			if channel:
				await channel.send(embed=embed)

	@commands.hybrid_command(name="autorole-remove", description="Remove an auto role.")
	@commands.has_permissions(administrator=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def autorole_remove(self, ctx, auto_role: discord.Role):
		guild_id = str(ctx.guild.id)
		autorole = autorole_collection.find_one({"guild_id": guild_id, "role": str(auto_role.id)})

		if autorole:
			autorole_collection.delete_one({"guild_id": guild_id, "role": str(auto_role.id)})
			channel = ctx.guild.system_channel
			embed = discord.Embed(
				title="Auto Role",
				description=f"{auto_role.mention} has been removed from auto role by {ctx.author.mention}.",
				color=discord.Color.red()
			)
			try: embed.set_thumbnail(url=ctx.guild.icon.url)
			except: pass
			embed.set_footer(text="Spectra")
			self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Removed an Auto-Role", f"Removed {auto_role.mention} as an Auto-Role.")
			await ctx.send(f"<:Checkmark:1326642406086410317> {auto_role.mention} has been successfully removed.", ephemeral=True)
			if channel:
				await channel.send(embed=embed)
		else:
			await ctx.send("That AutoRole has not been set.", delete_after=10)

async def setup(bot):
	await bot.add_cog(AutoRole_Commands(bot))