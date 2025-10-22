import asyncio
import datetime
import discord
import os
import re
from discord.ext import commands
from discord import app_commands, ui
from dotenv import load_dotenv
from db import antispam_collection
from typing import Optional, Dict, List

load_dotenv()

class SpamRules:
    def __init__(self):
        self.message_spam = {"enabled": True, "messages": 5, "seconds": 10}
        self.duplicate_spam = {"enabled": False, "messages": 3, "seconds": 10}
        self.mention_spam = {"enabled": False, "max_mentions": 5, "seconds": 10}
        self.emoji_spam = {"enabled": False, "max_emojis": 10, "seconds": 10}
        self.link_spam = {"enabled": False, "max_links": 3, "seconds": 10}
        self.punishment = {"timeout": True, "timeout_duration": 60}
        
    @classmethod
    def from_dict(cls, data: Optional[Dict] = None):
        rules = cls()
        if data:
            if "rules" in data:
                rules_data = data["rules"]
                for rule_type in ["message_spam", "duplicate_spam", "mention_spam", "emoji_spam", "link_spam"]:
                    if rule_type in rules_data:
                        setattr(rules, rule_type, rules_data[rule_type])
                if "punishment" in rules_data:
                    rules.punishment = rules_data["punishment"]
        return rules

    def to_dict(self):
        return {
            "rules": {
                "message_spam": self.message_spam,
                "duplicate_spam": self.duplicate_spam,
                "mention_spam": self.mention_spam,
                "emoji_spam": self.emoji_spam,
                "link_spam": self.link_spam,
                "punishment": self.punishment
            }
        }

class SpamRuleModal(ui.Modal, title="Anti-Spam Rule Configuration"):
    def __init__(self, rule_type: str, current_values: dict):
        super().__init__()
        self.rule_type = rule_type
        
        if rule_type == "message_spam":
            self.messages = ui.TextInput(
                label="Messages per timeframe",
                default=str(current_values.get("messages", 5)),
                required=True,
                min_length=1,
                max_length=3
            )
            self.seconds = ui.TextInput(
                label="Timeframe (seconds)",
                default=str(current_values.get("seconds", 10)),
                required=True,
                min_length=1,
                max_length=3
            )
            self.add_item(self.messages)
            self.add_item(self.seconds)
            
        elif rule_type == "punishment":
            self.timeout_duration = ui.TextInput(
                label="Timeout Duration (minutes)",
                default=str(current_values.get("timeout_duration", 60)),
                required=True,
                min_length=1,
                max_length=4
            )
            self.add_item(self.timeout_duration)

class SetupView(ui.View):
    def __init__(self, cog, rules: SpamRules):
        super().__init__(timeout=300)
        self.cog = cog
        self.rules = rules
        self.log_channel = None
        
    @ui.button(label="Configure Message Spam", style=discord.ButtonStyle.secondary)
    async def message_spam_button(self, interaction: discord.Interaction, button: ui.Button):
        modal = SpamRuleModal("message_spam", self.rules.message_spam)
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        try:
            messages = int(modal.messages.value)
            seconds = int(modal.seconds.value)
            if messages < 1 or seconds < 1:
                raise ValueError
            
            self.rules.message_spam["messages"] = messages
            self.rules.message_spam["seconds"] = seconds
            self.rules.message_spam["enabled"] = True
            
            await interaction.followup.send("Message spam settings updated!", ephemeral=True)
        except ValueError:
            await interaction.followup.send("Please enter valid numbers!", ephemeral=True)
            
    @ui.button(label="Configure Punishment", style=discord.ButtonStyle.secondary)
    async def punishment_button(self, interaction: discord.Interaction, button: ui.Button):
        modal = SpamRuleModal("punishment", self.rules.punishment)
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        try:
            duration = int(modal.timeout_duration.value)
            if duration < 1:
                raise ValueError
                
            self.rules.punishment["timeout_duration"] = duration
            self.rules.punishment["timeout"] = True
            
            await interaction.followup.send("Punishment settings updated!", ephemeral=True)
        except ValueError:
            await interaction.followup.send("Please enter a valid duration!", ephemeral=True)
            
    @ui.button(label="Toggle Duplicate Detection", style=discord.ButtonStyle.secondary)
    async def duplicate_button(self, interaction: discord.Interaction, button: ui.Button):
        self.rules.duplicate_spam["enabled"] = not self.rules.duplicate_spam["enabled"]
        status = "enabled" if self.rules.duplicate_spam["enabled"] else "disabled"
        await interaction.response.send_message(f"Duplicate message detection {status}!", ephemeral=True)
        
    @ui.button(label="Toggle Mention Spam", style=discord.ButtonStyle.secondary)
    async def mention_button(self, interaction: discord.Interaction, button: ui.Button):
        self.rules.mention_spam["enabled"] = not self.rules.mention_spam["enabled"]
        status = "enabled" if self.rules.mention_spam["enabled"] else "disabled"
        await interaction.response.send_message(f"Mention spam detection {status}!", ephemeral=True)
        
    @ui.button(label="Save Configuration", style=discord.ButtonStyle.green, row=4)
    async def save_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.save_config(interaction.guild_id, self.rules, self.log_channel)
        await interaction.response.send_message("Anti-spam configuration saved!", ephemeral=True)
        self.stop()

class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}
        self.warned_users = {}
        self.message_history = {}
        self.spam_rules = {}
        
    async def save_config(self, guild_id: int, rules: SpamRules, log_channel: Optional[discord.TextChannel] = None):
        data = {"guild_id": guild_id, "enabled": True}
        if log_channel:
            data["channel_id"] = log_channel.id
        data.update(rules.to_dict())
        await antispam_collection.update_one({"guild_id": guild_id}, {"$set": data}, upsert=True)
        await self.load_guild_config(guild_id)
        
    def get_spam_rules(self, guild_id: int) -> SpamRules:
        if guild_id not in self.spam_rules:
            self.spam_rules[guild_id] = SpamRules.from_dict(self.cache.get(guild_id))
        return self.spam_rules[guild_id]

    async def load_guild_config(self, guild_id):
        config = await antispam_collection.find_one({"guild_id": guild_id})
        self.cache[guild_id] = config or {}
        if guild_id in self.spam_rules:
            del self.spam_rules[guild_id]

    async def check_spam(self, message: discord.Message, rules: SpamRules) -> bool:
        guild_id = message.guild.id
        author_id = message.author.id
        current_time = datetime.datetime.now().timestamp()
        
        if guild_id not in self.message_history:
            self.message_history[guild_id] = {}
            
        if author_id not in self.message_history[guild_id]:
            self.message_history[guild_id][author_id] = {
                "messages": [],
                "last_message": None
            }
            
        history = self.message_history[guild_id][author_id]
        history["messages"] = [msg for msg in history["messages"] if current_time - msg["time"] <= 10]
        history["messages"].append({"time": current_time, "content": message.content})
        
        if rules.message_spam["enabled"]:
            timeframe = rules.message_spam["seconds"]
            recent_messages = [msg for msg in history["messages"] if current_time - msg["time"] <= timeframe]
            if len(recent_messages) >= rules.message_spam["messages"]:
                return True
                
        if rules.duplicate_spam["enabled"] and history["last_message"]:
            if message.content == history["last_message"] and len(history["messages"]) >= rules.duplicate_spam["messages"]:
                return True
                
        if rules.mention_spam["enabled"] and len(message.mentions) > rules.mention_spam["max_mentions"]:
            return True
            
        if rules.emoji_spam["enabled"]:
            emoji_count = len(re.findall(r'<a?:\w+:\d+>|[\U0001F300-\U0001F9FF]', message.content))
            if emoji_count > rules.emoji_spam["max_emojis"]:
                return True
                
        if rules.link_spam["enabled"]:
            link_count = len(re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message.content))
            if link_count > rules.link_spam["max_links"]:
                return True
                
        history["last_message"] = message.content
        return False

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
            
        rules = self.get_spam_rules(message.guild.id)
        log_channel = self.bot.get_channel(antispam_guild.get("channel_id"))
        
        if await self.check_spam(message, rules):
            await message.delete()
            current_time = datetime.datetime.now().timestamp()
            last_warn = self.warned_users.get(message.author.id, 0)
            
            if current_time - last_warn >= 10:
                warning_embed = discord.Embed(description="Stop spamming or you will be timed out.")
                await message.channel.send(f"{message.author.mention}", embed=warning_embed, delete_after=10)
                self.warned_users[message.author.id] = current_time
                
                try:
                    if rules.punishment["timeout"]:
                        duration = rules.punishment["timeout_duration"]
                        await message.author.timeout(datetime.timedelta(minutes=duration), reason="Spamming")
                        if log_channel:
                            embed = discord.Embed(title="User Timed Out")
                            embed.add_field(name="User", value=message.author.mention, inline=False)
                            embed.add_field(name="Reason", value="Spamming", inline=False)
                            embed.add_field(name="Duration", value=f"{duration} minutes", inline=False)
                            embed.add_field(name="Issued By", value=self.bot.user.mention, inline=False)
                            embed.add_field(name="Issued At", value=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=False)
                            try:
                                embed.set_thumbnail(url=message.author.display_avatar.url)
                            except:
                                pass
                            embed.set_footer(text="Anti-Spam")
                            await log_channel.send(embed=embed)
                except discord.Forbidden:
                    if log_channel:
                        failed_embed = discord.Embed(
                            title="Failed to mute",
                            description=f"I attempted to mute {message.author.mention} for spamming but lacked permission."
                        )
                        failed_embed.set_footer(text="Anti-Spam")
                        await log_channel.send(embed=failed_embed)
                except Exception as e:
                    print(e)
                try:
                    dm_embed = discord.Embed(
                        title="Timed Out",
                        description=f"You have been timed out for {rules.punishment['timeout_duration']} minutes due to spamming."
                    )
                    dm_embed.add_field(name="Server", value=message.guild.name, inline=False)
                    dm_embed.add_field(name="Duration", value=f"{rules.punishment['timeout_duration']} minutes", inline=False)
                    dm_embed.add_field(name="Issued At", value=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), inline=False)
                    dm_embed.set_footer(text="Anti-Spam")
                    try:
                        await message.author.send(embed=dm_embed)
                    except:
                        pass
                        
                    channel_embed = discord.Embed(
                        title="Timed out",
                        description=f"<:modshield:1325613380945444864> **{message.author.name}** has been timed out for spamming."
                    )
                    channel_embed.set_footer(text="Anti-Spam")
                    try:
                        await message.channel.send(embed=channel_embed, delete_after=10)
                    except:
                        pass
                except Exception as e:
                    print(e)

    @commands.hybrid_group(name="anti-spam", description="Commands for managing anti-spam")
    async def antispam(self, ctx):
        pass

    @antispam.command(name="setup", description="Setup spam detection with a configuration wizard.")
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def anti_spam_setup(self, ctx):
        if not ctx.interaction:
            await ctx.send("Due to security reasons, this command cannot be used via prefix.", ephemeral=True)
            return
        rules = self.get_spam_rules(ctx.guild.id)
        view = SetupView(self, rules)
        
        embed = discord.Embed(
            title="Anti-Spam Setup Wizard",
            description=(
                "Configure your anti-spam settings using the buttons below.\n\n"
                "**Available Options:**\n"
                "• Message Spam: Configure message rate limits\n"
                "• Duplicate Detection: Detect repeated messages\n"
                "• Mention Spam: Limit user/role mentions\n"
                "• Punishment: Configure timeout duration\n\n"
                "Click the buttons below to configure each option."
            )
        )
        
        await ctx.send(embed=embed, view=view, ephemeral=True)
        await view.wait()
        
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
            rules = SpamRules()
            await self.save_config(ctx.guild.id, rules, channel)
            self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Enabled Anti-Spam", "Enabled the Anti-Spam system.")
            await ctx.send("<:switch_on:1326648555414224977> Enabled spam detection. Use `/anti-spam setup` to configure rules!", ephemeral=True)
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