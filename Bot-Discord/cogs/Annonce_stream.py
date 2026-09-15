import json
import os
import re
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

# Chemin absolu basé sur le dossier racine du bot (évite les erreurs de dossier courant sur Render)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "twitch_config.json")


class TwitchWatchButton(discord.ui.View):
    """Bouton cliquable direct vers le live Twitch."""
    def __init__(self, twitch_url: str):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Regarder le live",
                url=twitch_url,
                style=discord.ButtonStyle.link,
                emoji="🟣"
            )
        )


class AnnonceStreamCog(commands.Cog):
    # Groupe de commandes /twitch
    twitch_group = app_commands.Group(name="twitch", description="Gestion des alertes de stream Twitch")

    def __init__(self, bot):
        self.bot = bot
        self.twitch_client_id = os.getenv("TWITCH_CLIENT_ID")
        self.twitch_client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        self.access_token = None

        # Configuration persistante
        self.id_salon_annonce_stream = None
        self.id_role_annonce_stream = None
        self.liste_streamers = []

        # État temporaire en mémoire
        self.streamers_en_live = []

        # Chargement des réglages sauvegardés
        self.charger_config()

        print("Le système d'annonce de stream est prêt !")
        self.verifier_streams.start()

    def cog_unload(self):
        self.verifier_streams.cancel()

    # -- Persistance JSON --

    def charger_config(self):
        """Lit la configuration depuis twitch_config.json s'il existe."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.id_salon_annonce_stream = data.get("salon_id")
                    self.id_role_annonce_stream = data.get("role_id")
                    self.liste_streamers = data.get("streamers", [])
                print(f"Config Twitch chargée : {len(self.liste_streamers)} streamer(s) en mémoire.")
            except Exception as e:
                print(f"⚠️ Erreur lors de la lecture de {CONFIG_FILE} : {e}")
        else:
            print("Aucun fichier de configuration trouvé, création d'une config par défaut.")
            self.sauvegarder_config()

    def sauvegarder_config(self):
        """Écrit l'état actuel dans twitch_config.json."""
        data = {
            "salon_id": self.id_salon_annonce_stream,
            "role_id": self.id_role_annonce_stream,
            "streamers": self.liste_streamers
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ Erreur lors de l'écriture de {CONFIG_FILE} : {e}")

    # -- Utilitaires Twitch --

    @staticmethod
    def extraire_pseudo_twitch(entree: str) -> str:
        """Extrait le pseudo à partir d'une URL complète ou d'une chaîne brute."""
        entree = entree.strip().lower()
        entree = entree.split("?")[0]
        match = re.search(r"(?:https?:\/\/)?(?:www\.)?twitch\.tv\/([a-zA-Z0-9_]{4,25})", entree)
        if match:
            return match.group(1).lower()
        return re.sub(r"[^a-zA-Z0-9_]", "", entree)

    async def get_twitch_token(self, session: aiohttp.ClientSession):
        """Génère un token OAuth d'application Twitch."""
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            "client_id": self.twitch_client_id,
            "client_secret": self.twitch_client_secret,
            "grant_type": "client_credentials",
        }
        async with session.post(url, params=params) as response:
            if response.status == 200:
                data = await response.json()
                self.access_token = data.get("access_token")
                return self.access_token
            print(f"⚠️ Erreur OAuth Twitch ({response.status}) : {await response.text()}")
            return None

    async def fetch_user_profile_image(self, session: aiohttp.ClientSession, headers: dict, user_id: str) -> str:
        """Récupère l'image de profil Twitch du créateur."""
        url = "https://api.twitch.tv/helix/users"
        params = {"id": user_id}
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("data"):
                    return data["data"][0].get("profile_image_url", "")
        return ""

    # -- Boucle de vérification (toutes les 60s) --

    @tasks.loop(seconds=60)
    async def verifier_streams(self):
        if not self.liste_streamers or not self.id_salon_annonce_stream:
            return

        async with aiohttp.ClientSession() as session:
            if not self.access_token:
                await self.get_twitch_token(session)
                if not self.access_token:
                    return

            headers = {
                "Client-ID": self.twitch_client_id,
                "Authorization": f"Bearer {self.access_token}",
            }

            for username in self.liste_streamers:
                url = "https://api.twitch.tv/helix/streams"
                params = {"user_login": username}

                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 401:
                        print("Token Twitch expiré, renouvellement prévu...")
                        self.access_token = None
                        return

                    if response.status != 200:
                        continue

                    resultat = await response.json()

                if "data" not in resultat:
                    continue

                est_en_live = bool(resultat["data"])

                # Cas 1 : Le streamer démarre son live
                if est_en_live and username not in self.streamers_en_live:
                    self.streamers_en_live.append(username)

                    stream = resultat["data"][0]
                    channel = self.bot.get_channel(self.id_salon_annonce_stream)

                    if channel is not None:
                        role = (
                            channel.guild.get_role(self.id_role_annonce_stream)
                            if self.id_role_annonce_stream
                            else None
                        )

                        profile_pic = await self.fetch_user_profile_image(
                            session, headers, stream["user_id"]
                        )

                        stream_url = f"https://twitch.tv/{username}"
                        thumbnail_url = (
                            stream["thumbnail_url"]
                            .replace("{width}", "1280")
                            .replace("{height}", "720")
                        )

                        embed = discord.Embed(
                            title=stream.get("title") or "En direct sur Twitch !",
                            url=stream_url,
                            color=discord.Color.from_rgb(145, 70, 255)
                        )

                        if profile_pic:
                            embed.set_author(name=stream["user_name"], icon_url=profile_pic, url=stream_url)
                            embed.set_thumbnail(url=profile_pic)

                        embed.add_field(
                            name="🎮 Jeu / Catégorie",
                            value=stream.get("game_name") or "Discussion / Autre",
                            inline=True
                        )
                        embed.add_field(
                            name="👥 Spectateurs",
                            value=f"{stream.get('viewer_count', 0):,} viewers",
                            inline=True
                        )

                        embed.set_image(url=thumbnail_url)
                        embed.set_footer(
                            text="Twitch Alert",
                            icon_url="https://raw.githubusercontent.com/Walkx-x/dashboard-icons/main/png/twitch.png"
                        )

                        view = TwitchWatchButton(stream_url)
                        await channel.send(
                            content=role.mention if role else None,
                            embed=embed,
                            view=view,
                            allowed_mentions=discord.AllowedMentions(roles=True)
                        )

                # Cas 2 : Le streamer a coupé son live
                elif not est_en_live and username in self.streamers_en_live:
                    self.streamers_en_live.remove(username)

    @verifier_streams.before_loop
    async def attendre_bot(self):
        await self.bot.wait_until_ready()

    # -- Commandes Slash sous /twitch --

    @twitch_group.command(name="salon", description="Définir le salon d'annonce pour les lives")
    @app_commands.describe(salon="Le salon textuel où envoyer les alertes")
    async def config_salon(self, interaction: discord.Interaction, salon: discord.TextChannel):
        self.id_salon_annonce_stream = salon.id
        self.sauvegarder_config()
        await interaction.response.send_message(
            f"✅ Les annonces de live seront envoyées dans {salon.mention}.",
            ephemeral=True
        )

    @twitch_group.command(name="role", description="Définir le rôle mentionné lors des lives")
    @app_commands.describe(role="Le rôle à notifier")
    async def config_role(self, interaction: discord.Interaction, role: discord.Role):
        self.id_role_annonce_stream = role.id
        self.sauvegarder_config()
        await interaction.response.send_message(
            f"✅ Le rôle {role.mention} sera mentionné à chaque stream.",
            ephemeral=True
        )

    @twitch_group.command(name="ajouter", description="Ajouter une chaîne à surveiller (lien ou pseudo)")
    @app_commands.describe(chaine="Lien Twitch (ex: twitch.tv/streamer) ou pseudo direct")
    async def add_streamer(self, interaction: discord.Interaction, chaine: str):
        username = self.extraire_pseudo_twitch(chaine)

        if not username:
            await interaction.response.send_message(
                "❌ Format invalide. Merci de fournir un pseudo ou un lien Twitch correct.",
                ephemeral=True
            )
            return

        if username not in self.liste_streamers:
            self.liste_streamers.append(username)
            self.sauvegarder_config()
            await interaction.response.send_message(
                f"✅ **{username}** (`https://twitch.tv/{username}`) est maintenant surveillé !",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ **{username}** est déjà dans la liste.",
                ephemeral=True
            )

    @twitch_group.command(name="retirer", description="Retirer une chaîne de la liste de surveillance")
    @app_commands.describe(chaine="Lien Twitch ou pseudo à retirer")
    async def remove_streamer(self, interaction: discord.Interaction, chaine: str):
        username = self.extraire_pseudo_twitch(chaine)

        if username in self.liste_streamers:
            self.liste_streamers.remove(username)
            if username in self.streamers_en_live:
                self.streamers_en_live.remove(username)
            self.sauvegarder_config()
            await interaction.response.send_message(f"🗑️ **{username}** a été retiré de la liste.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ **{username}** n'est pas dans la liste.", ephemeral=True)

    @twitch_group.command(name="liste", description="Voir la liste des streamers surveillés")
    async def list_streamers(self, interaction: discord.Interaction):
        # Chemins possibles
        chemin_cog = os.path.join(os.path.dirname(os.path.abspath(__file__)), "twitch_config.json")
        chemin_racine = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "twitch_config.json")
        
        existe_cog = os.path.exists(chemin_cog)
        existe_racine = os.path.exists(chemin_racine)

        contenu_lu = "Non lu"
        chemin_trouve = None

        if existe_cog:
            chemin_trouve = chemin_cog
        elif existe_racine:
            chemin_trouve = chemin_racine

        if chemin_trouve:
            try:
                with open(chemin_trouve, "r", encoding="utf-8") as f:
                    contenu_lu = f.read()
            except Exception as e:
                contenu_lu = f"Erreur lecture : {e}"

        msg = (
            f"📍 **Chemin cherché actuellement :** `{CONFIG_FILE}`\n"
            f"📁 **Existe dans cogs/ ?** `{'Oui' if existe_cog else 'Non'}`\n"
            f"📁 **Existe à la racine ?** `{'Oui' if existe_racine else 'Non'}`\n"
            f"🧠 **En mémoire RAM :** `{self.liste_streamers}`\n\n"
            f"📄 **Contenu brut du fichier trouvé :**\n```json\n{contenu_lu[:800]}\n```"
        )
        await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot):
    await bot.add_cog(AnnonceStreamCog(bot))