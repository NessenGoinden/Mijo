"""Génération de menus de la semaine (tirage aléatoire varié) et liste de courses."""
from __future__ import annotations

import random
import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Optional

from .db import Database
from .models import DAYS_FR, Menu, MenuFilters, MenuGenerateRequest, MenuSlot, Recipe, format_unit, normalize_text, normalize_unit

# ---------------------------------------------------------------------------
# Tirage varié
# ---------------------------------------------------------------------------

def _key(value: Optional[str]) -> str:
    return normalize_text(value or "") or "?"


def _candidates(db: Database, filters: MenuFilters) -> list[Recipe]:
    recipes = db.list_recipes(
        categories=filters.categories or None,
        tags=filters.tags or None,
        max_total_time=filters.max_total_time,
        limit=100000,
    )
    excluded = set(filters.exclude_recipe_ids)
    return [r for r in recipes if r.id not in excluded]


def pick_varied(
    pool: list[Recipe],
    count: int,
    usage: dict[str, int],
    already: Optional[list[Recipe]] = None,
    rng: Optional[random.Random] = None,
) -> list[Recipe]:
    """Choisit `count` recettes distinctes en variant protéines, cuisines et catégories.

    Score = aléa + pénalités (protéine déjà tirée ×2, cuisine ×1, catégorie ×0,5, utilisée récemment).
    """
    rng = rng or random.Random()
    pool = list(pool)
    rng.shuffle(pool)
    chosen: list[Recipe] = []
    protein: dict[str, int] = defaultdict(int)
    cuisine: dict[str, int] = defaultdict(int)
    category: dict[str, int] = defaultdict(int)
    for r in already or []:
        protein[_key(r.main_protein)] += 1
        cuisine[_key(r.cuisine)] += 1
        category[_key(r.category)] += 1
    while pool and len(chosen) < count:
        best, best_score = None, None
        for r in pool:
            score = rng.random()
            score += 2.0 * protein[_key(r.main_protein)]
            score += 1.0 * cuisine[_key(r.cuisine)]
            score += 0.5 * category[_key(r.category)]
            score += 0.4 * min(usage.get(r.id, 0), 6)
            if best_score is None or score < best_score:
                best, best_score = r, score
        assert best is not None
        chosen.append(best)
        pool.remove(best)
        protein[_key(best.main_protein)] += 1
        cuisine[_key(best.cuisine)] += 1
        category[_key(best.category)] += 1
    return chosen


def _build_slots(count: int, moments: str) -> list[MenuSlot]:
    slots: list[MenuSlot] = []
    if moments == "midi_soir":
        for i in range(count):
            slots.append(MenuSlot(day=(i // 2) % 7, moment="midi" if i % 2 == 0 else "soir"))
    else:
        for i in range(count):
            slots.append(MenuSlot(day=i % 7, moment=moments if count <= 7 else ("midi" if i < 7 else "soir")))
    return slots


def next_monday(today: Optional[date] = None) -> date:
    today = today or date.today()
    return today + timedelta(days=(7 - today.weekday()) % 7 or 7) if today.weekday() != 0 else today


def generate_menu(db: Database, req: MenuGenerateRequest) -> tuple[Menu, list[str]]:
    pool = _candidates(db, req.filters)
    warnings: list[str] = []
    if not pool:
        raise ValueError("Aucune recette ne correspond à ces filtres. Élargissez les critères ou importez des recettes.")
    picked = pick_varied(pool, req.count, db.recent_usage())
    if len(picked) < req.count:
        warnings.append(f"Seulement {len(picked)} recette(s) disponible(s) pour {req.count} repas : certains créneaux restent vides.")
    slots = _build_slots(req.count, req.moments)
    for slot, r in zip(slots, picked):
        slot.recipe_id = r.id
    week_start = req.week_start or next_monday().isoformat()
    name = req.name or f"Semaine du {_fmt_date(week_start)}"
    menu = Menu(name=name, week_start=week_start, slots=slots, filters=req.filters, servings=req.servings)
    return menu, warnings


def reroll_slot(db: Database, menu: Menu, slot_index: int) -> Menu:
    if not 0 <= slot_index < len(menu.slots):
        raise ValueError("Créneau inconnu.")
    pool = _candidates(db, menu.filters)
    in_menu = {s.recipe_id for s in menu.slots if s.recipe_id}
    current = menu.slots[slot_index].recipe_id
    pool = [r for r in pool if r.id not in in_menu]
    if not pool:
        raise ValueError("Aucune autre recette disponible avec ces filtres.")
    others = [r for r in db.get_recipes(in_menu - {current}).values()]
    picked = pick_varied(pool, 1, db.recent_usage(), already=others)
    menu.slots[slot_index].recipe_id = picked[0].id if picked else current
    return menu


def _fmt_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
        return d.strftime("%d/%m/%Y")
    except ValueError:
        return iso


# ---------------------------------------------------------------------------
# Liste de courses
# ---------------------------------------------------------------------------

_TO_BASE = {"kg": ("g", 1000.0), "l": ("ml", 1000.0), "cl": ("ml", 10.0)}

_DEPARTMENTS: list[tuple[str, list[str]]] = [
    ("Fruits & légumes", ["oignon", "ail", "echalote", "tomate", "carotte", "courgette", "aubergine", "poivron", "pomme de terre",
                           "patate", "salade", "laitue", "epinard", "brocoli", "chou", "poireau", "champignon", "citron", "pomme",
                           "banane", "fraise", "framboise", "myrtille", "avocat", "concombre", "celeri", "haricot vert", "petit pois",
                           "mangue", "ananas", "orange", "poire", "peche", "abricot", "raisin", "kiwi", "gingembre", "persil",
                           "coriandre", "basilic", "menthe", "ciboulette", "thym", "romarin", "herbes", "fenouil", "radis", "navet",
                           "betterave", "potiron", "courge", "butternut", "mais", "legume", "fruit", "piment", "citron vert", "lime"]),
    ("Viandes & poissons", ["poulet", "dinde", "boeuf", "veau", "porc", "agneau", "canard", "lardon", "jambon", "saucisse", "chorizo",
                            "steak", "viande", "escalope", "filet", "saumon", "thon", "cabillaud", "crevette", "poisson", "merlu",
                            "dorade", "bar", "truite", "moule", "calamar", "gambas", "bacon", "magret", "cuisse", "blanc de"]),
    ("Crèmerie & œufs", ["oeuf", "lait", "beurre", "creme", "yaourt", "fromage", "parmesan", "mozzarella", "feta", "cheddar",
                         "gruyere", "comte", "emmental", "ricotta", "mascarpone", "chevre", "skyr", "fromage blanc", "tofu"]),
    ("Boulangerie", ["pain", "baguette", "brioche", "tortilla", "wrap", "pita", "pate feuilletee", "pate brisee", "pate a pizza"]),
    ("Surgelés", ["surgele", "glace", "congele"]),
    ("Boissons", ["vin", "biere", "eau", "jus", "soda", "cafe", "the ", "rhum", "vodka"]),
    ("Épicerie", ["farine", "sucre", "sel", "poivre", "huile", "vinaigre", "riz", "pate", "pates", "nouille", "lentille", "pois chiche",
                  "haricot", "quinoa", "semoule", "boulgour", "epice", "curry", "paprika", "cumin", "curcuma", "cannelle", "vanille",
                  "levure", "chocolat", "cacao", "miel", "sirop", "moutarde", "ketchup", "mayonnaise", "sauce soja", "lait de coco",
                  "bouillon", "concentre", "coulis", "conserve", "olive", "capre", "noix", "amande", "noisette", "graine", "flocon",
                  "avoine", "cereale", "biscuit", "maizena", "fecule", "bicarbonate", "sesame", "tahini", "nuoc", "sriracha", "harissa"]),
]


def _ingredient_key(name: str) -> str:
    n = normalize_text(name)
    n = re.sub(r"^(de |d'|du |des |la |le |les |l')", "", n).strip()
    n = re.sub(r"\s*\(.*?\)\s*", " ", n).strip()
    return n


def _department(name_key: str) -> str:
    best, best_len = "Autres", 0
    for dept, words in _DEPARTMENTS:
        for w in words:
            if w in name_key and len(w) > best_len:  # le mot-clé le plus précis l'emporte (« lait de coco » > « lait »)
                best, best_len = dept, len(w)
    return best


def _fmt_qty(q: float) -> str:
    if q is None:
        return ""
    fractions = {0.25: "¼", 0.5: "½", 0.75: "¾", 0.33: "⅓", 0.34: "⅓", 0.66: "⅔", 0.67: "⅔"}
    whole = int(q)
    frac = round(q - whole, 2)
    if frac in fractions:
        return (str(whole) if whole else "") + fractions[frac]
    if abs(q - round(q)) < 0.01:
        return str(int(round(q)))
    return f"{q:.1f}".replace(".", ",").rstrip("0").rstrip(",")


def shopping_list(db: Database, menu: Menu) -> list[dict[str, Any]]:
    recipes = db.get_recipes([s.recipe_id for s in menu.slots if s.recipe_id])
    agg: dict[tuple[str, Optional[str]], dict[str, Any]] = {}
    for slot in menu.slots:
        r = recipes.get(slot.recipe_id or "")
        if not r:
            continue
        factor = 1.0
        if menu.servings and r.servings:
            factor = menu.servings / r.servings
        for ing in r.ingredients:
            key_name = _ingredient_key(ing.name)
            if not key_name:
                continue
            unit = normalize_unit(ing.unit)
            qty = ing.quantity * factor if ing.quantity is not None else None
            if unit in _TO_BASE and qty is not None:
                unit, mult = _TO_BASE[unit]
                qty *= mult
            k = (key_name, unit)
            item = agg.setdefault(k, {
                "key": f"{key_name}|{unit or ''}", "name": ing.name.strip(), "unit": unit, "quantity": 0.0,
                "has_unknown": False, "estimated": False, "recipes": [], "department": _department(key_name),
            })
            if qty is None:
                item["has_unknown"] = True
            else:
                item["quantity"] += qty
            item["estimated"] = item["estimated"] or ing.estimated
            if r.title not in item["recipes"]:
                item["recipes"].append(r.title)
    items: list[dict[str, Any]] = []
    for item in agg.values():
        qty, unit = item["quantity"], item["unit"]
        if unit == "g" and qty >= 1000:
            qty, unit = qty / 1000, "kg"
        elif unit == "ml" and qty >= 1000:
            qty, unit = qty / 1000, "l"
        display_qty = _fmt_qty(round(qty, 2)) if qty else ""
        label = " ".join(x for x in [display_qty, format_unit(unit, qty), item["name"]] if x).strip()
        if item["has_unknown"] and not qty:
            label = item["name"]
        items.append({**item, "quantity": round(qty, 2), "unit": unit, "label": label,
                      "checked": item["key"] in set(menu.checked_items)})
    order = {d: i for i, (d, _) in enumerate(_DEPARTMENTS)}
    items.sort(key=lambda it: (order.get(it["department"], 99), normalize_text(it["name"])))
    return items


def menu_as_text(db: Database, menu: Menu) -> str:
    recipes = db.get_recipes([s.recipe_id for s in menu.slots if s.recipe_id])
    lines = [menu.name, ""]
    for s in menu.slots:
        r = recipes.get(s.recipe_id or "")
        lines.append(f"{DAYS_FR[s.day % 7]} {s.moment} : {r.title if r else '—'}".replace("  ", " "))
    lines += ["", "Liste de courses :"]
    dept = None
    for it in shopping_list(db, menu):
        if it["department"] != dept:
            dept = it["department"]
            lines.append(f"\n[{dept}]")
        lines.append(f"- {it['label']}" + (" (estimé)" if it["estimated"] else ""))
    return "\n".join(lines)
