import json
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from database import PLACEMENT_MATCHES_REQUIRED, get_rank_display

# ==============================================================================
# CONFIGURATION & CHEMINS
# ==============================================================================

CONFIG_FILE = Path(__file__).resolve().parent / "config.json"


# ==============================================================================
# GESTION DU FICHIER CONFIG (LECTURE / ÉCRITURE)
# ==============================================================================

def get_ranked_config() -> dict:
    """Lit uniquement la section 'ranked' du fichier config.json."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("ranked", {"matchmaking_channel_id": None, "match_category_id": None, "referee_role_id": None})
        except Exception as e:
            print(f"⚠️ Erreur de lecture de {CONFIG_FILE} : {e}")
    return {"matchmaking_channel_id": None, "match_category_id": None, "referee_role_id": None}


def update_ranked_config(key: str, value: int):
    """Met à jour un paramètre dans 'ranked' en préservant le reste du fichier (ex: 'twitch')."""
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

    if "ranked" not in data:
        data["ranked"] = {}

    data["ranked"][key] = value

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Erreur d'écriture dans {CONFIG_FILE} : {e}")


# ==============================================================================
# INTERFACE UTILISATEUR : PANNEAU & FILE D'ATTENTE (MATCHMAKING)
# ==============================================================================

def build_matchmaking_embed(queue_count: int) -> discord.Embed:
    """Génère l'embed du panneau de recherche avec le nombre de joueurs en attente."""
    embed = discord.Embed(
        title="🏆 Arène Compétitive — Ranked 1v1",
        description=(
            "Prêt à monter dans le classement ?\n\n"
            "• **Clique sur le bouton vert** pour rejoindre la file d'attente.\n"
            "• Dès qu'un adversaire est disponible, un salon privé sera créé automatiquement.\n"
            "• Tu peux quitter la file à tout moment avec le bouton rouge."
        ),
        color=discord.Color.blurple()
    )
    status_text = (
        f"**{queue_count} joueur{'s' if queue_count > 1 else ''}** en recherche..."
        if queue_count > 0
        else "Aucun joueur en recherche"
    )
    embed.add_field(name="👥 File d'attente", value=status_text, inline=False)
    embed.set_footer(text="Système 1v1 Automatisé • Bonne chance !")
    return embed

# Panneau Abitre (fin de match)
class RefereeControlView(discord.ui.View):
    """Panneau d'arbitrage final avec 3 boutons d'action."""

    def __init__(self, cog, channel_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.channel_id = channel_id
        self.resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cfg = get_ranked_config()
        ref_role_id = cfg.get("referee_role_id")

        is_admin = interaction.user.guild_permissions.administrator
        has_ref_role = ref_role_id and any(r.id == ref_role_id for r in interaction.user.roles)

        if not (is_admin or has_ref_role):
            await interaction.response.send_message(
                "⛔ Seuls les arbitres officiels peuvent valider l'issue du match.",
                ephemeral=True
            )
            return False

        if self.resolved:
            await interaction.response.send_message("⚠️ Ce match a déjà été validé ou clôturé.", ephemeral=True)
            return False

        return True

    # --- Bouton 1 : Joueur A Win ---
    @discord.ui.button(label="Joueur A Win", style=discord.ButtonStyle.success, emoji="🏆")
    async def win_player_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        match = self.cog.active_matches.get(self.channel_id)
        if not match:
            await interaction.response.send_message("❌ Données du match introuvables.", ephemeral=True)
            return

        self.resolved = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        winner = match["p1"]
        loser = match["p2"]
        await self.cog.resolve_match(interaction.channel, winner=winner, loser=loser, referee=interaction.user)

    # --- Bouton 2 : Joueur B Win ---
    @discord.ui.button(label="Joueur B Win", style=discord.ButtonStyle.primary, emoji="🏆")
    async def win_player_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        match = self.cog.active_matches.get(self.channel_id)
        if not match:
            await interaction.response.send_message("❌ Données du match introuvables.", ephemeral=True)
            return

        self.resolved = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        winner = match["p2"]
        loser = match["p1"]
        await self.cog.resolve_match(interaction.channel, winner=winner, loser=loser, referee=interaction.user)

    # --- Bouton 3 : Annuler Match ---
    @discord.ui.button(label="Annuler Match", style=discord.ButtonStyle.danger, emoji="🛑")
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.resolved = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        self.cog.active_matches.pop(self.channel_id, None)

        embed = discord.Embed(
            title="🛑 Match Annulé",
            description=f"Ce match a été annulé par l'arbitre {interaction.user.mention}.\nFermeture du salon dans **10 secondes**.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)

        import asyncio
        await asyncio.sleep(10)
        await interaction.channel.delete(reason=f"Annulé par l'arbitre {interaction.user.name}")

class MatchmakingView(discord.ui.View):
    """Vue persistante contenant les boutons pour rejoindre ou quitter la file."""

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    # --- Bouton : Rejoindre la file ---
    @discord.ui.button(
        label="Rechercher un match",
        style=discord.ButtonStyle.success,
        emoji="⚔️",
        custom_id="ranked_matchmaking_join"
    )
    async def join_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        queue = self.cog.queue

        # 1. Vérifier si l'utilisateur attend déjà
        if user.id in queue:
            await interaction.response.send_message(
                "⏳ Tu es déjà dans la file d'attente.",
                ephemeral=True
            )
            return

        # 2. Si la file est vide, on l'ajoute et on met à jour l'embed
        if len(queue) == 0:
            queue.append(user.id)
            await interaction.response.send_message(
                "✅ Tu as rejoint la file d'attente 1v1 !",
                ephemeral=True
            )
            embed = build_matchmaking_embed(len(queue))
            await interaction.message.edit(embed=embed)
            return

        # 3. Si un adversaire attend déjà, on lance le match
        opponent_id = queue.pop(0)
        opponent = interaction.guild.get_member(opponent_id)

        # Vérification si l'adversaire est toujours valide
        if not opponent or opponent.id == user.id:
            queue.append(user.id)
            await interaction.response.send_message("✅ Tu as rejoint la file d'attente 1v1 !", ephemeral=True)
            embed = build_matchmaking_embed(len(queue))
            await interaction.message.edit(embed=embed)
            return

        # Met à jour le message public (la file repasse à 0)
        embed = build_matchmaking_embed(len(queue))
        await interaction.message.edit(embed=embed)

        # Création du salon dédié au match
        await interaction.response.send_message("⚔️ Adversaire trouvé ! Création du salon...", ephemeral=True)
        await self.cog.create_match_channel(interaction.guild, user, opponent)

    # --- Bouton : Quitter la file ---
    @discord.ui.button(
        label="Quitter la file",
        style=discord.ButtonStyle.danger,
        emoji="🚪",
        custom_id="ranked_matchmaking_leave"
    )
    async def leave_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        queue = self.cog.queue

        if user.id in queue:
            queue.remove(user.id)
            await interaction.response.send_message("🚪 Tu as quitté la file d'attente.", ephemeral=True)
            embed = build_matchmaking_embed(len(queue))
            await interaction.message.edit(embed=embed)
        else:
            await interaction.response.send_message("Tu n'es pas dans la file d'attente.", ephemeral=True)

class MatchControlView(discord.ui.View):
    """Gère l'annulation à l'amiable et le forfait dans le salon temporaire."""

    def __init__(self, cog, p1: discord.Member, p2: discord.Member):
        super().__init__(timeout=None)
        self.cog = cog
        self.p1 = p1
        self.p2 = p2
        self.cancel_votes: set[int] = set()
        self.forfeit_votes: set[int] = set()
        self.match_ended = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Restreint l'usage aux deux duellistes."""
        if interaction.user.id not in (self.p1.id, self.p2.id):
            await interaction.response.send_message(
                "❌ Seuls les deux duellistes peuvent utiliser ces boutons.",
                ephemeral=True
            )
            return False
        if self.match_ended:
            await interaction.response.send_message(
                "⚠️ Ce match est déjà terminé ou annulé.",
                ephemeral=True
            )
            return False
        return True

    # --- Bouton : Annuler le match (aucun impact d'Elo) ---
    @discord.ui.button(
        label="Annuler le match (0/2)",
        style=discord.ButtonStyle.secondary,
        emoji="🛑",
        custom_id="match_action_cancel"
    )
    async def request_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id

        if user_id in self.cancel_votes:
            self.cancel_votes.remove(user_id)
            button.label = f"Annuler le match ({len(self.cancel_votes)}/2)"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                f"↩️ {interaction.user.mention} a retiré sa demande d'annulation.",
                ephemeral=False
            )
            return

        self.cancel_votes.add(user_id)
        button.label = f"Annuler le match ({len(self.cancel_votes)}/2)"

        if len(self.cancel_votes) == 2:
            self.match_ended = True
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(view=self)

            embed = discord.Embed(
                title="🛑 Match Annulé",
                description=(
                    "Les deux joueurs ont accepté d'annuler la partie.\n"
                    "• **Aucun Elo** n'a été modifié.\n"
                    "• Ce match ne compte pas dans l'historique.\n\n"
                    "Ce salon sera supprimé automatiquement dans **10 secondes**."
                ),
                color=discord.Color.light_grey()
            )
            await interaction.followup.send(embed=embed)
            
            # Suppression automatique après 10s
            import asyncio
            await asyncio.sleep(10)
            await interaction.channel.delete(reason="Match annulé par consentement mutuel")
        else:
            await interaction.response.edit_message(view=self)
            other = self.p2 if user_id == self.p1.id else self.p1
            await interaction.followup.send(
                f"🛑 {interaction.user.mention} souhaite **annuler le match** (sans perte d'Elo). {other.mention}, clique sur le bouton pour confirmer.",
                ephemeral=False
            )

    # --- Bouton : Déclarer forfait / Abandonner ---
    @discord.ui.button(
        label="Déclarer forfait",
        style=discord.ButtonStyle.danger,
        emoji="🏳️",
        custom_id="match_action_forfeit"
    )
    async def forfeit(self, interaction: discord.Interaction, button: discord.ui.Button):
        loser = interaction.user
        if loser.id == self.p1.id:
            winner = self.p2 
        else:
            winner = self.p1

        # Vérification si l'utilisateur re-clique pour confirmer son propre abandon
        if loser.id not in self.forfeit_votes:
            self.forfeit_votes.add(loser.id)
            await interaction.response.send_message(
                "⚠️ Tu as cliqué sur **Déclarer forfait**. Clique une seconde fois sur le bouton pour confirmer définitivement ton abandon.",
                ephemeral=True
            )
            return

        # Si confirmé une 2e fois
        self.match_ended = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        embed = discord.Embed(
            title="🏳️ Victoire par Forfait",
            description=(
                f"{loser.mention} a déclaré forfait !\n"
                f"🏆 Victoire attribuée à {winner.mention}.\n\n"
                "Un arbitre appliquera l'ajustement d'Elo."
            ),
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)

# ==============================================================================
# COG PRINCIPAL : RANKED 1V1
# ==============================================================================

class Ranked1V1(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue: list[int] = []
        self.active_matches: dict[int, dict] = {}

    async def cog_load(self):
        """Enregistre la vue persistante au chargement du cog."""
        self.bot.add_view(MatchmakingView(self))

    # --- Groupes de commandes slash ---
    setup_group = app_commands.Group(
        name="setup_ranked",
        description="Configuration du système de ranked 1v1",
        default_permissions=discord.Permissions(administrator=True)
    )
    admin_group = app_commands.Group(
        name="elo_admin",
        description="Commandes d'ajustement de l'Elo",
        default_permissions=discord.Permissions(administrator=True)
    )

    # --------------------------------------------------------------------------
    # 1. COMMANDES JOUEURS (PUBLIQUES)
    # --------------------------------------------------------------------------

    @app_commands.command(name="rank", description="Consulte ton rang ou celui d'un autre joueur")
    @app_commands.describe(joueur="Le joueur à observer (laisse vide pour voir le tien)")
    async def rank(self, interaction: discord.Interaction, joueur: discord.Member | None = None):
        target = joueur or interaction.user
        elo, matches = await self.bot.db.get_player_data(target.id, target.name)
        rank_badge = get_rank_display(elo, matches)

        embed = discord.Embed(
            title=f"Statut Compétitif — {target.display_name}",
            color=discord.Color.blurple() if matches >= PLACEMENT_MATCHES_REQUIRED else discord.Color.light_grey()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Rang", value=f"**{rank_badge}**", inline=True)
        embed.add_field(name="Matchs disputés", value=f"{matches}", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="ranks", description="Affiche le tableau des rangs du serveur")
    async def ranks(self, interaction: discord.Interaction):
        players = await self.bot.db.get_all_players_by_rank()
        if not players:
            await interaction.response.send_message("Aucune partie enregistrée pour l'instant.", ephemeral=True)
            return

        lines = []
        for p in players:
            badge = get_rank_display(p["elo"], p["matches_played"])
            lines.append(f"<@{p['user_id']}> : **{badge}**")

        embed = discord.Embed(
            title="🏆 Tableau des Rangs",
            description="\n".join(lines[:25]),
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------------------------------
    # 2. CONFIGURATION DES SALONS & RÔLES (/setup_ranked)
    # --------------------------------------------------------------------------

    @setup_group.command(name="arbitre", description="Définit le rôle autorisé à arbitrer et valider les matchs")
    @app_commands.describe(role="Le rôle Discord à désigner comme arbitre")
    async def set_arbitre(self, interaction: discord.Interaction, role: discord.Role):
        update_ranked_config("referee_role_id", role.id)
        await interaction.response.send_message(
            f"✅ Le rôle {role.mention} a été défini comme rôle d'arbitrage officiel.",
            ephemeral=True
        )

    @setup_group.command(name="channel", description="Définit le salon où les joueurs recherchent des matchs")
    @app_commands.describe(salon="Le salon textuel réservé à la recherche")
    async def set_channel(self, interaction: discord.Interaction, salon: discord.TextChannel):
        update_ranked_config("matchmaking_channel_id", salon.id)
        await interaction.response.send_message(
            f"✅ Salon de recherche défini sur {salon.mention}.",
            ephemeral=True
        )

    @setup_group.command(name="category", description="Définit la catégorie où créer les salons temporaires 1v1")
    @app_commands.describe(categorie="La catégorie Discord")
    async def set_category(self, interaction: discord.Interaction, categorie: discord.CategoryChannel):
        update_ranked_config("match_category_id", categorie.id)
        await interaction.response.send_message(
            f"📁 Catégorie des matchs définie sur **{categorie.name}**.",
            ephemeral=True
        )

    @setup_group.command(name="view", description="Affiche la configuration actuelle des salons et rôles")
    async def view_config(self, interaction: discord.Interaction):
        cfg = get_ranked_config()
        ch_id = cfg.get("matchmaking_channel_id")
        cat_id = cfg.get("match_category_id")
        ref_id = cfg.get("referee_role_id")

        embed = discord.Embed(title="⚙️ Configuration Ranked Actuelle", color=discord.Color.blue())
        embed.add_field(name="Salon de recherche", value=f"<#{ch_id}>" if ch_id else "❌ Non configuré", inline=False)
        embed.add_field(name="Catégorie des matchs", value=f"<#{cat_id}>" if cat_id else "❌ Non configurée", inline=False)
        embed.add_field(name="Rôle arbitre", value=f"<@&{ref_id}>" if ref_id else "❌ Non configuré", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --------------------------------------------------------------------------
    # 3. GESTION DES MATCHS & CRÉATION DE SALONS TEMPORAIRES
    # --------------------------------------------------------------------------

    async def create_match_channel(self, guild: discord.Guild, p1: discord.Member, p2: discord.Member):
        """Crée le salon temporaire privé pour les deux joueurs sous la catégorie configurée."""
        self.active_matches[channel.id] = {
            "p1": p1,
            "p2": p2,
            "scores": {p1.id: 0, p2.id: 0},
            "round": 1,
            "round_msg_id": None,
            "waiting_vote": True
        }
        
        cfg = get_ranked_config()
        cat_id = cfg.get("match_category_id")
        ref_id = cfg.get("referee_role_id")

        category = guild.get_channel(cat_id) if cat_id else None
        ref_role = guild.get_role(ref_id) if ref_id else None

        # Permissions : visible uniquement par p1, p2, le bot et les arbitres
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            p1: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            p2: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }

        if ref_role:
            overwrites[ref_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel_name = f"⚔️・{p1.name[:10]}-vs-{p2.name[:10]}"
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        elo1, _ = await self.bot.db.get_player_data(p1.id, p1.name)
        elo2, _ = await self.bot.db.get_player_data(p2.id, p2.name)

        embed = discord.Embed(
            title="⚔️ Match 1v1 — Prêt pour le combat !",
            description=f"Le duel oppose {p1.mention} à {p2.mention}.\nAjoutez-vous en jeu et lancez la partie !",
            color=discord.Color.gold()
        )
        embed.add_field(name=p1.display_name, value=f"Elo : **{elo1}**", inline=True)
        embed.add_field(name=p2.display_name, value=f"Elo : **{elo2}**", inline=True)
        embed.set_footer(text="Une fois le match terminé, un arbitre validera le résultat.")

        view = MatchControlView(self, p1, p2)
        await channel.send(content=f"{p1.mention} vs {p2.mention}", embed=embed, view=view)
        await self.send_round_message(channel, self.active_matches[channel.id])

    @setup_group.command(name="spawn_panel", description="Poste le panneau de matchmaking dans le salon configuré")
    async def spawn_panel(self, interaction: discord.Interaction):
        """Envoie l'embed interactif de file d'attente dans le salon prévu."""
        cfg = get_ranked_config()
        channel_id = cfg.get("matchmaking_channel_id")

        if not channel_id:
            await interaction.response.send_message(
                "❌ Aucun salon de matchmaking n'a été configuré. Fais d'abord `/setup_ranked channel`.",
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("❌ Le salon configuré est introuvable.", ephemeral=True)
            return

        embed = build_matchmaking_embed(len(self.queue))
        view = MatchmakingView(self)
        await channel.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Panneau envoyé avec succès dans {channel.mention} !", ephemeral=True)

    # --------------------------------------------------------------------------
    # 4. GESTION ADMINISTRATIVE DE L'ELO (/elo_admin)
    # --------------------------------------------------------------------------

    @admin_group.command(name="set", description="Définit manuellement l'Elo d'un joueur")
    @app_commands.describe(joueur="Le joueur ciblé", valeur="Valeur d'Elo")
    async def set_elo(self, interaction: discord.Interaction, joueur: discord.Member, valeur: int):
        if valeur < 0:
            await interaction.response.send_message("L'Elo ne peut pas être négatif.", ephemeral=True)
            return

        new_score, matches = await self.bot.db.set_player_elo(joueur.id, valeur, joueur.name)
        new_rank = get_rank_display(new_score, matches)

        await interaction.response.send_message(
            f"✏️ L'Elo de {joueur.mention} a été défini à **{new_score}** (Rang : **{new_rank}**)."
        )

    @admin_group.command(name="add", description="Ajoute des points d'Elo à un joueur")
    @app_commands.describe(joueur="Le joueur ciblé", montant="Points à ajouter")
    async def add_elo(self, interaction: discord.Interaction, joueur: discord.Member, montant: int):
        if montant <= 0:
            await interaction.response.send_message("Le montant doit être supérieur à 0.", ephemeral=True)
            return

        new_score, matches = await self.bot.db.adjust_player_elo(joueur.id, montant, joueur.name)
        new_rank = get_rank_display(new_score, matches)

        await interaction.response.send_message(
            f"🔼 **+{montant}** Elo accordés à {joueur.mention} (Total : **{new_score}** — **{new_rank}**)."
        )

    @admin_group.command(name="remove", description="Retire des points d'Elo à un joueur")
    @app_commands.describe(joueur="Le joueur ciblé", montant="Points à retirer")
    async def remove_elo(self, interaction: discord.Interaction, joueur: discord.Member, montant: int):
        if montant <= 0:
            await interaction.response.send_message("Le montant doit être supérieur à 0.", ephemeral=True)
            return

        new_score, matches = await self.bot.db.adjust_player_elo(joueur.id, -montant, joueur.name)
        new_rank = get_rank_display(new_score, matches)

        await interaction.response.send_message(
            f"🔻 **-{montant}** Elo retirés à {joueur.mention} (Total : **{new_score}** — **{new_rank}**)."
        )

    # --------------------------------------------------------------------------
    # 5. Affichage manche par manche du match
    # --------------------------------------------------------------------------
    async def send_round_message(self, channel: discord.TextChannel, match: dict):
        """Poste un nouveau message distinct pour chaque manche."""
        p1 = match["p1"]
        p2 = match["p2"]
        round_num = match["round"]

        embed = discord.Embed(
            title=f"🎮 Manche {round_num} / 3",
            description=(
                f"Réagissez avec l'émoji correspondant au vainqueur de ce jeu :\n\n"
                f"🅰️ — **{p1.display_name}**\n"
                f"🅱️ — **{p2.display_name}**\n\n"
                f"*Score actuel : {p1.display_name} `{match['scores'][p1.id]}` — `{match['scores'][p2.id]}` {p2.display_name}*"
            ),
            color=discord.Color.blurple()
        )
        msg = await channel.send(embed=embed)
        match["round_msg_id"] = msg.id
        match["waiting_vote"] = True

        await msg.add_reaction("🅰️")
        await msg.add_reaction("🅱️")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Détecte la réaction sans supprimer ni verrouiller les émojis."""
        # 1. Ignorer les réactions du bot lui-même
        if payload.user_id == self.bot.user.id:
            return

        channel_id = payload.channel_id
        if channel_id not in self.active_matches:
            return

        match = self.active_matches[channel_id]

        # 2. Vérifier si ce message est bien la manche en attente de vote
        if payload.message_id != match.get("round_msg_id") or not match.get("waiting_vote"):
            return

        p1 = match["p1"]
        p2 = match["p2"]

        # 3. Seuls les deux participants peuvent voter
        if payload.user_id not in (p1.id, p2.id):
            return

        emoji_str = str(payload.emoji)
        if emoji_str not in ("🅰️", "🅱️"):
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        # On arrête d'écouter cette manche
        match["waiting_vote"] = False

        # 4. Comptabilisation du point
        round_winner = p1 if emoji_str == "🅰️" else p2
        match["scores"][round_winner.id] += 1
        current_round = match["round"]

        # Message de transition dans le salon
        await channel.send(
            f"✅ **Manche {current_round}** terminée ! Remportée par {round_winner.mention}.\n"
            f"📊 Score : **{p1.display_name}** `{match['scores'][p1.id]}` — `{match['scores'][p2.id]}` **{p2.display_name}**"
        )

        # 5. Si la manche 3 vient d'être validée -> affichage du panneau arbitre
        if current_round >= 3:
            ref_embed = discord.Embed(
                title="⚖️ Panneau Arbitrage — Fin des 3 manches",
                description=(
                    f"Les 3 manches sont closes !\n"
                    f"• **Score final déclaré** : {p1.mention} `{match['scores'][p1.id]}` — `{match['scores'][p2.id]}` {p2.mention}\n\n"
                    "L'arbitre clique sur le bouton correspondant pour valider le vainqueur officiel :"
                ),
                color=discord.Color.gold()
            )

            ref_view = RefereeControlView(self, channel_id)
            ref_view.children[0].label = f"{p1.display_name[:15]} Win"
            ref_view.children[1].label = f"{p2.display_name[:15]} Win"

            await channel.send(embed=ref_embed, view=ref_view)
        else:
            # Passage à la manche suivante : nouveau message posté à la suite
            match["round"] += 1
            await self.send_round_message(channel, match)

    # --------------------------------------------------------------------------
    # 6. CLÔTURE DU MATCH APRÈS VALIDATION ARBITRALE
    # --------------------------------------------------------------------------
    async def resolve_match(self, channel: discord.TextChannel, winner: discord.Member, loser: discord.Member, referee: discord.Member):
        """Clôture le match après validation arbitrale."""
        # Nettoyage du match en mémoire
        self.active_matches.pop(channel.id, None)

        # TODO : Emplacement pour le calcul d'Elo futur
        embed = discord.Embed(
            title="⚔️ Match Homologué",
            description=f"Validé par l'arbitre {referee.mention}.",
            color=discord.Color.green()
        )
        embed.add_field(name="🏆 Vainqueur", value=winner.mention, inline=True)
        embed.add_field(name="💀 Perdant", value=loser.mention, inline=True)
        embed.set_footer(text="Fermeture du salon dans 20 secondes...")

        await channel.send(embed=embed)

        import asyncio
        await asyncio.sleep(20)
        await channel.delete(reason="Match terminé et validé par l'arbitre")

# ==============================================================================
# ENREGISTREMENT DU COG DANS LE BOT
# ==============================================================================

async def setup(bot):
    await bot.add_cog(Ranked1V1(bot))