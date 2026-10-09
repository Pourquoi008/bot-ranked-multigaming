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


# ==============================================================================
# COG PRINCIPAL : RANKED 1V1
# ==============================================================================

class Ranked1V1(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue: list[int] = []

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
        cfg = get_ranked_config()
        cat_id = cfg.get("match_category_id")
        ref_id = cfg.get("referee_role_id")

        category = guild.get_channel(cat_id) if cat_id else None
        ref_role = guild.get_role(ref_id) if ref_id else None

        # Permissions : visible uniquement par p1, p2, le bot et les arbitres
        overwrites = {