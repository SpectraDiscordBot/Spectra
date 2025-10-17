import discord
from discord import app_commands
from discord.ext import commands, tasks
from db import server_stats_collection
import asyncio
import datetime

class ServerStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}
        self.channel_update_cache = {}

    async def cog_unload(self):
        self.periodic_update.stop()
    
    async def load_guild_config(self, guild_id):
        config = await server_stats_collection.find_one({"guild_id": str(guild_id)})
        if config:
            self.cache[str(guild_id)] = config
        else:
            self.cache[str(guild_id)] = {}

    def get_counter_display_name(self, counter_type, custom_name=None):
        if custom_name:
            return custom_name
        return counter_type.replace("_", " ").title()

    async def update_counter(self, guild, counter_type, channel_id, custom_name=None):
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        count = 0
        if counter_type == "Members":
            count = sum(1 for m in guild.members if not m.bot)
        elif counter_type == "Bots":
            count = sum(1 for m in guild.members if m.bot)
        elif counter_type == "Members and Bots":
            count = len(guild.members)
        elif counter_type == "Online":
            count = sum(1 for m in guild.members if m.status != discord.Status.offline)
        elif counter_type == "Roles":
            count = len(guild.roles)
        elif counter_type == "Boosts":
            count = guild.premium_subscription_count or 0
        elif counter_type == "Emojis":
            count = len(guild.emojis)
        elif counter_type == "Stickers":
            count = len(guild.stickers)
        elif counter_type == "Text Channels":
            count = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
        elif counter_type == "Voice Channels":
            count = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
        elif counter_type == "Categories":
            count = len([c for c in guild.channels if isinstance(c, discord.CategoryChannel)])
        elif counter_type == "Threads":
            count = len([t for t in guild.threads])

        display_name = self.get_counter_display_name(counter_type, custom_name)
        new_name = f"{display_name}: {count}"

        now = datetime.datetime.utcnow()
        cache_entry = self.channel_update_cache.get(channel.id)

        try:
            current_name = channel.name
        except Exception:
            current_name = None

        if current_name == new_name:
            return

        if cache_entry:
            last_name = cache_entry.get("name")
            last_update = cache_entry.get("last_update")
            if last_name == new_name and last_update and (now - last_update).total_seconds() < 15:
                return

        try:
            await channel.edit(name=new_name, reason="Updating server stats counter")
            self.channel_update_cache[channel.id] = {"name": new_name, "last_update": now}
        except Exception as e:
            print(f"Failed to update counter channel name: {e}")
            self.channel_update_cache.setdefault(channel.id, {})["last_update"] = now

    @tasks.loop(seconds=60)
    async def periodic_update(self):
        if not self.bot.ready:
            return
        for guild_id, config in list(self.cache.items()):
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                continue
            counters = config.get("counters", [])
            for counter in counters:
                await asyncio.sleep(0.5)
                try:
                    await self.update_counter(
                        guild,
                        counter["type"],
                        counter["channel_id"],
                        counter.get("custom_name")
                    )
                except Exception as e:
                    print(f"Error updating server stat for guild {guild_id}, counter {counter}: {e}")
            await asyncio.sleep(0.2)

    @commands.hybrid_group(name="serverstats")
    async def serverstats(self, ctx):
        pass

    @serverstats.group(name="category", description="Manage counter categories")
    async def serverstats_category(self, ctx):
        pass

    @serverstats.group(name="counter", description="Manage counters")
    async def serverstats_counter(self, ctx):
        pass

    @serverstats.command(name="info", description="Get information about the server stats configuration")
    @commands.has_permissions(manage_channels=True)
    async def serverstats_info(self, ctx):
        guild_id = str(ctx.guild.id)
        config = self.cache.get(guild_id, {})
        category_id = config.get("category_id")
        counters = config.get("counters", [])
        embed = discord.Embed(title="Server Stats Configuration")
        embed.add_field(name="Counter Category", value=f"<#{category_id}>" if category_id else "Not Set", inline=False)
        if counters:
            counter_list = "\n".join([
                f"- {self.get_counter_display_name(c['type'], c.get('custom_name'))}: <#{c['channel_id']}>"
                for c in counters
            ])
            embed.add_field(name="Counters", value=counter_list, inline=False)
        else:
            embed.add_field(name="Counters", value="No counters set up.", inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    @serverstats_category.command(name="create", description="Create a counter category")
    @commands.has_permissions(manage_channels=True)
    async def create_category(self, ctx):
        guild_id = str(ctx.guild.id)
        existing = self.cache.get(guild_id, {}).get("category_id")
        if existing:
            await ctx.send(embed=discord.Embed(description=f"A counter category already exists."), ephemeral=True)
            return
        category = await ctx.guild.create_category("Server Stats", reason="Creating counter category for server stats", position=0)
        await category.edit(position=0)
        await server_stats_collection.insert_one({"guild_id": guild_id, "category_id": category.id, "counters": []})
        await self.load_guild_config(guild_id)
        await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> Counter category created successfully."), ephemeral=True)
        self.bot.dispatch(
            "modlog",
            ctx.guild.id,
            ctx.author.id,
            "Created Counter Category",
            f"A counter category named 'Server Stats' has been created.",
        )

    @serverstats_category.command(name="delete", description="Delete the counter category and all its channels")
    @commands.has_permissions(manage_channels=True)
    async def delete_category(self, ctx):
        guild_id = str(ctx.guild.id)
        config = self.cache.get(guild_id, {})
        category_id = config.get("category_id")
        if not category_id:
            await ctx.send(embed=discord.Embed(description="No counter category is set."), ephemeral=True)
            return
        category = ctx.guild.get_channel(category_id)
        if category:
            for channel in category.channels:
                await channel.delete()
            await category.delete()
        await server_stats_collection.delete_one({"guild_id": guild_id})
        await self.load_guild_config(guild_id)
        await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> Counter category and all its channels have been deleted."), ephemeral=True)
        self.bot.dispatch(
            "modlog",
            ctx.guild.id,
            ctx.author.id,
            "Deleted Counter Category",
            f"The counter category named 'Server Stats' has been deleted.",
        )

    async def counter_create_autocomplete(self, interaction: discord.Interaction, current: str):
        options = ["Members", "Bots", "Members and Bots", "Online", "Text Channels", "Voice Channels", "Roles", "Boosts", "Emojis", "Stickers", "Categories", "Threads"]
        return [
            app_commands.Choice(name=option.replace("_", " ").title(), value=option)
            for option in options if current.lower() in option.lower()
        ][:25]
    
    async def counter_channel_type_autocomplete(self, interaction: discord.Interaction, current: str):
        options = ["Text Channel", "Voice Channel", "Stage Channel", "Announcement Channel", "Forum Channel"]
        return [
            app_commands.Choice(name=option.title(), value=option)
            for option in options if current.lower() in option.lower()
        ][:25]

    @serverstats_counter.command(name="add", description="Add a new counter")
    @commands.has_permissions(manage_channels=True)
    @app_commands.describe(counter_type="Type of counter to create", channel_type="Type of channel to create", custom_name="Custom name for the counter (optional)")
    @app_commands.autocomplete(counter_type=counter_create_autocomplete, channel_type=counter_channel_type_autocomplete)
    async def counter_add(self, ctx, counter_type: str, channel_type: str = "Voice Channel", custom_name: str = None):
        guild_id = str(ctx.guild.id)
        config = self.cache.get(guild_id, {})
        category_id = config.get("category_id")
        if not category_id:
            await ctx.send(embed=discord.Embed(description="No counter category is set. Please create one first."), ephemeral=True)
            return
        counters = config.get("counters", [])
        if any(c['type'] == counter_type for c in counters):
            await ctx.send(embed=discord.Embed(description=f"A counter for {counter_type.replace('_', ' ').title()} already exists."), ephemeral=True)
            return
        category = ctx.guild.get_channel(category_id)
        if not category:
            await ctx.send(embed=discord.Embed(description="The counter category no longer exists. Please recreate it."), ephemeral=True)
            return
        
        display_name = self.get_counter_display_name(counter_type, custom_name)
        channel_name = f"{display_name}: 0"

        channel_overwrites = discord.PermissionOverwrite(
            send_messages=False, connect=False, create_public_threads=False, create_private_threads=False, 
        )
        
        if channel_type == "Text Channel":
            channel = await ctx.guild.create_text_channel(channel_name, category=category, overwrites={ctx.guild.default_role: channel_overwrites})
        elif channel_type == "Voice Channel":
            channel = await ctx.guild.create_voice_channel(channel_name, category=category, overwrites={ctx.guild.default_role: channel_overwrites})
        elif channel_type == "Stage Channel":
            channel = await ctx.guild.create_stage_channel(channel_name, category=category, overwrites={ctx.guild.default_role: channel_overwrites})
        elif channel_type == "Announcement Channel":
            channel = await ctx.guild.create_news_channel(channel_name, category=category, overwrites={ctx.guild.default_role: channel_overwrites})
        elif channel_type == "Forum Channel":
            channel = await ctx.guild.create_forum_channel(channel_name, category=category, overwrites={ctx.guild.default_role: channel_overwrites})
        else:
            await ctx.send(embed=discord.Embed(description="Invalid channel type specified."), ephemeral=True)
            return
            
        counter_data = {"type": counter_type, "channel_id": channel.id}
        if custom_name:
            counter_data["custom_name"] = custom_name
            
        counters.append(counter_data)
        await server_stats_collection.update_one({"guild_id": guild_id}, {"$set": {"counters": counters}})
        await self.load_guild_config(guild_id)
        await self.update_counter(ctx.guild, counter_type, channel.id, custom_name)
        await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> Counter for {counter_type.replace('_', ' ').title()} created successfully."), ephemeral=True)
        self.bot.dispatch(
            "modlog",
            ctx.guild.id,
            ctx.author.id,
            "Created Counter",
            f"A counter for {counter_type.replace('_', ' ').title()} has been created.",
        )

    @serverstats_counter.command(name="remove", description="Remove an existing counter")
    @commands.has_permissions(manage_channels=True)
    @app_commands.describe(counter_type="Type of counter to remove")
    @app_commands.autocomplete(counter_type=counter_create_autocomplete)
    async def counter_remove(self, ctx, counter_type: str):
        guild_id = str(ctx.guild.id)
        config = self.cache.get(guild_id, {})
        counters = config.get("counters", [])
        counter = next((c for c in counters if c['type'] == counter_type), None)
        if not counter:
            await ctx.send(embed=discord.Embed(description=f"No counter for {counter_type.replace('_', ' ').title()} exists."), ephemeral=True)
            return
        channel = ctx.guild.get_channel(counter['channel_id'])
        if channel:
            await channel.delete()
        counters = [c for c in counters if c['type'] != counter_type]
        await server_stats_collection.update_one({"guild_id": guild_id}, {"$set": {"counters": counters}})
        await self.load_guild_config(guild_id)
        await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> Counter for {counter_type.replace('_', ' ').title()} has been removed."), ephemeral=True)
        self.bot.dispatch(
            "modlog",
            ctx.guild.id,
            ctx.author.id,
            "Removed Counter",
            f"The counter for {counter_type.replace('_', ' ').title()} has been removed.",
        )

    @serverstats_counter.command(name="rename", description="Rename an existing counter")
    @commands.has_permissions(manage_channels=True)
    @app_commands.describe(counter_type="Type of counter to rename", new_name="New name for the counter")
    @app_commands.autocomplete(counter_type=counter_create_autocomplete)
    async def counter_rename(self, ctx, counter_type: str, new_name: str):
        guild_id = str(ctx.guild.id)
        config = self.cache.get(guild_id, {})
        counters = config.get("counters", [])
        counter = next((c for c in counters if c['type'] == counter_type), None)
        if not counter:
            await ctx.send(embed=discord.Embed(description=f"No counter for {counter_type.replace('_', ' ').title()} exists."), ephemeral=True)
            return
            
        counter["custom_name"] = new_name
        await server_stats_collection.update_one({"guild_id": guild_id}, {"$set": {"counters": counters}})
        await self.load_guild_config(guild_id)
        await self.update_counter(ctx.guild, counter_type, counter['channel_id'], new_name)
            
        await ctx.send(embed=discord.Embed(description=f"<:Checkmark:1326642406086410317> Counter renamed to {new_name}."), ephemeral=True)
        self.bot.dispatch(
            "modlog",
            ctx.guild.id,
            ctx.author.id,
            "Renamed Counter",
            f"The counter for {counter_type.replace('_', ' ').title()} has been renamed to {new_name}.",
        )

    @serverstats_counter.command(name="list", description="List all counters in the server")
    @commands.has_permissions(manage_channels=True)
    async def counter_list(self, ctx):
        guild_id = str(ctx.guild.id)
        config = self.cache.get(guild_id, {})
        counters = config.get("counters", [])
        if not counters:
            await ctx.send(embed=discord.Embed(description="No counters are set up in this server."), ephemeral=True)
            return
        description = "\n".join([
            f"- {self.get_counter_display_name(c['type'], c.get('custom_name'))}"
            for c in counters
        ])
        embed = discord.Embed(title="Server Counters", description=description)
        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot):
    cog = ServerStats(bot)

    async for config in server_stats_collection.find():
        guild_id = config["guild_id"]
        cog.cache[guild_id] = config
    
    cog.periodic_update.start()
    await bot.add_cog(cog)