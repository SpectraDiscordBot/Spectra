import datetime
import discord
import os
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from discord.ui import View
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ.get('MONGO_URI'))
db = client['Spectra']
note_collection = db["Notes"]
cases_collection = db['Cases']

class Notes(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="note", description="Leave a note for a user, e.g. known troll.")
    @commands.has_permissions(moderate_members=True)
    async def note(self, ctx: commands.Context, member: discord.Member, note: str):
        try:
            cases = cases_collection.find_one({"guild_id": str(ctx.guild.id)})
            if not cases:
                cases_collection.insert_one({"guild_id": str(ctx.guild.id), "cases": 0})
            
            cases_collection.update_one({"guild_id": str(ctx.guild.id)}, {"$set": {"cases": cases["cases"] +1}})

            case = cases_collection.find_one({'guild_id': str(ctx.guild.id)}) 
            case_number = case["cases"]
            try: note_collection.insert_one({"guild_id": ctx.guild.id, "member_id": member.id, "note": note, "case_number": case_number, "timestamp": datetime.datetime.utcnow()})
            except: return await ctx.send("Couldn't leave the note, please join the support server and report this bug.", ephemeral=True)
            embed = discord.Embed(title=f"<:Checkmark:1326642406086410317> [#{case_number}] Note left successfully.", description="", color=discord.Colour.pink())
            try: self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Left a Note", f"Left a note for {member.mention}\nNote: {note}")
            except Exception as e: print(e)
            try:
                await ctx.send(embed=embed, ephemeral=True)
            except:
                pass
        except:
            try:
                await ctx.send("Couldn't leave the note, please join the support server and report this bug.", ephemeral=True)
            except:
                pass
    
    @commands.hybrid_command(name="remove-note", description="Remove a note from a user", aliases=["unnote"])
    @commands.has_permissions(moderate_members=True)
    async def remove_note(self, ctx: commands.Context, member: discord.Member, number: int):
        try:
            now = note_collection.count_documents({"guild_id": ctx.guild.id})
            collection = note_collection.find_one({"guild_id": ctx.guild.id, "member_id": member.id, "number": number})
            try: self.bot.dispatch("modlog", ctx.guild.id, ctx.author.id, "Removed a Note", f"Removed a note from {member.mention}\nCase Number: {number}")
            except Exception as e: print(e)
            try: note_collection.delete_one({"guild_id": ctx.guild.id, "number": number})
            except: return await ctx.send("Couldn't find that note, please check the number or the user and try again.", ephemeral=True) 
            case_number = note_collection.count_documents({"guild_id": ctx.guild.id})
            embed = discord.Embed(title=f"<:Checkmark:1326642406086410317> Note removed successfully, there are now {case_number} notes.", description="", color=discord.Colour.pink())
            try:
                await ctx.send(embed=embed, ephemeral=True)
            except:
                pass
        except:
            try:
                await ctx.send("Couldn't remove the note, please join the support server and report this bug.", ephemeral=True)
            except:
                pass
    @commands.hybrid_command(name="list-notes", description="List notes of a user, or of the whole server", aliases=["notes"])
    @commands.has_permissions(moderate_members=True)
    async def list_notes(self, ctx: commands.Context, member: discord.Member = None):
        class notePaginator(View):
            def __init__(self, notes, per_page=20):
                super().__init__(timeout=60)
                self.notes = notes
                self.per_page = per_page
                self.current_page = 0

            def get_embed(self):
                embed = discord.Embed(
                    title="List of Notes",
                    description="",
                    color=discord.Color.pink()
                )
                embed.set_footer(text="Spectra", icon_url="https://i.ibb.co/cKqBfp1/spectra.gif")
                start = self.current_page * self.per_page
                end = start + self.per_page
                for note in self.notes[start:end]:
                    member = discord.utils.get(ctx.guild.members, id=note["member_id"])
                    case_number = cases_collection.find_one({'guild_id': str(ctx.guild.id)}) 
                    embed.add_field(name=f"{member.name} {member.id}", value=f'Note: {note["note"]}\nTimestamp: {note["timestamp"]}\nCase Number: {case_number["cases"]}', inline=False)
                return embed
            @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
            async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.current_page > 0:
                    self.current_page -= 1
                    await interaction.response.edit_message(embed=self.get_embed(), view=self)

            @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
            async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
                if (self.current_page + 1) * self.per_page < len(self.commands):
                    self.current_page += 1
                    await interaction.response.edit_message(embed=self.get_embed(), view=self)
        if member is None:
            notes = [note for note in note_collection.find({"guild_id": ctx.guild.id})]
        if member is not None:
            notes = [note for note in note_collection.find({"guild_id": ctx.guild.id, "member_id": member.id})]
        paginator = notePaginator(notes)
        await ctx.send(embed=paginator.get_embed(), view=paginator, ephemeral=True)
        

async def setup(bot):
    await bot.add_cog(Notes(bot))