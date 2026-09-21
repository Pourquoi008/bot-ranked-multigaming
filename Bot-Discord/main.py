import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from database import Database
from keep_alive import keep_alive

# Chargement du .env
load_dotenv()

# Variables d'environnement
token = os.getenv('DISCORD_TOKEN')
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("Erreur : la variable DATABASE_URL est introuvable !")

class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Attache la base de données directement à l'objet Bot
        self.db = Database(database_url=DATABASE_URL)

    async def setup_hook(self):
        # 1. Connexion à Neon
        await self.db.connect()

        # 2. Chargement des extensions
        for extension in ['Annonce_ranked', 'Reaction_role', 'Annonce_stream']:
            await self.load_extension(f'cogs.{extension}')

        # 3. Synchronisation des slash commands (une seule fois au démarrage)
        try:
            synced = await self.tree.sync()
            print(f"{len(synced)} commande(s) synchronisée(s)")
        except Exception as e:
            print(f"Erreur de sync : {e}")

    async def close(self):
        # Ferme proprement la base lors de l'extinction
        await self.db.close()
        await super().close()

intents = discord.Intents.all()
bot = Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")

@bot.tree.command(name="test", description="Test de commande")
async def test(interaction: discord.Interaction):
    await interaction.response.send_message("Je test des choses !")

keep_alive()
bot.run(token=token)