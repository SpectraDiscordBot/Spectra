import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

class ManageRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_group(name="role")
    async def manage_roles(self, ctx):
        pass

    @manage_roles.command(name="create", description="Create a role.")
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
            await ctx.send(f"<:Checkmark:1326642406086410317> Created role {role.mention}.", ephemeral=True)
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
            await ctx.send(embed=embed, ephemeral=True)

    @manage_roles.command(name="delete", description="Delete a role.")
    @app_commands.describe(role="The role you want to delete.")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def delete(self, ctx: commands.Context, role: discord.Role):
        try:
            await role.delete(reason=f"Deleted by {ctx.author.name}")
            await ctx.send(f"<:Checkmark:1326642406086410317> Deleted role {role.name}.", ephemeral=True)
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
            await ctx.send(embed=embed, ephemeral=True)

    @manage_roles.command(name="list", description="List all roles.")
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
            await ctx.send(embed=embed, ephemeral=True)
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
            await ctx.send(embed=embed, ephemeral=True)

    @manage_roles.command(name="edit", description="Edit a role.")
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
            await ctx.send(f"<:pencil:1326648942993084426> Edited role {role.mention}.", ephemeral=True)
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
            await ctx.send(embed=embed, ephemeral=True)

    @manage_roles.command(name="info", description="Get information about a role.")
    @app_commands.describe(role="The role you want to get information about.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def roleinfo(self, ctx: commands.Context, role: discord.Role):
        try:
            embed = discord.Embed(
                title=f"Role Info: {role.name}",
                color=role.color
            )
            embed.add_field(name="Name", value=role.name, inline=True)
            embed.add_field(name="ID", value=role.id, inline=True)
            embed.add_field(name="Color", value=str(role.color), inline=True)
            embed.add_field(name="Mentionable", value=role.mentionable, inline=True)
            embed.add_field(name="Hoisted", value=role.hoist, inline=True)
            embed.add_field(name="Position", value=role.position, inline=True)
            embed.add_field(name="Members", value=len(role.members), inline=True)
            embed.add_field(name="Created At", value=discord.utils.format_dt(role.created_at, "F"), inline=True)
            embed.set_footer(text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif")
            embed.set_thumbnail(url=ctx.guild.icon.url)
            await ctx.send(embed=embed, ephemeral=True)
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
            await ctx.send(embed=embed, ephemeral=True)

    @manage_roles.command(name="members", description="List members with a specific role.")
    @app_commands.describe(role="The role you want to list members for.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rolemembers(self, ctx: commands.Context, role: discord.Role):
        class PaginatedRoles(discord.ui.View):
            def __init__(self, roles, **kwargs):
                super().__init__(**kwargs)
                self.roles = roles
                self.current_page = 0
            
            def update_buttons(self):
                self.previous.disabled = self.current_page == 0
                self.next.disabled = (self.current_page + 1) * 10 >= len(self.roles)

            @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
            async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page -= 1
                self.update_buttons()
                await interaction.response.edit_message(embed=self.get_embed(), view=self)

            @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
            async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page += 1
                self.update_buttons()
                await interaction.response.edit_message(embed=self.get_embed(), view=self)

            def get_embed(self):
                embed = discord.Embed(
                    title=f"Members with role {role.name}",
                    description="",
                    color=role.color
                )
                start = self.current_page * 10
                end = start + 10
                for member in self.roles[start:end]:
                    embed.add_field(name=member.display_name, value=member.mention, inline=False)
                embed.set_footer(text=f"Page {self.current_page + 1} of {((len(self.roles) - 1) // 10) + 1}")
                return embed
            
        try:
            members = role.members
            if not members:
                return await ctx.send(f"No members have the role **{role.name}**.", ephemeral=True)
            view = PaginatedRoles(members)
            view.update_buttons()
            await ctx.send(embed=view.get_embed(), view=view, ephemeral=True)
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
            await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ManageRoles(bot))