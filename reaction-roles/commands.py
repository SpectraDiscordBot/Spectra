import datetime
import discord
import os
import emoji
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ.get('MONGO_URI'))
db = client['Spectra']
button_roles_collection = db['ButtonRoles']

class Reaction_Role_Commands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="add-reaction-role", description="Add a reaction role.")
    @app_commands.describe(role="The role to give when a user reacts", label="The label to put on the button", button_emoji="The emoji to put on the button")
    async def add_reaction_role(self, ctx: commands.Context, role: discord.Role, label: str, button_emoji: str = "none"): 
        guild_id = str(ctx.guild.id)

        if len(label) > 10:
            await ctx.send("The label must be less than or equal to 10 characters.")
            return
        
        if emoji and not emoji.is_emoji(button_emoji):
            if button_emoji == "none":
                pass
            else:
                await ctx.send("Invalid emoji. Please use a valid emoji.")
                return

        existing_data = button_roles_collection.find_one({"guild_id": guild_id})
        roles = existing_data.get("roles", []) if existing_data else []

        for r in roles:
            if r["role_id"] == str(role.id):
                await ctx.send(f"The role {role.name} is already configured.")
                return
            if len(list(roles)) >= 3:
                await ctx.send("You have reached the maximum limit of 3 reaction roles. Please remove one first.")
                return

        roles.append({"label": label, "emoji": str(button_emoji), "role_id": str(role.id)})

        button_roles_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"roles": roles}},
            upsert=True
        )

        self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Added a reaction role", f"Added {role.mention} as a reaction role.")

        await ctx.send(f"<:Checkmark:1326642406086410317> Added reaction role: `{role.name}` with label `{label}` and emoji {button_emoji}.")

    @commands.hybrid_command(name="remove-reaction-role", description="Remove a reaction role.")
    @app_commands.describe(role="The role to remove")
    async def remove_reaction_role(self, ctx: commands.Context, role: discord.Role):
        guild_id = str(ctx.guild.id)
        data = button_roles_collection.find_one({"guild_id": guild_id})

        if not data or "roles" not in data:
            await ctx.send("No reaction roles are configured for this guild.", ephemeral=True)
            return

        roles = data["roles"]
        for idx, role_data in enumerate(roles):
            if int(role_data["role_id"]) == role.id:
                roles.pop(idx)
                break
        else:
            await ctx.send(f"The role `{role.name}` is not configured as a reaction role.", ephemeral=True)
            return

        button_roles_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"roles": roles}}
        )

        self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Removed a reaction role", f"Removed {role.mention} from reaction roles.")

        await ctx.send(f"<:Checkmark:1326642406086410317> Removed reaction role: `{role.name}`.")

    @commands.hybrid_command(name="send-reaction-role", description="Send the reaction roles message")
    @commands.has_permissions(manage_roles=True)
    @app_commands.describe(channel="The channel to send the reaction roles in")
    async def send_button_roles(self, ctx: commands.Context, channel: discord.TextChannel = None):
        guild_id = str(ctx.guild.id)
        if channel is None:
            channel = ctx.channel

        data = button_roles_collection.find_one({"guild_id": guild_id})
        roles = data.get("roles", []) if data else []

        if not roles:
            await ctx.send("No roles have been configured for buttons yet.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Select Your Roles",
            description="Click a button to assign/remove roles.",
            color=discord.Color.pink()
        )

        try:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        except:
            pass

        view = discord.ui.View()
        for role_data in roles:
            custom_id = f"role_{role_data['role_id']}"
            if role_data.get("emoji") and emoji.is_emoji(role_data.get("emoji")):
                view.add_item(discord.ui.Button(
                    label=role_data["label"],
                    custom_id=custom_id,
                    emoji=role_data["emoji"],
                    style=discord.ButtonStyle.primary
                ))
            else:
                view.add_item(discord.ui.Button(
                    label=role_data["label"],
                    custom_id=custom_id,
                    style=discord.ButtonStyle.primary
                ))

        message = await channel.send(embed=embed, view=view)

        button_roles_collection.update_one(
            {"guild_id": guild_id},
            {"$set": {"message_id": str(message.id)}},
            upsert=True
        )

        self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Sent the reaction roles", f"Sent reaction roles in {channel.mention}.")

        await ctx.send("<:switch_on:1326648555414224977> Button roles setup complete!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Reaction_Role_Commands(bot))