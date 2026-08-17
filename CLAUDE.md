# CLAUDE.md — Triple Threat (SkillCorner ACB)

Fichier de travail. Règles, pas de prose. À lire en entier avant toute modification.

---

## 1. Objectif

**Triple Threat** — application Streamlit locale permettant à un analyste / scout basket d'explorer
des données offensives agrégées **par joueur** sur la saison **2024-2025 de la Liga ACB** (Espagne).
Le nom renvoie aux trois façons de menacer une défense que les données décrivent : **tirer, attaquer
sur écran, créer pour les autres**. Deux domaines de données : **tir** et **pick-and-roll**.

C'est un **test technique évalué** (alternance dev Python chez SkillCorner, ~6 h de travail
suggérées). Grille de notation — à garder en tête à chaque décision :

| Poids | Critère | Traduction opérationnelle |
|---|---|---|
| 30 % | Justesse analytique | Seuils sur le bon dénominateur, taux vs volume, comparaisons valides |
| 25 % | Structure / qualité du code | Modularité, **séparation stricte data ↔ UI** |
| 25 % | Produit & UX | Layout intuitif, filtres dynamiques, valeur réelle pour un scout |
| 20 % | Documentation | Install, justification des métriques, seuils, limites |

Contraintes de l'énoncé, non négociables :

- `pip install -r requirements.txt` puis `streamlit run app.py`, et ça tourne.
- **Zéro dépendance externe à l'exécution** : pas d'API, pas de base de données, pas de
  credential cloud. Les CSV du repo sont la seule source.
- **2 à 3 vues distinctes minimum**, chacune sur un sujet analytique précis.
- Interactivité réelle : dropdowns, sliders de seuils (matchs, tentatives), graphiques interactifs.
- Gestion explicite des tailles d'échantillon, de la distinction taux / volume, de la normalisation.

**Langue** : README, noms de variables, docstrings, commentaires, libellés d'interface → **anglais**.
Ce `CLAUDE.md` → français.

⚠️ **`README.fr.md` est la traduction française de `README.md`, mot pour mot.** Elle existe pour
que l'utilisateur relise le livrable confortablement, pas pour dire autre chose. **Toute
modification de l'un doit être répercutée sur l'autre dans la même session** — chiffres, tableaux,
titres de section, ordre des paragraphes. Le fichier anglais reste le livrable noté ; le français
n'est jamais la source. Chacun pointe vers l'autre dans son en-tête.

---

## 2. Stack et commandes

- Python ≥ 3.10, `pandas`, `streamlit`, `plotly`, `pytest`.
- Pas de dépendance lourde inutile (ni scikit-learn, ni matplotlib, ni base vectorielle).

```bash
python -m venv .venv && .venv\Scripts\activate    # Windows / PowerShell
pip install -r requirements.txt
streamlit run app.py

pytest -q                                          # tests unitaires
python scripts/profile_denominators.py             # distributions des dénominateurs → aide au choix des seuils
```

---

## 3. Arborescence

La séparation traitement des données / interface pèse 25 % de la note : **elle est lisible dans
l'arborescence elle-même**.

```
app.py                      # entrée Streamlit : config de page, navigation, rien d'autre
pages/                      # une vue = un fichier. UI PURE : widgets, appels au core, rendu.
  1_shot_quality.py         # fait
  2_pick_and_roll.py        # à faire
  3_shortlist.py            # à faire
  4_admin.py                # bonus, seulement si le reste est fini
src/
  data/
    schema.py               # TOUS les noms de colonnes bruts, en un seul endroit
    glossary.py             # metric_glossary.csv : display_name / definition / unit + colonnes dérivées
    loader.py               # lecture CSV, jointure picks×shots sur player_id, cache
  core/
    metrics.py              # vocabulaire (Column/Axis/Threshold/View/Lens) + DENOMINATORS
    catalogue.py            # les vues elles-mêmes, pure déclaration
    aggregate.py            # colonnes dérivées, fonctions pures
    thresholds.py           # filtrage à deux étages, bornes de sliders
    ranking.py              # éligibilité, percentiles, tri à deux étages, épinglage
  ui/
    filters.py              # barre de portée, expander de seuils, sélecteurs
    charts.py               # factories Plotly, figures figées
    tables.py               # composition du tableau (layout), styles, rendu
    panel.py                # fiche joueur
    selection.py            # quel joueur est chargé
    sorting.py              # sur quelle colonne le tableau est trié
    format.py               # nombres, pourcentages, percentiles
    theme.py                # palette résolue selon le thème du lecteur
tests/                      # le core uniquement (+ tables.layout, question de données)
data/                       # les 3 CSV fournis, en lecture seule, jamais modifiés
logs/                       # journal d'usage local (page 4), hors git
README.md                   # en anglais, livrable noté
```

**Règle dure** : aucun `pandas` métier dans `pages/`. Un fichier de page lit des widgets, appelle
une fonction de `src/`, passe le résultat à un renderer de `src/ui/`. Si une page contient un
`groupby`, un `quantile`, un masque booléen de filtrage ou un calcul de ratio → le code est au
mauvais endroit. Vérification rapide :
`grep -n "groupby\|quantile\|\.merge(\|import pandas" pages/*.py` doit ne rien renvoyer.

## 4. Modèle de données

### 4.1 Les trois fichiers (dans `data/`)

| Fichier | Lignes | Colonnes | Contenu |
|---|---|---|---|
| `SPAIN_2024-2025_picks_offense.csv` | 292 joueurs | 599 | Pick-and-roll par joueur |
| `SPAIN_2024-2025_shots_offense.csv` | 295 joueurs | 228 | Tir par joueur |
| `metric_glossary.csv` | 827 lignes | 10 | Dictionnaire des colonnes des deux fichiers |

**Clé de jointure : `player_id`** (unique dans chaque fichier, aucun doublon). Effectifs
différents (292 vs 295) → la jointure doit être explicite (`how="outer"` avec indicateur de
provenance, ou `inner` assumé et documenté). Ne jamais joindre sur `player_name`.

Identifiants partagés : `league`, `season`, `player_id`, `player_name`, `team_name`,
`meta_team_id`, `games_played`, `appearances`, `is_traded`.

### 4.2 Le glossaire est la porte d'entrée

`metric_glossary.csv` décrit **chaque** colonne : `dataset`, `column`, `display_name`, `category`,
`role`, `split_type`, `split_value`, `data_type`, `unit`, `definition`.

Il sert à :
- construire les libellés d'interface (`display_name`) et les infobulles (`definition`) — **ne jamais
  réécrire à la main un libellé que le glossaire fournit** ;
- déduire le formatage à partir de `unit` (`ratio 0-1` → %, `points per pick` → 2 décimales,
  `events` / `shots` / `points` → entier, `metres` → 1 décimale) ;
- énumérer les splits disponibles (`split_type` / `split_value`) plutôt que de les coder en dur.

Répartition utile :
- `unit` : `events` (313), `ratio 0-1` (307), `shots` (100), `points` (44),
  `points per shot` (26), `points per pick` (18), `games` (4), `metres` (1).
- `role` (picks uniquement) : `Ball Handler` (328), `Screener` (262), vide (237).

### 4.3 Structure `picks_offense`

Tout est dédoublé par rôle : préfixes **`handler_`** (porteur qui utilise l'écran) et
**`screener_`** (poseur d'écran).
Catégories : Volume, Scoring, Playmaking, Outcome, Shooting, Efficiency.

Splits (suffixes) :
- **Couverture défensive** (`split_type = "Defensive coverage"`) : `_vs_blitz`, `_vs_switch`,
  `_vs_ice`, `_vs_over`, `_vs_under` (handler) ; `_vs_blitz`, `_vs_switch`, `_vs_ice`,
  `_vs_show`, `_vs_soft` (screener). **Les jeux de couvertures ne sont pas identiques entre les
  deux rôles** — ne pas supposer la symétrie.
- **Zone de terrain** (`split_type = "Court location"`) : `_at_middle`, `_at_wing`, `_at_stepUp`.

Dénominateurs : `handler_total_picks`, `screener_total_picks` en global ;
`{role}_picks_vs_{coverage}` et `{role}_picks_at_{zone}` sur les splits.

Efficacité : `{role}_ppp` (points per pick), `{role}_score_rate`, `{role}_turnover_rate`,
`{role}_success_rate`, déclinés `_vs_{coverage}`. **Aucune colonne de `picks_offense` ne contient
le mot `percentage`** — les taux s'y appellent `_rate` ou `_pct`. Ne pas écrire de détection de
métrique par `"percentage" in col` sur ce fichier.

### 4.4 Structure `shots_offense`

Catégories : Volume, Scoring, Efficiency, Shot Profile, Free Throws, Shot Creation.
Trio récurrent `{préfixe}_attempts` / `{préfixe}_mades` / `{préfixe}_fg_percentage`.

| Split | Préfixe | Valeurs |
|---|---|---|
| Shot creation | `cns_`, `od_` | Catch & Shoot, Off the Dribble |
| Contest | `contested_`, `uncontested_` | 2 valeurs |
| Contest level | `cl_` | `average`, `blocked`, `light`, `open`, `plus` |
| Shot zone (SkillCorner) | `rim_`, `short_midrange_paint_`, `long_midrange_`, `zone_three_` | 4 zones |
| Shot zone (NBA) | `attempts_X` / `mades_X` | Restricted_Area, Paint_Non_RA, Mid_Range, Corner_3, Above_Break_3 |
| Shot type | `cst_` | 14 valeurs (`catchAndShoot`, `dribblePullUp`, `dunk`, `floater`, `heave`, `hook`, `layup`, `leaner`, `lob`, `offMove`, `postFadeaway`, `shakeAndRaise`, `stepback`, `tip`) |

### 4.5 Irrégularités de nomenclature (à traiter comme exceptions curées)

La régularité doit être exploitée par génération automatique, **mais ces cas cassent le motif** :

- **Zones NBA** : préfixe inversé (`attempts_Corner_3`, pas `corner_3_attempts`), casse mixte,
  **aucune colonne de pourcentage fournie** → si on affiche un FG% par zone NBA, il faut le
  calculer (`mades / attempts`) et donc gérer soi-même la division par zéro.
- **camelCase** au milieu du snake_case : `_at_stepUp`, `cst_catchAndShoot_`, `cst_dribblePullUp_`,
  `cst_offMove_`, `cst_postFadeaway_`, `cst_shakeAndRaise_`.
- Les taux de picks sont `_rate` / `_pct`, ceux de tir sont `_percentage`.
- Toutes les valeurs `ratio 0-1` sont **sur une échelle 0-1, pas 0-100** — le formatage `%` est
  une responsabilité de `src/ui/format.py`, jamais une multiplication éparpillée dans le code.
  **L'eFG dépasse 1, mais pas sur la colonne qu'on croit** : `efg_percentage` plafonne à **1,00**
  exactement (2 joueurs, sur 6 et 3 tirs). Ce sont les colonnes de split qui montent —
  `cns_efg_percentage` **1,50**, `contested_efg_percentage` et `uncontested_efg_percentage`
  **1,25**, toutes sur **2 tentatives**. L'eFG peut atteindre 1,5 par construction (tout rentré,
  tout à 3 points) : **ne jamais clipper à 1**. Ces trois valeurs sont aussi la meilleure
  illustration du seuil — les trois joueurs tombent sous la barre des 35 tirs.
- **`avg_shot_distance` est en PIEDS, pas en mètres**, contrairement à ce qu'annonce le glossaire.
  Preuve la plus courte : la **médiane** de la ligue vaut **14,43**. Lue en mètres, le tir médian
  d'ACB partirait de derrière le milieu de terrain (14 m sur 28). Lue en pieds tout se recale :
  parmi les 234 joueurs à 35 tirs ou plus, le plus lointain tire à 22,20 ft = **6,77 m**, soit la
  ligne à 3 points FIBA (6,75 m) au centimètre, et le plus proche du cercle à 3,27 ft = 1,00 m, un
  lay-up. ⚠️ Sur le fichier entier le max monte à 23,91 (3 tirs, 100 % à trois points) : citer les
  bornes **sur une population qui tient**, pas sur les 295 lignes brutes. Conversion assurée par
  `schema.FEET_TO_METRES` vers la colonne dérivée `derived_avg_shot_distance_metres` ; la colonne
  brute n'est jamais écrasée, et un test verrouille la conversion.
- ~89 colonnes de `picks_offense` sur 599 sont vides à plus de 50 %.

### 4.6 Pièges de données à documenter dans le README

1. **Blitz et Ice sont des couvertures rares en ACB.** Maximum league-wide par joueur :
   `handler_picks_vs_blitz` = **5**, `handler_picks_vs_ice` = **7**, `screener_picks_vs_blitz` = **5**,
   `screener_picks_vs_ice` = **9**, médiane 0. Ce n'est pas un défaut de données : les défenses
   espagnoles jouent très peu ces couvertures. **On les garde et on les affiche comme les autres** —
   la machinerie de seuils fait son travail toute seule (à 3 événements minimum, 5 handlers
   franchissent la barre vs Blitz, 19 vs Ice). Une note en clair sur la vue dit que la couverture est
   rare, sans refuser de la montrer. Décision de l'utilisateur, ne pas rouvrir.
2. **Pas de colonne de poste.** Aucun moyen fiable de comparer « entre intérieurs ». Le rôle
   `handler` / `screener` et le profil de tir sont les seuls proxys disponibles → à assumer et
   documenter comme limite.
3. **`is_traded`** : 8 joueurs sur 292. **Une seule ligne par joueur** — le glossaire est explicite :
   « *the row still aggregates all of his season events* ». `team_name` ne porte que la dernière
   équipe, donc un agrégat par équipe les compte au mauvais endroit → toggle d'exclusion, pas de
   dédoublonnage. Question tranchée, ne pas rouvrir.
4. **`games_played == appearances`** dans les deux fichiers (vérifié, identiques ligne à ligne) →
   n'exposer qu'un seul des deux dans l'UI.
5. **`games_played` va de 1 à 44** (médiane 28) pour une saison régulière de 34 journées : les
   valeurs > 34 incluent des matchs de playoffs. Ne pas coder 34 en dur comme total de matchs.
6. `games_played` compte les matchs avec **au moins un événement tracké dans ce dataset** — ce
   n'est pas le temps de jeu. Il n'y a **aucune colonne de minutes** → toute normalisation « par
   36 minutes » est impossible. Normaliser par événement (per pick, per shot) ou par match.
7. **Les dénominateurs s'effondrent sur les splits fins.** Ordres de grandeur sur 292 / 295 joueurs :

   | Dénominateur | max | médiane | n ≥ 25 | n ≥ 50 |
   |---|---|---|---|---|
   | `attempts` (tirs) | 471 | 131 | — | 216 |
   | `three_attempts` | 279 | 45 | — | 139 |
   | `rim_attempts` | 137 | 25 | — | 70 |
   | `handler_total_picks` | 901 | 8.5 | — | — |
   | `handler_picks_vs_over` | 557 | 4 | 105 | 86 |
   | `handler_picks_vs_switch` | 180 | 2 | 61 | 25 |
   | `screener_picks_vs_show` | 347 | 7 | 99 | 70 |
   | `cst_stepback_attempts` | 36 | 1 | — | 0 |
   | `uncontested_three_attempts` | 62 | 14 | — | 9 |

   Conséquence directe : **un seuil unique pour toute l'app est faux**. Le seuil est propre à la
   métrique affichée, et son maximum de slider est propre à la colonne dénominateur.

8. **⚠️ AUCUN split de tir ne totalise `attempts`.** Vérifié colonne par colonne : une partie des
   tirs ne porte pas de classification. Part du total couverte, sur 42 340 tirs de ligue :

   | Split | Couverture | Pire joueur |
   |---|---|---|
   | `contested_` + `uncontested_` | 97,5 % (1 059 tirs non classés) | 15 tirs |
   | `cns_` + `od_` | 94,1 % (2 494 tirs) | 31 tirs |
   | les 5 zones NBA | 96,8 % | 25 % de ses tirs |
   | les 4 zones SkillCorner | 96,8 % | — |
   | les 5 `cl_` (contest level) | 97,5 % | 15 tirs |
   | les 14 `cst_` (shot type) | 97,5 % | 15 tirs |

   Conséquences appliquées : **les parts se calculent contre le TOTAL** et tombent légitimement
   sous 100 % — ne jamais renormaliser à 100 ; le mid-range reste une **somme de deux zones**,
   jamais `100 − rim − 3pts` (déjà acté) ; le shot chart couvre « la plupart » des tirs, pas tous.
   `zone_three_attempts` est **≤ `three_attempts`** pour 203 joueurs (jusqu'à 17 de moins), même
   cause. **Deux splits partitionnent bien**, eux : `two_attempts + three_attempts == attempts`
   exactement sur les 295 lignes, et les 5 couvertures couvrent 98 à 100 % des picks — c'est ce
   qui justifie la barre 100 % du bloc couvertures.
9. **Zéro et manquant sont correctement distingués à la source.** Une tranche jamais jouée porte
   **NaN**, pas 0 : 72 joueurs sans pick handler, 243 sans pick vs blitz, 201 sans `cst_heave`.
   L'app fait pareil (`aggregate.safe_ratio` → NaN, `fmt.BLANK` à l'affichage). Confondre les deux
   transformerait « jamais tenté » en « tenté et raté » sur toutes les fiches.
10. **Colonnes mortes, chiffres exacts** : **24** colonnes de picks à zéro partout (dont toute la
    famille `no_outcome_pick` et `screener_ft_attempts_in_pick` — le PPS screener est donc FG-only,
    alors que `handler_ft_attempts_in_pick` monte à 79) ; **1** colonne entièrement vide,
    `handler_fg2_pct_vs_blitz` ; **89** colonnes de picks vides à plus de 50 % ; **4** colonnes de
    tir à zéro partout (`cl_blocked_mades`, `_points`, `_fg_percentage`, `_points_per_shot`) — ce
    qui est **logique et non un défaut** : un tir contré n'est jamais rentré ; **8** colonnes de tir
    vides à plus de 50 % (pourcentages et PPS des types rares : heave, leaner, lob, postFadeaway).
11. **Le glossaire couvre 100 % des deux fichiers, dans les deux sens** : 599 + 228 = 827, aucune
    colonne non décrite, aucune ligne orpheline. C'est ce qui rend sûre la règle « le glossaire est
    la seule autorité de nommage » (§7).
12. **Rosters et clés** : 288 joueurs communs, 4 uniquement dans picks, 7 uniquement dans shots,
    **299 au total**. 18 équipes dans les deux fichiers. Aucun `player_id` ni `player_name` en
    double — mais la jointure reste sur l'**id** : l'unicité d'une saison n'est pas une garantie.

---

## 5. Règles de seuils — le cœur analytique du projet

### 5.1 Le seuil porte sur le dénominateur de la métrique, jamais sur `games_played`

Un joueur peut avoir joué 34 matchs et n'avoir que 11 pick-and-roll face à une couverture donnée.
Filtrer sur `games_played` ne protège **rien** : afficher son efficacité sur ce split, c'est
afficher du bruit.

**Chaque pourcentage / taux affiché est filtré sur le nombre d'événements qui composent réellement
sa fraction.** Cela impose une table de correspondance `métrique → colonne dénominateur`, vivant
dans `src/core/metrics.py` :

```python
DENOMINATORS = {
    "three_pt_percentage":           "three_attempts",
    "efg_percentage":                "attempts",
    "cns_efg_percentage":            "cns_attempts",
    "rim_fg_percentage":             "rim_attempts",
    "contested_three_fg_percentage": "contested_three_attempts",
    "handler_ppp":                   "handler_total_picks",
    "handler_ppp_vs_blitz":          "handler_picks_vs_blitz",
}
```

- **Uniquement pour les métriques réellement affichées**, pas pour les 827 colonnes.
- La majeure partie est **générée** par la régularité de nommage ; les exceptions de §4.5 sont
  curées à la main.
- **Test obligatoire** : un test vérifie que chaque métrique du catalogue a un dénominateur
  existant dans le dataframe. Un dénominateur manquant est une erreur, pas un fallback silencieux.

### 5.2 Filtrage à deux étages — deux questions différentes

| Étage | Contrôle | Question | Portée |
|---|---|---|---|
| **Population** | `games_played` (ou part des matchs de l'équipe) | « Qui est un joueur de rotation ? » | Périmètre d'analyse, global à la page |
| **Échantillon** | dénominateur réel de la métrique affichée | « Cette estimation est-elle fiable ? » | Recalculé **pour chaque métrique et chaque split** |

Ne jamais fusionner les deux étages en un seul filtre.

### 5.3 Les colonnes de comptage ne sont soumises à aucun seuil

Totaux, volumes, événements : **un total est un total**. Aucun seuil d'échantillon ne s'y applique.
Seul l'étage population peut les restreindre.

### 5.4 Valeurs de seuil

Les valeurs par défaut sont **choisies par l'utilisateur du repo (le candidat)**, pas déduites
automatiquement. Chaque seuil dispose d'un **slider allant de 0 au maximum réellement observé dans
le CSV pour cette colonne dénominateur** (`int(df[denominator].max())`), jamais un maximum codé en
dur. `scripts/profile_denominators.py` sert à alimenter ce choix.

**Tous les seuils de tir valent une tentative par match officiel** — `metrics.SEASON_MINIMUM`
= `SHOTS_PER_GAME (1) × schema.REGULAR_SEASON_GAMES (34)` **arrondi au cran supérieur du slider**
(`MINIMUM_STEP = 5`) = **35**. Un défaut hors grille ne peut plus être retrouvé dès que le lecteur
touche le curseur : tout défaut se pose sur un cran, et `MINIMUM_STEP` est la seule source du pas
(`filters.minimum_expander`, `criteria._minimum_input`). Formulé par match, pas en nombre nu : 35
ne se lit pas tout seul, « un tir par match » se discute. Volontairement bas — il sert à sortir un
pourcentage sur cinq tirs d'un classement, pas à réduire le board aux gros volumes ; le lecteur
monte le slider s'il veut resserrer. Le même chiffre porte des exigences très différentes selon le
dénominateur (234 joueurs à 35 tirs, 135 à 35 trois points contestés), ce qui est exactement
l'intérêt de gater chaque taux sur SON compteur.
⚠️ `REGULAR_SEASON_GAMES = 34` est la **longueur de la saison régulière**, jamais un maximum :
§4.6 point 5 tient toujours, `games_played` monte à 44 à cause des playoffs et rien ne compare un
joueur à ce 34.

**Les seuils picks sont propres au rôle** : `HANDLER_MINIMUM = 10`, `SCREENER_MINIMUM = 20`
(couvertures : 25, ou 3 si rare). Un écran n'est pas un tir, et les deux rôles ne sont pas le même
métier : un screener pose des écrans toute la partie, un handler joue ceux que l'équipe appelle
pour lui — les volumes ne sont pas comparables et une barre unique classerait deux métiers sur une
seule échelle. À 10 et 20 : 141 handlers et 150 screeners mesurés (contre 102 / 103 à l'ancien 50).

**`MINIMUM_STEP = 5`, un seul pas pour toute l'app**, donc **tout défaut doit tomber sur un cran**.
Un défaut de 8, atteignable ni depuis 5 ni depuis 10, est une barre que le lecteur perd au premier
mouvement du curseur (essayé, puis ramené à 10 sur demande de l'utilisateur — ne pas réintroduire
un pas variable pour rattraper un défaut mal choisi ; c'est le défaut qu'on arrondit). **Seule
exception : un défaut inférieur au pas** — les 3 picks des couvertures rares s'ouvrent sous le
premier arrêt du slider, et 0 (tout le monde, comptes affichés) est le retour. Test dédié, qui
autorise explicitement ce cas et rien d'autre.

---

## 6. Comportement de l'interface — appliquer partout où un seuil s'applique

1. Les sliders de seuils minimums sont **regroupés dans un expander fermé par défaut**, avec des
   valeurs par défaut déjà appliquées. L'app est utile sans jamais ouvrir l'expander.
2. Juste en dessous : un **toggle « afficher / masquer les joueurs non éligibles »**.
3. Quand ils sont affichés, les **non-éligibles sont grisés**, et leur colonne de rang / percentile
   affiche **un tiret**, jamais une valeur.
4. Les **percentiles se calculent uniquement sur la population éligible**. Inclure les
   non-éligibles déforme l'échelle pour tout le monde.
5. **Tri par défaut à deux niveaux** : éligibles d'abord (triés entre eux), non-éligibles ensuite
   (triés entre eux également).
6. Toute valeur soumise à seuil affiche, à portée de regard, **la taille d'échantillon** qui la
   sous-tend (la colonne dénominateur à côté de la métrique).

### 6.1 Pas de shrinkage dans la version principale

La régression vers la moyenne (ajout de tentatives fictives à la moyenne de la ligue) est une piste
**étudiée et écartée** : les outils de consultation du marché fonctionnent au seuil, et c'est ce
qui est livré. Elle pourra revenir **en toute fin de projet**, sous forme de case à cocher
optionnelle « adjusted value », **à côté** de la valeur brute et **jamais à sa place**.
**Ne pas l'implémenter tant que ce n'est pas explicitement demandé.**

---

## 7. Conventions de code

- **Anglais** pour tout identifiant, docstring, commentaire et libellé d'interface.
- `snake_case` fonctions/variables, `UPPER_SNAKE` constantes, `PascalCase` dataclasses.
- **Type hints obligatoires** sur toute fonction publique de `src/`. Docstring courte
  (une ligne d'intention + `Args` / `Returns` si non trivial).
- **Fonctions pures dans `src/core/`** : elles reçoivent un `DataFrame` et des paramètres,
  renvoient un nouvel objet. Aucun accès à `st.*` en dehors de `src/ui/` et `pages/`.
- **Aucune mutation en place** d'un dataframe mis en cache (`df.copy()` avant modification).
- **Taille max ~250 lignes par fichier.** Au-delà, découper.
- **Constantes** : `src/data/schema.py` (colonnes, splits, préfixes) et `src/core/metrics.py`
  (catalogue de métriques, dénominateurs, défauts de seuils). **Aucune chaîne de nom de colonne en
  dur dans `pages/` ou dans `src/ui/`.**
- **Aucun libellé de colonne écrit à la main.** Tout nom de colonne affiché vient de
  `glossary.name(key)`, c'est-à-dire du `display_name` de `metric_glossary.csv`. `Column`,
  `Threshold` et `profile.Axis` n'ont **pas** de champ `label` : c'est une propriété qui interroge
  le glossaire. Les colonnes dérivées sont nommées dans `glossary.derived_names()`, dans le style
  du glossaire (`Split - Métrique`, title case), à côté de leur définition. Seules les **phrases**
  restent écrites à la main : libellés d'axes de nuage (`metrics.Axis.label`), quadrants,
  descriptions de vues, et `Threshold.events` (« guarded shots », pour les phrases de la fiche).
- **Un board ne répète pas dans ses en-têtes ce que ses propres sélecteurs disent**
  (`catalogue.short(view, name)`, appliqué aux en-têtes de `tables.layout`, aux tuiles de la carte,
  au slider de seuil et au hover du nuage) :
  - le **rôle**, retiré via `Lens.prefix` — dérivé de `Lens.prefix_from` (une colonne de la
    lentille) et **jamais tapé** : `glossary.name("handler_total_picks")` → `Ball Handler - ` ;
  - la **couverture**, retirée via `glossary.without_split` **uniquement sur une vue de
    couverture** (`"_vs_" in view.threshold.key`), où toutes les colonnes portent la même. Ailleurs
    le split est ce qui distingue deux colonnes, on n'y touche pas.
  `Screener - Points Per Pick (vs Soft (Drop))` = 32 caractères dont 28 répètent les deux
  contrôles juste au-dessus, sept fois de suite : le lecteur devait faire défiler son propre
  tableau vers la droite. Ce qui est retiré reste dans l'infobulle (définition du glossaire).
  ⚠️ **La shortlist garde les noms entiers** : les deux rôles y sont listés ensemble, le préfixe
  est la seule chose qui sépare deux `Points Per Pick`. Deux tests verrouillent les deux côtés.
- **Cache** : `@st.cache_data` sur le chargement et le parsing des CSV (coûteux, immuable).
  Pas de cache sur du filtrage trivial. Toute fonction cachée renvoie un objet non muté ensuite.
- Aucune écriture dans `data/`. Les CSV sont en lecture seule.
- Tests : `tests/` couvre le core (dénominateurs, éligibilité, percentiles sur population éligible,
  tri à deux niveaux). Pas de test d'UI Streamlit.

---

## 7bis. Charte graphique — identique sur toutes les pages

Établie sur la page 1, à reproduire telle quelle. Toute nouvelle page réutilise `src/ui/`, elle
n'invente pas ses propres composants.

**Structure d'une page**, dans cet ordre :
1. `st.title` + une phrase de `st.caption` qui dit ce que la page sépare.
2. Sélecteur de lentille en `st.segmented_control`, libellé masqué, suivi d'une `st.caption`.
3. `st.container(border=True)` — barre de portée (équipe, matchs minimum, recherche, transférés),
   puis expander de seuils **fermé par défaut**.
4. `st.columns([1.6, 1])` — graphique encadré à gauche, fiche joueur encadrée à droite.
5. `st.container(border=True)` — tableau, avec sa légende de tri en dessous.

Les conteneurs sont **créés dans l'ordre de lecture et remplis dans l'ordre de dépendance**
(cf. `pages/1_shot_quality.py`), ce qui permet à un sélecteur d'être physiquement dans la carte du
graphique tout en étant lu avant les filtres.

**Couleurs** : uniquement via `src/ui/theme.py`. Jamais de hex en dur ailleurs.
`accent` pour les marques actives, `muted` pour les non-éligibles, rampe `zones` ordonnée par
distance au panier, `highlight` (colonne triée) ≪ `selected` (joueur chargé), `GRID` translucide.

**Graphiques** : figés (`charts.STATIC` pour les figures de fiche, `charts.CLICKABLE` +
`fixedrange` pour un nuage cliquable). Jamais de zoom, de pan ni de barre d'outils. Médianes
calculées sur les éligibles seuls, quadrants nommés en langage de scout.

**Tableau** : un seul, non-éligibles grisés en bas, joueur chargé épinglé en première ligne, tri par
clic sur en-tête (flèche + teinte), sélection par clic sur une cellule (jamais de case à cocher),
infobulle du glossaire sur chaque en-tête.

**Fiche joueur** : titre + bouton `Clear`, ligne de contexte, phrase en langage courant
(`View.summary`), tuiles `View.tiles` avec taille d'échantillon et percentile ordinal, puis les
figures. Une `st.divider()` entre les blocs.

**Langue et vocabulaire** : anglais partout. Seul terme statistique toléré : « percentile ».

---

## 7ter. Feuille de route des pages

### Page 2 — `2_pick_and_roll.py`

**Deux lentilles, une par rôle** : Ball Handler et Screener. Le rôle est un proxy de poste presque
parfait (seuls 4 joueurs sur 292 dépassent 50 picks dans les deux rôles), c'est donc le bon axe de
séparation, pas un filtre annexe.

**Métrique de tête : `{role}_ppp`.** ⚠️ Elle inclut les points marqués par les coéquipiers sur les
passes décisives — c'est la production offensive totale générée par pick, **pas** une efficacité de
scoreur. Ne jamais la comparer à `points_per_shot` du fichier tirs. Pour le scoreur pur en pick :
`{role}_points_per_shot_in_pick` (TS avec 0.44×FTA).

**Sous-vues par lentille** (mêmes rouages que la page 1 : `Lens` → `views`) :

| Lentille | Sous-vue | x | y | Dénominateur du seuil | Éligibles observés |
|---|---|---|---|---|---|
| Handler | Overall | `handler_shot_taken_pct` | `handler_ppp` | `handler_total_picks` | 102 à ≥50 |
| Handler | vs Over | `handler_shot_rate_3pt_vs_over` | `handler_ppp_vs_over` | `handler_picks_vs_over` | 105 à ≥25 |
| Handler | vs Under | `handler_shot_rate_3pt_vs_under` | `handler_ppp_vs_under` | `handler_picks_vs_under` | 55 à ≥25 |
| Handler | vs Switch | `handler_shot_taken_pct_vs_switch` | `handler_ppp_vs_switch` | `handler_picks_vs_switch` | 61 à ≥25 |
| Screener | Overall | `screener_shot_rate_3pt` (roll vs pop) | `screener_ppp` | `screener_total_picks` | 103 à ≥50 |
| Screener | vs Show | — | `screener_ppp_vs_show` | `screener_picks_vs_show` | 99 à ≥25 |
| Screener | vs Soft | — | `screener_ppp_vs_soft` | `screener_picks_vs_soft` | 82 à ≥25 |

**Blitz et Ice sont affichés comme les autres couvertures**, avec un seuil par défaut bas (3) et une
note disant qu'elles sont rares en ACB (§4.6). Le seuil fait le tri de lui-même.

**Colonnes qui font la valeur de la page** :
- Handler : `_score_rate`, `_turnover_rate`, `_success_rate` (avantage créé, indépendant du tir),
  `_assist_opportunity_rate`, et surtout `_pass_to_screener_pct` — joue-t-il vraiment avec son
  roll-man ou cherche-t-il le kick-out ?
- Screener : `screener_assist_rate` / `screener_assist_opportunity` = **la passe en short roll**,
  compétence rare et difficilement mesurable ailleurs. C'est l'angle le plus original du projet.
- `{role}_shot_rate_2pt` / `_3pt` pour séparer roll et pop.

**Zone de terrain** : `{role}_pick_rate_at_{middle,wing,stepUp}` = **un profil, pas une performance**
→ aucun seuil, valable pour les 292 joueurs. À mettre sur la fiche joueur en barre 100 %, comme le
shot menu de la page 1. ⚠️ camelCase `stepUp`.

**Colonnes mortes à ne jamais afficher** : toute la famille `no_outcome_pick` (0 partout),
`screener_ft_attempts_in_pick` / `_ft_mades_in_pick` (0 partout, donc le PPS screener est FG-only).

### Page 3 — `3_shortlist.py` (première page de l'app)

Deux blocs sur une seule page, pas de page par joueur.

**Bloc 1 — construction de la sélection.** Critères empilables choisis dans un sélecteur alimenté
par le catalogue (métrique + opérateur + valeur). Chaque critère porte **son propre dénominateur**,
appliqué automatiquement via `DENOMINATORS`. Export CSV du résultat.

**Bloc 2 — tableau long + « See more ».** Un `st.expander` par joueur, ouvert **sous sa ligne**, qui
contient :
- radar de **percentiles** sur la population éligible (jamais sur valeurs brutes : les échelles ne
  sont pas comparables) ;
- shot chart : demi-terrain en zones NBA (`Restricted_Area`, `Paint_Non_RA`, `Mid_Range`,
  `Corner_3`, `Above_Break_3`) — seule convention qui sépare corner et above-break.
  ⚠️ **Aucune colonne de pourcentage n'existe pour ces zones** : calculer `mades / attempts` avec
  `aggregate.safe_ratio`, et griser une zone sous `ZONE_MIN_ATTEMPTS` ;
- profil pick (barre 100 % par zone de terrain) + profil de tir, côte à côte.

**Croise les deux fichiers** → justifie la jointure de `loader.load_shot_profiles`.

### Page 4 — `4_admin.py` (bonus, en dernier)

**Journal local uniquement.** Écriture en JSONL dans `logs/usage.jsonl`, **jamais dans `data/`**,
dossier hors git. Aucune dépendance réseau, aucun identifiant personnel : un `session_id` tiré au
hasard au premier run et rien d'autre.

**Ce qu'on journalise** (un événement = une ligne) : horodatage, `session_id`, page, lentille et
sous-vue, filtres de portée, seuil retenu, colonne de tri, joueur consulté, mode valeurs/percentiles.

**Ce qu'on affiche**, orienté décision et pas vanité :
- activité par jour et par session, durée médiane de session ;
- **quelles vues sont réellement utilisées** — si une lentille ne sert jamais, elle est à revoir ;
- joueurs les plus consultés (proxy de l'intérêt marché) ;
- **valeurs de seuils réellement choisies** vs valeurs par défaut : si les scouts déplacent
  systématiquement un slider, le défaut est mauvais → c'est l'insight qui justifie la page ;
- entonnoir : sessions → filtre modifié → joueur ouvert.

L'écriture passe par un module dédié `src/data/usage.py` (fonctions pures + une écriture append),
la page ne fait que lire et rendre.

---

## 8. À ne pas faire

- ❌ Filtrer sur `games_played` pour protéger une métrique de pourcentage. Le seuil porte sur le
  dénominateur de la fraction affichée.
- ❌ Calculer des percentiles ou des rangs sur la population entière. Population **éligible**
  uniquement.
- ❌ Mettre du calcul (`groupby`, `quantile`, `merge`, ratio, masque de filtrage) dans un fichier de
  `pages/`. Ça coûte directement sur les 25 % « structure du code ».
- ❌ Implémenter le shrinkage / la régression vers la moyenne sans demande explicite.
- ❌ Employer du vocabulaire statistique dans l'interface. Pas de « sample size », « percentile
  rank », « regularized », « n≥ », « statistically significant » visibles à l'écran. Le libellé
  utilisateur parle de **matchs, de tentatives, de picks** — le raisonnement statistique va dans le
  README, pas dans l'UI.
- ❌ Coller `@st.cache_data` partout par réflexe. Cacher ce qui est coûteux et immuable
  (lecture CSV, parsing du glossaire), pas ce qui dépend d'un slider.
- ❌ Réécrire à la main des libellés que `metric_glossary.csv` fournit déjà.
- ❌ Supposer la symétrie handler / screener sur les couvertures défensives (§4.3).
- ❌ Coder en dur un maximum de slider, un nombre de matchs (34), ou une liste de splits que le
  glossaire peut fournir.
- ❌ Ajouter une dépendance externe, un appel réseau, ou un fichier de credential.
- ❌ Multiplier les ratios par 100 dans le code métier. Le formatage est une affaire d'UI.

---

## 9. État d'avancement

> Section maintenue à jour à la fin de chaque session. Ne pas laisser dériver.

**Session 1 — 2026-08-16**
- [x] Exploration des données : structure, effectifs, splits, distributions des dénominateurs
- [x] `CLAUDE.md` rédigé

**Session 2 — 2026-08-16**
- [x] Maquette HTML interactive de la vue tir, validée avec l'utilisateur
- [x] Squelette du repo + `requirements.txt`
- [x] `src/data/` : `schema.py`, `glossary.py`, `loader.py`
- [x] `src/core/` : `metrics.py` (vocabulaire + `DENOMINATORS`), `catalogue.py` (les vues),
      `thresholds.py`, `ranking.py`, `aggregate.py`
- [x] `src/ui/` : `filters.py`, `charts.py`, `tables.py`, `panel.py`, `format.py`, `theme.py`
- [x] `pages/1_shot_quality.py` — vue 1 : 3 lentilles (zone / contest / création)
- [x] `tests/test_core.py` — 18 tests, tous verts
- [x] `README.md` (anglais)
- [x] Percentiles, mid-range, épinglage, tri par en-tête, charte graphique fixée
- [x] Nom arrêté : **Triple Threat**
- [x] Page 2 : pick-and-roll — deux lentilles, 6 vues chacune, Blitz/Ice inclus
- [x] `src/ui/board.py` : corps de page partagé, les deux pages ne peuvent plus diverger
- [x] `src/core/` découpé : `metrics.py` (vocabulaire) / `shot_views.py` / `pick_views.py` /
      `catalogue.py` (agrégation + lookups)
- [x] Page 3 : shortlist + fiche détaillée — critères empilables, radar, shot chart
- [x] Logo `assets/triple_threat.svg` via `st.logo`, bouton `Reverse` retiré

**Session 3 — 2026-08-17**
- [x] Boutons `Shot quality` / `Pick & roll` sur la fiche de la shortlist (`src/ui/navigation.py`)
- [x] **Tous les noms de colonnes viennent du glossaire** : `Column`/`Threshold`/`profile.Axis`
      perdent leur champ `label`, `glossary.name()` + `glossary.DERIVED_NAMES` deviennent la
      seule autorité de nommage, `glossary.family()` sert au regroupement des couvertures
- [x] Seuils de tir ramenés à **un tir par match officiel**, arrondi au cran du slider
      (`metrics.SEASON_MINIMUM` = 35)
- [x] Panneau de minimums de la shortlist **supprimé**, remplacé par un second critère d'ouverture
      (`attempts >= 35`)
- [x] Planchers par tranche énoncés sous les figures, et **pilotés par le panneau** sur les boards
- [x] Le message « too few to judge him here » dit comment le faire revenir
- [x] Fiche shortlist passée **sous le tableau**, en deux étages (Shot quality / Pick & roll),
      chaque bouton de board au-dessus de ses figures ; `Close` remplacé par un `st.expander` à clé
- [x] Bloc **couvertures défensives** (volume + PPP) sur le board pick-and-roll et la fiche
      shortlist ; `src/ui/facets.py` créé, médianes de tranche corrigées
- [x] **Demi-terrain des spots de pick** (`profile_charts.pick_court`) : deux figures fusionnées
      en une, ce qui rend la carte du board pick-and-roll lisible ; tuiles deux par rangée,
      hauteur des barres proportionnelle à leur nombre
- [x] Seuils pick par rôle (10 handler / 20 screener, sur un cran de 5), et figure des
      couvertures sans seuil mais avec le compte de picks par couverture
- [x] En-têtes des boards débarrassés de ce que leurs sélecteurs disent déjà
      (`catalogue.short`) : plus de défilement horizontal sur le board pick-and-roll
- [ ] **Piste étudiée, NON retenue** : déplier la fiche *dans* le tableau, sous la ligne du joueur.
      `st.dataframe` est un canvas (glide-data-grid) sans API de ligne de détail, et on ne peut pas
      y rendre d'élément Streamlit — un radar Plotly n'y entrera jamais. La seule voie sans
      dépendance serait de remplacer la grille par une liste de `st.expander`, ce qui coûte le tri
      par en-tête, la barre d'outils (recherche, menu de colonnes, export), et impose une
      pagination (213 lignes × ~10 colonnes de widgets = plusieurs milliers d'éléments par rerun).
      À ne rouvrir que si l'utilisateur accepte explicitement ces pertes.
- [x] Shot chart de la shortlist repeint avec **la rampe du shot menu** (`_ZONE_TONE`), encre du
      pourcentage choisie contre le remplissage (`theme.ink_on`), `DARK.zones[2]` nudgé
- [x] **`README.fr.md`** : traduction mot pour mot du README, à tenir synchronisée (§1)

**Session 4 — 2026-08-17**
- [x] **Barre de portée globale** sur les trois pages, avec `min_attempts`, mémoire inter-pages
      et ligne « 213 of 299 players are the league here »
- [x] **Un seul vivier de percentiles** = cette barre, partout (tableaux, radar, médianes)
- [x] **Seuils de couverture dérivés de la part de ligue** : de 25 uniforme à 5/1, éligibles
      doublés, Blitz et Ice passent de 0 à 45 et 67
- [x] Le critère de shortlist redevient **une seule condition** ; `OPENING` supprimé
- [x] Percentiles sur les comptages, tableaux teintés + légende, percentile des comptages sur
      les fiches, anneau médian sur le radar
- [x] `.gitignore` en liste blanche, index reconstruit (45 fichiers suivis)
- [x] `tests/test_core.py` — 66 tests verts
- [ ] Page 4 : admin & usage analytics (§7ter)
- [ ] Bonus : déploiement
- [x] `tests/test_core.py` — 62 tests verts (nommage, seuil par match, planchers, préfixes de
      board, appariement des rampes, contraste des encres)
- [x] **`README.md` réécrit au format imposé par l'énoncé** : § Setup / § Metrics and why /
      § Filtering, thresholds and normalisation / § Assumptions and limitations, puis
      § How the code is organised. Le §3 est le plus long, c'est là que porte la note.
- [x] **Second audit complet des CSV** (§4.5 et §4.6 points 8 à 12) : splits qui ne totalisent pas
      `attempts`, NaN ≠ 0 à la source, colonnes mortes chiffrées, couverture du glossaire, rosters.
      Deux affirmations de ce fichier étaient **fausses** et ont été corrigées : le max d'eFG et le
      mécanisme de `segment_medians`.
- [ ] Page 4 : admin & usage analytics (§7ter)
- [ ] Bonus : déploiement

**Décisions arrêtées** (ne pas rouvrir sans demande explicite)
- Seuil sur le dénominateur de la métrique, pas sur `games_played`
- Filtrage à deux étages population / échantillon
- ⚠️ **UN SEUL VIVIER DE PERCENTILES POUR TOUTE L'APP : la ligue de la barre de portée**
  (`thresholds.league_mask` = matchs joués + tirs tentés + transférés). Remplace la règle
  « population éligible » et les trois viviers du §7ter. Motif utilisateur : un classement qui
  bouge dès qu'un slider bouge est un chiffre qu'on ne peut pas emporter d'un écran à l'autre.
  Conséquences :
  - `ranking.add_percentiles(frame, columns, pool)` prend le vivier en paramètre ; `board.render`
    le calcule **avant** `apply_population` et la shortlist passe `league=pool` ;
  - **équipe et recherche par nom ne définissent PAS le vivier** — elles restreignent l'écran.
    Sinon un lecteur qui tape un nom serait classé contre lui-même. `league_mask` vs
    `apply_population`, test dédié ;
  - **un joueur sous le seuil de la vue GARDE son percentile.** La ligne grisée dit que
    l'échantillon est mince ; elle n'a plus à supprimer le chiffre qui le situe. §6 point 3
    (tiret dans la colonne de rang) est **annulé** ;
  - le radar aussi : `profile.radar_scores` note tout le monde contre le vivier.
    `Axis.minimum` ne sert plus qu'à décider si **LUI** est placé (trou), pas à tailler un
    sous-vivier par axe ;
  - les **médianes de tranche** (`segment_medians`) se calculent sur ce même vivier, en plus du
    filtre par `min_count` de la tranche. Les deux conditions tiennent.
- Pas de shrinkage dans la version principale
- Sliders de seuils de 0 au max observé, dans un expander fermé par défaut
- **La barre de portée est GLOBALE et présente sur les TROIS pages** (`filters.scope_row`),
  y compris la shortlist. Annule la décision « la shortlist n'a PAS de barre de portée ».
  Elle porte **équipe / matchs minimum / tirs minimum / recherche / transférés**, et
  `PopulationFilter.min_attempts` (défaut `SEASON_MINIMUM` = 35) est un champ à part entière.
  - **Ses réponses survivent au changement de page** : Streamlit détruit l'état d'un widget non
    rendu au run précédent, donc le choix est mémorisé hors widget (`filters._STORE`, un dict)
    et les widgets sont semés depuis lui. Sans ça, passer de la shortlist à un board remettait
    15 matchs en silence.
  - **Une ligne sous la barre dit ce qu'elle coûte** (`filters.scope_reading`) : « 213 of 299
    players are the league here ». Un lecteur à qui on montre 213 noms ne peut pas savoir si le
    fichier en contient 220 ou 500.
  - **`load_pick_profiles` embarque `attempts`** (jointure depuis le fichier tir) : la barre est
    globale, donc chaque page doit pouvoir répondre à ses deux questions. Les 4 joueurs
    présents seulement dans picks tombent hors d'une portée qui demande des tirs, ce qui est
    correct — ils n'ont aucun événement de tir.
- **Les seuils de split sont DÉRIVÉS de la part de ligue** (`pick_views.split_minimum` +
  `LEAGUE_SHARE`) : `barre du rôle × part de la couverture`, arrondie **vers le bas** au cran du
  slider, plancher 1. Remplace `COMMON_MINIMUM = 25` / `RARE_MINIMUM = 3`, supprimés.
  Motif : 25 par couverture exigeait bien plus d'un split que le board n'exige du tout (handler
  mesuré à 10 picks, mais 25 exigés vs une seule couverture) → 97 éligibles vs Over, 54 vs
  Under, **0 vs Blitz et vs Ice**. Résultat : handler Over 5, tout le reste 1 ; screener Show 5,
  Soft 5, reste 1. Éligibles sur les 213 : Over 122, Under 143, Switch 147, Ice 67, Blitz 45.
  Les `LEAGUE_SHARE` sont **remesurées par un test** sur les CSV. Les spots de terrain suivent
  la même règle. ⚠️ Les parts sont identiques pour les deux rôles, et c'est normal : un écran
  switché est un événement, compté une fois de chaque côté.
- **Un critère de shortlist est UNE condition, la valeur.** Annule « un critère filtre sur DEUX
  conditions ». `Criterion.minimum`, `shortlist.default_minimum`, `FALLBACK_MINIMUM` et
  `criteria._minimum_input` sont **supprimés**. Motif utilisateur, littéral : demander 40 % à
  trois points exigeait en silence 40 tentatives, donc un nom pouvait manquer pour une raison
  illisible à l'écran. Ce qui protège l'échantillon est désormais la barre de portée, visible.
  `shortlist.OPENING` disparaît aussi : la page s'ouvre sur **une rangée vide**
  (`criteria._OPENING_ROWS = 1`), le périmètre étant au-dessus.
- **Les comptages DEVIENNENT des percentiles en mode percentile** (tirs, trois points, picks,
  matchs joués). Annule « les colonnes de comptage restent des comptages ». Le tableau s'ouvre
  sur les valeurs, la bascule est à un clic, donc rien n'est perdu ; et « 615 picks » ne veut
  rien dire tant que ce n'est pas « 96ᵉ percentile ».
- **Le mode percentile est TEINTÉ** (`tables.tint_percentiles`, `theme.percentile_tint`) : un
  seul bleu dont l'alpha suit le classement, plus une légende en cinq crans
  (`tables.percentile_key`), sur les deux tableaux. **Jamais de rouge-vert** — ça se lirait
  comme bon-mauvais, et une part élevée de tirs contestés n'est pas une vertu. Ordre de peinture
  dans `tables.style` : colonne triée → teinte de percentile → ligne du joueur chargé (une
  teinte qui porte une valeur bat un indice d'ordre, et le joueur à l'écran bat les deux).
- **Les comptages de la fiche portent leur percentile** : tuiles du board (`panel._headline`,
  « 615 events (96th) ») et fiche shortlist (`detail._role` via `profile.standing`).
- **Le radar porte un anneau pointillé au 50ᵉ percentile** (`profile_charts.MEDIAN_RING`) :
  une forme sur une toile ne dit rien sans une ligne de lecture.
- **`.gitignore` en liste blanche** : tout est exclu (`*`), seuls le code source, `requirements.txt`,
  `README.md`, `assets/*.svg`, `.streamlit/config.toml` et `data/*.csv` sont réadmis. ⚠️ Les
  motifs de dossier sont **ancrés** (`/logs/`) : écrit `data/`, le motif mordrait aussi
  `src/data/`, qui est du code. Les CSV **restent versionnés** — l'énoncé exige que
  `pip install` puis `streamlit run app.py` marche sur un clone neuf. Sont exclus : `main.py`
  (reliquat vide), `CLAUDE.md`, `README.fr.md`, `*.docx`, `__pycache__`.
- **Un seul slider par vue.** Le seuil pilote la métrique principale de la vue ; les colonnes de
  contexte portent un plancher fixe (`Column.min_sample`) et se blanchissent seules. Multiplier les
  sliders alourdit l'interface sans rien protéger de plus.
- **L'efficacité contestée est ventilée par type de tir** (All / 2PT / 3PT). L'eFG contesté brut
  corrèle à +0,17 avec la part de tirs au cercle (biais intérieurs) ; l'écart contesté − ouvert
  corrèle à −0,37, donc **pire** — piste écartée. Le 3PT% contesté corrèle à −0,10 : c'est la
  lecture propre.
- **`avg_shot_distance` converti pieds → mètres** (§4.5).
- Tableau limité à ~5 colonnes de valeurs ; la profondeur va dans la fiche joueur.
- Une phrase en langage courant sur chaque fiche joueur (`View.summary`), générée à partir des
  colonnes — c'est le principal levier anti-jargon.
- **Un seul tableau**, non-éligibles grisés et maintenus en bas **quel que soit le tri**. Deux
  tableaux séparés : refusé. Un menu déroulant `Sort by` : refusé. Le tri se fait en cliquant sur
  les en-têtes.
  Mécanisme : `selection_mode=["single-row", "single-column"]` sur `st.dataframe`. La doc Streamlit
  est explicite — « *When column selections are enabled, column sorting is disabled* » — donc le
  clic sur en-tête remonte comme un **événement** au lieu de réordonner la grille dans notre dos.
  `src/ui/sorting.py` traduit ce clic en colonne de tri, `ranking.two_tier_sort` applique l'ordre.
  Le magasin de dernier clic est indexé par la clé du tableau, sinon un re-clic sur le même en-tête
  ne serait pas vu comme un nouveau clic et l'inversion serait impossible. Bouton `Reverse` en
  garantie si la grille ne désélectionne pas au second clic.
  **Marquage de la colonne triée** : flèche ▼ / ▲ ajoutée au libellé via `column_config`, et teinte
  bleue des cellules posée par le `Styler` (`theme.Palette.highlight`). Ne PAS utiliser
  `selection_default` pour re-sélectionner la colonne : cet écho serait relu comme un clic au run
  suivant et inverserait le tri tout seul. Le libellé renvoyé par la grille contient la flèche, il
  est nettoyé par `sorting.plain_label` avant d'être remonté à sa colonne.
  **Hiérarchie des teintes** : `highlight` (colonne triée) est un indice, `selected` (joueur chargé)
  est le sujet — garder un rapport d'environ 1 à 5 entre les deux alphas, sinon la colonne mange la
  sélection.
  **Aucune colonne triée à l'arrivée** : `sorting.chosen()` renvoie `None` tant que le lecteur n'a
  rien cliqué, `sorting.order_by()` retombe sur la métrique de la vue pour l'ordre réel. Ni flèche
  ni teinte tant que rien n'est choisi.
- **Pas de classement (`#`) dans les tableaux** — retiré à la demande de l'utilisateur, remplacé par
  les percentiles.
- **Les percentiles sont calculés à chaque run, jamais lus dans un CSV précalculé.** Ils portent sur
  la population **éligible**, qui dépend des filtres et du seuil : un fichier figé serait faux dès
  que le lecteur bouge un slider, et écrire dans `data/` est interdit. `rank(pct=True)` sur 300
  lignes coûte des microsecondes.
- **Trier par percentile ou par valeur brute donne le MÊME ordre** — un percentile est la valeur
  brute réexprimée contre le même échantillon. Le sélecteur `Values / Percentiles` change donc
  l'affichage, pas l'ordre. Ne pas proposer deux tris distincts, ce serait un faux choix.
- **Les colonnes de comptage restent des comptages en mode percentile.** La taille d'échantillon est
  la garantie du lecteur contre le bruit ; la remplacer par un rang retire exactement l'information
  que le seuil sert à exposer. Critère : `fmt == INT` → jamais converti.
- **« Percentile » est le seul terme statistique toléré à l'écran**, par exception explicite à la
  règle du §8 : c'est le vocabulaire courant du scouting basket (Synergy, InStat, Cerebro l'affichent
  tel quel). Affiché en ordinal (`86th of 174`), jamais « percentile rank ».
- **`% from mid-range` = somme des deux zones mid-range, PAS `100 − rim − 3pts`.** Les quatre zones
  ne totalisent que ~97 % des tirs (min 91 %) : la soustraction gonflerait le mid-range de 3 à 9
  points. Test dédié.
- **Un seul tableau, joueur chargé épinglé sur la première ligne** (`ranking.pin_first`).
  Deux approches ont été essayées puis **refusées par l'utilisateur** — ne pas les reproposer :
  une seconde table d'une ligne au-dessus (impression de doublon), et le défilement automatique par
  `st.iframe` + DOM (`st.dataframe` n'a pas d'API de scroll, la grille est un canvas).
  L'épinglage est un signet, pas un classement : le tableau ne porte plus de colonne de rang, donc
  la première ligne dit « celui que tu regardes », pas « le meilleur ». La ligne reste grisée si le
  joueur est sous le seuil.
  **La clé du tableau contient le joueur épinglé** : il occupe la ligne 0, donc tous les index en
  dessous glissent quand il change, et un clic mémorisé pointerait sur son voisin. Pour la même
  raison `selection.sync` reçoit l'ordre **reconstruit** du rendu précédent
  (`pin_first(visible, previous)`), pas l'ordre courant.
- **`src/ui/board.py` contient le corps de page complet.** Une page = un titre + un appel à
  `board.render(frames, lenses, caption)`. Ne jamais recopier la logique d'orchestration dans une
  page : c'est ce qui garantit la charte graphique identique partout (§7bis).
- **La fiche de la shortlist est SOUS le tableau, en DEUX étages de deux colonnes**, chacun
  surmonté du bouton de SON board :
  - étage 1 **Shot quality** : radar | (shot chart puis shot menu, superposés) ;
  - étage 2 **Pick & roll** : Ball Handler | Screener, chaque colonne portant le terrain des
    spots ET le bloc couvertures de CE rôle.
  Le radar voyage avec le tir bien que la moitié de ses branches soit pick-and-roll : il se lit
  comme un profil, et lui donner un étage à lui seul faisait une carte à trois niveaux pour une
  figure. Une colonne par rôle plutôt qu'un seul rôle principal : les deux rôles n'affrontent pas
  les mêmes couvertures, donc n'en montrer qu'un obligerait à jeter l'autre jeu de cinq.
  La fiche dit *ce qu'est* un joueur, un board dit *où il se
  situe* : un bouton se lit comme la suite des figures qu'il surmonte, pas comme une rangée
  d'actions en haut de carte n'appartenant à rien. **Rien n'est transmis** — `selection.SELECTED`
  est du `session_state`, donc global à l'app : le joueur est déjà chargé quand le board s'ouvre
  (vérifié par `AppTest` sur `app.py`, pas sur la page seule — `st.switch_page` résout ses chemins
  par rapport au script principal, donc lancer la page directement échoue alors que l'app
  fonctionne). Les chemins de pages vivent dans `src/ui/navigation.py` et `app.py` les lit de là.
- **La fiche de la shortlist est un `st.expander`, sans bouton `Close`.** Replier remplace fermer ;
  rien n'est déchargé, donc la ligne reste marquée dans le tableau. La `key` de l'expander
  **contient le nom du joueur** : l'état plié/déplié est mémorisé par widget, donc sous une clé
  partagée un lecteur qui l'aurait replié cliquerait un autre joueur et ne verrait rien se passer.
  Clé par joueur = nouveau widget = rouvert. `st.expander` n'accepte `key` que depuis Streamlit
  1.61 ; sans elle, ce comportement serait impossible à obtenir.
  ⚠️ Conséquence : **la shortlist n'a plus de désélection**. Les boards gardent leur bouton
  `Clear` (`panel.card`) ; ici on replie. Décision de l'utilisateur.
- **`Lens.dataset` dit quel fichier charger**, `Lens.profile` décrit les deux figures de la fiche
  joueur (`breakdown` = répartition sans seuil, `comparison` = valeur par tranche avec seuil propre),
  `Lens.view_label` nomme le sélecteur de sous-vue (« Shot type », « Coverage »).
- **Les noms de colonnes picks sont construits, pas listés** : `schema.pick_column(role, metric,
  coverage=..., spot=...)`. 599 colonnes ne se tapent pas à la main. Idem pour `DENOMINATORS` côté
  picks, généré par `metrics._pick_denominators()`.
- **Une métrique filtrable porte ses splits, elle ne se répète pas** (`Filterable.variants`).
  41 entrées au lieu de 96 : le sélecteur liste l'idée (« Ball Handler - Points Per Pick »), la
  couverture se choisit juste à côté (`Lens.view_label` → « Coverage » / « Shot type »).
  **Le regroupement se fait sur `glossary.family(key)`** — le `display_name` privé de son suffixe
  `(vs …)` — et non sur un libellé écrit à la main. Le glossaire écrit lui-même la couverture dans
  le nom (`Ball Handler - Points Per Pick (vs Over)`), donc c'est la donnée qui dit ce qui est une
  variante de quoi. La regex est ancrée en fin de chaîne et gourmande, pour que `(vs Soft (Drop))`
  parte d'un bloc. Historique du bug : les libellés manuels étant identiques d'une couverture à
  l'autre, un titre construit sur groupe + libellé désignait **6 colonnes** et le sélecteur en
  gardait silencieusement une, la dernière (Ice). Trois tests verrouillent ça.
- **`Filterable.title` est le nom du glossaire seul**, sans préfixe de lentille : le nom porte déjà
  le rôle et le split (`Ball Handler - …`, `Three-Point Zone - …`), et « Shot distance · % from
  three » était justement le libellé jugé illisible. Le groupe ne sert plus qu'à trier (totaux de
  saison en tête, puis alphabétique **insensible à la casse**, sinon `eFG%` tombe derrière toutes
  les majuscules) et à désambiguïser un en-tête si deux colonnes venaient à partager un nom
  (`columns._header`, garde-fou verrouillé par `test_filterable_titles_are_unique`).
- **Le tableau shortlist contient TOUTES les métriques**, `column_order` décide seulement de
  celles ouvertes à l'écran. Le menu de visibilité de colonnes de Streamlit (barre d'outils du
  tableau, en haut à droite) permet alors d'en rappeler n'importe laquelle — le choix des colonnes
  se fait donc sur le tableau lui-même, pas dans un widget à part. L'export CSV emporte tout.
  Doc Streamlit : « *Columns omitted from column_order are hidden by default but can still be shown
  by the user via the column visibility menu in the table toolbar.* »
- **Infobulles du glossaire sur toutes les colonnes du tableau shortlist**, y compris celles que le
  lecteur rappelle lui-même : `results._column_config` couvre tout le catalogue, pas seulement les
  colonnes ouvertes.
- **La shortlist n'a PLUS d'expander « Minimum shots behind each number ».** Supprimé
  (`results.minimums` et `columns.denominators()` n'existent plus) : un board gate **une** métrique
  à la fois, donc son panneau a un sens ; la shortlist les montre toutes, et une seconde batterie
  de sliders à côté de critères qui portent **déjà** leur compteur était un minimum que personne
  n'avait demandé, posé à côté de ceux que le lecteur a écrits. Ce qui protège un chiffre ici est
  la barre visible. Historique : le panneau avait été taillé de 24 à 11 puis à 7 sliders — le fait
  qu'il faille trois passes pour décider lesquels garder disait déjà qu'il n'avait pas sa place.
  **Les planchers des boards, eux, restent** (`columns._baseline_floors` : Open 3PT% blanchi sous
  10 tirs ouverts). Ils ne sont pas à cette page de les fixer, et sans eux la shortlist serait le
  seul endroit où un chiffre mince passe. Test dédié.
- **Grisé ou blanchi : les deux existent et ne disent pas la même chose.** Ligne **grisée**
  (`theme.Palette.muted`, `tables.style`) = « ce joueur n'est pas mesuré sur la métrique dont parle
  cette vue » — il garde ses valeurs, son percentile passe au tiret. Cellule **blanchie**
  (`fmt.BLANK`, `tables.build` et `columns._gate`) = « ce chiffre précis n'a pas l'échantillon ».
  La shortlist n'a **pas** de métrique de tête, donc pas d'éligibilité de ligne : tous ses seuils
  sont par cellule, donc blanchis — même langage que les colonnes de contexte des boards. Griser
  la cellule serait un troisième signal, et exposerait un nombre bruité que le lecteur comparerait
  quand même (aux défauts : 132 joueurs sur 220 sous 50 picks en screener). Le blanc les exclut
  aussi du vivier des percentiles, comme l'exige §6 point 4.
- **La shortlist s'ouvre sur DEUX critères : `games_played >= 15` et `attempts >= 34`**
  (`shortlist.OPENING`, tuple, aligné sur `thresholds.DEFAULT_MIN_GAMES` et
  `metrics.SEASON_MINIMUM`). Le premier est le périmètre de la barre de portée des boards, le
  second le plancher de tir que les boards appliquent — la page n'ayant plus de panneau de
  minimums, c'est **la seule** protection d'échantillon, donc elle doit être visible. Le lecteur
  peut monter, baisser ou retirer chacune. 213 joueurs sur 299 à l'ouverture.
  Conséquences : `criteria._STORE` démarre à `len(OPENING)` (donc 2 rangées), `_opening_index` et
  `_opening(index)` distribuent les barres semées rangée par rangée. Tests dédiés : le critère
  matchs retient exactement la même population que `apply_population` par défaut, et le critère
  tirs mord par-dessus.
- **Le mode d'ouverture d'un critère suit la nature de la métrique** (`criteria._mode_index`) :
  `Percentile` pour un taux (« les 20 % meilleurs » est la question du scout), `Value` pour un
  comptage — personne ne demande un joueur dans le top 20 % des matchs joués.
- ~~**Les comptages nus sont renommés en clair**~~ — **annulé.** Décision remplacée par la règle
  « aucun libellé écrit à la main » (§7) : le glossaire dit « Attempts » et « Made », et c'est ce
  qui s'affiche. Le nom nu n'est plus ambigu puisque tous ses voisins portent leur split.
- **Bascule valeurs / percentiles sur la shortlist aussi**, comme sur les boards. ⚠️ Les percentiles
  se mesurent sur la **LIGUE ENTIÈRE** (`columns.build(..., league=players)`), jamais sur la
  shortlist : sinon une shortlist de shooteurs afficherait son moins bon en 1ᵉʳ percentile. Bug
  corrigé, ne pas réintroduire. Les comptages restent des comptages.
- **Le catalogue de colonnes est de la configuration : `@cache` dessus**, pas de `st.cache_data`.
  `catalogue_columns()` coûtait 12 ms par rerun alors qu'il ne dépend d'aucune donnée. Après
  mémoïsation le rendu du tableau passe de 36 à 13 ms (valeurs) et de 79 à 47 ms (percentiles).
  Ne pas cacher `build()` lui-même : il dépend des sliders, et hacher un DataFrame de 300×825
  coûterait plus cher que le calcul.
- **Le shot chart porte la MÊME rampe que le shot menu** (`profile_charts._ZONE_TONE`). Les deux
  figures sont empilées sur la même colonne de la fiche shortlist et toutes deux ordonnées en
  s'éloignant du cercle : une distance ne peut donc pas changer de couleur de l'une à l'autre. Le
  ton d'une zone est son **rang dans `schema.NBA_ZONES`**, jamais une couleur écrite à la main —
  cercle le plus clair, trois points le plus sombre, dans les deux figures. Les conventions
  diffèrent (4 zones SkillCorner en bas, 5 zones NBA en haut) mais s'alignent : le trois points du
  menu se scinde en corner et above-the-break, et c'est **exactement à ça que sert le 5ᵉ ton ajouté
  au bout sombre**. Le gris `muted` sous le seuil est conservé — c'est la seule chose que la
  couleur dit encore ici. `opacity` du marqueur passé de 0.85 à 1 : un ton adouci n'est plus le ton
  que le menu imprime pour cette zone.
  - **Le texte posé SUR une marque se lit contre la marque, pas contre la page** :
    `theme.ink_on(fill)` renvoie le noir ou le blanc qui contraste le mieux avec le remplissage
    (luminance relative WCAG). Une seule encre pour tout le nuancier laisserait le pourcentage
    illisible à l'une des deux extrémités de la rampe.
  - **Un ton du thème sombre a été déplacé pour ça** : `DARK.zones[2]` passe de `#2a78d6` à
    `#2570cc`. L'ancien tombait dans la bande étroite de luminance où **ni** le noir **ni** le blanc
    n'atteint 4,5:1 (4,46 et 4,32). Un test tient les 10 tons des deux rampes à cette barre.
- **Le marqueur corner 3 du shot chart est posé HORS du terrain** (`x = -4.5`), relié par un trait.
  Le couloir de corner fait trois pieds de large : aucun marqueur lisible n'y tient. Posé à x=6 il
  débordait de la ligne de touche **et se lisait comme un tir de mid-range**.
- **« What the defence does about it » : une barre 100 % + des barres de PPP, par couverture.**
  `metrics.Facet` (paire figure-répartition / figure-valeur, autonome) accroché en option à
  `Profile.coverage` ; construit par `pick_views._coverage_facet(role)`, rendu par
  `ui/facets.coverage_block`, affiché sur le board pick-and-roll ET sur la fiche shortlist. Motif :
  le board se parcourt déjà couverture par couverture, mais c'est six clics pour comparer six
  chiffres, et surtout ça ne dit pas **ce qu'il affronte le plus**. Les deux questions se lisent
  ensemble ou pas du tout — un bon PPP contre le blitz ne vaut rien s'il le voit deux fois.
  - **Les parts par couverture sont DÉRIVÉES** (`schema.coverage_share`, `aggregate`) : le fichier
    livre `pick_rate_at_{spot}` mais rien par couverture. Les cinq couvertures couvrent bien la
    totalité des picks (minimum observé 98 %), ce qui justifie la barre 100 % — test dédié.
  - **Ce facet garde SES propres seuils** et ne suit pas le panneau, contrairement aux tranches de
    `Profile.comparison` : il compte les picks contre UNE couverture, pas ceux sur lesquels la vue
    est bâtie. Demander 50 picks vs Blitz viderait la figure pour toute la ligue. Seuils = ceux de
    la vue correspondante (`_coverage_minimum` : 3 si rare, 25 sinon), et `facets._floors` énonce
    les deux chiffres.
  - `Palette.zones` passe à **5 tons**, le cinquième ajouté **au bout sombre** : zones de tir (4) et
    court spots (3) prennent les premiers, donc rien de déjà dessiné ne change de couleur.
  - Les barres de PPP sont peintes avec **la même rampe dans le même ordre** que la barre empilée
    (`charts.comparison_bars(..., ramp=True)`), donc les teintes appairent les deux figures. Entre
    les deux, la **légende porte le nombre de picks par couverture** — comme le shot menu sous sa
    propre barre. Elle avait été retirée pour compacter : c'était une erreur, ce compte est
    précisément ce qui permet de se passer de seuil.
  - **`COVERAGE_MINIMUM = 1` : cette figure ne cache RIEN.** Seule exception à la règle du seuil,
    et elle se justifie : c'est une **fiche**, pas un classement — personne n'y est placé contre
    personne, et le compte est écrit à côté de chaque tranche, donc le lecteur juge l'échantillon
    lui-même. À 25 (la barre des boards de couverture) **aucun joueur de la ligue** n'avait de
    chiffre contre le blitz ni contre l'ice : ça se lit comme une donnée manquante, pas comme une
    couverture rare. Le plancher de 1 sert seulement à ne pas imprimer un PPP sur zéro pick.
    Test dédié.
- **Les spots de picks se lisent sur un DEMI-TERRAIN, pas en deux figures**
  (`profile_charts.pick_court`, `core.profile.spot_returns`, `facets.spots_block`). Remplissage =
  part de ses picks à ce spot (échelle relative à SON spot le plus chargé, sinon trois zones qui se
  partagent un joueur n'atteignent jamais le haut d'une rampe 0-100), chiffre écrit dessus = PPP,
  zone grise et chiffre retiré sous le seuil. Motif : « où il pose ses écrans » et « ce que chaque
  spot rapporte » sont **une** question posée deux fois, et la poser deux fois est l'essentiel de
  ce qui rendait la carte du board pick-and-roll illisible sans scroller.
  Ailes et step-ups sont dessinés **des deux côtés avec le même chiffre** (un seul chiffre dans les
  données) : n'en colorier qu'un se lirait comme un joueur qui ne pose jamais d'écran à gauche. Dit
  en légende, comme le corner 3 du shot chart.
  Piloté par `Profile.on_court` : le board tir garde ses deux figures (ses zones ont déjà leur
  propre shot chart, bâti sur les colonnes NBA). Deux tests verrouillent l'alignement
  `breakdown`/`comparison` et le fait que chaque `COURT_SPOT` a bien une boîte sur le plan.
- **Budget vertical de la carte du board** (le lecteur doit pouvoir lire sans scroller) :
  `comparison_bars` a désormais une **hauteur fonction du nombre de barres** (`40 + 32 n`) — cinq
  couvertures dans une boîte taillée pour trois étaient illisibles — et `panel._headline` dispose
  les tuiles **deux par rangée** au lieu de quatre de front : les noms du glossaire sont longs et
  la carte est le côté étroit du board, `Ball Handler - Assist Opportunity Rate` sur un quart de
  colonne se repliait sur cinq lignes.
- **La médiane d'une tranche se calcule sur les joueurs QUI ONT la tranche** (`segment_medians`).
  Bug corrigé. ⚠️ **Le mécanisme n'est PAS celui écrit initialement** (« un joueur sans pick porte
  0,00 ») : vérifié sur les CSV, une tranche jamais jouée porte **NaN**, pas 0 — 72 joueurs sans
  pick handler, 243 sans pick vs blitz, tous en NaN — et `league_median` les écarte déjà par
  `dropna()`. Ce qui tire la médiane vers le bas, ce sont les **petits échantillons réels** :
  un joueur avec deux step-ups qui n'a rien marqué porte un vrai 0,00. Chiffres :
  `screener_ppp_at_stepUp` médiane **0,09** sur tout le fichier contre **0,32** parmi ceux qui ont
  25 picks à ce spot ; `screener_ppp_at_wing` 0,15 contre 0,27. Même règle que pour les percentiles
  (§6 point 4), appliquée à la ligne de référence. Test dédié.
- **`src/ui/facets.py` porte ce que les DEUX fiches dessinent** (légende de barre empilée, bloc
  couverture). `panel._legend` et `detail._legend` étaient déjà deux copies divergentes de la même
  fonction (marges 12 vs 14 px) — c'est le signe qu'il fallait un module, pas une troisième copie.
- **Le radar n'a pas de tableau sous lui** : l'infobulle porte la valeur brute et le percentile, et
  les sommets sont **nommés comme les colonnes des tableaux** — c'est-à-dire par le glossaire
  (`eFG%`, `Ball Handler - Points Per Pick`, pas « Efficiency » ni « Pick production ») pour que le
  lecteur n'ait aucune traduction à faire. Les noms ne sont **jamais raccourcis** ; ils sont
  seulement **repliés** sur plusieurs lignes (`profile_charts._wrapped`, coupure d'abord sur le
  ` - ` du glossaire puis entre mots à 18 caractères), et le nom entier passe par `customdata`
  pour que l'infobulle le montre d'un bloc. Marges et hauteur du polaire élargies en conséquence.
- **Une colonne appartient à la première lentille qui l'affiche** (`shortlist.options`). La part de
  tirs au cercle est imprimée par trois boards et reste un fait de distance : elle est rangée sous
  « Shot distance ».
- **Les totaux de saison ne relèvent d'aucune lentille** : groupe **« Season totals »**
  (`shortlist.GENERAL_GROUP` / `_SEASON_TOTALS`), revendiqué **avant** les lentilles dans
  `options()`. Il contient `games_played`, `attempts`, `two_attempts`, `three_attempts` — des faits
  de volume et de présence, de même nature que les matchs joués, pas des réponses à la question que
  pose un board. Rangés sous « Shot distance » ou « Shot contestation », ils étaient cherchés là où
  personne ne les cherche. Aucun dénominateur : un total est un total (§5.3). Le groupe **ouvre le
  sélecteur de critères** (tri dans `criteria.builder`), le reste suit par ordre alphabétique.
  Conséquences verrouillées par tests :
  - `columns.catalogue_columns()` démarre son `seen` avec `_IDENTITY` — le tableau porte déjà
    `Games Played` à côté du nom, l'émettre à nouveau doublerait la colonne ;
  - `columns._plain_names()` **a été supprimé** : il renommait « Attempts » en « Field goal
    attempts » parce que le nom nu ne disait rien à côté d'une douzaine d'autres comptages. Ce
    n'est plus vrai — tous les autres portent désormais leur split du glossaire (`Contested -
    Attempts`, `3PT Attempts`, `Ball Handler - Picks`), donc le nom nu **est** celui de la saison
    entière. `columns.count_name` = `glossary.name`, un seul chemin ;
  - `opening_columns` retombe sur `_DEFAULTS` quand les critères n'ouvrent aucune colonne de
    métrique — une shortlist bâtie sur les seuls matchs joués s'ouvrirait sinon sur trois colonnes
    d'identité et rien à lire ;
  - la ligne de lecture d'un critère sans dénominateur dit « of the 299 players », **sans** « with
    enough events » : promettre un seuil d'échantillon là où il n'y en a pas serait faux.
  Les totaux de picks (`{role}_total_picks`) **restent dans leur lentille** : ce sont des faits de
  rôle, et ils portent déjà leurs variantes de couverture.
- **La shortlist n'a PAS de barre de portée** (§7bis point 3 : exception explicite, les boards la
  gardent). Tout ce qui restreint la ligue y est un critère, matchs joués compris. Deux raisons :
  les boards servent à regarder une population, la shortlist à en construire une ; et le percentile
  écrit sous chaque barre est mesuré sur la **ligue entière** — un filtre de portée par-dessus
  laisserait cette ligne décrire une liste que personne ne voit. Conséquence assumée : l'équipe et
  le toggle « transférés » disparaissent de cette page (aucun agrégat par équipe ici, donc §4.6
  point 3 ne s'applique pas), et la recherche par nom passe par la **barre d'outils de
  `st.dataframe`**, qui embarque son propre champ de recherche. Ne pas réintroduire `scope_row`
  sur cette page.
- **Le mode par défaut d'un critère est `Percentile`** : « les 20 % meilleurs » est la question avec
  laquelle un scout arrive, la valeur exacte est ce qu'il ajuste ensuite. **Sauf pour un comptage**,
  qui s'ouvre en `Value` (voir plus bas).
- **Une barre de critère se règle en valeur OU en percentile**, et la ligne sous la rangée énonce
  toujours les deux (« 39.5% — 80th percentile, keeping the top 20% of the 125 players with enough
  events »). Les pourcentages se saisissent **en pourcentage** (34.2, pas 0.342) et la case s'ouvre
  sur la **médiane du vivier**, jamais sur 0. Le percentile est calculé sur le vivier que le critère
  filtre réellement — changer le minimum d'événements change donc le percentile affiché, ce qui est
  le comportement voulu.
- **Un critère de shortlist filtre sur DEUX conditions** : la valeur ET le nombre d'événements
  derrière elle (`shortlist.mask`). Le minimum par défaut vient du seuil de la vue qui gate déjà ce
  dénominateur (`shortlist.default_minimum`) — une seule réponse à « combien suffit » dans toute
  l'app. Test dédié : le même seuil de 40 % passe de N joueurs à beaucoup moins quand on exige
  40 tirs.
- **Le radar utilise un percentile PAR AXE, calculé dans la population propre à cet axe**
  (`ranking.percentile_series`). Un axe fondé sur les tirs contestés ne doit pas être mis à
  l'échelle par des joueurs qui n'en prennent presque pas. Un joueur sous le minimum d'un axe n'y
  est **pas placé** (trou), jamais placé à zéro — ce serait lui prêter une faiblesse non observée.
  Les deux derniers axes suivent le rôle du joueur (`PRIMARY_ROLE`).
- **Le shot chart utilise les zones NBA** (`schema.NBA_ZONES`) : seule convention qui sépare corner
  et above-break. Aucune colonne de pourcentage n'existe pour elles → `shortlist.zone_accuracy`
  calcule `mades / attempts` avec `safe_ratio`, NaN et non zéro quand rien n'a été tenté. Les corner
  threes sont un seul chiffre pour les deux corners, dit en clair sur la légende.
- **Tout plancher par tranche est ÉNONCÉ sous sa figure, franchi ou non.** `panel._thin_segments`
  (« Measured from 35 shots upwards, as set above. Too few, so nothing is shown for: … ») et la
  légende du shot chart de `detail.py`. Une barre grise ou une case vide ne dit pas au lecteur si
  le chiffre est absent ou nul : il faut lui donner le nombre, et pas seulement quand le joueur
  échoue — sinon le seuil n'est connaissable que par accident. `detail.ZONE_MINIMUM` **dérive** de
  `schema.ZONE_MIN_ATTEMPTS`.
- **Sur les BOARDS, le plancher des figures par tranche est celui du panneau, pas le sien.**
  `panel.card(..., minimum)` → `_profile` remplace le `Segment.min_count` de toutes les tranches
  par `max(minimum, 1)` (`dataclasses.replace`, le `Profile` du catalogue n'est jamais muté).
  Motif : le panneau demandait 35 tirs pendant que la figure en demandait 20 sans le dire — deux
  nombres sur un écran, et aucun moyen de savoir lequel s'applique. Le lecteur en choisit **un**,
  c'est celui-là. Le plancher `1` évite d'imprimer un pourcentage sur une zone jamais tentée.
  Conséquence assumée : sur une couverture rare (Blitz, défaut 3), le PPP par zone de terrain se
  lit à partir de 3 picks — plus permissif que les 25 d'avant, mais c'est la barre que le lecteur a
  posée et la légende l'énonce. La **shortlist** garde `ZONE_MIN_ATTEMPTS` fixe : elle n'a pas de
  panneau de minimums à suivre (§ shortlist).
- **Un joueur écarté par le seuil apprend comment revenir.** `panel.card` ne dit plus seulement
  « too few to judge him here » : il nomme le panneau (`filters.minimum_title(view)`) et dit de le
  baisser. Sans ça le lecteur croit que l'app a tranché contre le joueur alors que c'est sa propre
  barre. **Sauf s'il n'a aucun événement** : là, baisser le seuil ne le ramène pas, et le promettre
  serait faux — la phrase reste « nothing to judge here ».
  `filters.minimum_title` / `events_word` déduisent « shots » ou « picks » de `threshold.key`, donc
  le board pick-and-roll ne réclame plus un minimum de *tirs*.
- **`tables.layout(view)` est la seule source de la composition du tableau** — `build`,
  `column_config` et `sort_targets` en dérivent tous. Elle déduplique : une colonne de comptage déjà
  affichée pour elle-même n'est pas réaffichée comme taille d'échantillon d'un taux qui en dépend
  (`attempts` était sorti deux fois, en `Shots` et en `shots`). Deux tests verrouillent ça : aucun
  doublon de colonne ni d'en-tête, et tout taux affiché a son comptage présent dans la ligne.
- **Sélection du joueur centralisée dans `src/ui/selection.py`.** Trois règles, chacune corrige un
  bug constaté :
  1. **Les entrées sont lues dans `st.session_state` AVANT tout rendu** (`selection.sync`). Lire
     l'événement après avoir dessiné le graphique le laisse un rendu en retard : le clic charge la
     fiche mais le point n'apparaît sélectionné qu'au clic suivant.
  2. **Une entrée n'est adoptée que si sa propre valeur a changé**, sinon le nuage rejoue son
     dernier clic par-dessus celui du tableau.
  3. **La trace « Selected » porte un `customdata`.** Sans lui, cliquer sur le marqueur noir renvoie
     un point sans identité, interprété comme un clic dans le vide → la fiche disparaissait.
  4. **Une entrée qui ne renvoie rien ne désélectionne jamais.** Streamlit détruit l'état d'un widget
     non rendu au run précédent : un graphique qui revient sous une clé déjà utilisée (le lecteur
     revient à un réglage de filtre déjà visité) renvoie exactement le même « rien » qu'un widget
     jamais touché. Les deux cas sont indistinguables, donc le clic dans le vide ne désélectionne
     plus — la désélection passe par le bouton `Clear` de la fiche, et par lui seul.
  Corollaire : **changer un filtre ne désélectionne jamais le joueur.** S'il sort du périmètre, la
  fiche cède la place à un message qui le nomme, et il revient dès que les filtres le laissent
  passer. Vérifié sur matchs minimum, slider de seuil, équipe, recherche, transférés et changement
  de vue.
  Le compteur `_table_sync` n'est incrémenté que quand la sélection vient d'ailleurs que du tableau :
  la clé du tableau change alors, ce qui permet à `selection_default` de rejouer la sélection native
  (donc la vraie coche et le vrai surlignage). Un clic dans le tableau ne change pas la clé, donc ne
  réinitialise pas le défilement.
- **Le tableau sélectionne des CELLULES, pas des lignes** (`["single-cell", "single-column"]`).
  Le mode `single-row` impose une colonne de cases à cocher ; en mode cellule, cliquer n'importe où
  sur une ligne charge le joueur. Conséquence : le surlignage de la ligne est peint par nous dans le
  `Styler` (`theme.Palette.selected`), pas par la grille. La ligne est appliquée **après** la
  colonne triée pour gagner à l'intersection.
- **`primaryColor` déclaré par variante** dans `.streamlit/config.toml` : `[theme.light]` et
  `[theme.dark]`, **jamais un `[theme]` nu**. Un bloc `[theme]` sans `base` épingle l'app en thème
  clair et retire le mode sombre au lecteur. Vérifier avec `config.get_option("theme.base") is None`.
- **Pas de sélecteur de thème maison.** `theme.base` a `scriptable = False` et `st.set_option` refuse
  tout ce qui sort de `client.*` : un bouton soleil/lune ne peut pas piloter le vrai thème. Une
  bascule en CSS laisserait le tableau (canvas glide-data-grid) en clair. On s'appuie donc sur le
  sélecteur natif de Streamlit, et `client.toolbarMode = "viewer"` — surtout pas `"minimal"`, qui
  masque le menu où il se trouve.
- **Les choix de sliders sont mémorisés hors widget** (`minimum_choice_{view.key}`). Streamlit
  détruit l'état d'un widget non rendu au run précédent, donc un slider appartenant à une autre vue
  se réinitialisait au retour.
- **Graphiques figés** : `staticPlot` sur les graphiques de la fiche, `fixedrange` + `dragmode=False`
  sur le nuage (qui doit rester cliquable). Aucun zoom, aucun pan, pas de barre d'outils.
- **Thème détecté via `st.context.theme["type"]`**, pas `st.get_option("theme.base")` qui ne renvoie
  que la config. La grille est en `rgba(137,135,129,0.22)` : lisible sur les deux fonds même si la
  détection se trompe au premier rendu.
- **Le glossaire est indexé une fois, pas à chaque infobulle** : `@cache` sur `glossary._index` et
  `glossary.definition`. Sans lui, `_index` reparcourait les 827 lignes à chaque appel, `definition`
  l'appelle jusqu'à 3 fois (les deux datasets), et `columns.column_config` demande une définition
  pour les 105 colonnes du catalogue → ~300 reconstructions par rerun, **293 ms mesurées, tombées à
  2,4 ms**. `MetricInfo` est frozen et personne ne mute le dict, donc le partage est sûr. Même
  raison que `catalogue_columns` : c'est de la configuration, pas de la donnée filtrée, donc
  `functools.cache` et surtout pas `st.cache_data`.
- **`columns.build` assemble le tableau en un `pd.concat`**, pas colonne par colonne : 105
  affectations successives faisaient recopier un bloc fragmenté à chaque fois (pandas le signalait
  lui-même par `PerformanceWarning`).
- **Le bloc de critères est un `@st.fragment`** (`criteria._rows`). Empiler une ligne, ou ouvrir un
  sélecteur de métrique, ne change **la liste de personne** : rerunner toute la page pour ça
  reconstruisait le tableau, l'export CSV et toutes les figures d'une fiche ouverte. Le fragment se
  redessine seul et ne réclame le rerun global (`st.rerun(scope="app")`) que si le tuple de
  `Criterion` a réellement changé — comparaison par valeur, les dataclasses sont frozen. Les
  critères transitent par `st.session_state["criteria_built"]` : un rerun de fragment ne délivre
  aucune valeur de retour à la page. Au tout premier run, `previous is None` → on stocke sans
  rerunner, la page est encore en train de descendre et lira le store juste après.
- **Les boutons `Add a criterion` / `Remove the last` passent par `on_click`, jamais par
  `st.rerun()` en ligne.** Le rerun inline coupait le script à la rangée de boutons : tout ce qui
  avait déjà été streamé en dessous (fiche joueur, tableau) était démonté le temps d'une frame avant
  d'être repeint. Le callback met le compteur à jour **avant** que le corps ne s'exécute, donc un
  seul rendu, directement dans l'état final. Les deux boutons sont **toujours dessinés** et grisés
  aux bornes (`disabled`) : en cacher un retirait une colonne de la rangée et faisait glisser
  l'autre sous le curseur. Le `min`/`max` de `_stack` remplace les gardes de rendu, pour qu'un
  double-clic juste avant la désactivation ne sorte pas du bornage.

**Questions ouvertes**
- Nom de l'application — piste retenue : le vocabulaire de la **menace offensive**, puisque c'est
  exactement ce que les deux fichiers décrivent (menacer par le tir, par le pick, par la passe).
  Candidats classés dans la réponse de session 3 ; à trancher par l'utilisateur.
- `main.py` à la racine est vide et non utilisé (reliquat) : à supprimer ou à ignorer
