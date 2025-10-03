import discord
import asyncio
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from db import autorole_collection

load_dotenv()

class AutoRoleQueue:
	def __init__(self, bot, per_guild_delay: float = 1.0, batch_size: int = 10, hybrid_threshold: int = 2):
		self.bot = bot
		self.per_guild_delay = per_guild_delay
		self.batch_size = batch_size
		self.hybrid_threshold = hybrid_threshold
		self._queues: dict[int, asyncio.Queue] = {}
		self._workers: dict[int, asyncio.Task] = {}
		self._processing: dict[int, set[int]] = {}

	async def ensure_queue(self, guild_id: int):
		if guild_id not in self._queues:
			self._queues[guild_id] = asyncio.Queue()
			self._processing[guild_id] = set()
			self._workers[guild_id] = asyncio.create_task(self._worker(guild_id))

	async def enqueue_member(self, member: discord.Member):
		guild_id = member.guild.id
		await self.ensure_queue(guild_id)

		if member.id in self._processing[guild_id] or any(m.id == member.id for m in self._queues[guild_id]._queue):
			return

		queue = self._queues[guild_id]
		if queue.qsize() < self.hybrid_threshold:
			await self._process_member(member)
		else:
			await queue.put(member)

	async def _worker(self, guild_id: int):
		queue = self._queues[guild_id]
		while True:
			batch = []
			try:
				member = await queue.get()
				batch.append(member)

				while len(batch) < self.batch_size:
					try:
						member = await asyncio.wait_for(queue.get(), timeout=self.per_guild_delay)
						batch.append(member)
					except asyncio.TimeoutError:
						break
			except asyncio.CancelledError:
				return

			if batch:
				await self._process_batch(guild_id, batch)
				for _ in batch:
					queue.task_done()

	async def _process_batch(self, guild_id: int, members: list[discord.Member]):
		tasks = [self._process_member(member) for member in members]
		await asyncio.gather(*tasks)

	async def _process_member(self, member: discord.Member):
		guild_id = member.guild.id
		self._processing[guild_id].add(member.id)
		try:
			roles_data = self.bot.get_cog("AutoRole_Commands").cache.get(str(guild_id))
			if roles_data is None:
				await self.bot.get_cog("AutoRole_Commands").load_guild_roles(guild_id)
				roles_data = self.bot.get_cog("AutoRole_Commands").cache.get(str(guild_id), [])

			roles_to_add = []
			for r in roles_data:
				if r.get("ignore_bots", False) and member.bot:
					continue
				role = member.guild.get_role(r["role_id"])
				if role:
					roles_to_add.append(role)

			if roles_to_add:
				await self._safe_add_roles(member, roles_to_add)

		finally:
			self._processing[guild_id].discard(member.id)

	async def _safe_add_roles(self, member: discord.Member, roles: list[discord.Role]):
		backoff = 1.0
		for attempt in range(5):
			try:
				await member.add_roles(*roles, reason="Spectra AutoRole")
				return
			except discord.Forbidden:
				return 
			except discord.HTTPException:
				await asyncio.sleep(backoff)
				backoff = min(backoff * 2, 60)
			except Exception as e:
				print(f"Error adding roles to {member.id}: {e}")
		print(f"Failed to add roles to member {member.id} after multiple attempts.")

	async def shutdown(self):
		for task in self._workers.values():
			task.cancel()
		await asyncio.gather(*self._workers.values(), return_exceptions=True)

class AutoRole_Commands(commands.Cog):
	def __init__(self, bot):
		self.bot = bot
		self.cache = {}
		self.queue = AutoRoleQueue(bot)

	async def load_guild_roles(self, guild_id):
		data = await autorole_collection.find({"guild_id": str(guild_id)}).to_list(length=None)
		self.cache[str(guild_id)] = [
			{"role_id": int(d["role"]), "ignore_bots": d.get("ignore_bots", False)} for d in data
		]

	async def cog_unload(self):
		await self.queue.shutdown()

	@commands.Cog.listener()
	async def on_guild_role_delete(self, role):
		existing = await autorole_collection.find_one({"guild_id": str(role.guild.id), "role": str(role.id)})
		if existing:
			try: 
				await autorole_collection.delete_one({"guild_id": str(role.guild.id), "role": str(role.id)})
				if str(role.guild.id) in self.cache:
					self.cache[str(role.guild.id)] = [
						r for r in self.cache[str(role.guild.id)] if r["role_id"] != role.id
					]
				self.bot.dispatch(
					"modlog",
					role.guild.id,
					self.bot.user.id,
					"Removed an Auto-Role",
					f"Automatically removed **{role.name}** `{role.id}` as an Auto-Role due to it being deleted.",
				)
			except Exception as e:
				print(e)

	@commands.hybrid_group(name="autorole", description="Manage auto roles.")
	async def autorole(self, ctx):
		pass
	
	@autorole.command(name="add", description="Add an auto role.")
	@commands.has_permissions(manage_roles=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(auto_role="The role you want to set as auto role.", ignore_bots="Whether to ignore bots when assigning this role.")
	async def autorole_add(self, ctx, auto_role: discord.Role, ignore_bots: bool = False):
		role_id = str(auto_role.id)
		guild_id = str(ctx.guild.id)
		if guild_id not in self.cache:
			await self.load_guild_roles(guild_id)
		existing_autorole = await autorole_collection.find_one(
			{"guild_id": guild_id, "role": role_id}
		)
		count = len(self.cache.get(guild_id, []))

		if count >= 5:
			await ctx.send(
				"You have reached the maximum limit of 5 auto roles. Please remove one first.",
				delete_after=10,
				ephemeral=True
			)
			return
		if auto_role.managed:
			await ctx.send("You cannot set a managed role as an auto role.", delete_after=10, ephemeral=True)
			return
		if existing_autorole:
			await ctx.send("That AutoRole has already been set.", delete_after=10, ephemeral=True)
			return
		if auto_role.position >= ctx.guild.me.top_role.position:
			await ctx.send("I cannot assign that role because it is higher than my highest role.", delete_after=10, ephemeral=True)
			return
		else:
			await autorole_collection.insert_one({"guild_id": guild_id, "role": role_id, "ignore_bots": ignore_bots})
			self.cache.setdefault(guild_id, []).append({"role_id": auto_role.id, "ignore_bots": ignore_bots})
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Added an Auto-Role",
				f"Added {auto_role.mention} as an Auto-Role.\nIgnore Bots: {ignore_bots}",
			)
			await ctx.send(
				f"<:Checkmark:1326642406086410317> **{auto_role.name}** has been successfully added.", ephemeral=True
			)

	@autorole.command(name="remove", description="Remove an auto role.")
	@commands.has_permissions(manage_roles=True)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@app_commands.describe(auto_role="The role you want to remove from auto roles.")
	async def autorole_remove(self, ctx, auto_role: discord.Role):
		guild_id = str(ctx.guild.id)
		if guild_id not in self.cache:
			await self.load_guild_roles(guild_id)
		autorole = await autorole_collection.find_one(
			{"guild_id": guild_id, "role": str(auto_role.id)}
		)

		if autorole:
			await autorole_collection.delete_one(
				{"guild_id": guild_id, "role": str(auto_role.id)}
			)
			if guild_id in self.cache:
				self.cache[guild_id] = [
					r for r in self.cache[guild_id] if r["role_id"] != auto_role.id
				]
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Removed an Auto-Role",
				f"Removed {auto_role.mention} as an Auto-Role.",
			)
			await ctx.send(
				f"<:Checkmark:1326642406086410317> **{auto_role.name}** has been successfully removed.",
				ephemeral=True,
			)
		else:
			await ctx.send("That AutoRole has not been set.", delete_after=10)

	@autorole.command(name="list", description="List all auto roles in the server.")
	async def autorole_list(self, ctx):
		roles = self.cache.get(str(ctx.guild.id), [])
		if not roles:
			await self.load_guild_roles(ctx.guild.id)
			roles = self.cache.get(str(ctx.guild.id), [])
			if not roles:
				await ctx.send("No auto roles have been set up yet.", ephemeral=True)
				return

		role_mentions = []
		for r in roles:
			role = ctx.guild.get_role(r["role_id"])
			if role:
				role_mentions.append(role.mention)

		if not role_mentions:
			await ctx.send("No valid auto roles found.", ephemeral=True)
			return

		embed = discord.Embed(
			title="Auto Roles",
			description="\n".join(role_mentions)
		)
		await ctx.send(embed=embed, ephemeral=True)

	@commands.Cog.listener()
	async def on_member_join(self, member: discord.Member):
		await self.queue.enqueue_member(member)

async def setup(bot):
	await bot.add_cog(AutoRole_Commands(bot))