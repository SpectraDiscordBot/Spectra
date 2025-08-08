import discord
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

class ManageRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="create-role", description="Create a role.")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    @app_commands.describe(
        name="The name of the role.",
        color="The color of the role.",
        mentionable="Whether the role is mentionable or not."
    )
    async def create(self, ctx: commands.Context, name: str, color: str, mentionable: bool = False):
        try:
            try:
                color = discord.Color(int(color.replace("#", ""), 16))
            except ValueError:
                color = getattr(discord.Color, color.lower(), discord.Color.default())()
            role = await ctx.guild.create_role(
                name=name,
                colour=color,
                mentionable=mentionable,
                reason=f"Created by {ctx.author.name}"
            )
            await ctx.send(f"<:Checkmark:1326642406086410317> Created role {role.mention}.")
            self.bot.dispatch(
                "modlog",
                ctx.guild.id,
                ctx.author.id,
                "Created a role",
                f"Created the role {role.mention}."
            )
        except Exception as e:
            embed = discord.Embed(
                title="Error!",
                description=f"```{e}```\n\n[Get Support](https://discord.gg/fcPF66DubA)",
                color=discord.Color.red()
            )
            embed.set_footer(text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif")
            embed.set_thumbnail(
                url="https://media.discordapp.net/attachments/914579638792114190/1280203446825517239/error-icon-25239.png"
            )
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="delete-role", description="Delete a role.")
    @app_commands.describe(role="The role you want to delete.")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def delete(self, ctx: commands.Context, role: discord.Role):
        try:
            await role.delete(reason=f"Deleted by {ctx.author.name}")
            await ctx.send(f"<:Checkmark:1326642406086410317> Deleted role {role.name}.")
            self.bot.dispatch(
                "modlog",
                ctx.guild.id,
                ctx.author.id,
                "Deleted a role",
                f"Deleted the role **{role.name}**."
            )
        except Exception as e:
            embed = discord.Embed(
                title="Error!",
                description=f"```{e}```\n\n[Get Support](https://discord.gg/fcPF66DubA)",
                color=discord.Color.red()
            )
            embed.set_footer(text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif")
            embed.set_thumbnail(
                url="https://media.discordapp.net/attachments/914579638792114190/1280203446825517239/error-icon-25239.png"
            )
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="list-roles", description="List all roles.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def list(self, ctx: commands.Context):
        try:
            roles = [role.mention for role in reversed(ctx.guild.roles)]
            embed = discord.Embed(
                title=f"{len(roles)} Roles",
                description="\n".join(roles),
                color=discord.Color.blue(),
            )
            embed.set_footer(
                text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
            )
            embed.set_thumbnail(url=ctx.guild.icon.url)
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="Error!",
                description=f"```{e}```\n\n[Get Support](https://discord.gg/fcPF66DubA)",
                color=discord.Color.red(),
            )
            embed.set_footer(
                text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
            )
            embed.set_thumbnail(
                url="https://media.discordapp.net/attachments/914579638792114190/1280203446825517239/error-icon-25239.png?ex=66d739de&is=66d5e85e&hm=83a98b27d14a3a19f4795d3fec58d1cd7306f6a940c45e49cd2dfef6edcdc96e&=&format=webp&quality=lossless&width=640&height=640SS"
            )
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="edit-role", description="Edit a role.")
    @app_commands.describe(
        role="The role you want to edit.",
        name="The name of the role.",
        color="The color of the role.",
        mentionable="Whether the role is mentionable or not."
    )
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def edit(self, ctx: commands.Context, role: discord.Role, name: str = None, color: str = None, mentionable: bool = None):
        try:
            if name is not None:
                await role.edit(name=name, reason=f"Edited by {ctx.author.name}")
            if color is not None:
                try:
                    color = discord.Color(int(color.replace("#", ""), 16))
                except ValueError:
                    color = getattr(discord.Color, color.lower(), discord.Color.default())()
                await role.edit(color=color, reason=f"Edited by {ctx.author.name}")
            if mentionable is not None:
                await role.edit(mentionable=mentionable, reason=f"Edited by {ctx.author.name}")
            await ctx.send(f"<:pencil:1326648942993084426> Edited role {role.mention}.")
            self.bot.dispatch(
                "modlog",
                ctx.guild.id,
                ctx.author.id,
                "Edited a role",
                f"Edited the role {role.mention}.\nName: {name}\nColor: {color}\nMentionable: {mentionable}"
            )
        except Exception as e:
            embed = discord.Embed(
                title="Error!",
                description=f"```{e}```\n\n[Get Support](https://discord.gg/fcPF66DubA)",
                color=discord.Color.red()
            )
            embed.set_footer(text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif")
            embed.set_thumbnail(
                url="https://media.discordapp.net/attachments/914579638792114190/1280203446825517239/error-icon-25239.png"
            )
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ManageRoles(bot))