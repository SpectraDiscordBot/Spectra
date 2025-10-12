import discord
import emoji as Emoji
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from db import reaction_roles_collection, button_roles_collection, button_settings_collection

load_dotenv()

class ReactionRoleCommands(commands.Cog):
	def __init__(self, bot):
		self.bot = bot

	async def get_settings(self, guild_id):
		default = {
			"embed_title": "Select Your Roles",
			"embed_description": "Click a button to assign/remove roles.",
			"embed_color": 0xE91E63,
			"max_buttons": 15,
			"button_add_msg": "Added the **{role}** role",
			"button_remove_msg": "Removed the **{role}** role",
			"reaction_add_msg": "Added the **{role}** role",
			"reaction_remove_msg": "Removed the **{role}** role"
		}
		data = await button_settings_collection.find_one({"guild_id": guild_id})
		if data:
			default.update(data)
		return default

	@commands.hybrid_group(name="reaction-role")
	async def reaction_role(self, ctx):
		pass

	@reaction_role.command(name="reaction-role-settings", description="Configure role assignment settings")
	@commands.has_permissions(manage_guild=True)
	@app_commands.describe(
		embed_title="Embed title",
		embed_description="Embed description",
		embed_color="Embed color (hex, e.g. #ff00ff)",
		button_add_msg="Button role added message",
		button_remove_msg="Button role removed message",
		reaction_add_msg="Reaction role added message",
		reaction_remove_msg="Reaction role removed message"
	)
	async def reaction_role_settings(
		self,
		ctx,
		embed_title: str = None,
		embed_description: str = None,
		embed_color: str = None,
		button_add_msg: str = None,
		button_remove_msg: str = None,
		reaction_add_msg: str = None,
		reaction_remove_msg: str = None
	):
		if not ctx.interaction:
			await ctx.send("Due to security reasons, this command cannot be used via prefix.")
			return
		guild_id = str(ctx.guild.id)
		data = await button_settings_collection.find_one({"guild_id": guild_id}) or {}

		if embed_title is not None:
			data["embed_title"] = embed_title
		if embed_description is not None:
			data["embed_description"] = embed_description
		if embed_color is not None:
			try:
				if embed_color.startswith("#"):
					embed_color = embed_color[1:]
				color_int = int(embed_color, 16)
				data["embed_color"] = color_int
			except:
				await ctx.send("Invalid embed color. Use hex code like #ff00ff.", ephemeral=True)
				return
		if button_add_msg is not None:
			data["button_add_msg"] = button_add_msg
		if button_remove_msg is not None:
			data["button_remove_msg"] = button_remove_msg
		if reaction_add_msg is not None:
			data["reaction_add_msg"] = reaction_add_msg
		if reaction_remove_msg is not None:
			data["reaction_remove_msg"] = reaction_remove_msg

		await button_settings_collection.update_one({"guild_id": guild_id}, {"$set": data}, upsert=True)
		await ctx.send("Role settings updated.", ephemeral=True)

	@reaction_role.command(name="add", description="Add a new role assignment")
	@commands.has_permissions(manage_roles=True)
	@app_commands.describe(
		type="Button or reaction role",
		role="Role to assign",
		label="Button label (for button roles)",
		emoji="Emoji for button/reaction",
		style="Button style (primary, secondary, success, danger)",
		message="Message link (for reaction roles)"
	)
	async def add_raction_role(
		self,
		ctx: commands.Context,
		type: str,
		role: discord.Role,
		label: str = None,
		emoji: str = None,
		style: str = "primary",
		message: str = None
	):
		if not ctx.interaction:
			await ctx.send("Due to security reasons, this command cannot be used via prefix.")
			return
		guild_id = str(ctx.guild.id)
		type = type.lower()
		
		if type not in ["button", "reaction"]:
			await ctx.send("Invalid type. Use 'button' or 'reaction'.", ephemeral=True)
			return
		
		if type == "button":
			if not label:
				await ctx.send("Label is required for button roles.", ephemeral=True)
				return
			if len(label) > 80:
				await ctx.send("Label max length is 80 characters.", ephemeral=True)
				return
			
			if emoji:
				if emoji.isdigit():
					custom_emoji = self.bot.get_emoji(int(emoji))
					if not custom_emoji:
						await ctx.send("Custom emoji not found.", ephemeral=True)
						return
				elif not Emoji.is_emoji(emoji):
					await ctx.send("Invalid emoji. Use unicode or custom emoji ID.", ephemeral=True)
					return
			
			style_map = {
				"primary": discord.ButtonStyle.primary,
				"secondary": discord.ButtonStyle.secondary,
				"success": discord.ButtonStyle.success,
				"danger": discord.ButtonStyle.danger,
			}
			if style.lower() not in style_map:
				await ctx.send("Invalid button style.", ephemeral=True)
				return
			
			existing = await button_roles_collection.find_one({"guild_id": guild_id})
			roles = existing.get("roles", []) if existing else []
			settings = await self.get_settings(guild_id)
			
			if len(roles) >= settings["max_buttons"]:
				await ctx.send(f"Max buttons reached ({settings['max_buttons']}).", ephemeral=True)
				return
			
			for r in roles:
				if r["role_id"] == str(role.id):
					await ctx.send(f"Role {role.name} already configured.", ephemeral=True)
					return
				
			if role.position >= ctx.guild.me.top_role.position:
				await ctx.send("Cannot assign this role due to role hierarchy.", ephemeral=True)
				return
			
			if role.position >= ctx.author.top_role.position and ctx.author != ctx.guild.owner:
				await ctx.send("You cannot assign a role higher than or equal to your highest role.", ephemeral=True)
				return
			
			roles.append({
				"label": label,
				"emoji": emoji or None,
				"role_id": str(role.id),
				"style": style.lower()
			})
			await button_roles_collection.update_one({"guild_id": guild_id}, {"$set": {"roles": roles}}, upsert=True)
			await ctx.send(f"Added button role `{role.name}`.", ephemeral=True)
		
		elif type == "reaction":
			if not message:
				await ctx.send("Message link is required for reaction roles.", ephemeral=True)
				return
			if not emoji:
				await ctx.send("Emoji is required for reaction roles.", ephemeral=True)
				return
			
			try:
				message_id = int(message.split('/')[-1])
				channel_id = int(message.split('/')[-2])
			except:
				await ctx.send("Invalid message link.", ephemeral=True)
				return
			
			channel = self.bot.get_channel(channel_id)
			if not channel:
				await ctx.send("Channel not found.", ephemeral=True)
				return
			
			try:
				message_obj = await channel.fetch_message(message_id)
			except:
				await ctx.send("Message not found.", ephemeral=True)
				return
			
			custom_emoji = None
			emoji_str = emoji
			if emoji.isdigit():
				custom_emoji = self.bot.get_emoji(int(emoji))
				if not custom_emoji:
					await ctx.send("Custom emoji not found.", ephemeral=True)
					return
				emoji_str = str(custom_emoji.id)
			elif emoji.startswith('<:') and emoji.endswith('>'):
				parts = emoji.split(':')
				if len(parts) < 3:
					await ctx.send("Invalid custom emoji format.", ephemeral=True)
					return
				emoji_id = parts[2][:-1]
				if not emoji_id.isdigit():
					await ctx.send("Invalid custom emoji ID.", ephemeral=True)
					return
				custom_emoji = self.bot.get_emoji(int(emoji_id))
				if not custom_emoji:
					await ctx.send("Custom emoji not found.", ephemeral=True)
					return
				emoji_str = emoji_id
			else:
				if not Emoji.is_emoji(emoji):
					await ctx.send("Invalid emoji. Use unicode or custom emoji.", ephemeral=True)
					return
				emoji_str = emoji

			existing_messages = await reaction_roles_collection.distinct(
				"message_id", {"guild_id": guild_id}
			)

			if len(existing_messages) >= 4:
				await ctx.send("You have reached the maximum of 4 reaction role messages.", ephemeral=True)
				return

			"""
			if len(existing_messages) >= 4:
				if len(existing_messages) == 8:
					await ctx.send("You have reached the maximum of 8 reaction role messages.", ephemeral=True)
					return
				
				topgg_cog = self.bot.get_cog("TopGG")
				if topgg_cog:
					has_voted = await topgg_cog.check_vote(ctx.author.id)
					if not has_voted:
						embed = discord.Embed(
							title="Vote Required!",
							description=(
								"Your server already has 4 reaction role messages configured.\n\n"
								"To add more, you need to vote for the bot on [Top.gg](https://top.gg/bot/1279512390756470836/vote).\n"
								"You can vote every 12 hours."
							),
							color=discord.Color.orange()
						)
						button = discord.ui.Button(
							label="Vote Here!", url=f"https://top.gg/bot/{self.bot.user.id}/vote"
						)
						view = discord.ui.View()
						view.add_item(button)
						return await ctx.send(embed=embed, view=view, ephemeral=True)
				if not topgg_cog:
					await ctx.send("We're having issues with TopGG at the moment, please check back later.", ephemeral=True)
					return
			"""
			existing = await reaction_roles_collection.find_one({
				"guild_id": guild_id,
				"message_id": str(message_obj.id),
				"emoji": emoji_str
			})
			if existing:
				await ctx.send("Reaction role already exists for this message and emoji.", ephemeral=True)
				return
			
			if role.position >= ctx.guild.me.top_role.position:
				await ctx.send("Cannot assign this role due to role hierarchy.", ephemeral=True)
				return
			
			if role.position >= ctx.author.top_role.position and ctx.author != ctx.guild.owner:
				await ctx.send("You cannot assign a role higher than or equal to your highest role.", ephemeral=True)
				return
			
			try:
				await message_obj.add_reaction(custom_emoji if emoji_str.isdigit() else emoji)
			except:
				await ctx.send("Failed to add reaction.", ephemeral=True)
				return
			
			await reaction_roles_collection.insert_one({
				"guild_id": guild_id,
				"message_id": str(message_obj.id),
				"emoji": emoji_str,
				"role_id": str(role.id)
			})
			await ctx.send(f"Added reaction role: {custom_emoji or emoji} for {role.mention}", ephemeral=True)

	@reaction_role.command(name="remove", description="Remove a role assignment")
	@commands.has_permissions(manage_roles=True)
	@app_commands.describe(
		type="Button or reaction role",
		role="Role to remove (for button roles)",
		message="Message link (for reaction roles)",
		emoji="Emoji (for reaction roles)"
	)
	async def remove_reaction_role(
		self,
		ctx: commands.Context,
		type: str,
		role: discord.Role = None,
		message: str = None,
		emoji: str = None
	):
		if not ctx.interaction:
			await ctx.send("Due to security reasons, this command cannot be used via prefix.")
			return
		guild_id = str(ctx.guild.id)
		type = type.lower()
		
		if type not in ["button", "reaction"]:
			await ctx.send("Invalid type. Use 'button' or 'reaction'.", ephemeral=True)
			return
		
		if type == "button":
			if not role:
				await ctx.send("Role is required for button roles.", ephemeral=True)
				return
			
			data = await button_roles_collection.find_one({"guild_id": guild_id})
			if not data or "roles" not in data:
				await ctx.send("No button roles configured.", ephemeral=True)
				return
			
			roles = data["roles"]
			found = False
			for idx, role_data in enumerate(roles):
				if int(role_data["role_id"]) == role.id:
					roles.pop(idx)
					found = True
					break
			
			if not found:
				await ctx.send(f"Button role for `{role.name}` not found.", ephemeral=True)
				return
			
			await button_roles_collection.update_one({"guild_id": guild_id}, {"$set": {"roles": roles}})
			await ctx.send(f"Removed button role `{role.name}`.", ephemeral=True)
		
		elif type == "reaction":
			if not message or not emoji:
				await ctx.send("Message link and emoji are required for reaction roles.", ephemeral=True)
				return
			
			try:
				message_id = int(message.split('/')[-1])
			except:
				await ctx.send("Invalid message link.", ephemeral=True)
				return
			
			emoji_str = emoji
			if emoji.isdigit():
				emoji_str = emoji
			elif emoji.startswith('<:') and emoji.endswith('>'):
				parts = emoji.split(':')
				if len(parts) < 3:
					await ctx.send("Invalid custom emoji format.", ephemeral=True)
					return
				emoji_id = parts[2][:-1]
				if not emoji_id.isdigit():
					await ctx.send("Invalid custom emoji ID.", ephemeral=True)
					return
				emoji_str = emoji_id
			
			data = await reaction_roles_collection.find_one({
				"guild_id": guild_id,
				"message_id": str(message_id),
				"emoji": emoji_str
			})
			if not data:
				await ctx.send("Reaction role not found.", ephemeral=True)
				return
			
			await reaction_roles_collection.delete_one({"_id": data["_id"]})
			await ctx.send("Reaction role configuration removed.", ephemeral=True)

	@reaction_role.command(name="send", description="Send the button role panel")
	@commands.has_permissions(manage_channels=True)
	@app_commands.describe(channel="Channel to send message in")
	async def send_panel(self, ctx: commands.Context, channel: discord.TextChannel = None):
		guild_id = str(ctx.guild.id)
		if not channel:
			channel = ctx.channel
		
		data = await button_roles_collection.find_one({"guild_id": guild_id})
		roles = data.get("roles", []) if data else []
		if not roles:
			await ctx.send("No button roles configured.", ephemeral=True)
			return
		
		settings = await self.get_settings(guild_id)
		embed = discord.Embed(
			title=settings["embed_title"],
			description=settings["embed_description"],
			color=settings["embed_color"]
		)
		try:
			embed.set_thumbnail(url=ctx.guild.icon.url)
		except:
			pass
		
		view = discord.ui.View(timeout=None)
		style_map = {
			"primary": discord.ButtonStyle.primary,
			"secondary": discord.ButtonStyle.secondary,
			"success": discord.ButtonStyle.success,
			"danger": discord.ButtonStyle.danger,
		}
		
		for role_data in roles:
			style = style_map.get(role_data.get("style", "primary").lower(), discord.ButtonStyle.primary)
			button_emoji = role_data.get("emoji")
			
			if button_emoji:
				if button_emoji.isdigit():
					custom_emoji = self.bot.get_emoji(int(button_emoji))
					if custom_emoji:
						button = discord.ui.Button(
							label=role_data["label"],
							emoji=custom_emoji,
							style=style,
							custom_id=f"role_{role_data['role_id']}"
						)
					else:
						button = discord.ui.Button(
							label=role_data["label"],
							style=style,
							custom_id=f"role_{role_data['role_id']}"
						)
				else:
					button = discord.ui.Button(
						label=role_data["label"],
						emoji=button_emoji,
						style=style,
						custom_id=f"role_{role_data['role_id']}"
					)
			else:
				button = discord.ui.Button(
					label=role_data["label"],
					style=style,
					custom_id=f"role_{role_data['role_id']}"
				)
			view.add_item(button)
		
		message = await channel.send(embed=embed, view=view)
		await button_roles_collection.update_one({"guild_id": guild_id}, {"$set": {"message_id": str(message.id)}})
		await ctx.send("Role panel sent successfully!", ephemeral=True)

	@commands.Cog.listener()
	async def on_interaction(self, interaction: discord.Interaction):
		if interaction.type != discord.InteractionType.component:
			return
		
		custom_id = interaction.data.get("custom_id")
		if not custom_id or not custom_id.startswith("role_"):
			return
		
		guild = interaction.guild
		member = interaction.user
		if not guild or not member:
			await interaction.response.send_message("Guild or member not found.", ephemeral=True)
			return
		
		role_id = int(custom_id.split("_")[1])
		role = guild.get_role(role_id)
		if not role:
			await interaction.response.send_message("Role not found.", ephemeral=True)
			return
		
		bot_member = guild.get_member(self.bot.user.id)
		if role.position >= bot_member.top_role.position:
			await interaction.response.send_message("Cannot assign this role due to role hierarchy.", ephemeral=True)
			return
		
		guild_id = str(guild.id)
		settings = await self.get_settings(guild_id)
		
		if role in member.roles:
			try:
				await member.remove_roles(role, reason="Button Roles")
				await interaction.response.send_message(settings["button_remove_msg"].format(role=role.name), ephemeral=True)
			except discord.Forbidden:
				await interaction.response.send_message("Missing permissions to remove role.", ephemeral=True)
		else:
			try:
				await member.add_roles(role, reason="Button Roles")
				await interaction.response.send_message(settings["button_add_msg"].format(role=role.name), ephemeral=True)
			except discord.Forbidden:
				await interaction.response.send_message("Missing permissions to add role.", ephemeral=True)

	@commands.Cog.listener()
	async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
		if payload.member and payload.member.bot:
			return
		
		guild_id = str(payload.guild_id)
		message_id = str(payload.message_id)
		emoji_str = str(payload.emoji.id) if payload.emoji.id else str(payload.emoji)
		
		role_data = await reaction_roles_collection.find_one({
			"guild_id": guild_id,
			"message_id": message_id,
			"emoji": emoji_str
		})
		if not role_data:
			return
		
		guild = self.bot.get_guild(payload.guild_id)
		if not guild:
			return
		
		role = guild.get_role(int(role_data["role_id"]))
		if not role:
			return
		
		member = guild.get_member(payload.user_id)
		if not member:
			return
		
		bot_member = guild.get_member(self.bot.user.id)
		if role.position >= bot_member.top_role.position:
			return
		
		settings = await self.get_settings(guild_id)
		try:
			await member.add_roles(role, reason="Reaction Role")
			try:
				await member.send(
					f"{settings['reaction_add_msg'].format(role=role.name)} in **{member.guild.name}** via reaction roles.", 
				)
			except:
				pass
		except:
			pass

	@commands.Cog.listener()
	async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
		guild_id = str(payload.guild_id)
		message_id = str(payload.message_id)
		emoji_str = str(payload.emoji.id) if payload.emoji.id else str(payload.emoji)
		
		role_data = await reaction_roles_collection.find_one({
			"guild_id": guild_id,
			"message_id": message_id,
			"emoji": emoji_str
		})
		if not role_data:
			return
		
		guild = self.bot.get_guild(payload.guild_id)
		if not guild:
			return
		
		role = guild.get_role(int(role_data["role_id"]))
		if not role:
			return
		
		member = guild.get_member(payload.user_id)
		if not member:
			return
		
		bot_member = guild.get_member(self.bot.user.id)
		if role.position >= bot_member.top_role.position:
			return
		
		settings = await self.get_settings(guild_id)
		try:
			await member.remove_roles(role, reason="Reaction Roles")
			try:
				await member.send(
					f"{settings['reaction_remove_msg'].format(role=role.name)} in **{member.guild.name}** via reaction roles.", 
				)
			except:
				pass
		except:
			pass

async def setup(bot):
	await bot.add_cog(ReactionRoleCommands(bot))