import discord
from discord import app_commands
from discord.ext import commands
import asyncio

# Création de la classe sous méthode Cog
class ReactionRole(commands.Cog):
    def __init__(self,bot):
        print("Le système de réactions est prêt !")
        self.bot=bot

    # Commande pour voir les 12 derniers inscrits
    @app_commands.command(name="liste_inscrits", description="Affiche les 12 premiers inscrits")
    @app_commands.describe(message_id="L'ID du message", emoji="L'émoji de réaction")
    async def liste_inscrits(self, interaction: discord.Interaction, message_id: str, emoji: str):
        # On doit mettre "self" en premier argument ci-dessus
        try:
            await interaction.response.defer(ephemeral=False) # Optionnel: donne du temps au bot
            
            msg_id_int = int(message_id)
            target_message = await interaction.channel.fetch_message(msg_id_int)
            
            # Recherche de la réaction
            reaction = discord.utils.get(target_message.reactions, emoji=emoji)
            
            if not reaction:
                await interaction.followup.send(f"L'émoji {emoji} n'est pas présent sur ce message.")
                return

            # L'API Discord les donne alors strictement du plus ancien au plus récent
            all_users = [u async for u in reaction.users(limit=100)]
            
            inscrits = []
            # 2. On filtre ensuite manuellement pour ne garder que les 12 premiers humains
            for user in all_users:
                if not user.bot:
                    inscrits.append(user)
                
                # Dès qu'on en a 12, on arrête de remplir la liste
                if len(inscrits) == 12:
                    break

            if not inscrits:
                await interaction.followup.send("Aucun inscrit trouvé.")
                return

            embed = discord.Embed(
                title=f"🕒 12 premiers inscrits ({emoji})",
                color=discord.Color.green()
            )

            liste_texte = ""
            for i, user in enumerate(inscrits, 1):
                liste_texte += f"**{i}.** {user.mention} (`{user.name}`)\n"
            
            embed.description = liste_texte
            await interaction.followup.send(embed=embed)

        except ValueError:
            await interaction.followup.send("L'ID du message est invalide.")
        except discord.NotFound:
            await interaction.followup.send("Message introuvable dans ce salon.")
        except Exception as e:
            await interaction.followup.send(f"Erreur : {e}")
    
    #-- Ajout d'un rôle suite à une réaction sous le message d'annonce ranked
    @commands.Cog.listener()
    async def on_raw_reaction_add(self,payload):
        # Est executé quand quelqu'un ajoute une réaction 

        # On récupère le serveur (guild)
        serveur=self.bot.get_guild(payload.guild_id)
        # Sécurité si le serveur n'existe pas
        if not serveur:
            return

        # On vérie qu'on a bien récupérer le membre qui a cliqué sur la réaction
        membre = payload.member
        if not membre:
            membre = serveur.get_member(payload.user_id)

        if not membre or membre.bot: 
            return

        # Vérification du salon
        salon=serveur.get_channel(payload.channel_id)
        # Si le salon existe bien et si la réaction se produit dans inscription-ranked
        if salon and salon.name=="『🥇』inscription-ranked":
            if salon.category and "Ranked" in salon.category.name:
                # On récupère l'objet du message pour pouvoir enlever les réactions
                message = await salon.fetch_message(payload.message_id)

                role_inscrit=discord.utils.get(serveur.roles,name="📝 | Inscrit Ranked")
                role_attente=discord.utils.get(serveur.roles,name="⏳ | En Attente Ranked")

                # On regarde quel réaction a été cliqué
                emoji = str(payload.emoji)

                # Test dans la console quand on clic sur une réaction
                print(f"Clic détecté : {emoji} par {membre.display_name}")

                # Si la réaction est ✅ on donne le rôle Inscrit-ranked
                if emoji=="✅":
                    # Si le rôle inscrit a bien été retrouvé ou existe
                    if role_inscrit:
                        # On donne le rôle Inscrit-Ranked
                        await membre.add_roles(role_inscrit)

                        # S'il a les deux rôles (Inscrit / En-Attente) on supprime celui qu'il avait avant (ici En-Attente)
                        if role_attente in membre.roles:
                            await membre.remove_roles(role_attente)

                        # On retire tous les autres réactions potentiellement mise (s'il clique sur ✅)
                        try:
                            await message.remove_reaction("❔", membre)
                            await asyncio.sleep(0.1)
                            await message.remove_reaction("❌", membre)
                        except: pass
            
                # Si la réaction est ❓ on donne le rôle En-Attente-ranked        
                elif emoji=="❔":
                    # Si le rôle en-attente a bien été retrouvé ou existe
                    if role_attente:
                        # On donne le rôle En-Attente-Ranked
                        await membre.add_roles(role_attente)

                        # S'il a les deux rôles (Inscrit / En-Attente) on supprime celui qu'il avait avant (ici Inscrit)
                        if role_inscrit in membre.roles:
                            await membre.remove_roles(role_inscrit)

                        # On retire tous les autres réactions potentiellement mise (s'il clique sur ❔)
                        try:
                            await message.remove_reaction("✅", membre)
                            await asyncio.sleep(0.1)
                            await message.remove_reaction("❌", membre)
                        except: pass

                # Si la réaction est ❌ on retire les rôles Inscrit-Reanke ou En-Attente-Ranke)   
                elif emoji=="❌":
                    if role_inscrit and role_attente:
                        # On lui enlève ses rôles (s'il les as)
                        if role_inscrit in membre.roles:
                            await membre.remove_roles(role_inscrit)
                        if role_attente in membre.roles:
                            await membre.remove_roles(role_attente)
                    
                        # On retire tous les autres réactions potentiellement mise (s'il clique sur ❌)
                        try:
                            await message.remove_reaction("✅", membre)
                            await asyncio.sleep(0.1)
                            await message.remove_reaction("❔", membre)
                        except: pass
                   


    #-- Enlever un rôle quand quelqu'un retire sa réaction sous le message d'annonce ranked
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self,payload):
        serveur=self.bot.get_guild(payload.guild_id)
        membre = serveur.get_member(payload.user_id)
        
        # Si c'est le bot ou le membre qui a cliqué n'existe pas on sort
        if not membre or membre.bot:
            return

        salon=serveur.get_channel(payload.channel_id)
        # Si la réaction a bien lieu dans le channel inscription ranked
        if salon and salon.name=="『🥇』inscription-ranked":

            # Si un membre retire sa réaction ✅ on lui enlève le rôle Inscrit-Ranked
            if str(payload.emoji)=="✅":
                # Recherche du rôle
                role_remove=discord.utils.get(serveur.roles, name="📝 | Inscrit Ranked")

                # Si on a bien trouvé le rôle on lui remove le rôle
                if role_remove:
                    await membre.remove_roles(role_remove)
            
            # Si un membre retire sa réaction ❓ on lui enlève le rôle En-Attente-Ranked
            elif str(payload.emoji)=="❔":
                # Recherche du rôle
                role_remove=discord.utils.get(serveur.roles, name="⏳ | En Attente Ranked")

                # Si on a bien trouvé le rôle on lui remove le rôle
                if role_remove:
                    await membre.remove_roles(role_remove)
# Setup le bot
async def setup(bot):
    await bot.add_cog(ReactionRole(bot))