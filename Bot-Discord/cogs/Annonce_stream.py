import os
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from discord.ext import tasks

class AnnonceStreamCog(commands.Cog):
    id_salon_annonce_stream = None
    id_role_annonce_stream = None
    liste_streamers = []
    streamers_en_live = []
    TWITCH_CLIENT_ID=os.getenv('TWITCH_CLIENT_ID')
    TWITCH_ACCESS_TOKEN=os.getenv('TWITCH_ACCESS_TOKEN')

    def __init__(self,bot):
        self.bot=bot
        print("Le système d'annonce de stream est prêt !")
        self.verifier_streams.start()

    # -- Boucle de vérification des streams --
    @tasks.loop(seconds=60)
    async def verifier_streams(self):
        headers = {
            "Client-ID": self.TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {self.TWITCH_ACCESS_TOKEN}"
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            for username in self.liste_streamers:
                url = "https://api.twitch.tv/helix/streams"
                params = {"user_login": username}

                async with session.get(url, params=params) as response:
                    resultat = await response.json()

                est_en_live = bool(resultat["data"])

                if est_en_live and username not in self.streamers_en_live:
                    self.streamers_en_live.append(username)

                    stream = resultat["data"][0]
                    channel = self.bot.get_channel(self.id_salon_annonce_stream)

                    if channel is not None:
                        role = channel.guild.get_role(self.id_role_annonce_stream)
                        thumbnail_url = stream["thumbnail_url"].replace(
                            "{width}", "640"
                        ).replace("{height}", "360")
                        embed = discord.Embed(
                            title=f"{stream['user_name']} est maintenant en live !",
                            url=f"https://twitch.tv/{username}",
                            description=stream["title"],
                            color=discord.Color.purple()
                        )
                        embed.add_field(
                            name="Catégorie",
                            value=stream["game_name"] or "Aucune catégorie",
                        )
                        embed.set_image(url=thumbnail_url)
                        embed.set_footer(text="Twitch")

                        await channel.send(
                            content=role.mention if role else None,
                            embed=embed,
                            allowed_mentions=discord.AllowedMentions(roles=True)
                        )

                elif not est_en_live:
                    if username in self.streamers_en_live:
                        self.streamers_en_live.remove(username)

    @verifier_streams.before_loop
    async def attendre_bot(self):
        await self.bot.wait_until_ready()

    # -- Ajout Streamers --
    @app_commands.command(name="add_streamers",description="Ajouter un streamer à la liste des annonces")
    async def add_streamer(self,interaction:discord.Interaction,twitch_username:str):
        username = twitch_username.strip().lower()
        
        if username not in self.liste_streamers:
            self.liste_streamers.append(username)

    # -- Config salon --
    @app_commands.command(name="config_salon",description="Configurer le salon d'annonce")
    async def config_salon(self,interaction:discord.Interaction,channel:discord.TextChannel):
        self.id_salon_annonce_stream = channel.id

    @app_commands.command(
        name="config_role_annonce",
        description="Choisir le rôle à mentionner pour les annonces"
    )
    async def config_role_annonce(self,interaction: discord.Interaction,role: discord.Role):
        self.id_role_annonce_stream = role.id
        await interaction.response.send_message(
            f"Le rôle {role.mention} sera mentionné dans les annonces.",
            ephemeral=True
        )


# Setup le bot
async def setup(bot):
    await bot.add_cog(AnnonceStreamCog(bot))