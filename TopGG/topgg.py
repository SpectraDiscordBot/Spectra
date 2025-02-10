from discord.ext import commands, tasks

import os

import discord

import topgg

from dotenv import load_dotenv

load_dotenv()


class TopGG(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.token = os.environ.get("TOP_GG")
        self.topggpy = topgg.DBLClient(
            self.bot,
            self.token,
            webhook_path="/dblwebhook",
            webhook_auth="youshallnotpass",
            webhook_port=5000,
        )
        self.update_stats.start()

    def cog_unload(self):
        self.update_stats.cancel()

    @commands.Cog.listener()
    async def on_topgg_vote(self, vote_data):
        embed = discord.Embed(
            title="Thanks!",
            description=f"Thank you for voting! ♥",
            color=discord.Colour.pink(),
        )
        embed.set_footer(
            text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
        )
        user_id = vote_data.get("user")
        user = self.bot.get_user(user_id)
        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass
        except Exception as e:
            print(
                "Failed to send thank you message\n{}: {}".format(type(e).__name__, e)
            )

    @tasks.loop(minutes=30)
    async def update_stats(self):
        await self.bot.wait_until_ready()
        try:
            server_count = len(self.bot.guilds)
            await self.topggpy.post_guild_count(server_count)
            print("Posted server count ({})".format(server_count))
        except Exception as e:
            print("Failed to post server count\n{}: {}".format(type(e).__name__, e))


async def setup(bot):
    await bot.add_cog(TopGG(bot))
