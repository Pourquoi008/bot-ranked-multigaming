# 🤖 Bot Discord — Ranked & Twitch Alert

Bot Discord multifonction développé avec **Python (discord.py)**, conçu pour l'organisation automatisée d'événements ranked (matchs compétitifs, gestion des rôles et des salons vocaux) ainsi que pour la surveillance et l'annonce de streams Twitch en direct.

---

## ⚡ Fonctionnalités principales

### 🏆 1. Organisation de matchs ranked
Un système complet pour planifier, inscrire et répartir automatiquement les joueurs lors des sessions ranked.

* **Création via modal dédié :**
  * Accessible uniquement aux membres ayant le rôle **Modérateur Ranked**.
  * Saisie guidée des informations : date, heure, mode de jeu (équipe, duo, trio, 2v2, etc.) et jeux sélectionnés.
* **Annonce automatique & inscriptions :**
  * Publication d'un message stylisé dans le salon dédié.
  * Ajout automatique de 3 réactions pour gérer les statuts des joueurs :
    * ✅ : Obtention du rôle **Inscrit Ranked**.
    * ❓ : Obtention du rôle **Attente Ranked**.
    * ❌ : Désinscription / refus.
* **Génération dynamique des salons vocaux :**
  * Création des salons vocaux adaptée au format et au nombre de participants :
    * Format équipe : `Team A`, `Team B`, etc.
    * Format petits groupes : `Duo #1`, `Trio #1`, `Trio #2`, etc.
* **Archivage et gestion du salon des scores :**
  * Sauvegarde automatique des scores précédents : extraction des messages postés par les modérateurs et export au format `.txt` dans un salon d'archive/backup.
  * Suppression de l'ancien salon des scores et création d'un salon propre pour la session en cours.

---

### 📺 2. Annonces de streams Twitch
Système de détection automatique pour avertir la communauté dès qu'un streamer passe en direct.

* **Configuration personnalisable :**
  * Définition du salon d'annonce et du rôle à mentionner.
  * Ajout, suppression et consultation de la liste des chaînes Twitch surveillées.
* **Alertes en direct :**
  * Publication d'un embed détaillé (miniature, avatar, jeu en cours, nombre de viewers).
  * Bouton interactif intégré permettant de rejoindre directement le stream sur Twitch.

---

## 🛠️ Stack technique

* **Langage :** Python 3.11+
* **Librairie :** [discord.py](https://github.com/Rapptz/discord.py)
* **APIs tierces :** API Twitch Helix
* **Persistance :** Fichiers JSON locaux

---

## ⚙️ Variables d'environnement

Crée un fichier `.env` à la racine du projet avec les clés suivantes :

```env
DISCORD_TOKEN=ton_token_discord
TWITCH_CLIENT_ID=ton_client_id_twitch
TWITCH_CLIENT_SECRET=ton_client_secret_twitch
