import discord
import aiohttp
from discord.ext import commands

class GitHub(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	@commands.hybrid_command(name="release-notes", description="Get the latest release notes for Spectra.")
	@commands.cooldown(1, 10, commands.BucketType.user)
	async def release_notes(self, ctx: commands.Context):
		await ctx.defer()

		try:
			async with aiohttp.ClientSession() as session:
				async with session.get(
					"https://api.github.com/repos/SpectraDiscordBot/Spectra/releases/latest"
				) as response:
					if response.status != 200:
						embed = discord.Embed(
							title="Error",
							description="Failed to fetch release notes. Please try again later.",
							color=discord.Color.red()
						)
						await ctx.send(embed=embed, ephemeral=True)
						return

					data = await response.json()

			tag_name = data.get("tag_name", "Unknown")
			release_name = data.get("name", "No title")
			body = data.get("body", "No description available.")
			published_at = data.get("published_at", "")
			html_url = data.get("html_url", "")

			date_str = ""
			if published_at:
				try:
					from datetime import datetime
					dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
					date_str = f"Published: <t:{int(dt.timestamp())}:F>"
				except:
					date_str = f"Published: {published_at}"

			embed = discord.Embed(
				title=f"{release_name}",
				description=f"**Version:** {tag_name}\n{date_str}",
				color=discord.Color.pink(),
				url=html_url
			)

			clean_body = body.replace('\r\n', '\n').strip()
			clean_body = clean_body.replace('##', '')
			if len(clean_body) > 4000:
				clean_body = clean_body[:3997] + "..."

			embed.add_field(
				name="Release Notes",
				value=clean_body or "No release notes available.",
				inline=False
			)

			embed.set_footer(text="Spectra", icon_url=self.bot.user.display_avatar.url)

			await ctx.send(embed=embed, ephemeral=True)

		except Exception as e:
			embed = discord.Embed(
				title="Error",
				description="An unexpected error occurred while fetching release notes.",
				color=discord.Color.red()
			)
			embed.set_footer(text=f"Error: {str(e)[:1000]}")
			await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
	await bot.add_cog(GitHub(bot))