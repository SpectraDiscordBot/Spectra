import discord
from discord.ext import commands
from discord import app_commands
from db import anti_ping_collection

class AntiPing(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.Cog.listener()
	async def on_message(self, message: discord.Message):
		if message.author.bot or not message.guild:
			return

		guild_id = str(message.guild.id)
		data = anti_ping_collection.find({"guild_id": guild_id})

		async for entry in data:
			role_id = int(entry["role"])
			bypass_role_id = entry.get("bypass_role")

			role = message.guild.get_role(role_id)
			bypass_role = message.guild.get_role(int(bypass_role_id)) if bypass_role_id else None

			if bypass_role and bypass_role in message.author.roles:
				continue

			blocked = False
			for user in message.mentions:
				if role in user.roles:
					blocked = True
					break

			if role in message.role_mentions:
				blocked = True

			if message.mention_everyone:
				blocked = True

			if blocked:
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
			
	@commands.hybrid_group(name="anti-ping")
	async def anti_ping(self, ctx):
		pass
	
	@anti_ping.command(name="add", description="Add a role to the anti-ping list")
	@commands.has_permissions(manage_roles=True)
	@app_commands.describe(role="The role for anti-ping", bypass_role="They will be able to ping the role")
	async def anti_ping_add(self, ctx: commands.Context, role: discord.Role, bypass_role: discord.Role = None):
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
			await anti_ping_collection.insert_one({"guild_id": guild_id, "role": role_id, "bypass_role": bypass_role_id})
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

	@anti_ping.command(name="remove", description="Remove a role from the anti-ping list")
	@commands.has_permissions(administrator=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
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
				f"Removed <@&{anti_ping_role["role"]}> as an Anti-Ping role.",
			)
			await ctx.send(
				f"<:Checkmark:1326642406086410317> {role.name} has been successfully removed.",
				ephemeral=True,
			)
		else:
			await ctx.send("That Anti-Ping role has not been set.", delete_after=10)

async def setup(bot):
	await bot.add_cog(AntiPing(bot))