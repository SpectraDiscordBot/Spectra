import discord
import os
from discord import PartialEmoji, app_commands
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client["Spectra"]
verification_collection = db["Verification"]
autorole_collection = db["AutoRole"]

class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        if interaction.data.get("custom_id") != "verify":
            return

        guild = interaction.guild
        member = interaction.user
        data = await verification_collection.find_one({"guild_id": str(guild.id)})
        if not data:
            await interaction.response.send_message("❌ Verification system is not set up.", ephemeral=True)
            return

        verified_roles = []
        for r in data.get("verified_roles", []):
            role = guild.get_role(int(r["role_id"]))
            if role:
                verified_roles.append(role)
        if not verified_roles:
            await interaction.response.send_message("❌ No verified roles found.", ephemeral=True)
            return

        unverified_role = None
        if data.get("unverified_role"):
            unverified_role = guild.get_role(int(data["unverified_role"]))

        to_add = [r for r in verified_roles if r not in member.roles]
        try:
            if to_add:
                await member.add_roles(*to_add, reason="Spectra Verification")
            if unverified_role and unverified_role in member.roles:
                await member.remove_roles(unverified_role)
            await interaction.response.send_message("<:Checkmark:1326642406086410317> Successfully verified!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Missing permissions to assign roles.", ephemeral=True)
        except Exception as e:
            print(f"Failed to verify member: {e}")
            await interaction.response.send_message("❌ An error occurred during verification.", ephemeral=True)

    @commands.hybrid_group(name="verification")
    async def verification(self, ctx):
        pass

    @verification.command(name="setup-verification", description="Setup the verification system")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="Channel to send the verification message in",
        unverified_role="Role removed after verification",
        verified_role_1="Verified role 1",
        verified_role_2="Verified role 2",
        verified_role_3="Verified role 3",
        verified_role_4="Verified role 4",
        verified_role_5="Verified role 5"
    )
    async def setup_verification(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        unverified_role: discord.Role,
        verified_role_1: discord.Role,
        verified_role_2: discord.Role = None,
        verified_role_3: discord.Role = None,
        verified_role_4: discord.Role = None,
        verified_role_5: discord.Role = None
    ):
        guild_id = str(ctx.guild.id)
        if await verification_collection.find_one({"guild_id": guild_id}):
            await ctx.send("❌ Verification system already set up. Use `/disable-verification` first.", ephemeral=True)
            return

        verified_roles = [r for r in [verified_role_1, verified_role_2, verified_role_3, verified_role_4, verified_role_5] if r]
        if not verified_roles:
            await ctx.send("❌ You must provide at least one verified role.", ephemeral=True)
            return

        if not await autorole_collection.find_one({"guild_id": guild_id, "role": str(unverified_role.id)}):
            if await autorole_collection.count_documents({"guild_id": guild_id}) < 5:
                await autorole_collection.insert_one({"guild_id": guild_id, "role": str(unverified_role.id)})
                await ctx.send(f"<:Checkmark:1326642406086410317> {unverified_role.name} added to autoroles.", ephemeral=True)
            else:
                await ctx.send(f"⚠ Couldn't add {unverified_role.name} to autoroles (limit reached).", ephemeral=True)

        await verification_collection.insert_one({
            "guild_id": guild_id,
            "channel": str(channel.id),
            "unverified_role": str(unverified_role.id),
            "verified_roles": [{"role_id": str(r.id), "name": r.name} for r in verified_roles]
        })

        embed = discord.Embed(
            title="🔐 Verify Yourself",
            description="Click the button below to verify and gain access to the server.",
            color=discord.Color.pink()
        )
        embed.set_footer(text="Powered by Spectra", icon_url=self.bot.user.avatar.url)
        try:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        except:
            pass

        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify", emoji="✔"))

        await channel.send(embed=embed, view=view)
        await ctx.send(f"<:switch_on:1326648555414224977> Verification system set up in {channel.mention}.", ephemeral=True)

        try:
            self.bot.dispatch(
                "modlog",
                ctx.guild.id,
                ctx.author.id,
                "Verification System Enabled",
                f"Channel: {channel.mention}\nVerified: {', '.join(r.mention for r in verified_roles)}\nUnverified: {unverified_role.mention}"
            )
        except:
            pass

    @verification.command(name="disable-verification", description="Disable the verification system")
    @commands.has_permissions(manage_guild=True)
    async def disable_verification(self, ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        if not await verification_collection.find_one({"guild_id": guild_id}):
            await ctx.send("❌ No verification system found.", ephemeral=True)
            return
        await verification_collection.delete_one({"guild_id": guild_id})
        await ctx.send("<:switch_off:1326648782393180282> Verification system has been disabled.", ephemeral=True)
        try:
            self.bot.dispatch(
                "modlog",
                ctx.guild.id,
                ctx.author.id,
                "Verification System Disabled",
                "Verification system was disabled."
            )
        except:
            pass

    @verification.command(name="send", description="Resend the verification message")
    @commands.has_permissions(manage_guild=True)
    async def send_verification(self, ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        data = await verification_collection.find_one({"guild_id": guild_id})
        if not data:
            await ctx.send("❌ Verification system is not set up.", ephemeral=True)
            return
        channel = ctx.guild.get_channel(int(data["channel"]))
        if not channel:
            await ctx.send("❌ Verification channel no longer exists.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔐 Verify Yourself",
            description="Click the button below to verify and gain access to the server.",
            color=discord.Color.pink()
        )
        embed.set_footer(text="Powered by Spectra", icon_url=self.bot.user.avatar.url)
        try:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        except:
            pass

        view = discord.ui.View(timeout=None)
        checkmark = PartialEmoji(name="Checkmark", id=1326642406086410317)
        view.add_item(discord.ui.Button(label="Verify", style=discord.ButtonStyle.green, custom_id="verify", emoji=checkmark))

        await channel.send(embed=embed, view=view)
        await ctx.send("<:Checkmark:1326642406086410317> Verification message sent.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Verification(bot))