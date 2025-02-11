import discord
from discord.ext import commands
from googletrans import Translator

COMMON_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "nl": "Dutch",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "pl": "Polish",
    "tr": "Turkish",
    "el": "Greek",
    "cs": "Czech",
    "ro": "Romanian",
    "hu": "Hungarian",
    "id": "Indonesian"
}

class LanguageDropdown(discord.ui.Select):
    def __init__(self, text: str):
        self.text = text
        self.translator = Translator()
        options = [discord.SelectOption(label=name, value=code) for code, name in COMMON_LANGUAGES.items()]
        super().__init__(placeholder="Choose a language", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]
        result = self.translator.translate(self.text, dest=target)
        await interaction.response.send_message(f"**{COMMON_LANGUAGES[target]}:** {result.text}", ephemeral=True)

class TranslateView(discord.ui.View):
    def __init__(self, text: str):
        super().__init__(timeout=30)
        self.add_item(LanguageDropdown(text))

class Translate(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="translate", aliases=["tr"])
    async def translate(self, ctx: commands.Context, *, text: str):
        view = TranslateView(text)
        await ctx.send("Select a language:", view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(Translate(bot))