import discord
from discord.ext import commands
from discord import app_commands
from db import cases_collection

class Information(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="info", description="Information commands")
    async def info(self, ctx):
        pass

    @info.command(name="user", description="Get information about a user")
    @app_commands.describe(user="The user to get information about")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def info_user(self, ctx: commands.Context, user: discord.Member = None):
        await ctx.defer(ephemeral=True)
        if user == None:
            user = ctx.author
        embed = discord.Embed()
        embed.set_author(name=f"{user}", icon_url=user.display_avatar.url)
        embed.add_field(name="General Information", value=f"> Name: `{user.nick if user.nick else user.name}`\n> ID: `{user.id}`\n> Created: {discord.utils.format_dt(user.created_at, 'f')}\n> Joined: {discord.utils.format_dt(user.joined_at, 'f')}", inline=False)
        if user.id == ctx.guild.owner.id:
            embed.add_field(name="Permissions", value="> Owner", inline=False)
        elif user.guild_permissions.administrator:
            embed.add_field(name="Permissions", value="> Administrator", inline=False)
        elif user.guild_permissions.moderate_members:
            embed.add_field(name="Permissions", value="> Moderator", inline=False)
        roles = user.roles[-10:]
        if len(user.roles) > 10:
            embed.add_field(name="Roles", value=f"> {', '.join([role.mention for role in roles])} +{len(user.roles) - 10} roles", inline=False)
        else:
            embed.add_field(name="Roles", value=f"> {', '.join([role.mention for role in roles])}", inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.send(embed=embed)

    @info.command(name="server", description="Get information about the server")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def info_server(self, ctx):
        await ctx.defer(ephemeral=True)
        embed = discord.Embed()
        embed.set_author(name=f"{ctx.guild.name}", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.add_field(name="General Information", value=f"> Name: `{ctx.guild.name}`\n> ID: `{ctx.guild.id}`\n> Created: {discord.utils.format_dt(ctx.guild.created_at, 'f')}\n> Boosts: `{ctx.guild.premium_subscription_count}`\n> Members: `{len(ctx.guild.members)}`\n> Roles: `{len(ctx.guild.roles)}`\n> Text Channels: `{len(ctx.guild.text_channels)}`\n> Voice Channels: `{len(ctx.guild.voice_channels)}`", inline=False)
        administrators = [member for member in ctx.guild.members if member.guild_permissions.administrator and not member.bot]
        moderators = [member for member in ctx.guild.members if member.guild_permissions.moderate_members and not member.bot]
        embed.add_field(name="Permissions", value=f"> Administrators: `{len(administrators)}`\n> Moderators: `{len(moderators)}`", inline=False)
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)

    @info.command(name="avatar", description="Get the avatar of a user")
    @app_commands.describe(user="The user to get the avatar of")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def info_avatar(self, ctx: commands.Context, user: discord.User = None):
        await ctx.defer(ephemeral=True)
        if user == None:
            user = ctx.author
        embed = discord.Embed()
        embed.set_author(name=f"{user}'s Avatar", icon_url=user.display_avatar.url)
        embed.set_image(url=user.display_avatar.url)
        await ctx.send(embed=embed)

    @info.command(name="icon", description="Get the icon of the server")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def info_icon(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        if not ctx.guild.icon:
            await ctx.send(embed=discord.Embed(description="This server has no icon."))
            return
        embed = discord.Embed()
        embed.set_author(name=f"{ctx.guild.name}'s Icon", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_image(url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)

    @info.command(name="banner", description="Get the banner of the server")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def info_banner(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        if not ctx.guild.banner:
            await ctx.send(embed=discord.Embed(description="This server has no banner."))
            return
        embed = discord.Embed()
        embed.set_author(name=f"{ctx.guild.name}'s Banner", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.set_image(url=ctx.guild.banner.url if ctx.guild.banner else None)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Information(bot))