import os
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

class AnnonceStreamCog(commands.Cog):
    # Groupe principal /twitch
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
                        thumbnail_url = (
                            stream["thumbnail_url"]
                            .replace("{width}", "640")
                            .replace("{height}", "360")
                        )

                        embed = discord.Embed(
                            title=f"{stream['user_name']} est maintenant en live !",
                            url=f"https://twitch.tv/{username}",
                            description=stream.get("title", "Sans titre"),
                            color=discord.Color.purple(),
                        )
                        embed.add_field(
                            name="Catégorie",
                            value=stream.get("game_name") or "Aucune catégorie",
                        )
                        embed.set_image(url=thumbnail_url)
                        embed.set_footer(text="Twitch")

                        await channel.send(
                            content=role.mention if role else None,
                            embed=embed,
                            allowed_mentions=discord.AllowedMentions(roles=True),
                        )

                elif not est_en_live and username in self.streamers_en_live:
                    self.streamers_en_live.remove(username)

    @verifier_streams.before_loop
    async def attendre_bot(self):
        await self.bot.wait_until_ready()

    # --- Commandes regroupées sous /twitch ---

    @twitch_group.command(name="salon", description="Définir le salon où publier les annonces de live")
    @app_commands.describe(salon="Le salon textuel cible")
    async def config_salon(self, interaction: discord.Interaction, salon: discord.TextChannel):
        self.id_salon_annonce_stream = salon.id
        await interaction.response.send_message(
            f"✅ Les annonces de live seront publiées dans {salon.mention}.",
            ephemeral=True
        )

    @twitch_group.command(name="role", description="Définir le rôle à mentionner lors des lives")
    @app_commands.describe(role="Le rôle à ping")
    async def config_role(self, interaction: discord.Interaction, role: discord.Role):
        self.id_role_annonce_stream = role.id
        await interaction.response.send_message(
            f"✅ Le rôle {role.mention} sera notifié.",
            ephemeral=True
        )

    @twitch_group.command(name="ajouter", description="Ajouter une chaîne à surveiller")
    @app_commands.describe(streamer="Le nom d'utilisateur Twitch (ex: aminematue)")
    async def add_streamer(self, interaction: discord.Interaction, streamer: str):
        username = streamer.strip().lower()
        if username not in self.liste_streamers:
            self.liste_streamers.append(username)
            await interaction.response.send_message(
                f"✅ **{username}** a été ajouté aux streamers surveillés.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ **{username}** est déjà dans la liste.",
                ephemeral=True
            )

    @twitch_group.command(name="liste", description="Afficher la liste des chaînes surveillées")
    async def list_streamers(self, interaction: discord.Interaction):
        if not self.liste_streamers:
            await interaction.response.send_message("Aucun streamer n'est actuellement surveillé.", ephemeral=True)
            return

        streamers = "\n".join(f"• `{s}`" for s in self.liste_streamers)
        await interaction.response.send_message(f"**Chaînes surveillées :**\n{streamers}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AnnonceStreamCog(bot))