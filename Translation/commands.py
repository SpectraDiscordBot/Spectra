import discord
from discord.ext import commands
from discord import app_commands, ui
from libretranslatepy import LibreTranslateAPI # type: ignore

class LanguageDropdown(ui.Select):
    def __init__(self, bot, text):
        self.bot = bot
        self.text = text
        self.lt = LibreTranslateAPI("https://translate.argosopentech.com")
        self.languages = {lang["code"]: lang["name"].title() for lang in self.lt.languages()}

        options = [discord.SelectOption(label=name, value=code) for code, name in self.languages.items()]
        super().__init__(placeholder="Choose a language", options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            translated = self.lt.translate(self.text, target=self.values[0])
            await interaction.response.send_message(f"**{self.languages[self.values[0]]}:** {translated}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

class TranslateView(ui.View):
    def __init__(self, bot, text):
        super().__init__()
        self.add_item(LanguageDropdown(bot, text))

class Translate(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lt = LibreTranslateAPI("https://translate.argosopentech.com")

    @commands.hybrid_command(name="translate", description="Translate something", aliases=["tr"])
    async def translate(self, ctx, *, text: str):
        await ctx.send("Select a language:", view=TranslateView(self.bot, text))

async def setup(bot):
    await bot.add_cog(Translate(bot))
