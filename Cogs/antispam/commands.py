import asyncio
import datetime
import discord
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from db import antispam_collection

load_dotenv()

class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}

    anti_spam = commands.CooldownMapping.from_cooldown(5, 10, commands.BucketType.member)
    too_many_violations = commands.CooldownMapping.from_cooldown(3, 30, commands.BucketType.member)

    async def load_guild_config(self, guild_id):
        config = await antispam_collection.find_one({"guild_id": guild_id})
        self.cache[guild_id] = config or {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        antispam_guild = self.cache.get(message.guild.id)
        if antispam_guild is None:
            await self.load_guild_config(message.guild.id)
            antispam_guild = self.cache.get(message.guild.id)
        if not antispam_guild:
            return
        if message.author.top_role.position >= message.guild.me.top_role.position:
            return
        if message.author.id == message.guild.owner_id:
            return
        bucket = self.anti_spam.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        log_channel = self.bot.get_channel(antispam_guild.get("channel_id"))
        if retry_after:
            await message.delete()
            warning_embed = discord.Embed(title="Stop Spamming", description="Stop spamming or you will be timed out.")
            warning_embed.set_footer(text="Anti-Spam")
            await message.channel.send(f"{message.author.mention}", embed=warning_embed, delete_after=10)
            violations = self.too_many_violations.get_bucket(message)
            if violations.update_rate_limit():
                try:
                    try:
                        await message.author.timeout(datetime.timedelta(minutes=5), reason="Spamming")
                    except discord.Forbidden:
                        if log_channel:
                            failed_embed = discord.Embed(title="Failed to mute",
                                                         description=f"I attempted to mute {message.author.mention} for spamming but lacked permission.")
                            failed_embed.add_field(name="User", value=message.author.mention, inline=False)
                            failed_embed.add_field(name="Reason", value="Spamming", inline=False)
                            failed_embed.add_field(name="Attempted at",
                                                   value=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                   inline=False)
                            failed_embed.set_footer(text="Anti-Spam")
                            try:
                                failed_embed.set_thumbnail(url=message.author.display_avatar.url)
                            except:
                                pass
                            await asyncio.sleep(1)
                            await log_channel.send(embed=failed_embed)
                        return
                    await asyncio.sleep(1)
                    dm_embed = discord.Embed(title="Timed Out",
                                             description="You have been timed out for 5 minutes due to spamming.")
                    dm_embed.add_field(name="Server", value=message.guild.name, inline=False)
                    dm_embed.add_field(name="Duration", value="5 minutes", inline=False)
                    dm_embed.add_field(name="Issued At",
                                       value=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                       inline=False)
                    dm_embed.set_footer(text="Anti-Spam")
                    try:
                        await message.author.send(embed=dm_embed)
                    except:
                        pass
                    channel_embed = discord.Embed(title="Timed out",
                                                  description=f"<:modshield:1325613380945444864> **{message.author.name}** has been timed out for spamming.")
                    channel_embed.set_footer(text="Anti-Spam")
                    try:
                        await message.channel.send(embed=channel_embed)
                    except:
                        pass
                except Exception as e:
                    print(e)
                    return
                if log_channel:
                    embed = discord.Embed(title="User Timed Out")
                    embed.add_field(name="User", value=message.author.mention, inline=False)
                    embed.add_field(name="Reason", value="Spamming", inline=False)
                    embed.add_field(name="Issued By", value=self.bot.user.mention, inline=False)
                    embed.add_field(name="Issued At",
                                    value=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    inline=False)
                    try:
                        embed.set_thumbnail(url=message.author.display_avatar.url)
                    except:
                        pass
                    embed.set_footer(text="Anti-Spam")
                    await asyncio.sleep(1)
                    await log_channel.send(embed=embed)
                violations.reset()

    @commands.hybrid_group(name="anti-spam")
    async def antispam(self, ctx):
        pass

    @antispam.command(name="enable", description="Enable spam detection.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(channel="The channel to send logs to")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def anti_spam_enable(self, ctx, channel: discord.TextChannel = None):
        await self.load_guild_config(ctx.guild.id)
        if self.cache.get(ctx.guild.id):
            await ctx.send("Anti-Spam has already been enabled.", ephemeral=True)
            return
        try:
            data = {"guild_id": ctx.guild.id, "enabled": True}
            if channel:
                data["channel_id"] = channel.id
            await antispam_collection.update_one({"guild_id": ctx.guild.id}, {"$set": data}, upsert=True)
            await self.load_guild_config(ctx.guild.id)
            self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Enabled Anti-Spam", "Enabled the Anti-Spam system.")
            await ctx.send("<:switch_on:1326648555414224977> Enabled spam detection.", ephemeral=True)
        except Exception as e:
            print(e)
            await ctx.send("An error occurred while enabling spam detection. Please try again later.", ephemeral=True)

    @antispam.command(name="disable", description="Disable spam detection.")
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def anti_spam_disable(self, ctx):
        await self.load_guild_config(ctx.guild.id)
        if not self.cache.get(ctx.guild.id):
            await ctx.send("Anti-Spam has already been disabled.", ephemeral=True)
            return
        try:
            await antispam_collection.delete_one({"guild_id": ctx.guild.id})
            await self.load_guild_config(ctx.guild.id)
            self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Disabled Anti-Spam", "Disabled the Anti-Spam system.")
            await ctx.send("<:switch_off:1326648782393180282> Disabled spam detection.", ephemeral=True)
        except Exception as e:
            print(e)
            await ctx.send("An error occurred while disabling spam detection. Please try again later.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AntiSpam(bot))