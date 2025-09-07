import asyncio
import datetime
import discord
import os
from discord.ext import commands
from discord import app_commands, utils
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from humanfriendly import parse_timespan, InvalidTimespan
from db import cases_collection

load_dotenv()

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def discord_timestamp(val, style="F"):
        if isinstance(val, str):
            dt = datetime.datetime.fromisoformat(val)
        else:
            dt = val
        return f"<t:{int(dt.timestamp())}:{style}>"

    @commands.hybrid_command(name="purge", description="Purges messages from the channel.")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def purge(self, ctx, limit: int = 5, *, reason: str = None):
        await ctx.defer(ephemeral=True)
        if limit > 100:
            await ctx.send("Currently, you can only delete up to 100 messages.", ephemeral=True)
            return
        if limit < 1:
            await ctx.send("Please specify a number between 1 and 100.", ephemeral=True)
            return
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass

        messages = [msg async for msg in ctx.channel.history(limit=limit)]
        messages_to_delete = [m for m in messages if m.created_at > discord.utils.utcnow() - datetime.timedelta(days=14)]
        skipped = [m for m in messages if m.created_at <= discord.utils.utcnow() - datetime.timedelta(days=14)]

        if messages_to_delete:
            await ctx.channel.delete_messages(messages_to_delete)
        deleted_count = len(messages_to_delete)
        embed = discord.Embed(
            title="Purge Summary",
            description=f"Purged {deleted_count} messages from {ctx.channel.mention}",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow(),
        )
        embed.add_field(name="Deleted by", value=ctx.author.mention, inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided.", inline=False)
        if skipped:
            skipped_preview = "\n".join([f"**{msg.author}**: {discord.utils.escape_markdown((msg.content[:50] + "...") if len(msg.content) > 50 else msg.content)}" for msg in skipped[:5] if msg.content])
            embed.add_field(name="Skipped Messages (Older than 14 days)", value=skipped_preview or "No skipped messages.", inline=False)
        self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Purge", f"Purged {deleted_count} messages in {ctx.channel.mention}\nReason: {reason}")
        try:
            await ctx.send(f"<:Checkmark:1326642406086410317>", embed=embed, ephemeral=True, delete_after=5)
        except discord.HTTPException:
            pass

    async def _get_next_case_id(self, guild_id):
        doc = await cases_collection.find_one({"guild_id": str(guild_id)})
        if not doc:
            await cases_collection.insert_one({"guild_id": str(guild_id), "cases": [], "last_case_id": 0})
            return 1
        return doc.get("last_case_id", 0) + 1

    async def _add_case(self, guild_id, case):
        await cases_collection.update_one(
            {"guild_id": str(guild_id)},
            {"$push": {"cases": case}, "$set": {"last_case_id": case["case_id"]}},
            upsert=True
        )

    async def _edit_case(self, guild_id, case_id, editor_id, new_data):
        doc = await cases_collection.find_one({"guild_id": str(guild_id)})
        if not doc:
            return False
        cases = doc.get("cases", [])
        for i, c in enumerate(cases):
            if c["case_id"] == case_id:
                history = c.get("edit_history", [])
                history.append({"editor_id": editor_id, "timestamp": datetime.datetime.utcnow().isoformat(), "old_data": {k: c[k] for k in new_data}})
                for k, v in new_data.items():
                    c[k] = v
                c["edit_history"] = history
                cases[i] = c
                await cases_collection.update_one({"guild_id": str(guild_id)}, {"$set": {"cases": cases}})
                return True
        return False
        
    @commands.hybrid_command(name="case", description="View a moderation case.")
    @commands.has_permissions(moderate_members=True)
    async def case(self, ctx, case_id: int):
        doc = await cases_collection.find_one({"guild_id": str(ctx.guild.id)})
        if not doc or not doc.get("cases"):
            await ctx.send("No cases found.")
            return

        case = next((c for c in doc["cases"] if c["case_id"] == case_id), None)
        if not case:
            await ctx.send("Case not found.")
            return

        embed = discord.Embed(title=f"Case #{case['case_id']}", color=discord.Color.orange())
        embed.add_field(name="Type", value=case["type"])
        embed.add_field(name="Target", value=case["target"])
        embed.add_field(name="Moderator", value=case["moderator"])
        embed.add_field(name="Reason", value=case["reason"])
        embed.add_field(name="Timestamp", value=self.discord_timestamp(case["timestamp"], style="F"))

        if case.get("revoked"):
            r = case["revoked"]
            embed.add_field(
                name="Revoked",
                value=f"By <@{r['by']}> at {self.discord_timestamp(r['timestamp'], style='F')}",
                inline=False
            )

        if case.get("edit_history"):
            edits = "\n".join(
                [f"By <@{h['editor_id']}> at {self.discord_timestamp(h['timestamp'], style='F')}" for h in case["edit_history"]]
            )
            embed.add_field(name="Edit History", value=edits, inline=False)

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="editcase", description="Edit a moderation case.")
    @commands.has_permissions(moderate_members=True)
    async def editcase(self, ctx, case_id: int, *, reason: str):
        ok = await self._edit_case(ctx.guild.id, case_id, ctx.author.id, {"reason": reason})
        if ok:
            await ctx.send(f"<:Checkmark:1326642406086410317> Case #{case_id} updated.")
        else:
            await ctx.send("Case not found.")

    @commands.hybrid_command(name="mute", description="Mute a user.")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def mute(self, ctx, user: discord.Member, time: str, *, reason: str):
        if user.id == ctx.author.id:
            await ctx.send("You cannot mute yourself.")
            return
        if user.id == self.bot.user.id:
            await ctx.send("I cannot mute myself.")
            return
        try:
            if user.top_role > ctx.author.top_role:
                await ctx.send("You cannot ban this user.")
                return
        except:
            pass
        try:
            duration = parse_timespan(time)
        except InvalidTimespan:
            await ctx.send("Invalid time.")
            return
        if user.is_timed_out():
            await ctx.send(f"{user.mention} is already muted.")
            return
        try:
            case_id = await self._get_next_case_id(ctx.guild.id)
            await user.timeout(utils.utcnow() + datetime.timedelta(seconds=duration), reason=f"[#{case_id}] Moderator: {ctx.author.name}\nReason: {reason}")
            case_obj = {
                "case_id": case_id,
                "type": "Mute",
                "target": f"{user} [{user.id}]",
                "moderator": f"{ctx.author} [{ctx.author.id}]",
                "reason": reason,
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "edit_history": []
            }
            await self._add_case(ctx.guild.id, case_obj)
            self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Mute", f"[#{case_id}] Muted {user.mention} with reason: {reason}")
            await ctx.send(f"<:Checkmark:1326642406086410317> [#{case_id}] Muted {user.mention} for `{time}`.")
            try:
                await user.send(f"[#{case_id}] You have been muted in **{ctx.guild.name}** for: `{reason}`.")
            except:
                pass
        except Exception as e:
            await ctx.send("I do not have permission to mute users.")
            print(e)

    @commands.hybrid_command(name="unmute", description="Unmute a user.")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def unmute(self, ctx, user: discord.Member):
        if user.id == ctx.author.id:
            await ctx.send("You cannot unmute yourself.")
            return
        if user.id == self.bot.user.id:
            await ctx.send("I cannot unmute myself.")
            return
        if not user.is_timed_out():
            await ctx.send(f"{user.mention} is not muted.")
            return
        try:
            if user.top_role > ctx.author.top_role:
                await ctx.send("You cannot ban this user.")
                return
        except:
            pass
        try:
            await user.timeout(None)
            self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Unmute", f"Unmuted {user.mention}")
            await ctx.send(f"<:Checkmark:1326642406086410317> Unmuted {user.mention}.")
        except Exception as e:
            await ctx.send("I do not have permission to unmute users.")
            print(e)

    @commands.hybrid_command(name="ban", description="Ban a user.")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ban(self, ctx, user: discord.User, delete_message_days: int, *, reason: str = "No Reason Provided"):
        if user.id == ctx.author.id:
            await ctx.send("You cannot ban yourself.")
            return
        if user.id == self.bot.user.id:
            await ctx.send("I cannot ban myself.")
            return
        try:
            if user.top_role > ctx.author.top_role:
                await ctx.send("You cannot ban this user.")
                return
        except:
            pass
        if delete_message_days > 7:
            await ctx.send("Number of days to delete messages cannot be more than 7, or a week.")
            return
        try:
            case_id = await self._get_next_case_id(ctx.guild.id)
            await ctx.guild.ban(user, reason=f"[#{case_id}]Moderator: {ctx.author.name}\nReason: {reason}", delete_message_days=delete_message_days)
            case_obj = {
                "case_id": case_id,
                "type": "Ban",
                "target": f"{user} [{user.id}]",
                "moderator": f"{ctx.author} [{ctx.author.id}]",
                "reason": reason,
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "edit_history": []
            }
            await self._add_case(ctx.guild.id, case_obj)
            self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Ban", f"[#{case_id}]Banned {user.mention} with reason: {reason}")
            await ctx.send(f"<:Checkmark:1326642406086410317> [#{case_id}] Banned {user.mention}.")
        except Exception as e:
            await ctx.send("I do not have permission to ban users.")
            print(e)

    @commands.hybrid_command(name="kick", description="Kick a user.")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def kick(self, ctx, user: discord.Member, *, reason: str = "No Reason Provided"):
        if user.id == ctx.author.id:
            await ctx.send("You cannot kick yourself.")
            return
        if user.id == self.bot.user.id:
            await ctx.send("I cannot kick myself.")
            return
        if user.top_role > ctx.author.top_role:
            await ctx.send("You cannot kick this user.")
            return
        try:
            case_id = await self._get_next_case_id(ctx.guild.id)
            await user.kick(reason=f"[#{case_id}] Moderator: {ctx.author.name}\nReason: {reason}")
            case_obj = {
                "case_id": case_id,
                "type": "Kick",
                "target": f"{user} [{user.id}]",
                "moderator": f"{ctx.author} [{ctx.author.id}]",
                "reason": reason,
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "edit_history": []
            }
            await self._add_case(ctx.guild.id, case_obj)
            self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Kick", f"[#{case_id}] Kicked {user.mention} with reason: {reason}")
            await ctx.send(f"<:Checkmark:1326642406086410317> [#{case_id}] Kicked {user.mention}.")
        except Exception as e:
            await ctx.send("I do not have permission to kick users.")
            print(e)

    @commands.hybrid_command(name="unban", description="Unban a user.")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def unban(self, ctx, user: discord.User):
        try:
            await ctx.guild.unban(
                discord.Object(id=user.id), reason=f"Moderator: {ctx.author.name}"
            )
            self.bot.dispatch(
                "modlog",
                ctx.guild.id,
                ctx.author.id,
                "Unban",
                f"Unbanned `{user.name} [{user.id}]`",
            )
            await ctx.send(f"<:Checkmark:1326642406086410317> Unbanned user `{user.name}`.")
        except Exception as e:
            await ctx.send("I do not have permission to unban users.")
            print(e)

    @commands.hybrid_command(
        name="slowmode", description="Set the slowmode in a channel"
    )
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def slowmode(self, ctx, seconds: int, channel: discord.TextChannel = None):
        if not channel:
            channel = ctx.channel
        try:
            await channel.edit(slowmode_delay=seconds)
            await ctx.send(f"<:Checkmark:1326642406086410317> Set slowmode in {channel.mention} to {seconds} seconds.")
            self.bot.dispatch(
                "modlog",
                ctx.guild.id,
                ctx.author.id,
                "Slowmode",
                f"Set slowmode in #{channel.name} to {seconds} seconds",
            )
        except:
            await ctx.send("It seems I do not have permission to set slowmode.")
            return

async def setup(bot):
    await bot.add_cog(Moderation(bot))