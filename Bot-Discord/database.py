import asyncpg

PLACEMENT_MATCHES_REQUIRED = 3

RANKS = [
    (1700, "Diamant 💎"),
    (1500, "Platine 💠"),
    (1300, "Or 🥇"),
    (1100, "Argent 🥈"),
    (0,    "Bronze 🥉")
]

def get_rank_display(elo: int, matches_played: int) -> str:
    """Affiche 'Unranked (X/3)' ou le rang débloqué."""
    if matches_played < PLACEMENT_MATCHES_REQUIRED:
        return f"Unranked ({matches_played}/{PLACEMENT_MATCHES_REQUIRED})"
    
    for threshold, rank_name in RANKS:
        if elo >= threshold:
            return rank_name
    return "Bronze 🥉"

class Database:
    def __init__(self, database_url: str):
        self.database_url = database_url #database_url=lien dans une variable d'environnement
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.database_url) #database_url=lien dans une variable d'environnement
        print("Connecté à la Database Neon !")

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def get_player_data(self, user_id: int, username: str) -> tuple[int, int]:
        """Retourne (elo, matches_played) ou initialise le joueur à 1200 et 0 match."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT elo, matches_played FROM players WHERE user_id = $1", 
                user_id
            )
            if row:
                await conn.execute("UPDATE players SET username = $1 WHERE user_id = $2", username, user_id)
                return row["elo"], row["matches_played"]

            await conn.execute(
                "INSERT INTO players (user_id, username, elo, matches_played) VALUES ($1, $2, 1200, 0)",
                user_id, username
            )
            return 1200, 0

    async def record_match(self, user_id: int, new_elo: int, username: str | None = None):
        """Met à jour l'Elo et incrémente le compteur de match."""
        async with self.pool.acquire() as conn:
            if username:
                await conn.execute(
                    """
                    UPDATE players 
                    SET elo = $1, username = $2, matches_played = matches_played + 1 
                    WHERE user_id = $3
                    """,
                    new_elo, username, user_id
                )
            else:
                await conn.execute(
                    """
                    UPDATE players 
                    SET elo = $1, matches_played = matches_played + 1 
                    WHERE user_id = $2
                    """,
                    new_elo, user_id
                )

    async def get_all_players_by_rank(self) -> list[asyncpg.Record]:
        """Trie d'abord les joueurs classés par Elo, puis les Unranked."""
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT user_id, username, elo, matches_played 
                FROM players 
                ORDER BY (matches_played >= 3) DESC, elo DESC
            """)

    ## Modification elo
    async def set_player_elo(self, user_id: int, elo: int, username: str | None = None) -> tuple[int, int]:
        """Définit manuellement l'Elo et renvoie (elo, matches_played)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT matches_played FROM players WHERE user_id = $1", user_id)
            if row:
                if username:
                    await conn.execute("UPDATE players SET elo = $1, username = $2 WHERE user_id = $3", elo, username, user_id)
                else:
                    await conn.execute("UPDATE players SET elo = $1 WHERE user_id = $2", elo, user_id)
                return elo, row["matches_played"]
            else:
                await conn.execute(
                    "INSERT INTO players (user_id, username, elo, matches_played) VALUES ($1, $2, $3, 0)",
                    user_id, username, elo
                )
                return elo, 0

    async def adjust_player_elo(self, user_id: int, delta: int, username: str | None = None) -> tuple[int, int]:
        """Ajuste l'Elo et renvoie (nouveau_score, matches_played)."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT elo, matches_played FROM players WHERE user_id = $1", user_id)
            if row:
                new_elo = max(0, row["elo"] + delta)
                if username:
                    await conn.execute("UPDATE players SET elo = $1, username = $2 WHERE user_id = $3", new_elo, username, user_id)
                else:
                    await conn.execute("UPDATE players SET elo = $1 WHERE user_id = $2", new_elo, user_id)
                return new_elo, row["matches_played"]
            else:
                new_elo = max(0, 1200 + delta)
                await conn.execute(
                    "INSERT INTO players (user_id, username, elo, matches_played) VALUES ($1, $2, $3, 0)",
                    user_id, username, new_elo
                )
                return new_elo, 0
