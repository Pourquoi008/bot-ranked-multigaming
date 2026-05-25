from code import interact
import io
from sqlite3.dbapi2 import Timestamp
import string
import discord
from discord import app_commands
from discord import role
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import asyncio


# Dictionnaire des jours de la semaine
dico_semaine = {0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi", 4: "Vendredi", 5: "Samedi", 6: "Dimanche"}
# Dictionnaire des mois
dico_mois=["", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin","Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
# Mode de jeux disponibles pour les ranked
modes_dispo=["solo","duo","trio","quatuor","teams"]
# Salons a supprimer dans la catégories ranked
salons_suppr=["『🔍』logs-scores","『📜』scores","『🎤』choix-des-teams","『🗣️』FFA","『👤』ffa"]

# -- Interface pour Annoncer une Ranked + Affichage de celle-ci --
class AnnonceRankedModal(discord.ui.Modal,title="Annoncer une ranked"):
    date_input = discord.ui.TextInput(label="Date (JJ/MM)",placeholder="Format JJ/MM (ex: 13/06)")
    heure_input=discord.ui.TextInput(label="Heure (HH:00)",placeholder="21")
    mode_input=discord.ui.TextInput(label="Mode de Jeux",placeholder="Teams/Solo/Duo/Trio/Quatuor")
    jeux_input=discord.ui.TextInput(label="Jeux",style=discord.TextStyle.paragraph,placeholder="Sépare tes jeux par un changement de ligne ou une virgule")

    async def on_submit(self,interaction:discord.Interaction):
        try:
            if interaction.channel.name!="『🥇』inscription-ranked":
                await interaction.response.send_message("⚠️ Vous n'êtes pas dans le salon 『🥇』inscription-ranked.",ephemeral=True)
            else:
                saisie_mode=self.mode_input.value.lower()
                # Si l'heure n'est pas un entier compris entre 0 et 23 on affiche une erreur
                if not self.heure_input.value.isdigit() or int(self.heure_input.value)>23 or 0>int(self.heure_input.value):
                    await interaction.response.send_message(f"⚠️ Heure invalide ! Merci de préciser une heure comprise entre 0 et 23 (Ex: 15)",ephemeral=True)
                    return
                if saisie_mode not in modes_dispo:
                    await interaction.response.send_message(f"⚠️ Mode invalide ! Merci de choisir parmi : {', '.join(modes_dispo)}",ephemeral=True)
                    return
                # On récupère la date en format date d'après ce qui a été renseigné par l'utilisateur
                date_obj=datetime.strptime(self.date_input.value, "%d/%m")
                # On modifie l'année de cette date par l'année actuel (par défaut annnée 1900)
                date_obj = date_obj.replace(year=datetime.now().year)
                # On récupère jour et mois de la date passé en paramètre
                nom_jour=dico_semaine[date_obj.weekday()]
                jour=date_obj.day
                print(f"Numéro du jour de la semaine : {date_obj.weekday()}")
                mois=dico_mois[date_obj.month]
                # Format de l'heure avec H00 ajouté a l'heure indiqué
                heure=f"{self.heure_input.value}H00"
                # Récupération liste des jeux
                jeuxwithcomma=self.jeux_input.value.replace('\n',',')
                liste_jeux=[]
                # On sépare les jeux dans une liste suivant les virgules
                jeux_listees=jeuxwithcomma.split(',')
                for j in jeux_listees:
                    # On enlève les potentiel espace dans le jeux
                    jeux_nospace=j.strip()
                    # Si le jeux n'est pas vide (, ,)
                    if jeux_nospace!="":
                        liste_jeux.append(jeux_nospace)
                liste_jeux_stylisee= []
                for jeu in liste_jeux:
                    liste_jeux_stylisee.append(f"> {jeu}")
                # On prépare le texte final a rendre sur le messsage d'annonce ranked
                texte_jeux_final= "\n".join(liste_jeux_stylisee)
                # Inscriptions avec réactions au messages
                reactions = (
                    "✅ : Je participe\n"
                    "❔ : Pas sûr\n"
                    "❌ : Ne participe pas"
                )
                # On ping le rôle MG Ranked s'il existe
                role=discord.utils.get(interaction.guild.roles,name="🏆 | MG Ranked")
                mention_role=role.mention if role else ""

                await interaction.response.send_message(
                    f"## 📅 Date : {nom_jour} {jour} {mois}\n"
                    f"## ⏰ Heure : {heure}\n"
                    f"### 👥 Mode : {saisie_mode.capitalize()}\n"
                    f"### 🎮 JEUX :\n {texte_jeux_final}\n\n"
                    f"{reactions} \n\n"
                    "-# ⚠️ Tout désistement abusif après une inscription pourra donner lieu à un bannissement temporaire aux ranked.\n"
                    f"{mention_role}"
                )
                message=await interaction.original_response()
                await message.add_reaction("✅")
                await message.add_reaction("❔")
                await message.add_reaction("❌")

                # Message de confirmation que tout c'est bien passé
                await interaction.followup.send("✅ **L'annonce a été postée avec succès !**", ephemeral=True)

        except ValueError:
            await interaction.response.send_message("⚠️ Format de date invalide ! Format : JJ/MM (Ex: 25/06).",ephemeral=True)
            
class CreationRankedCog(commands.Cog):
    def __init__(self,bot):
        self.bot=bot
        print("Le système d'annonce de ranked est prêt !")

    #-- Annoncer une Ranked --
    @app_commands.command(name="annonce-ranked",description="Annoncer une ranked")
    async def annonce_ranked(self,interaction:discord.Interaction):
        await interaction.response.send_modal(AnnonceRankedModal())
        if interaction.channel.name == "『🥇』inscription-ranked":
            try:
                # Supprimer le rôle Inscrit-ranked a tout le monde
                # On récupère l'objet du rôle Inscrit-ranked
                role_inscritranked=discord.utils.get(interaction.guild.roles,name="📝 | Inscrit Ranked")
                # On enlève le rôle a tous les membres qui pourrait l'avoir
                if role_inscritranked:
                    for membre in role_inscritranked.members:
                        await membre.remove_roles(role_inscritranked, reason="Réinitialisation des inscrits")
                    print(f"Rôle {role_inscritranked.name} retiré à tout le monde.", flush=True)

                # On supprime les 5 derniers messages
                await interaction.channel.purge(limit=5)
            except discord.Forbidden:
                await interaction.followup.send("🚫 Erreur : Permissions insuffisantes (Gérer les messages).", ephemeral=True)
            except:
                await interaction.followup.send("⚠️ Erreur : Purge impossible.", ephemeral=True)
        
    
    #-- Création des salons en rapport avec les ranked (#team-A,#scores) --
    @app_commands.command(name="start-ranked",description="Creer les channels")
    async def start_ranked(self,interaction:discord.Interaction,id_message:int|None=None):

        # On prévient que le bot peut mettre du temps a répondre
        await interaction.response.defer(ephemeral=True)

        #== Vérification d'une annonce présente dans le salon inscription ranked ==
        salon_inscription = discord.utils.get(interaction.guild.text_channels, name="『🥇』inscription-ranked")

        # Si le salon inscription-ranked n'existe pas
        if not salon_inscription:
            await interaction.followup.send("❌ Erreur : Salon d'inscription introuvable.")
            return

        if interaction.channel!=salon_inscription:
            await interaction.followup.send("❌ Erreur : Vous n'êtes pas dans le salon 『🥇』inscription-ranked.")
            return
        else:
            message_annonce=None
            # On parcout tout l'historique du salon inscription-ranked pour trouver le message d'annonce (limite de 10)
            async for msg in salon_inscription.history(limit=10):
                if msg.author==self.bot.user and "Mode" in msg.content:
                    message_annonce=msg
                    break

            # Si on a pas trouvé le message d'annonce on envoie une erreur
            if not message_annonce:
                await interaction.followup.send("❌ Impossible de trouver l'annonce de la session dans le salon d'inscription.")
                return

            # Nombre de réactions (surtout utile pour les modes duo,trio,...)
            nombre_inscrit=0
            # On parcourt toutes les réactions présentes sur le message et on compte celle des "Je participe" (✅)
            for reaction in message_annonce.reactions:
                if str(reaction.emoji)=="✅":
                    # On garde le nombre d'inscrit dans nombre_inscrit
                    nombre_inscrit=reaction.count-1

            # Liste des mots (séparé par un espace,saut de ligne,etc..) du message d'annonce
            liste_message_prec=message_annonce.content.split()

            # On récupère le mode de jeux dans la variable mode_jeux
            try:
                indice = liste_message_prec.index("Mode")
                mode_jeux = liste_message_prec[indice + 2]
            except (ValueError, IndexError):
                await interaction.followup.send("❌ Le format du message d'annonce est invalide.")
                return
        
            # Erreur a renvoyé a la fin
            erreur=[]
        
            # Date où la commande est lancée
            aujourdhui=datetime.now()

            nom_jour=dico_semaine[aujourdhui.weekday()]
            jour_num=aujourdhui.day
            nom_mois=dico_mois[aujourdhui.month]

            # On récupère la category associé au channel inscription-ranked
            category=salon_inscription.category

            if not category:
                await interaction.followup.send("La catégorie du salon 『🥇』inscription-ranked est introuvable.", ephemeral=True)
                return
            # Initialise les messages
            messages = []
            
            # Backup salon scores
            salon_score=discord.utils.get(category.text_channels, name="『📜』scores")

            if salon_score:
                topic_scores=salon_score.topic
                if topic_scores:
                    # On sépare le topic en mots
                    mots_topic=topic_scores.split()
                    if len(mots_topic)>=5:
                        date_session=f"{mots_topic[3]} {mots_topic[4]}"
                    # Création du message a envoyer dans Backup Score avec le notfichier Backup.txt
                    messages=[f"--- BACKUP SCORES DU {date_session} ---"]
                    # Récupération des messages présents dans le salon
                    async for msg in salon_score.history(limit=30,oldest_first=True):
                        # On affiche heure / minutes / auteur et contenue des messages stockés dans scores
                        # Conversion heure des messages discord en heure française
                        tz_paris = timezone(timedelta(hours=1))
                        heure_fr=msg.created_at.astimezone(tz_paris)
                        timestamp=heure_fr.strftime("%d/%m %H:%M")
                        messages.append(f"[{timestamp}] {msg.author.name}: {msg.content}")
                if len(messages)>1:
                    texte="\n".join(messages)
                    with io.BytesIO(texte.encode('utf-8')) as binary_file:
                        channel_log=discord.utils.get(category.text_channels, name="『🔍』logs-scores")
                        if channel_log:
                            # On nomme le fichier avec la date de la session
                            for i,mois in enumerate(dico_mois):
                                if mois==mots_topic[4]:
                                    date_str=f"{mots_topic[3]}_0{i}"
                                    nom_fichier=f"Backup_Scores_{date_str}.txt"
                        
                            # Envoie du message dans logs-scores avec le fichier .txt
                            await channel_log.send(
                                content=f"📁 **Archive automatique des scores** (Session du {date_str})",
                                file=discord.File(binary_file, filename=nom_fichier)
                            )
                        else:
                            erreur.append("❌ Erreur : Le salon 『🔍』logs-scores est introuvable.")
            else:
                erreur.append("❌ Erreur : Le salon 『📜』scores n'existe pas.")

            # Enlever les rôles team A ou team B aux membres
            # On récupère les objets rôles correspondant aux rôles team A et team B
            role_teama=discord.utils.get(interaction.guild.roles, name="🔹 | Team A")
            role_teamb=discord.utils.get(interaction.guild.roles, name="🔸 | Team B")
            # Si le rôle existe on enlève le rôle aux membres qui l'ont
            if role_teama:
                for membre in role_teama.members:
                    await membre.remove_roles(role_teama,reason="Réinitialisation des équipes")
                print(f"Rôle {role_teama.name} retiré à tout le monde.", flush=True)
            # Pareil pour le rôle Team B
            if role_teamb:
                for member in role_teamb.members:
                    await member.remove_roles(role_teamb, reason="Réinitialisation des équipes")
                print(f"Rôle {role_teamb.name} retiré à tout le monde.", flush=True)

            # Salons a supprimer (supprimer les salons renseignés uniquement)
            salons_deleted=[]
            for salon in category.channels:
                # Supprimer les salons généraux comme le salon score ou annonce ranked
                if salon.name in salons_suppr:
                    salons_deleted.append(salon)
                # Supprimer tous les salons qui commence par 『👥』DUO, 『👪』TRIO ou 『👨‍👩‍👧‍👦』QUATUOR
                elif salon.name.startswith("『👥』DUO") or salon.name.startswith("『👪』TRIO") or salon.name.startswith("『👨‍👩‍👧‍👦』QUATUOR"):
                    salons_deleted.append(salon)
                # Supprimer tous les salons qui contient TEAM ou team ou TeaM dans leur nom
                elif "team" in salon.name.lower():
                    salons_deleted.append(salon)

            # Suppression des salons
            for channel in salons_deleted:
                await channel.delete()

            # Permissions du salon scores
            overwrite_scores={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False), # Everyone ne voit pas le salon
                discord.utils.get(interaction.guild.roles, name="📝 | Inscrit Ranked"): discord.PermissionOverwrite(read_messages=True,send_messages=False), # Inscrit-ranked peut voir les messages
                discord.utils.get(interaction.guild.roles, name="🤖 | Modérateur Ranked"): discord.PermissionOverwrite(read_messages=True,send_messages=True,manage_messages=True) # Modérateur-ranked peut modifier et envoyer des messages
            }

            # Créations du salons annonce-ranked/scores avec les bonnes permissions
            await interaction.guild.create_text_channel(name="『📣』annonce-ranked",category=category,topic=f"Session du {nom_jour} {jour_num} {nom_mois}",overwrites=overwrite_scores)
            await interaction.guild.create_text_channel(name="『📜』scores",category=category,topic=f"Session du {nom_jour} {jour_num} {nom_mois}",overwrites=overwrite_scores)
        

            # Création des salons (dépend du mode de jeux)
            vocaux_teams=["『🔵』TEAM A","『🔴』TEAM B"]
            textuel_teams=["『🟦』team-a","『🟥』team-b"]
            overwrite_choix_teams = {
                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
                    discord.utils.get(interaction.guild.roles, name="📝 | Inscrit Ranked"): discord.PermissionOverwrite(view_channel=True, connect=True,speak=True),
                    discord.utils.get(interaction.guild.roles, name="🤖 | Modérateur Ranked"): discord.PermissionOverwrite(manage_channels=True, mute_members=True, move_members=True)
                }

            overwrite_team_solo={
                        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False), # Everyone ne voit pas le salon
                        discord.utils.get(interaction.guild.roles, name="📝 | Inscrit Ranked"): discord.PermissionOverwrite(read_messages=True,send_messages=True), # Inscrit-ranked peut envoyer des messages
                        discord.utils.get(interaction.guild.roles, name="🤖 | Modérateur Ranked"): discord.PermissionOverwrite(read_messages=True,send_messages=True,manage_messages=True) # Modérateur-ranked gère les messages
                    }

            if mode_jeux=="Teams":
                # 1. Configuration de TOUTES les teams possibles (rôles)
                config_roles_teams = [
                    "🔹 | Team A",
                    "🔸 | Team B",
                    "🟢 | Team C",
                    "🟡 | Team D",
                    "🟣 | Team E",
                    "🟤 | Team F"
                ]

                # 2. Calcul dynamique du nombre de salons selon les paliers exacts
                if nombre_inscrit > 30:
                    nombre_de_salons = 6
                elif nombre_inscrit >= 20: 
                    nombre_de_salons = 4
                else:
                    nombre_de_salons = 2

                # 3. Récupération des rôles fixes (Inscrit Ranked & Modérateur Ranked)
                role_inscrit_ranked = discord.utils.get(interaction.guild.roles, name="📝 | Inscrit Ranked")
                role_modo = discord.utils.get(interaction.guild.roles, name="🤖 | Modérateur Ranked")

                # 4. Vérification de l'existence des rôles
                if not role_inscrit_ranked:
                    await interaction.followup.send("❌ **Erreur de configuration :** Le rôle `📝 | Inscrit Ranked` n'existe pas.", ephemeral=True)
                    return
            
                if not role_modo:
                    await interaction.followup.send("❌ **Erreur de configuration :** Le rôle `🤖 | Modérateur Ranked` n'existe pas.", ephemeral=True)
                    return
            
                # 4. Vérification des rôles de Team requis pour le palier actuel
                for index in range(nombre_de_salons):
                    nom_du_role = config_roles_teams[index]
                    role_verif = discord.utils.get(interaction.guild.roles, name=nom_du_role)
                    
                    if not role_verif:
                        await interaction.followup.send(f"❌ **Erreur de configuration :** Le rôle `{nom_du_role}` est requis pour cette session mais il n'existe pas sur le serveur !", ephemeral=True)
                        return

                # 5. Boucle unique et dynamique pour créer les salons
                # On créer un salon pour que les capitaines fassent le choix des équipes
                choix_cap=await interaction.guild.create_voice_channel(name="『🎤』choix-des-teams",category=category,overwrites=overwrite_choix_teams)
                #Ajout d'un status
                await choix_cap.edit(status="📝 Choix des membres par les capitaines")

                # On créer les salons vocaux & textuel pour les différentes équipes
                for index in range(nombre_de_salons):
                    # On récupère les rôles nécessaires pour ce tour de boucle
                    role_team_actuel = discord.utils.get(interaction.guild.roles, name=config_roles_teams[index])
                    
                    
                    # On prépare les permissions génériques pour la team en cours
                    overwrite_teams_X = {
                        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                        role_modo: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True),
                        role_team_actuel: discord.PermissionOverwrite(read_messages=True, send_messages=True) # Direct, sans le "if"
                    }
                        
                    # On prépare les permissions vocales (Ouvert à tous les inscrits)
                    overwrite_vocaux = {
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False), # Le reste du serveur ne voit pas
                        role_modo: discord.PermissionOverwrite(view_channel=True, connect=True, mute_members=True),
                        role_inscrit_ranked: discord.PermissionOverwrite(view_channel=True, connect=True) # Direct, sans le "if"
                    }
                        
                    # 6. Création des salons Vocaux et Textuels
                    await interaction.guild.create_voice_channel(
                        name=vocaux_teams[index], 
                        category=category,
                        overwrites=overwrite_vocaux
                    )
                    
                    await interaction.guild.create_text_channel(
                        name=textuel_teams[index], 
                        category=category, 
                        topic=f"Session du {nom_jour} {jour_num} {nom_mois}", 
                        overwrites=overwrite_teams_X  # Appliqué ici avec le nouveau nom
                    )
            
            elif mode_jeux=="Solo":
                await interaction.guild.create_voice_channel(name="『🗣️』FFA",category=category)
                await interaction.guild.create_text_channel(name="『👤』ffa",category=category,topic=f"Session du {nom_jour} {jour_num} {nom_mois}",overwrites=overwrite_team_solo)
            elif mode_jeux=="Duo":
                # On crée autant de salon vocaux duo qu'il n'y d'inscrit divisé par 2 (en prenant en compte que le nombre peut être impair)
                for i in range((nombre_inscrit//2)+1):
                    await interaction.guild.create_voice_channel(name=f"『👥』DUO #{i+1}",category=category,user_limit=2)
            elif mode_jeux=="Trio":
                # Idem pour le mode Trio
                for i in range((nombre_inscrit//3)+1):
                    await interaction.guild.create_voice_channel(name=f"『👪』TRIO #{i+1}",category=category,user_limit=3)
            elif mode_jeux=="Quatuor":
                # Idem pour le mode Quatuor
                for i in range((nombre_inscrit//4)+1):
                    await interaction.guild.create_voice_channel(name=f"『👨‍👩‍👧‍👦』QUATUOR #{i+1}",category=category,user_limit=4)
            # Tous c'est bien passé donc on renvoie une réponse
            erreur.append(f"✅ Tous les salons ont bien été créés.")
        
            # On crée le message a renvoyé avec tout les erreurs précédentes
            message_erreur="\n".join(erreur)
            print(message_erreur)

            # On répond avec toutes les erreurs qui aurait pu se produire (séparé d'un saut de ligne)
            await interaction.followup.send(message_erreur,ephemeral=True)

# Setup le bot
async def setup(bot):
    await bot.add_cog(CreationRankedCog(bot))
