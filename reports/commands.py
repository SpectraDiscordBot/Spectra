import asyncio
import datetime
from email import utils
import discord
import os
from discord.ext import commands
from discord import app_commands, utils
from dotenv import load_dotenv
from pymongo import MongoClient
from humanfriendly import parse_timespan, InvalidTimespan

load_dotenv()

client = MongoClient(os.environ.get('MONGO_URI'))
db = client['Spectra']
report_collection = db["Reports"]

class Report_Commands(commands.Cog):
	def __init__(self, bot):
		self.bot = bot		

	@commands.hybrid_command(name="enable-reports", description="Setup the user report system")
	@commands.has_permissions(manage_guild=True)
	async def setup_reports(self, ctx, channel: discord.TextChannel):
		guild_id = str(ctx.guild.id)
		if report_collection.find_one({"guild_id": guild_id}):
			report_collection.update_one({"guild_id": guild_id}, {"$set": {"channel_id": channel.id}})
		else:
			report_collection.insert_one({"guild_id": guild_id, "channel_id": channel.id})
			await ctx.send(f"User reports have been enabled in {channel.mention}.", ephemeral=True)
			try: self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Enabled a System", f"The reports system has been enabled, and report logs will be sent to {channel.mention}.")
			except Exception as e: print(e)

	@commands.hybrid_command(name="disable-reports", description="Setup the user report system")
	@commands.has_permissions(manage_guild=True)
	async def disable_reports(self, ctx):
		guild_id = str(ctx.guild.id)
		if not report_collection.find_one({"guild_id": guild_id}):
			await ctx.send("User reports are already disabled.", ephemeral=True)
		else:
			report_collection.delete_one({"guild_id": guild_id})
			await ctx.send(f"User reports have been disabled.", ephemeral=True)
			try: self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Disabled a System", f"The reports system has been disabled.")
			except Exception as e: print(e)
			

	@commands.hybrid_command(name="report-user", description="Report a user to server moderators.", aliases=["report"])
	@commands.cooldown(1, 5, commands.BucketType.user)
	async def report_user(self, ctx, user: discord.User, *, reason: str, proof: discord.Attachment = None):
		guild_id = str(ctx.guild.id)
		report_data = report_collection.find_one({"guild_id": guild_id})

		if ctx.message and ctx.message.attachments:
			proof = ctx.message.attachments[0]

		if not report_data:
			response = "User reports are not enabled in this server."
			if ctx.interaction:
				await ctx.interaction.response.send_message(response, ephemeral=True)
			elif ctx.message:
				try:
					await ctx.author.send(response)
				except discord.Forbidden:
					pass
			return

		embed = discord.Embed(
			title="New Report",
			description=f"{ctx.author.mention} has reported {user.mention}",
			color=discord.Colour.pink()
		)
		embed.add_field(name="User", value=f"{user.mention} `({user.name})`", inline=False)
		embed.add_field(name="User ID", value=user.id, inline=False)
		embed.add_field(name="Reason", value=reason, inline=False)
		embed.add_field(name="Proof", value=proof.url if proof else "No proof provided.", inline=False)
		embed.add_field(name="Timestamp", value=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=False)
		embed.set_footer(text="Spectra")
		if user.avatar:
			embed.set_thumbnail(url=user.avatar.url)

		class ReportButtons(discord.ui.View):
			def __init__(self):
				super().__init__(timeout=None)
				self.add_item(discord.ui.Button(label="Ban", style=discord.ButtonStyle.danger, custom_id=f"reports_ban_{user.id}"))
				self.add_item(discord.ui.Button(label="Kick", style=discord.ButtonStyle.danger, custom_id=f"reports_kick_{user.id}"))
				self.add_item(discord.ui.Button(label="Warn", style=discord.ButtonStyle.danger, custom_id=f"reports_warn_{user.id}"))

		try:
			channel = self.bot.get_channel(int(report_data["channel_id"]))
			if not channel:
				return await ctx.send("Couldn't find the report channel, please contact a server admin.", ephemeral=True)

			await channel.send(embed=embed, view=ReportButtons())

			success_message = f"<:Checkmark:1326642406086410317> Report successfully sent for user {user.mention}"
			if ctx.interaction:
				await ctx.interaction.response.send_message(success_message, ephemeral=True)
			elif ctx.message:
				try:
					await ctx.author.send(f"{success_message} in **{ctx.guild.name}**.")
				except discord.Forbidden:
					pass

			if ctx.message:
				try: await ctx.message.delete()
				except: pass

		except Exception as e:
			error_message = "Failed to send report. Please contact a server admin."
			if ctx.interaction:
				await ctx.interaction.response.send_message(error_message, ephemeral=True)
			elif ctx.message:
				await ctx.send(error_message)
			raise e


async def setup(bot):
	await bot.add_cog(Report_Commands(bot))