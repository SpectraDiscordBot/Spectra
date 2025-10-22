import datetime
import discord
import uuid
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from discord.ui import View
from db import note_collection

load_dotenv()


class Notes(commands.Cog):

	def __init__(self, bot):
		self.bot = bot

	@commands.hybrid_group(
		name="notes",
		description="Commands for managing user notes",
	)
	async def note_group(self, ctx: commands.Context):
		pass

	@note_group.command(
		name="add", description="Leave a note for a user, e.g. known troll."
	)
	@commands.has_permissions(moderate_members=True)
	@app_commands.describe(member="The member you want to leave a note for.", note="The note you want to leave.")
	async def add_note(self, ctx: commands.Context, member: discord.Member, *, note: str):
		try:
			note_id = str(uuid.uuid4())
			await note_collection.insert_one(
				{
					"guild_id": str(ctx.guild.id),
					"member_id": member.id,
					"note": note,
					"note_id": note_id,
					"timestamp": datetime.datetime.utcnow(),
				}
			)
			embed = discord.Embed(
				title=f"<:Checkmark:1326642406086410317> Note left successfully.",
				description=f"Note ID: `{note_id}`",
				color=discord.Colour.pink(),
			)
			try:
				self.bot.dispatch(
					"modlog",
					ctx.guild.id,
					ctx.author.id,
					"Left a Note",
					f"Left a note for {member.mention}\nNote: {note}\nNote ID: {note_id}",
				)
			except Exception as e:
				print(e)
			await ctx.send(embed=embed, ephemeral=True)
		except:
			try:
				await ctx.send(
					"Couldn't leave the note, please join the support server and report this bug.",
					ephemeral=True,
				)
			except:
				pass

	@note_group.command(
		name="remove", description="Remove a note from a user"
	)
	@commands.has_permissions(moderate_members=True)
	@app_commands.describe(note_id="The ID of the note you want to remove.")
	async def remove_note(self, ctx: commands.Context, note_id: str):
		try:
			result = await note_collection.delete_one(
				{"guild_id": str(ctx.guild.id), "note_id": note_id}
			)
			if result.deleted_count == 0:
				return await ctx.send(
					"Couldn't find that note, please check the ID and try again.",
					ephemeral=True,
				)
			self.bot.dispatch(
				"modlog",
				ctx.guild.id,
				ctx.author.id,
				"Removed a Note",
				f"Removed note with ID `{note_id}`",
			)
			remaining_notes = await note_collection.count_documents(
				{"guild_id": str(ctx.guild.id)}
			)
			embed = discord.Embed(
				title=f"<:Checkmark:1326642406086410317> Note removed successfully, there are now {remaining_notes} notes.",
				color=discord.Colour.pink(),
			)
			await ctx.send(embed=embed, ephemeral=True)
		except Exception as e:
			print(f"[remove_note] Error: {e}")
			await ctx.send(
				"Couldn't remove the note, please join the support server and report this bug.",
				ephemeral=True,
			)

	@note_group.command(
		name="list",
		description="List notes of a user, or of the whole server",
	)
	@commands.cooldown(1, 5, commands.BucketType.user)
	@commands.has_permissions(moderate_members=True)
	@app_commands.describe(member="The member you want to list notes for. Leave empty to list all notes in the server.")
	async def list_notes(self, ctx: commands.Context, member: discord.Member = None):
		class notePaginator(View):
			def __init__(self, notes, per_page=1):
				super().__init__(timeout=60)
				self.notes = notes
				self.per_page = per_page
				self.current_page = 0
				
			def update_buttons(self):
				self.previous_page.disabled = self.current_page == 0
				self.next_page.disabled = (self.current_page + 1) * self.per_page >= len(self.notes)

			def get_embed(self):
				embed = discord.Embed(
					title="List of Notes", description="", color=discord.Color.pink()
				)
				embed.set_footer(
					text="Spectra", icon_url=self.bot.user.display_avatar.url
				)
				start = self.current_page * self.per_page
				end = start + self.per_page
				for note in self.notes[start:end]:
					member_obj = discord.utils.get(
						ctx.guild.members, id=note["member_id"]
					)
					embed.add_field(
						name=(
							f"{member_obj} ({member_obj.id})"
							if member_obj
							else f"Unknown Member ({note['member_id']})"
						),
						value=f'Note: {note["note"]}\nTimestamp: {discord.utils.format_dt(note["timestamp"], "F")}\nNote ID: `{note["note_id"]}`',
						inline=False,
					)
				return embed

			@discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, disabled=True)
			async def previous_page(
				self, interaction: discord.Interaction, button: discord.ui.Button
			):
				if self.current_page > 0:
					self.current_page -= 1
					
				self.update_buttons()
				
				await interaction.response.edit_message(
					embed=self.get_embed(), view=self
				)

			@discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
			async def next_page(
				self, interaction: discord.Interaction, button: discord.ui.Button
			):
				if (self.current_page + 1) * self.per_page < len(self.notes):
					self.current_page += 1
				
				self.update_buttons()
				
				await interaction.response.edit_message(
					embed=self.get_embed(), view=self
				)

		if member is None:
			notes_cursor = note_collection.find({"guild_id": str(ctx.guild.id)})
		else:
			notes_cursor = note_collection.find(
				{"guild_id": str(ctx.guild.id), "member_id": member.id}
			)
		notes = await notes_cursor.to_list(length=None)
		if not notes:
			await ctx.send("No notes found.", ephemeral=True)
			return
		paginator = notePaginator(notes)
		await ctx.send(embed=paginator.get_embed(), view=paginator, ephemeral=True)


async def setup(bot):
	await bot.add_cog(Notes(bot))