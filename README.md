# 🤖 Bot Discord — Ranked & Twitch Alert

Bot Discord multifonctionnel développé avec **Python (discord.py)**. Il automatise la gestion d'événements compétitifs (inscriptions, attribution dynamique des rôles, création des salons et archivage des scores) et assure une notifications automatique des streams Twitch de streameurs selectionnés.

---

## ⚡ Fonctionnalités détaillées

### 🏆 1. Système de Ranked

#### 📅 Création & Annonce de session (`/annonce-ranked`)
* **Modal de saisie sécurisé :** accessible uniquement depuis le salon `『🥇』inscription-ranked`. Saisie de la date (`JJ/MM`), de l'heure (`0-23`), du mode de jeu et de la liste des jeux.
* **Réinitialisation automatique :** purge des derniers messages en raport avec une annonce d'un précédent match et retrait automatique du rôle `📝 | Inscrit Ranked` à tous les membres.
* **Publication formatée :** affichage dynamique de la date en français, mise en page des jeux, mention automatique du rôle `🏆 | MG Ranked` et ajout instantané des 3 réactions de statut :
  * ✅ : Obtention du rôle `📝 | Inscrit Ranked`.
  * ❔ : Obtention du rôle `⏳ | En Attente Ranked` .
  * ❌ : Désistement (retire les rôles d'inscriptions et nettoie les autres réactions).
* **Retrait réactif :** la suppression d'une réaction retire immédiatement le rôle associé au membre.

#### 👥 Consultation des inscriptions (`/liste_inscrits`)
* Commande permettant d'extraire et d'afficher sous forme d'embed les **12 premiers inscrits** par ordre chronologique d'arrivée sur une réaction donnée (en filtrant les bots).

#### 🚀 Lancement & Déploiement des salons (`/start-ranked`)
* **Nettoyage & Archivage :**
  * Extraction des messages du salon `『📜』scores` avec horodatage converti sur le fuseau horaire de Paris.
  * Génération à la volée d'un fichier texte compressé en mémoire (`Backup_Scores_JJ_MM.txt`) posté automatiquement dans `『🔍』logs-scores`.
  * Suppression des anciens salons de match et réinitialisation des rôles d'équipes (`Team A` à `Team F`).
* **Création des nouveaux salons selon le mode :**
  * **Teams :** 
    * Calcul automatique du nombre d'équipes selon l'affluence (2 équipes par défaut, 4 équipes dès 20 inscrits, 6 équipes au-delà de 30 inscrits).
    * Création du vocal `『🎤』choix-des-teams` avec statut vocal personnalisé pour les capitaines.
    * Création des salons vocaux et textuels privés pour chaque team avec gestion fine des permissions.
  * **Solo :** Création des salons `『🗣️』FFA` (vocal) et `『👤』ffa` (textuel privé).
  * **Duo / Trio / Quatuor :** Création dynamique du nombre exact de salons vocaux requis avec limitation stricte d'utilisateurs (`user_limit`).

---

### 📺 2. Annonces Twitch Helix

* **Boucle de surveillance (toutes les 60s) :**
  * Vérification automatique de l'état des streamers via l'API Twitch Helix avec renouvellement transparent du token OAuth en cas d'expiration (401).
* **Alertes en direct :**
  * Envoi d'un embed complet : jeu en cours, nombre de spectateurs en direct, avatar du streamer et miniature du stream en haute définition (1280x720).
  * Bouton interactif direct (`discord.ui.View`) redirigeant vers la chaîne.
  * Mention paramétrable d'un rôle Discord dédié.
* **Gestion via commandes Slash (`/twitch`) :**
  * `/twitch salon` : Définit le salon de diffusion des alertes.
  * `/twitch role` : Configure le rôle à mentionner.
  * `/twitch ajouter` : Ajoute un streamer (supporte les URLs ou les pseudos simples).
  * `/twitch retirer` : Retire un streamer de la surveillance.
  * `/twitch liste` : Affiche sous forme d'embed l'ensemble des chaînes surveillées.
  * **Persistance :** Sauvegarde automatique des paramètres au format JSON.

---

## 🛠️ Stack technique

* **Python 3.11+**
* **discord.py 2.x** (Cogs, App Commands, UI Views & Modals, Tasks)
* **aiohttp** (Requêtes asynchrones pour l'API Twitch)

---

## ⚙️ Configuration requise

Le bot s'appuie sur des variables d'environnement pour ses accès sécurisés :

* `DISCORD_TOKEN` : Token du bot Discord.
* `TWITCH_CLIENT_ID` : Identifiant client de l'application Twitch Developer.
* `TWITCH_CLIENT_SECRET` : Clé secrète de l'application Twitch Developer.

---

## 🚀 Installation

1. **Cloner le dépôt :**
   ```bash
   git clone [https://github.com/ton-profil/ton-repo.git](https://github.com/ton-profil/ton-repo.git)
   cd ton-repo
