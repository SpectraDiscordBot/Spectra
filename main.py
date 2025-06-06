# Imports

import asyncio
import discord
import datetime
import aiohttp
import os
import topgg
import motor.motor_asyncio
from discord.ext import commands
from discord import Button, app_commands
from discord.ui import View
from datetime import time
from dotenv import load_dotenv
from googleapiclient import discovery
from humanfriendly import parse_timespan
from discord.ext import tasks

# Load Dotenv

load_dotenv()

# Intents

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# AntiSpam Options

anti_spam = commands.CooldownMapping.from_cooldown(10, 40, commands.BucketType.member)
too_many_violations = commands.CooldownMapping.from_cooldown(
    5, 30, commands.BucketType.member
)

# MongoDB

client = motor.motor_asyncio.AsyncIOMotorClient(os.environ.get("MONGO_URI"))
db = client["Spectra"]
autorole_collection = db["AutoRole"]
welcome_messages_collection = db["WelcomeMessages"]
antispam_collection = db["AntiSpam"]
warning_collection = db["Warnings"]
modlog_collection = db["ModLogs"]
cases_collection = db["Cases"]
custom_cmds_collection = db["CustomCommands"]
custom_prefix_collection = db["CustomPrefixes"]
blacklist_collection = db["Blacklist"]


async def blacklist_check(ctx):
    user_blacklisted = await blacklist_collection.find_one({"_id": ctx.author.id})
    server_blacklisted = await blacklist_collection.find_one(
        {"_id": ctx.guild.id if ctx.guild else None}
    )

    if user_blacklisted:
        return False
    if server_blacklisted:
        await ctx.send("This server is blacklisted from using this bot.")
        return False
    return True


def blacklist_check_decorator():
    async def predicate(ctx):
        return await blacklist_check(ctx)

    return commands.check(predicate)


async def get_prefix(Client, message):
    if not message.guild:
        return ">"
    else:
        try:
            prefix = await custom_prefix_collection.find_one(
                {"guild_id": str(message.guild.id)}
            )
            return prefix["prefix"]
        except:
            return ">"


# Bot

bot = commands.AutoShardedBot(
    command_prefix=get_prefix,
    intents=intents,
    status=discord.Status.idle,
    activity=discord.CustomActivity(name=">help | spectrabot.pages.dev"),
    owner_ids=[856196104385986560, 998434044335374336],
    case_insensitive=True,
)

bot.remove_command("help")

# TopGG
bot.topgg_webhook = topgg.WebhookManager(bot).dbl_webhook(
    "/dblwebhook", "youshallnotpass"
)


@bot.event
async def setup_hook():
    token = os.environ.get("TOP_GG")
    if token:
        bot.topggpy = topgg.DBLClient(bot, token)


# Classes


class CommandPaginator(View):
    def __init__(self, commands, per_page=10):
        super().__init__(timeout=120)
        self.commands = commands
        self.per_page = per_page
        self.current_page = 0

    def get_embed(self):
        embed = discord.Embed(
            title="List of Commands", description="", color=discord.Color.pink()
        )
        embed.set_footer(
            text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
        )
        start = self.current_page * self.per_page
        end = start + self.per_page
        for command in self.commands[start:end]:
            if command.name == "help":
                continue
            if command.name == "refresh":
                continue
            if command.name == "verify":
                continue
            if command.name == "status":
                continue
            if command.name == "blacklist":
                return
            if command.name == "unblacklist":
                return

            aliases = (
                ", ".join(command.aliases)
                if hasattr(command, "aliases") and command.aliases
                else "None"
            )
            embed.add_field(
                name=f"{command.name}",
                value=command.description + f"\nAliases: {aliases}",
                inline=False,
            )
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
    async def previous_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if (self.current_page + 1) * self.per_page < len(self.commands):
            self.current_page += 1
            await interaction.response.edit_message(embed=self.get_embed(), view=self)


class HelpButtons(discord.ui.View):
    def __init__(self, *, timeout=120):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="List of Commands", style=discord.ButtonStyle.primary)
    async def first_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        commands = [
            command
            for command in bot.commands
            if command.name
            not in [
                "help",
                "refresh",
                "verify",
                "load",
                "unload",
                "biggest_server",
                "shutdown",
                "blacklist",
                "unblacklist",
            ]
        ]
        paginator = CommandPaginator(commands)
        await interaction.response.send_message(
            embed=paginator.get_embed(), view=paginator, ephemeral=True
        )

    @discord.ui.button(label="Support Server", style=discord.ButtonStyle.primary)
    async def support(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="Support Server",
            description="[Click here to join the support server.](https://discord.gg/fcPF66DubA)",
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Uptime", style=discord.ButtonStyle.primary)
    async def uptime(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="Uptime",
            description=f"The bot has been up for {datetime.datetime.now() - startTime}.",
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AutoRoleSetupButton(discord.ui.View):
    def __init__(self, *, timeout=120):
        super().__init__(timeout=timeout)

    @discord.ui.button(
        label="Remove AutoRole", emoji="⚠️", style=discord.ButtonStyle.danger
    )
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        query = {"guild_id": str(interaction.guild.id)}
        await autorole_collection.delete_one(query, comment="Removed AutoRole")
        await interaction.response.send_message(
            "AutoRole has been removed.", ephemeral=True
        )


class ErrorButtons(discord.ui.View):
    def __init__(self, *, timeout=120):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="Support Server", style=discord.ButtonStyle.secondary)
    async def support(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="Support Server",
            description="E-mail: spectra.official@protonmail.com/n[Click here to join the support server.](https://discord.gg/fcPF66DubA)",
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.before_invoke
async def before_any_command(ctx):
    if not await blacklist_check(ctx):
        raise commands.CheckFailure


# Bot Events


@bot.event
async def on_ready():
    assert bot.user is not None
    bot.topggpy.default_bot_id = bot.user.id

    try:
        await bot.topgg_webhook.run(5000)
    except:
        pass

    print(f"{bot.user} Is Ready.")
    await bot.load_extension("autorole.commands")
    await bot.load_extension("welcomemessage.commands")
    await bot.load_extension("manageroles.commands")
    await bot.load_extension("moderation.commands")
    await bot.load_extension("antispam.commands")
    await bot.load_extension("warning.commands")
    await bot.load_extension("reaction-roles.commands")
    await bot.load_extension("notes.commands")
    await bot.load_extension("moderation-logs.commands")
    await bot.load_extension("anti-toxicity.commands")
    await bot.load_extension("reports.commands")
    await bot.load_extension("owner-stuff.commands")
    await bot.load_extension("TopGG.topgg")
    await bot.load_extension("verification.commands")
    await bot.load_extension("Translation.commands")

    with open("spectra.gif", "rb") as f:
        image = f.read()

    try:
        await bot.user.edit(avatar=image)
    except:
        pass
    await bot.tree.sync()

    global startTime
    startTime = datetime.datetime.now()


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(
            "I don't think that command exists! If you're using another bot, consider changing my prefix for this server!",
            ephemeral=True,
        )
    elif isinstance(error, commands.CommandOnCooldown):
        msg = "**Still On Cooldown!** You may retry after {:.2f}s".format(
            error.retry_after
        )
        await ctx.send(msg, ephemeral=True)
    elif isinstance(error, commands.MissingRequiredArgument):
        required_params = [
            param
            for param in ctx.command.params
            if ctx.command.params[param].default == ctx.command.params[param].empty
        ]

        usage = f"/{ctx.command} " + " ".join(f"<{param}>" for param in required_params)
        await ctx.send(
            f"Error: Missing required argument `{error.param.name}`.\nUsage: `{usage}`",
            ephemeral=True,
        )
    else:
        embed = discord.Embed(
            title="Error!", description="{}".format(error), color=discord.Color.red()
        )
        embed.set_footer(
            text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif"
        )
        embed.set_thumbnail(
            url="https://media.discordapp.net/attachments/914579638792114190/1280203446825517239/error-icon-25239.png?ex=66d739de&is=66d5e85e&hm=83a98b27d14a3a19f4795d3fec58d1cd7306f6a940c45e49cd2dfef6edcdc96e&=&format=webp&quality=lossless&width=640&height=640SS"
        )
        await ctx.send(embed=embed, view=ErrorButtons(), ephemeral=True)
        print(error)


@bot.event
async def on_tree_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = "**Still On Cooldown!** You may retry after {:.2f}s".format(
            error.retry_after
        )
        try:
            await interaction.response.send_message(msg, ephemeral=True)
        except:
            await interaction.channel.send(
                interaction.user.mention, msg, delete_after=5
            )
    elif isinstance(error, commands.CommandOnCooldown):
        msg = "**Still On Cooldown!** You may retry after {:.2f}s".format(
            error.retry_after
        )
        try:
            await interaction.response.send_message(msg, ephemeral=True)
        except:
            await interaction.channel.send(
                interaction.user.mention, msg, delete_after=5
            )
    elif isinstance(error, app_commands.MissingPermissions):
        msg = "You are missing the following permissions: {}".format(
            ", ".join(error.missing_permissions)
        )
        try:
            await interaction.response.send_message(msg, ephemeral=True)
        except:
            await interaction.channel.send(
                interaction.user.mention, msg, delete_after=5
            )
    elif isinstance(error, commands.MissingPermissions):
        msg = "You are missing the following permissions: {}".format(
            ", ".join(error.missing_permissions)
        )
        try:
            await interaction.response.send_message(msg, ephemeral=True)
        except:
            await interaction.channel.send(
                interaction.user.mention, msg, delete_after=5
            )
    else:
        embed = discord.Embed(
            title="Error!", description="{}".format(error), color=discord.Color.red()
        )
        embed.set_footer(
            text="Spectra",
        )
        embed.set_thumbnail(
            url="https://media.discordapp.net/attachments/914579638792114190/1280203446825517239/error-icon-25239.png?ex=66d739de&is=66d5e85e&hm=83a98b27d14a3a19f4795d3fec58d1cd7306f6a940c45e49cd2dfef6edcdc96e&=&format=webp&quality=lossless&width=640&height=640"
        )
        try:
            await interaction.response.send_message(
                embed=embed, view=ErrorButtons(), delete_after=10, ephemeral=True
            )
        except:
            try:
                await interaction.followup.send(
                    embed=embed, view=ErrorButtons(), delete_after=10, ephemeral=True
                )
            except:
                pass
        print(error)


bot.tree.on_error = on_tree_error


@bot.event
async def on_member_join(member):

    try:
        autorole_data = await autorole_collection.find(
            {"guild_id": str(member.guild.id)}
        ).to_list(length=None)
    except Exception as e:
        print(f"Error fetching autorole data: {e}")
        return

    if autorole_data:
        for data in autorole_data:
            role_id = int(data.get("role"))
            role = member.guild.get_role(role_id)

            if role and role not in member.roles:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    pass

    try:
        welcome_messaging = await welcome_messages_collection.find_one(
            {"guild_id": str(member.guild.id)}
        )
    except Exception as e:
        print(f"Error fetching welcome message data: {e}")
        return

    if welcome_messaging:
        message = welcome_messaging.get("message")
        channel_id = welcome_messaging.get("channel")

        if message and channel_id:
            channel = member.guild.get_channel(int(channel_id))
            formatted_message = message.replace("{server}", member.guild.name)
            if "{user}" in formatted_message:
                    formatted_message = formatted_message.replace("{user}", member.mention)
            else:
                formatted_message = f"{member.mention} {formatted_message}"
            if channel:
                try:
                    await channel.send(f"{formatted_message}")
                except Exception as e:
                    return


@bot.event
async def on_guild_remove(guild):
    guild_id = guild.id

    for collection_name in db.list_collection_names():
        collection = db[collection_name]

        result = collection.delete_many({"guild_id": guild_id})
        print(
            f"Deleted {result.deleted_count} documents from collection '{collection_name}' for guild {guild_id}."
        )

    print(f"All data for guild {guild_id} has been removed from the database.")


@bot.event
async def on_message(message):
    if isinstance(message.channel, discord.channel.DMChannel):
        return

    await bot.process_commands(message)

    if bot.user.mentioned_in(message):
        if message.author.id == 856196104385986560:
            await message.reply(
                "<:Checkmark:1326642406086410317> Owner of Spectra Verified"
            )
        elif message.author.id == 998434044335374336:
            await message.reply(
                "<:Checkmark:1326642406086410317> Co Owner of Spectra Verified"
            )
        else:
            pass

    antispam_guild = await antispam_collection.find_one({"guild_id": message.guild.id})
    if antispam_guild:
        if message.author.top_role >= message.guild.me.top_role:
            return
        if message.author.id == message.guild.owner.id:
            return
        bucket = anti_spam.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        log_channel = bot.get_channel(antispam_guild.get("channel_id", None))

        if retry_after:
            await message.delete()
            warning_entry = await warning_collection.find_one(
                {"user_id": message.author.id, "guild_id": message.guild.id}
            )
            now = datetime.datetime.now()
            if (
                not warning_entry
                or (now - warning_entry["last_warning"]).total_seconds() > 10
            ):
                await warning_collection.update_one(
                    {"user_id": message.author.id, "guild_id": message.guild.id},
                    {"$set": {"last_warning": now}},
                    upsert=True,
                )
                warning_embed = discord.Embed(
                    title="Stop Spamming",
                    description="Stop spamming or you will be timed out.",
                    color=discord.Colour.red(),
                )
                warning_embed.set_footer(text="Anti-Spam")
                await message.channel.send(
                    f"{message.author.mention}", embed=warning_embed, delete_after=10
                )
            violations = too_many_violations.get_bucket(message)
            if violations.update_rate_limit():
                try:
                    try:
                        await message.author.timeout(
                            datetime.timedelta(minutes=5), reason="Spamming"
                        )
                    except discord.Forbidden:
                        if log_channel:
                            failed_embed = discord.Embed(
                                title="Failed to mute",
                                description=f"I've attempted to mute {message.author.mention} for spamming, but I've failed to do so as I don't have permission.",
                                color=discord.Colour.pink(),
                            )
                            failed_embed.add_field(
                                name="User", value=message.author.mention, inline=False
                            )
                            failed_embed.add_field(
                                name="Reason", value="Spamming", inline=False
                            )
                            failed_embed.add_field(
                                name="Attempted at",
                                value=f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                inline=False,
                            )
                            try:
                                failed_embed.set_thumbnail(
                                    url=message.author.avatar_url
                                )
                            except:
                                pass
                            failed_embed.set_footer(text="Anti-Spam")
                            await asyncio.sleep(1)
                            await log_channel.send(embed=failed_embed)
                            return
                    await asyncio.sleep(1)
                    dm_embed = discord.Embed(
                        title="Timed Out",
                        description="You have been timed out for a duration of 5 minutes due to spamming.",
                        color=discord.Colour.pink(),
                    )
                    dm_embed.add_field(
                        name="Server", value=message.guild.name, inline=False
                    )
                    dm_embed.add_field(name="Duration", value="5 minutes", inline=False)
                    dm_embed.add_field(
                        name="Issued At",
                        value=f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        inline=False,
                    )
                    dm_embed.set_footer(text="Anti-Spam")
                    try:
                        await message.author.send(embed=dm_embed)
                    except:
                        pass
                    channel_embed = discord.Embed(
                        title="Timed out",
                        description=f"<:modshield:1325613380945444864> **{message.author.name}** has been timed out for spamming.",
                        color=discord.Colour.pink(),
                    )
                    channel_embed.set_footer(text="Anti-Spam")
                    try:
                        await message.channel.send(embed=channel_embed)
                    except:
                        pass
                except Exception as e:
                    print(e)
                    return
                if log_channel:
                    embed = discord.Embed(
                        title="User Timed Out",
                        description=f"",
                        color=discord.Color.pink(),
                    )
                    embed.add_field(
                        name="User", value=f"{message.author.mention}", inline=False
                    )
                    embed.add_field(name="Reason", value="Spamming", inline=False)
                    embed.add_field(
                        name="Issued By", value=bot.user.mention, inline=False
                    )
                    embed.add_field(
                        name="Issued At",
                        value=f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        inline=False,
                    )
                    try:
                        embed.set_thumbnail(url=message.author.avatar_url)
                    except:
                        pass
                    embed.set_footer(text="Anti-Spam")
                    await asyncio.sleep(1)
                    await log_channel.send(embed=embed)
                violations._tokens = violations.rate
                violations._last = message.created_at.timestamp()
        else:
            pass
    else:
        pass


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data["custom_id"]
        guild = interaction.guild
        member = interaction.user

        if not guild or not member:
            await interaction.response.send_message(
                "Error: Guild or member not found.", ephemeral=True
            )
            return

        if custom_id.startswith("role_"):
            role_id = int(custom_id.split("_")[1])
            role = guild.get_role(role_id)

            if not role:
                await interaction.response.send_message(
                    "Error: Role not found.", ephemeral=True
                )
                return

            if role in member.roles:
                await member.remove_roles(role)
                await interaction.response.send_message(
                    f"Removed the {role.name} role.", ephemeral=True
                )
                try:
                    view = discord.ui.View()
                    button = discord.ui.Button(
                        label=f"Sent from {interaction.guild.name}",
                        style=discord.ButtonStyle.gray,
                        disabled=True,
                    )
                    view.add_item(button)
                    await interaction.user.send(
                        f"You were removed from the {role.name} role.", view=view
                    )
                except:
                    pass
            else:
                await member.add_roles(role)
                await interaction.response.send_message(
                    f"Added the {role.name} role.", ephemeral=True
                )
                try:
                    view = discord.ui.View()
                    button = discord.ui.Button(
                        label=f"Sent from {interaction.guild.name}",
                        style=discord.ButtonStyle.gray,
                        disabled=True,
                    )
                    view.add_item(button)
                    await interaction.user.send(
                        f"You were given the {role.name} role.", view=view
                    )
                except:
                    pass

        if custom_id.startswith("reports_ban"):
            user_id = int(custom_id.strip("reports_ban_"))
            user = await bot.fetch_user(user_id)
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
                        bot.dispatch(
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
            user = await bot.fetch_user(user_id)
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
                    bot.dispatch(
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
            user = await bot.fetch_user(user_id)
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


# Bot Commands


@bot.hybrid_command(name="help", description="Get help with the bot.")
@commands.cooldown(1, 15, commands.BucketType.user)
async def help(ctx: commands.Context):
    embed = discord.Embed(
        title="Help", description="Get help with the bot.", color=discord.Color.blue()
    )
    embed.set_footer(
        text="Made with ❤ by brutiv & tyler.hers",
        icon_url="https://i.ibb.co/cKqBfp1/spectra.gif",
    )
    embed.set_thumbnail(url="https://i.ibb.co/cKqBfp1/spectra.gif")
    embed.add_field(
        name="Prefix", value=f"`{await get_prefix(bot, ctx.message)}`\n`/`", inline=False
    )
    await ctx.send(embed=embed, view=HelpButtons(), ephemeral=True)


@bot.hybrid_command(
    name="set-prefix", description="Set a custom prefix for the server."
)
@commands.has_permissions(manage_guild=True)
@commands.cooldown(1, 5)
async def set_prefix(ctx: commands.Context, prefix: str):
    if len(str(prefix)) > 3:
        await ctx.send(
            "Prefix must be between 1 and 3 characters long.", ephemeral=True
        )
        return
    if len(str(prefix)) < 1:
        await ctx.send("Prefix must be at least 1 character long.", ephemeral=True)
        return

    prefixes = await custom_prefix_collection.find_one({"guild_id": str(ctx.guild.id)})
    if prefixes:
        prefixes["prefix"] = prefix
        await custom_prefix_collection.update_one(
            {"guild_id": str(ctx.guild.id)}, {"$set": prefixes}
        )
        await ctx.send(f"Prefix set to `{prefix}` for this server.")
    else:
        await custom_prefix_collection.insert_one(
            {"guild_id": str(ctx.guild.id), "prefix": prefix}
        )
        try:
            bot.dispatch(
                "modlog",
                ctx.guild.id,
                ctx.author.id,
                "Set a new prefix",
                f"Set prefix to {prefix} for this server.",
            )
        except Exception as e:
            print(e)
        await ctx.send(f"Prefix set to `{prefix}` for this server.")


@bot.hybrid_command(name="vote", description="Vote for Spectra!")
@commands.cooldown(1, 15, commands.BucketType.user)
async def vote(ctx: commands.Context):
    embed = discord.Embed(
        title="Want to support Spectra by voting? Click below!",
        description="[Click Me To Vote!](https://top.gg/bot/1279512390756470836/vote)",
        color=discord.Colour.blue(),
    )
    embed.set_footer(text="Support Spectra For Free!")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="ping", description="Check if the bot is online.")
@commands.cooldown(1, 5, commands.BucketType.user)
async def ping(ctx: commands.Context):
    then = datetime.datetime.now()

    msg = await ctx.send("Pinging...")

    now = datetime.datetime.now()
    time_diff = (now - then).total_seconds() * 1000

    await msg.edit(
        content=f"Pong! 🏓 \nDiscord: `{round(ctx.bot.latency * 1000)}ms`\nBot Latency: `{round(time_diff)}ms`"
    )


@bot.hybrid_command(name="invite", description="Invite Spectra to your server!")
@commands.cooldown(1, 5, commands.BucketType.user)
async def invite(ctx: commands.Context):
    embed = discord.Embed(
        title="Invite Spectra to your server!",
        description="[Click Me To Invite!](https://discord.com/oauth2/authorize?client_id=1279512390756470836&permissions=939912256&integration_type=0&scope=bot+applications.commands)",
        color=discord.Colour.blue(),
    )
    embed.set_footer(text="Invite Spectra For Free!")
    await ctx.send(embed=embed)


@bot.hybrid_command(name="support", description="Support server of the bot")
@commands.cooldown(1, 5, commands.BucketType.user)
async def support(ctx: commands.Context):
    embed = discord.Embed(
        title="Support Server",
        description="E-mail: spectra.official@protonmail.com\n[Click here to join the support server.](https://discord.gg/fcPF66DubA)",
        color=discord.Color.blue(),
    )
    embed.set_footer(text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif")
    await ctx.send(embed=embed, ephemeral=True)


@bot.command()
@commands.is_owner()
async def refresh(ctx: commands.Context, extension):
    if ctx.author.id == 856196104385986560 or ctx.author.id == 998434044335374336:
        await bot.reload_extension(f"{extension}")
        await ctx.send("Success.")
    else:
        return


@bot.command()
@commands.is_owner()
async def load(ctx: commands.Context, extension):
    if ctx.author.id == 856196104385986560 or ctx.author.id == 998434044335374336:
        await bot.load_extension(f"{extension}")
        await ctx.send("Success.")
    else:
        return


@bot.hybrid_command(name="servers", description="Spectra's server count")
@commands.cooldown(1, 15, commands.BucketType.user)
async def servers(ctx: commands.Context):
    await ctx.send(f"Currently in {len(bot.guilds)} servers.", ephemeral=True)


@bot.command()
@commands.is_owner()
async def blacklist(ctx, target: str, target_id: int):
    if target.lower() == "user":
        await blacklist_collection.update_one(
            {"_id": target_id}, {"$set": {"type": "user"}}, upsert=True
        )
        await ctx.send(f"User `{target_id}` has been blacklisted.")
    elif target.lower() == "server":
        await blacklist_collection.update_one(
            {"_id": target_id}, {"$set": {"type": "server"}}, upsert=True
        )
        await ctx.send(f"Server `{target_id}` has been blacklisted.")
    else:
        await ctx.send("Invalid target. Use `user` or `server`.")


@bot.command()
@commands.is_owner()
async def unblacklist(ctx, target: str, target_id: int):
    result = await blacklist_collection.delete_one({"_id": target_id})
    if result.deleted_count:
        await ctx.send(f"Successfully removed `{target_id}` from the blacklist.")
    else:
        await ctx.send(f"`{target_id}` is not blacklisted.")


# Mod Logs


async def send_modlog(guild_id, action_taker: discord.Member, action, message):
    guild = bot.get_guild(guild_id)
    if not guild:
        print(f"Guild not found for ID: {guild_id}")
        return
    mod_logs = await modlog_collection.find_one({"guild_id": str(guild.id)})
    if mod_logs:
        log_channel = discord.utils.get(guild.channels, id=int(mod_logs["channel_id"]))
        if not log_channel:
            print(f"Log channel not found for ID: {mod_logs['channel_id']}")
            return
        embed = discord.Embed(
            title=f"{action}",
            description=f"<:modshield:1325613380945444864> {message}",
            color=discord.Color.yellow(),
        )
        taker = guild.get_member(action_taker)
        embed.add_field(
            name="Issued by", value=(taker.mention if taker else "None found")
        )
        embed.add_field(
            name="Issued at",
            value=f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        )
        try:
            embed.set_thumbnail(url=guild.icon.url)
        except:
            pass
        embed.set_footer(text="Moderation Log")
        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            print(f"Error sending embed: {e}")
    else:
        print(f"No modlog configuration found for guild {guild.id}")


@bot.event
async def on_modlog(guild_id, action_taker, action, message):
    await send_modlog(guild_id, action_taker, action, message)

# Run Bot

async def main():
    await bot.start(os.environ.get("TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())