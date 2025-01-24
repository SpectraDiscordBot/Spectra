import datetime
import discord
import os
from discord.ext import commands
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ.get('MONGO_URI'))
db = client['Spectra']
warning_collection = db['Warnings']
cases_collection = db['Cases']

class Warning_Commands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="issue-warning", description="Issue a warning.", aliases=["warn"])
    @commands.cooldown(1, 5, type=commands.BucketType.user)
    @commands.has_permissions(moderate_members=True)
    async def issue_warning(self, ctx, user: discord.User, *, reason: str = "No Reason Provided"):
        if user.id == ctx.author.id:
            await ctx.send("You cannot warn yourself.")
            return
        if user.id == self.bot.user.id:
            await ctx.send("I cannot warn myself.")
            return

        data = warning_collection.find_one({"guild_id": str(ctx.guild.id)})
        if not data or not data.get("logs_channel"):
            await ctx.send("No warning system has been set up.", ephemeral=True)
            return

        cases = cases_collection.find_one({"guild_id": str(ctx.guild.id)})
        if not cases:
            cases_collection.insert_one({"guild_id": str(ctx.guild.id), "cases": 0})
        
        cases_collection.update_one({"guild_id": str(ctx.guild.id)}, {"$set": {"cases": cases["cases"] +1}})

        case = cases_collection.find_one({'guild_id': str(ctx.guild.id)})

        case_number = case["cases"]
        
        logs_channel = ctx.guild.get_channel(int(data.get("logs_channel")))
        warning_collection.insert_one({
            "guild_id": str(ctx.guild.id), 
            "user_id": str(user.id), 
            "reason": reason, 
            "issued_by": str(ctx.author.id),
            "issued_at": str(datetime.datetime.utcnow()), 
            "case_number": case_number
        })
        warn_log = discord.Embed(title=f"Warning issued to {user.name}", description="", color=discord.Color.pink())
        warn_log.add_field(name="Case Number:", value=f"CASE #{case_number}", inline=False)
        warn_log.add_field(name="Reason:", value=reason, inline=False)
        warn_log.add_field(name="Issued By:", value=f"<@{ctx.author.id}>", inline=False)
        warn_log.add_field(name="Issued At:", value=f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", inline=False)

        try:
            warn_log.set_thumbnail(url=user.avatar.url)
        except:
            pass

        warn_log.set_footer(text="Warning System")
        await ctx.send(f"<:Checkmark:1326642406086410317> `[CASE #{case_number}]` Warning issued to {user.mention} for `{reason}`.")
        try:
            await logs_channel.send(embed=warn_log)
        except:
            pass
        try:
            await user.send(f"You have been warned in **{ctx.guild.name}** for: `{reason}`.\n Your case number is `[CASE #{case_number}]`")
        except:
            pass

    @commands.hybrid_command(name="revoke-warning", description="Revoke a warning from a user.", aliases=["unwarn"])
    @commands.cooldown(1, 5, type=commands.BucketType.user)
    @commands.has_permissions(moderate_members=True)
    async def revoke_warning(self, ctx, case_number: int):

        data = warning_collection.find_one({"guild_id": str(ctx.guild.id)})
        if not data:
            await ctx.send("No warning system has been set up.", ephemeral=True)
            return
        
        warning = warning_collection.find_one({"guild_id": str(ctx.guild.id), "case_number": case_number})
        if not warning:
            await ctx.send("This warning does not exist.", ephemeral=True)
            return
        
        try: user = discord.utils.get(ctx.guild.members, id=int(warning["user_id"]))
        except: await ctx.send("Couldn't find the user in the warning.")

        if user.id == ctx.author.id:
            await ctx.send("You cannot revoke a warning from yourself.")
            return
        if user.id == self.bot.user.id:
            await ctx.send("I cannot revoke a warning from myself.")
            return

        warning_collection.delete_one({"guild_id": str(ctx.guild.id), "user_id": str(user.id), "case_number": case_number})
        warn_log = discord.Embed(title=f"Warning revoked from {user.name}", description="", color=discord.Color.pink())
        warn_log.add_field(name="Case Number:", value=f"CASE #{case_number}", inline=False)
        warn_log.add_field(name="Revoked By:", value=f"<@{ctx.author.id}>", inline=False)
        warn_log.add_field(name="Revoked At:", value=f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", inline=False)

        try:
            warn_log.set_thumbnail(url=user.avatar.url)
        except:
            pass

        warn_log.set_footer(text="Warning System")
        await ctx.send(f"<:Checkmark:1326642406086410317> `[CASE #{case_number}]` Warning revoked from {user.mention}.")
        try:
            await ctx.guild.get_channel(int(data["logs_channel"])).send(embed=warn_log)
        except:
            pass

    @commands.hybrid_command(name="list-warnings", description="List all warnings of a user.", aliases=["warns", "warnings"])
    @commands.cooldown(1, 5, type=commands.BucketType.user)
    @commands.has_permissions(moderate_members=True)
    async def list_warnings(self, ctx, user: discord.User = None):
        if user is None:
            user = ctx.author

        data = warning_collection.find_one({"guild_id": str(ctx.guild.id)})
        if not data:
            await ctx.send("No warning system has been set up.", ephemeral=True)
            return
        
        warnings = warning_collection.find({"guild_id": str(ctx.guild.id), "user_id": str(user.id)})
        embed = discord.Embed(title=f"<:Checkmark:1326642406086410317> Warnings of {user.name}", description="The following are the warnings of the user.", color=discord.Color.blue())
        embed.set_footer(text="Spectra")
        for warning in warnings:
            embed.add_field(name=f"Case #{warning['case_number']}", value=f"Reason: {warning['reason']}\nIssued by: <@{warning['issued_by']}>\nIssued at: {warning['issued_at']}", inline=False)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="clear-warnings", description="Clear all warnings of a user.")
    @commands.has_permissions(administrator=True)
    async def clear(self, ctx, user: discord.User):
        if user.id == ctx.author.id:
            await ctx.send("You cannot clear your own warnings.")
            return
        if user.id == self.bot.user.id:
            await ctx.send("I cannot clear my own warnings.")
            return

        data = warning_collection.find_one({"guild_id": str(ctx.guild.id)})
        if not data:
            await ctx.send("No warning system has been set up.", ephemeral=True)
            return
        
        warning_collection.delete_many({"guild_id": str(ctx.guild.id), "user_id": str(user.id)})
        warn_log = discord.Embed(title=f"Warnings cleared from {user.name}", description="", color=discord.Color.pink())
        warn_log.add_field(name="Cleared By:", value=f"<@{ctx.author.id}>", inline=False)
        warn_log.add_field(name="Cleared At:", value=f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", inline=False)
        
        try:
            warn_log.set_thumbnail(url=user.avatar.url)
        except:
            pass
        
        warn_log.set_footer(text="Warning System")
        await ctx.send(f"<:Checkmark:1326642406086410317> Warnings of {user.mention} have been cleared.")
        try:
            await ctx.guild.get_channel(int(data["logs_channel"])).send(embed=warn_log)
        except:
            pass

    @commands.hybrid_command(name="setup-warnings", description="Setup warning system.")
    @commands.has_permissions(manage_guild=True)
    async def setup(self, ctx, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        if warning_collection.find_one({"guild_id": guild_id}):
            await ctx.send("Warning System has already been set.", ephemeral=True)
            return
        else:
            warning_collection.insert_one({"guild_id": str(guild_id), "logs_channel": str(channel.id)})
            embed = discord.Embed(title="Warning System", description="Warning System has been set.", color=discord.Color.blue())
            embed.set_thumbnail(url=self.bot.user.avatar.url)
            embed.add_field(name="Set By:", value=ctx.author.mention, inline=False)
            await ctx.send("<:switch_on:1326648555414224977> Warning System has been set.")
            try: self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Enabled a System", f"The warning system has been successfully enabled.")
            except Exception as e: print(e)
            try:
                await channel.send(embed=embed)
            except:
                pass

    @commands.hybrid_command(name="disable-warnings", description="Disable warning system.")
    @commands.has_permissions(manage_guild=True)
    async def disable(self, ctx):
        guild_id = str(ctx.guild.id)
        if not warning_collection.find_one({"guild_id": guild_id}):
            await ctx.send("No warning system has been set up.", ephemeral=True)
            return
        warning_collection.delete_one({"guild_id": guild_id})
        await ctx.send("<:switch_off:1326648782393180282> Warning System has been disabled.", ephemeral=True)
        try: self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Disabled a System", f"The warning system has been successfully disabled.")
        except Exception as e: print(e)

async def setup(bot):
    await bot.add_cog(Warning_Commands(bot))