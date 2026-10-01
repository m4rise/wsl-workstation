# Securite

Le profil générique n'a besoin d'aucun secret. Les données personnelles restaurables vivent dans un dépôt privé chiffré ; les moyens de déchiffrement sont distribués séparément. Voir [Operations](docs/OPERATIONS.md#bundle-prive).

Gitleaks vérifie l'historique et les fichiers courants avec masquage. Il ne prouve ni l'absence de tout secret, ni l'absence de données personnelles. Les PR et la CI n'ont jamais besoin des vraies clés du mainteneur.

Un secret déjà exposé doit être révoqué ou remplacé, même s'il est ensuite effacé. Si une clé de chiffrement est compromise, les anciens commits chiffrés restent accessibles avec cette clé ; renouveler les secrets concernés. Le chiffrement au repos ne protège pas d'un programme exécuté sous ton compte qui peut lire une clé de déchiffrement disponible.

Le destinataire age est contrôlé et la configuration fnox validée est exécutée depuis une copie privée. Cela ne signe pas le bundle : une personne ayant accès en écriture au dépôt et connaissant la clé publique peut remplacer une entrée par un nouveau contenu chiffré, ou réintroduire un ancien état. Protéger le compte GitHub par MFA, limiter ses accès et comparer le commit récupéré à une référence conservée séparément. La signature SSH des commits fournit un contrôle supplémentaire si sa clé publique de confiance vient d'une source indépendante du bundle.

La copie locale de la clé age n'est pas chiffrée par le script. Les permissions Linux protègent des autres comptes ordinaires, pas de root, du compte Windows propriétaire de WSL ou d'un processus compromis sous ton compte. Conserver les sauvegardes hors ligne sur des supports protégés ; ne rendre la clé disponible que pour les opérations nécessaires. Les fichiers temporaires privés peuvent survivre à une coupure brutale. Une restauration de plusieurs fichiers n'est pas une transaction résistante aux pannes électriques.

Le téléchargement des CLI mise est verrouillé ; les paquets APT et l'installateur Codex restent évolutifs. Les dépôts shell peuvent être repris depuis le snapshot facultatif ou suivre leurs branches amont. Gitleaks est un détecteur de secrets, pas un audit de vulnérabilités de toutes les dépendances. Les connexions natives créent leurs propres caches locaux, exclus du bundle ; sans trousseau système, `gh` peut stocker son jeton dans un fichier en clair ([documentation GitHub CLI](https://cli.github.com/manual/gh_auth_login)). Ne pas partager `gh auth token` ni les caches des CLI.

Pour signaler un problème, utiliser le signalement privé GitHub Security du nouveau dépôt public quand il sera activé. S'il n'est pas disponible, demander un canal privé au mainteneur sans publier le détail exploitable ni de valeur sensible. Une issue publique peut contenir une reproduction avec des fixtures entièrement fictives.

Avant publication, activer les signalements privés de vulnérabilité sur le nouveau dépôt et vérifier que ce parcours fonctionne. Aucun ancien historique privé ne doit être publié.
