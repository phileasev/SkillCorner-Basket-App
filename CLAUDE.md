# CLAUDE.md — SkillCorner ACB Offense Explorer

Fichier de travail. Règles, pas de prose. À lire en entier avant toute modification.

---

## 1. Objectif

Application Streamlit locale permettant à un analyste / scout basket d'explorer des données
offensives agrégées **par joueur** sur la saison **2024-2025 de la Liga ACB** (Espagne).
Deux domaines : **pick-and-roll** et **tir**.

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

## 3. Arborescence cible

La séparation traitement des données / interface pèse 25 % de la note : **elle doit être lisible
dans l'arborescence elle-même**.

```
app.py                      # entrée Streamlit : config de page, navigation, rien d'autre
pages/                      # une vue = un fichier. UI PURE : widgets, appels au core, rendu.
  1_shooting_profile.py
  2_pick_and_roll.py
  3_player_comparison.py
  4_admin.py                # bonus, seulement si le reste est fini
src/
  data/
    loader.py               # lecture CSV, typage, jointure picks×shots, cache
    glossary.py             # parsing de metric_glossary.csv, lookups display_name / definition / unit
    schema.py               # constantes de colonnes, splits, groupes de métriques
  core/
    metrics.py              # catalogue des métriques affichées (METRICS) + dénominateurs
    thresholds.py           # éligibilité, filtrage à deux étages, valeurs par défaut
    ranking.py              # percentiles / rangs sur population éligible, tri à deux niveaux
    aggregate.py            # dérivations, normalisations, agrégats par équipe
  ui/
    filters.py              # constructeurs de widgets réutilisables (expander de seuils, toggles)
    tables.py               # rendu des dataframes, grisage des non-éligibles, formatage
    charts.py               # factories Plotly (scatter, bar, radar), thème commun
    format.py               # formatage nombres / pourcentages / labels
tests/                      # tests du core uniquement, pas de test d'UI
data/                       # les 3 CSV fournis, en lecture seule, jamais modifiés
scripts/                    # scripts ponctuels hors app (profilage, exploration)
README.md                   # en anglais, livrable noté
```

**Règle dure** : aucun `pandas` métier dans `pages/`. Un fichier de page lit des widgets, appelle
une fonction de `src/`, passe le résultat à un renderer de `src/ui/`. Si une page contient un
`groupby`, un `quantile`, un masque booléen de filtrage ou un calcul de ratio → le code est au
mauvais endroit.

---

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
  `efg_percentage` monte au-dessus de 1 (max observé 1.5) : ne pas clipper à 1.
- **`avg_shot_distance` est en PIEDS, pas en mètres**, contrairement à ce qu'annonce le glossaire.
  Preuve : max observé 22,11 → 6,74 m une fois converti, soit **exactement la ligne à 3 points FIBA**
  (6,75 m) ; min 3,78 → 1,15 m, un lay-up. Lus en mètres, tous les shooteurs tireraient de
  22 m. Conversion assurée par `schema.FEET_TO_METRES` vers la colonne dérivée
  `derived_avg_shot_distance_metres` ; la colonne brute n'est jamais écrasée, et un test verrouille
  la conversion.
- ~89 colonnes de `picks_offense` sur 599 sont vides à plus de 50 %.

### 4.6 Pièges de données à documenter dans le README

1. **Blitz et Ice sont inexploitables.** Maximum league-wide par joueur : `handler_picks_vs_blitz`
   = **5**, `handler_picks_vs_ice` = **7**, `screener_picks_vs_blitz` = **5**,
   `screener_picks_vs_ice` = **9** — médiane 0, **aucun joueur au-dessus de 25 événements**.
   Ces deux couvertures sont soit très rares en ACB, soit sous-étiquetées dans le tracking.
   → Ne pas proposer d'efficacité vs Blitz ou vs Ice comme métrique de comparaison. Les exposer
   uniquement en volume, ou les retirer des sélecteurs avec une note explicative. C'est un point
   d'analyse à valoriser dans le README, pas un bug à masquer.
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
- **Cache** : `@st.cache_data` sur le chargement et le parsing des CSV (coûteux, immuable).
  Pas de cache sur du filtrage trivial. Toute fonction cachée renvoie un objet non muté ensuite.
- Aucune écriture dans `data/`. Les CSV sont en lecture seule.
- Tests : `tests/` couvre le core (dénominateurs, éligibilité, percentiles sur population éligible,
  tri à deux niveaux). Pas de test d'UI Streamlit.

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
- ❌ Proposer une comparaison d'efficacité vs Blitz ou vs Ice : les données ne le permettent pas (§4.6).
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
- [ ] Vue 2 : pick-and-roll (handler / screener + couvertures)
- [ ] Vue 3 : shortlist builder
- [ ] Bonus : fiche joueur autonome, page admin, déploiement

**Décisions arrêtées** (ne pas rouvrir sans demande explicite)
- Seuil sur le dénominateur de la métrique, pas sur `games_played`
- Filtrage à deux étages population / échantillon
- Percentiles sur population éligible uniquement
- Pas de shrinkage dans la version principale
- Sliders de seuils de 0 au max observé, dans un expander fermé par défaut
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

**Questions ouvertes**
- Périmètre exact des vues 2 et 3
- `main.py` à la racine est vide et non utilisé (reliquat) : à supprimer ou à ignorer
