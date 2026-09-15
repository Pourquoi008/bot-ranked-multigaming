import os
import re
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks


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
    twitch_group = app_commands.Group(name="twitch", description="Gestion des alertes Twitch")

    def __init__(self, bot):
        self.bot = bot
        self.id_salon_annonce_stream = None
        self.id_role_annonce_stream = None
        self.liste_streamers = []
        self.streamers_en_live = []

        self.twitch_client_id = os.getenv("TWITCH_CLIENT_ID")
        self.twitch_client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        self.access_token = None

        print("Le système d'annonce de stream est prêt !")
        self.verifier_streams.start()

    def cog_unload(self):
        self.verifier_streams.cancel()

    @staticmethod
    def extraire_pseudo_twitch(entree: str) -> str:
        """Extrait le pseudo propre à partir d'une URL complète ou d'un pseudo brut."""
        entree = entree.strip().lower()
        # Supprime les paramètres d'URL (ex: ?referral=...)
        entree = entree.split("?")[0]
        # Regex pour attraper le pseudo après twitch.tv/
        match = re.search(r"(?:https?:\/\/)?(?:www\.)?twitch\.tv\/([a-zA-Z0-9_]{4,25})", entree)
        if match:
            return match.group(1).lower()
        # Si c'est déjà un pseudo simple
        return re.sub(r"[^a-zA-Z0-9_]", "", entree)

    async def get_twitch_token(self, session: aiohttp.ClientSession):
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
        """Récupère l'avatar du profil Twitch."""
        url = "https://api.twitch.tv/helix/users"
        params = {"id": user_id}
        async with session.get(url, headers=headers, params=params) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("data"):
                    return data["data"][0].get("profile_image_url", "")
        return ""

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
                        self.access_token = None
                        return

                    if response.status != 200:
                        continue

                    resultat = await response.json()

                if "data" not in resultat:
                    continue

                est_en_live = bool(resultat["data"])

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

                        # Récupération de l'avatar du streamer
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
                            description="",
                            color=discord.Color.from_rgb(145, 70, 255)  # Violet officiel Twitch
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
                        embed.set_footer(text="Twitch Alert", icon_url="https://static.twitchcdn.net/assets/favicon-32-eec4e62097d8eac56d9e.png")

                        view = TwitchWatchButton(stream_url)
                        await channel.send(
                            content=role.mention if role else None,
                            embed=embed,
                            view=view,
                            allowed_mentions=discord.AllowedMentions(roles=True)
                        )

                elif not est_en_live and username in self.streamers_en_live:
                    self.streamers_en_live.remove(username)

    @verifier_streams.before_loop
    async def attendre_bot(self):
        await self.bot.wait_until_ready()

    # --- Commandes Slash ---

    @twitch_group.command(name="ajouter", description="Ajouter une chaîne via son lien ou son pseudo")
    @app_commands.describe(chaine="Lien Twitch (ex: https://twitch.tv/monstreamer) ou pseudo")
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
            await interaction.response.send_message(
                f"✅ **{username}** (`https://twitch.tv/{username}`) est maintenant surveillé !",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ **{username}** est déjà dans la liste des alertes.",
                ephemeral=True
            )

    @twitch_group.command(name="retirer", description="Retirer une chaîne des annonces")
    @app_commands.describe(chaine="Lien Twitch ou pseudo à retirer")
    async def remove_streamer(self, interaction: discord.Interaction, chaine: str):
        username = self.extraire_pseudo_twitch(chaine)
        if username in self.liste_streamers:
            self.liste_streamers.remove(username)
            if username in self.streamers_en_live:
                self.streamers_en_live.remove(username)
            await interaction.response.send_message(f"🗑️ **{username}** a été retiré.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ **{username}** n'est pas dans la liste.", ephemeral=True)

    @twitch_group.command(name="liste", description="Afficher les chaînes actuellement surveillées")
    async def list_streamers(self, interaction: discord.Interaction):
        if not self.liste_streamers:
            await interaction.response.send_message("Aucun streamer surveillé pour le moment.", ephemeral=True)
            return

        lignes = [f"• [{s}](https://twitch.tv/{s})" for s in self.liste_streamers]
        embed = discord.Embed(
            title="📺 Chaînes surveillées",
            description="\n".join(lignes),
            color=discord.Color.from_rgb(145, 70, 255)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @twitch_group.command(name="salon", description="Définir le salon où poster les alertes")
    @app_commands.describe(salon="Le salon textuel cible")
    async def config_salon(self, interaction: discord.Interaction, salon: discord.TextChannel):
        self.id_salon_annonce_stream = salon.id
        await interaction.response.send_message(
            f"✅ Alertes configurées dans {salon.mention}.",
            ephemeral=True
        )

    @twitch_group.command(name="role", description="Définir le rôle à mentionner")
    @app_commands.describe(role="Le rôle à notifier")
    async def config_role(self, interaction: discord.Interaction, role: discord.Role):
        self.id_role_annonce_stream = role.id
        await interaction.response.send_message(
            f"✅ Le rôle {role.mention} sera ping à chaque annonce.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(AnnonceStreamCog(bot))