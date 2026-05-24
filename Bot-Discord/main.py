import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from keep_alive import keep_alive

# Récupération du token dans un fichier .env cachépi
load_dotenv()
token=os.getenv('DISCORD_TOKEN')

class Bot(commands.Bot):
    async def setup_hook(self):
        for extension in ['Annonce_ranked','Reaction_role']:
            await self.load_extension(f'cogs.{extension}')

intents=discord.Intents.all()
bot = Bot(command_prefix="!",intents=intents)

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"{len(synced)} commande(s) synchronisée(s)")
    except Exception as e:
        print(e)

@bot.tree.command(name="test",description="Test de commande")
async def test(interaction:discord.Interaction):
    await interaction.response.send_message("Je test des choses !")


keep_alive()
bot.run(token=token)
