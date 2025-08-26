import asyncio
import datetime
import discord
import os
import motor.motor_asyncio
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from discord.ui import View
from googleapiclient import discovery
from db import *

load_dotenv()

API_KEY = os.getenv("perspective")

client = discovery.build(
    "commentanalyzer",
    "v1alpha1",
    developerKey=API_KEY,
    discoveryServiceUrl="https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1",
    static_discovery=False,
)


def analyze_toxicity(message: str) -> float:
    try:
        analyze_request = {
            "comment": {"text": message},
            "languages": ["en"],
            "requestedAttributes": {"TOXICITY": {}},
        }
        response = client.comments().analyze(body=analyze_request).execute()
        return response["attributeScores"]["TOXICITY"]["summaryScore"]["value"]
    except Exception as e:
        print(f"Error analyzing message: {e}")
        return -1


class AntiToxicity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot        
        self.collection = toxicity_collection

    # Listener
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        guild_id = message.guild.id
        config = await self.collection.find_one({"_id": guild_id})

        if not config or not config.get("enabled", False):
            return

        threshold = config.get("threshold", 0.7)
        toxicity_score = analyze_toxicity(message.content)
        if toxicity_score == -1:
            return

        if toxicity_score > threshold:
            await message.delete()
            dm_embed = discord.Embed(
                title=f"<:modshield:1325613380945444864> Message Removed In {message.guild.name}",
                description="Your message was removed for being too toxic.",
                color=discord.Colour.pink(),
            )
            dm_embed.add_field(
                name="Message Content", value=message.content, inline=False
            )
            dm_embed.add_field(
                name="Toxicity Score", value=f"{toxicity_score}", inline=False
            )
            dm_embed.add_field(
                name="Issued At",
                value=f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                inline=False,
            )
            dm_embed.set_footer(text="Anti-Toxicity", icon_url=self.bot.user.avatar.url)
            try:
                dm_embed.set_thumbnail(url=message.guild.icon.url)
            except:
                dm_embed.set_thumbnail(url=self.bot.user.avatar.url)
            await asyncio.sleep(1)
            try:
                await message.author.send(embed=dm_embed)
            except:
                pass
            try:
                self.bot.dispatch(
                    "modlog",
                    message.guild.id,
                    self.bot.user.id,
                    "Toxic Message Deleted",
                    f"The Anti-Toxicity system has determined that a message sent by {message.author.mention} is toxic.\nToxicity Score: {toxicity_score}\nMessage Content: `{message.content}`",
                )
            except Exception as e:
                print(e)

    # Commands

    @commands.hybrid_group(name="anti-toxicity")
    async def anti_toxicity(self, ctx):
        pass

    @anti_toxicity.command(
        name="enable", description="Enable the anti-toxicity system"
    )
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def enable(self, ctx):
        guild_id = ctx.guild.id
        await self.collection.update_one(
            {"_id": guild_id}, {"$set": {"enabled": True}}, upsert=True
        )
        try:
            self.bot.dispatch(
                "modlog",
                ctx.guild.id,
                ctx.author.id,
                "Enabled a System",
                f"The Anti-Toxicity system has been enabled with a default threshold of `0.7`.",
            )
        except Exception as e:
            print(e)
        embed = discord.Embed(
            title=f"<:switch_on:1326648555414224977> Anti-Toxicity system enabled! Default threshold: 0.7",
            description="",
            color=discord.Colour.pink(),
        )
        await ctx.send(embed=embed, ephemeral=True)

    @anti_toxicity.command(
        name="disable", description="Disable the anti-toxicity system"
    )
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def disable(self, ctx):
        guild_id = ctx.guild.id
        await self.collection.update_one(
            {"_id": guild_id}, {"$set": {"enabled": False}}, upsert=True
        )
        try:
            self.bot.dispatch(
                "modlog",
                ctx.guild.id,
                ctx.author.id,
                "Disabled a System",
                f"The Anti-Toxicity system has been disabled.",
            )
        except Exception as e:
            print(e)
        embed = discord.Embed(
            title="<:switch_off:1326648782393180282> Anti-toxicity system disabled!",
            description="",
            color=discord.Colour.pink(),
        )
        await ctx.send(embed=embed, ephemeral=True)

    @anti_toxicity.command(
        name="configure", description="Set the toxicity threshold"
    )
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def configure(self, ctx, threshold: float):
        if not 0 <= threshold <= 1:
            await ctx.reply(
                "Please provide a threshold between 0 and 1.", ephemeral=True
            )
            return

        guild_id = ctx.guild.id
        await self.collection.update_one(
            {"_id": guild_id}, {"$set": {"threshold": threshold}}, upsert=True
        )
        try:
            self.bot.dispatch(
                "modlog",
                ctx.guild.id,
                ctx.author.id,
                "Updated a System",
                f"The Anti-Toxicity system has been updated, threshold set to `{threshold}`.",
            )
        except Exception as e:
            print(e)
        embed = discord.Embed(
            title=f"<:pencil:1326648942993084426> Toxicity threshold set to {threshold}!",
            description="",
            color=discord.Colour.pink(),
        )
        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AntiToxicity(bot))
