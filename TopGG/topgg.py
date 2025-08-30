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
            webhook_auth=os.environ.get("WEBHOOK_AUTH"),
            webhook_port=6350,
        )
        self.update_stats.start()

    def cog_unload(self):
        self.update_stats.cancel()

    async def check_vote(self, user_id: int) -> bool:
        try:
            return await self.topggpy.get_user_vote(user_id)
        except Exception as e:
            print(f"Vote check failed: {e}")
            return False

    @commands.Cog.listener()
    async def on_dbl_vote(self, vote_data):
        embed = discord.Embed(
            title="Thanks!",
            description=f"Thank you for voting! ♥\nYou can [vote again in 12 hours!](https://top.gg/bot/1279512390756470836/vote)",
            color=discord.Colour.pink(),
        )
        embed.add_field(
            name="Why vote?",
            value="Voting helps get Spectra out there and shows support for the bot! It also helps us get more features and improvements!\n\nYou can also join our [Support Server](https://discord.gg/fcPF66DubA) to stay updated with the latest news and updates!",
            inline=False,
        )
        embed.set_footer(
            text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
        )
        button = discord.ui.Button(
            label="Vote Here!", url="https://top.gg/bot/1279512390756470836/vote"
        )
        view = discord.ui.View()
        view.add_item(button)
        user_id = int(vote_data.get("user"))
        user = self.bot.get_user(user_id)
        try:
            await user.send(embed=embed, view=view)
        except discord.Forbidden:
            pass
        except Exception as e:
            print(
                "Failed to send thank you message\n{}: {}".format(type(e).__name__, e)
            )

        channel = self.bot.get_channel(1282737932544905282)
        if channel:
            embed = discord.Embed(
                title="New Vote!",
                description=f"**{user}** just voted for Spectra! ♥",
                color=discord.Colour.pink(),
            )
            embed.set_author(name=str(user), icon_url=user.display_avatar.url)
            embed.set_footer(
                text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
            )
            await channel.send(embed=embed, view=view)

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
