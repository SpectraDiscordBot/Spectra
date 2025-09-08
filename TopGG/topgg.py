import os
import asyncio
import discord
from discord.ext import commands
import topgg
from dotenv import load_dotenv

load_dotenv()

class TopGG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.token = os.environ.get("TOP_GG")
        self.webhook_auth = os.environ.get("WEBHOOK_AUTH")
        self.topggpy = topgg.Client(self.token)
        self.webhooks = topgg.Webhooks(self.webhook_auth, 6350)
        self.webhooks.on_vote("/dblwebhook")(self.voted)
        self.bot.loop.create_task(self.start_webhooks())
        self.topggpy.autopost_retrieval(self.get_server_count)
        self.topggpy.autopost_success(self.success)
        self.topggpy.autopost_error(self.error)
        self.topggpy.start_autoposter()

    async def start_webhooks(self):
        await self.webhooks.start()
        await asyncio.Event().wait()

    def cog_unload(self):
        self.topggpy.stop_autoposter()
        if self.topggpy.http_session:
            self.bot.loop.create_task(self.topggpy.http_session.close())
        self.webhooks.stop()

    async def voted(self, vote: topgg.Vote):
        user = await self.bot.fetch_user(vote.voter_id)
        embed = discord.Embed(
            title="Thanks!",
            description="Thank you for voting! ♥\nYou can [vote again in 12 hours!](https://top.gg/bot/1279512390756470836/vote)",
            color=discord.Colour.pink()
        )
        button = discord.ui.Button(label="Vote Here!", url="https://top.gg/bot/1279512390756470836/vote")
        view = discord.ui.View()
        view.add_item(button)
        try:
            await user.send(embed=embed, view=view)
        except discord.Forbidden:
            pass
        channel = self.bot.get_channel(1282737932544905282)
        if channel:
            embed = discord.Embed(
                title="New Vote!",
                description=f"**{user}** just voted for Spectra! ♥",
                color=discord.Colour.pink()
            )
            embed.set_author(name=str(user), icon_url=user.display_avatar.url)
            await channel.send(embed=embed, view=view)

    def get_server_count(self) -> int:
        return len(self.bot.guilds)

    def success(self, server_count: int) -> None:
        print(f"Successfully posted {server_count} servers to the API!")

    def error(self, error: topgg.Error) -> None:
        print(f"Error: {error!r}")

async def setup(bot):
    await bot.add_cog(TopGG(bot))