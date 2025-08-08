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
from db import *

load_dotenv()


class Report_Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data["custom_id"]
            guild = interaction.guild
            member = interaction.user

            if not guild or not member:
                await interaction.response.send_message(
                    "Error: Guild or member not found.", ephemeral=True
                )
                return
            
            if custom_id.startswith("reports_ban"):
                user_id = int(custom_id.strip("reports_ban_"))
                user = await self.bot.fetch_user(user_id)
                if user:
                    if not interaction.user.guild_permissions.ban_members:
                        await interaction.response.send_message(
                            "You do not have permission to ban members.", ephemeral=True
                        )
                        return

                    cases = await cases_collection.find_one(
                        {"guild_id": str(interaction.guild.id)}
                    )
                    if not cases:
                        await cases_collection.insert_one(
                            {"guild_id": str(interaction.guild.id), "cases": 0}
                        )
                    async for entry in guild.bans(limit=500):
                        if entry.user.id == user_id:
                            await interaction.response.send_message(
                                "User is already banned.", ephemeral=True
                            )
                            break
                        for item in interaction.message.components[0].children:
                            if isinstance(
                                item, discord.ui.Button
                            ) and item.custom_id.startswith("reports_ban"):
                                item.disabled = True
                        else:
                            await cases_collection.update_one(
                                {"guild_id": str(interaction.guild.id)},
                                {"$set": {"cases": cases["cases"] + 1}},
                            )

                            case = await cases_collection.find_one(
                                {"guild_id": str(interaction.guild.id)}
                            )

                            case_number = case["cases"]

                            await guild.ban(
                                user,
                                reason=f"[#{case_number}] Banned by {interaction.user.name}",
                            )
                            await interaction.response.send_message(
                                f"<:Checkmark:1326642406086410317> [#{case_number}] Banned {user.mention}.",
                                ephemeral=True,
                            )
                            self.bot.dispatch(
                                "modlog",
                                interaction.guild.id,
                                interaction.user.id,
                                "Ban",
                                f"[#{case_number}] Banned {user.mention} by user report.",
                            )
                            for item in interaction.message.components[0].children:
                                if isinstance(
                                    item, discord.ui.Button
                                ) and item.custom_id.startswith("reports_ban"):
                                    item.disabled = True
                if not user:
                    await interaction.response.send_message(
                        "User not found.", ephemeral=True
                    )
                    return
            if custom_id.startswith("reports_kick"):
                user_id = int(custom_id.strip("reports_kick_"))
                user = await self.bot.fetch_user(user_id)
                if user:
                    if not interaction.user.guild_permissions.kick_members:
                        await interaction.response.send_message(
                            "You do not have permission to kick members.", ephemeral=True
                        )
                        return

                    cases = await cases_collection.find_one(
                        {"guild_id": str(interaction.guild.id)}
                    )
                    if not cases:
                        await cases_collection.insert_one(
                            {"guild_id": str(interaction.guild.id), "cases": 0}
                        )

                    if not user in guild.members:
                        await interaction.response.send_message(
                            "User is not in the server.", ephemeral=True
                        )
                        for item in interaction.message.components[0].children:
                            if isinstance(
                                item, discord.ui.Button
                            ) and item.custom_id.startswith("reports_ban"):
                                item.disabled = True
                        pass
                    if user in guild.members:
                        await cases_collection.update_one(
                            {"guild_id": str(interaction.guild.id)},
                            {"$set": {"cases": cases["cases"] + 1}},
                        )

                        case = await cases_collection.find_one(
                            {"guild_id": str(interaction.guild.id)}
                        )

                        case_number = case["cases"]
                        await guild.kick(user, reason=f"Kicked by {interaction.user.name}")
                        await interaction.response.send_message(
                            f"<:Checkmark:1326642406086410317> [#{case_number}] Kicked {user.mention}.",
                            ephemeral=True,
                        )
                        self.bot.dispatch(
                            "modlog",
                            interaction.guild.id,
                            interaction.user.id,
                            "Kick",
                            f"[#{case_number}] Kicked {user.mention} by user report.",
                        )
                        for item in interaction.message.components[0].children:
                            if isinstance(
                                item, discord.ui.Button
                            ) and item.custom_id.startswith("reports_kick"):
                                item.disabled = True
                if not user:
                    await interaction.response.send_message(
                        "User not found.", ephemeral=True
                    )
                    pass
            if custom_id.startswith("reports_warn"):
                user_id = int(custom_id.strip("reports_warn_"))
                user = await self.bot.fetch_user(user_id)
                if user:
                    if not interaction.user.guild_permissions.moderate_members:
                        await interaction.response.send_message(
                            "You do not have permission to moderate members.",
                            ephemeral=True,
                        )
                        return

                    data = await warning_collection.find_one(
                        {"guild_id": str(interaction.guild.id)}
                    )
                    if not data or not data.get("logs_channel"):
                        await interaction.response.send_message(
                            "No warning system has been set up.", ephemeral=True
                        )
                        return

                    cases = await cases_collection.find_one(
                        {"guild_id": str(interaction.guild.id)}
                    )
                    if not cases:
                        await cases_collection.insert_one(
                            {"guild_id": str(interaction.guild.id), "cases": 0}
                        )

                    if not user in guild.members:
                        await interaction.response.send_message(
                            "User is not in the server.", ephemeral=True
                        )
                        for item in interaction.message.components[0].children:
                            if isinstance(
                                item, discord.ui.Button
                            ) and item.custom_id.startswith("reports_ban"):
                                item.disabled = True
                        pass
                    if user in guild.members:
                        await cases_collection.update_one(
                            {"guild_id": str(interaction.guild.id)},
                            {"$set": {"cases": cases["cases"] + 1}},
                        )

                        case = await cases_collection.find_one(
                            {"guild_id": str(interaction.guild.id)}
                        )

                        case_number = case["cases"]
                        logs_channel = interaction.guild.get_channel(
                            int(data.get("logs_channel"))
                        )
                        await warning_collection.insert_one(
                            {
                                "guild_id": str(interaction.guild.id),
                                "user_id": str(user.id),
                                "reason": "By user report",
                                "issued_by": str(interaction.user.id),
                                "issued_at": str(datetime.datetime.utcnow()),
                                "case_number": case_number,
                            }
                        )
                        warn_log = discord.Embed(
                            title=f"Warning issued to {user.name}",
                            description="",
                            color=discord.Color.pink(),
                        )
                        warn_log.add_field(
                            name="Case Number:", value=f"CASE #{case_number}", inline=False
                        )
                        warn_log.add_field(
                            name="Reason:", value="By user report", inline=False
                        )
                        warn_log.add_field(
                            name="Issued By:",
                            value=f"<@{interaction.user.id}>",
                            inline=False,
                        )
                        warn_log.add_field(
                            name="Issued At:",
                            value=f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                            inline=False,
                        )

                        try:
                            warn_log.set_thumbnail(url=user.avatar.url)
                        except:
                            pass

                        warn_log.set_footer(text="Warning System")
                        await interaction.response.send_message(
                            f"<:Checkmark:1326642406086410317> `[CASE #{case_number}]` Warning issued to {user.mention} by user report.",
                            ephemeral=True,
                        )
                        try:
                            await logs_channel.send(embed=warn_log)
                        except:
                            pass
                        for item in interaction.message.components[0].children:
                            if isinstance(
                                item, discord.ui.Button
                            ) and item.custom_id.startswith("reports_warn"):
                                item.disabled = True
                if not user:
                    await interaction.response.send_message(
                        "User not found.", ephemeral=True
                    )
                    pass
            else:
                pass

        else:
            pass

    @commands.hybrid_command(
        name="enable-reports", description="Setup the user report system"
    )
    @commands.has_permissions(manage_guild=True)
    async def setup_reports(self, ctx, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        if report_collection.find_one({"guild_id": guild_id}):
            report_collection.update_one(
                {"guild_id": guild_id}, {"$set": {"channel_id": channel.id}}
            )
        else:
            report_collection.insert_one(
                {"guild_id": guild_id, "channel_id": channel.id}
            )
            await ctx.send(
                f"User reports have been enabled in {channel.mention}.", ephemeral=True
            )
            try:
                self.bot.dispatch(
                    "modlog",
                    ctx.guild.id,
                    ctx.author.id,
                    "Enabled a System",
                    f"The reports system has been enabled, and report logs will be sent to {channel.mention}.",
                )
            except Exception as e:
                print(e)

    @commands.hybrid_command(
        name="disable-reports", description="Setup the user report system"
    )
    @commands.has_permissions(manage_guild=True)
    async def disable_reports(self, ctx):
        guild_id = str(ctx.guild.id)
        if not report_collection.find_one({"guild_id": guild_id}):
            await ctx.send("User reports are already disabled.", ephemeral=True)
        else:
            report_collection.delete_one({"guild_id": guild_id})
            await ctx.send(f"User reports have been disabled.", ephemeral=True)
            try:
                self.bot.dispatch(
                    "modlog",
                    ctx.guild.id,
                    ctx.author.id,
                    "Disabled a System",
                    f"The reports system has been disabled.",
                )
            except Exception as e:
                print(e)

    @commands.hybrid_command(
        name="report-user",
        description="Report a user to server moderators.",
        aliases=["report"],
    )
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def report_user(
        self, ctx, user: discord.User, *, reason: str, proof: discord.Attachment = None
    ):
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
            color=discord.Colour.pink(),
        )
        embed.add_field(
            name="User", value=f"{user.mention} `({user.name})`", inline=False
        )
        embed.add_field(name="User ID", value=user.id, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(
            name="Proof",
            value=proof.url if proof else "No proof provided.",
            inline=False,
        )
        embed.add_field(
            name="Timestamp",
            value=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            inline=False,
        )
        embed.set_footer(text="Spectra")
        if user.avatar:
            embed.set_thumbnail(url=user.avatar.url)

        class ReportButtons(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
                self.add_item(
                    discord.ui.Button(
                        label="Ban",
                        style=discord.ButtonStyle.danger,
                        custom_id=f"reports_ban_{user.id}",
                    )
                )
                self.add_item(
                    discord.ui.Button(
                        label="Kick",
                        style=discord.ButtonStyle.danger,
                        custom_id=f"reports_kick_{user.id}",
                    )
                )
                self.add_item(
                    discord.ui.Button(
                        label="Warn",
                        style=discord.ButtonStyle.danger,
                        custom_id=f"reports_warn_{user.id}",
                    )
                )

        try:
            channel = self.bot.get_channel(int(report_data["channel_id"]))
            if not channel:
                return await ctx.send(
                    "Couldn't find the report channel, please contact a server admin.",
                    ephemeral=True,
                )

            await channel.send(embed=embed, view=ReportButtons())

            success_message = f"<:Checkmark:1326642406086410317> Report successfully sent for user {user.mention}"
            if ctx.interaction:
                await ctx.interaction.response.send_message(
                    success_message, ephemeral=True
                )
            elif ctx.message:
                try:
                    await ctx.author.send(f"{success_message} in **{ctx.guild.name}**.")
                except discord.Forbidden:
                    pass

            if ctx.message:
                try:
                    await ctx.message.delete()
                except:
                    pass

        except Exception as e:
            error_message = "Failed to send report. Please contact a server admin."
            if ctx.interaction:
                await ctx.interaction.response.send_message(
                    error_message, ephemeral=True
                )
            elif ctx.message:
                await ctx.send(error_message)
            raise e


async def setup(bot):
    await bot.add_cog(Report_Commands(bot))
