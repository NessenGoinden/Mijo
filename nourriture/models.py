"""Modèles de données (Pydantic) : recettes, menus, requêtes d'API."""
from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

CATEGORIES: list[str] = [
    "entrée", "plat", "dessert", "petit-déjeuner", "snack", "boisson", "accompagnement", "sauce", "autre",
]

PROTEINS: list[str] = [
    "poulet", "volaille", "bœuf", "porc", "agneau", "poisson", "fruits de mer", "œufs",
    "tofu et soja", "légumineuses", "fromage et laitages", "aucune",
]

_CATEGORY_ALIASES = {
    "entree": "entrée", "starter": "entrée", "apéritif": "entrée", "aperitif": "entrée", "apéro": "entrée",
    "plat principal": "plat", "main": "plat", "main course": "plat", "plats": "plat", "dîner": "plat", "déjeuner": "plat",
    "desserts": "dessert", "sweet": "dessert", "pâtisserie": "dessert", "gâteau": "dessert",
    "petit déjeuner": "petit-déjeuner", "petit-dejeuner": "petit-déjeuner", "breakfast": "petit-déjeuner", "brunch": "petit-déjeuner",
    "snacks": "snack", "goûter": "snack", "encas": "snack", "en-cas": "snack", "collation": "snack",
    "boissons": "boisson", "drink": "boisson", "cocktail": "boisson", "smoothie": "boisson",
    "side": "accompagnement", "accompagnements": "accompagnement", "garniture": "accompagnement",
    "sauces": "sauce", "condiment": "sauce", "dip": "sauce",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def normalize_text(s: str) -> str:
    """Minuscules sans accents, pour la recherche."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("œ", "oe").replace("æ", "ae")
    return re.sub(r"\s+", " ", s).strip()


def normalize_category(value: str | None) -> str:
    if not value:
        return "plat"
    v = value.strip().lower()
    if v in CATEGORIES:
        return v
    if v in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[v]
    nv = normalize_text(v)
    for c in CATEGORIES:
        if normalize_text(c) == nv:
            return c
    for alias, cat in _CATEGORY_ALIASES.items():
        if normalize_text(alias) == nv:
            return cat
    return "autre"


_UNIT_ALIASES: dict[str, Optional[str]] = {
    "g": "g", "gr": "g", "grs": "g", "gramme": "g", "grammes": "g",
    "kg": "kg", "kilo": "kg", "kilos": "kg", "kilogramme": "kg", "kilogrammes": "kg",
    "ml": "ml", "millilitre": "ml", "millilitres": "ml", "cl": "cl", "centilitre": "cl", "centilitres": "cl",
    "l": "l", "litre": "l", "litres": "l", "dl": "dl",
    "c. a soupe": "c. à soupe", "c a soupe": "c. à soupe", "c. a s.": "c. à soupe", "c. a s": "c. à soupe", "c.a.s": "c. à soupe",
    "c.a.s.": "c. à soupe", "cas": "c. à soupe", "cs": "c. à soupe", "cas.": "c. à soupe", "cuillere a soupe": "c. à soupe",
    "cuilleres a soupe": "c. à soupe", "cuillere soupe": "c. à soupe", "tbsp": "c. à soupe", "tablespoon": "c. à soupe", "cuil. a soupe": "c. à soupe",
    "c. a cafe": "c. à café", "c a cafe": "c. à café", "c. a c.": "c. à café", "c. a c": "c. à café", "c.a.c": "c. à café",
    "c.a.c.": "c. à café", "cac": "c. à café", "cc": "c. à café", "cuillere a cafe": "c. à café", "cuilleres a cafe": "c. à café",
    "tsp": "c. à café", "teaspoon": "c. à café", "cuil. a cafe": "c. à café", "cuillere a the": "c. à café",
    "pincee": "pincée", "pincees": "pincée", "gousse": "gousse", "gousses": "gousse", "tranche": "tranche", "tranches": "tranche",
    "boite": "boîte", "boites": "boîte", "sachet": "sachet", "sachets": "sachet", "botte": "botte", "bottes": "botte",
    "poignee": "poignée", "poignees": "poignée", "feuille": "feuille", "feuilles": "feuille", "brin": "brin", "brins": "brin",
    "verre": "verre", "verres": "verre", "tasse": "tasse", "tasses": "tasse", "cup": "tasse", "cups": "tasse",
    "piece": None, "pieces": None, "pc": None, "pcs": None, "unite": None, "unites": None, "entier": None, "entiere": None, "": None,
    "none": None, "null": None, "-": None,
}

PLURAL_UNITS = {"gousse", "tranche", "boîte", "sachet", "botte", "poignée", "feuille", "brin", "verre", "tasse", "pincée"}


def normalize_unit(unit: Optional[str]) -> Optional[str]:
    """Harmonise l'écriture des unités (« c. à s. » → « c. à soupe », « gr » → « g »…)."""
    if unit is None:
        return None
    raw = str(unit).strip()
    key = normalize_text(raw).replace(" .", ".").strip()
    key = re.sub(r"\s+", " ", key)
    if key in _UNIT_ALIASES:
        return _UNIT_ALIASES[key]
    k2 = key.rstrip(".")
    if k2 in _UNIT_ALIASES:
        return _UNIT_ALIASES[k2]
    if re.match(r"^c\.? ?a ?s", key) or key.startswith("cuillere a s") or key.startswith("cuilleres a s"):
        return "c. à soupe"
    if re.match(r"^c\.? ?a ?c", key) or key.startswith("cuillere a c") or key.startswith("cuilleres a c"):
        return "c. à café"
    return raw[:30] or None


def format_unit(unit: Optional[str], quantity: Optional[float]) -> str:
    if not unit:
        return ""
    if unit in PLURAL_UNITS and quantity is not None and quantity >= 2:
        return unit + "s"
    return unit


def normalize_tag(tag: str) -> str:
    t = re.sub(r"\s+", " ", (tag or "").strip().lower().lstrip("#"))
    return t[:40]


# ---------------------------------------------------------------------------
# Recette
# ---------------------------------------------------------------------------

class Ingredient(BaseModel):
    name: str = ""
    quantity: Optional[float] = None
    unit: Optional[str] = None
    estimated: bool = False
    note: Optional[str] = None

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v: Any) -> str:
        return str(v or "").strip()

    @field_validator("note", mode="before")
    @classmethod
    def _opt_str(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    @field_validator("unit", mode="before")
    @classmethod
    def _unit(cls, v: Any) -> Optional[str]:
        return normalize_unit(v if v is None else str(v))

    @field_validator("quantity", mode="before")
    @classmethod
    def _qty(cls, v: Any) -> Optional[float]:
        if v is None or v == "":
            return None
        if isinstance(v, (int, float)):
            return float(v) if v >= 0 else None
        s = str(v).strip().replace(",", ".")
        m = re.match(r"^(\d+)\s*/\s*(\d+)$", s)
        if m and int(m.group(2)):
            return int(m.group(1)) / int(m.group(2))
        m = re.match(r"^(\d+)\s+(\d+)\s*/\s*(\d+)$", s)
        if m and int(m.group(3)):
            return int(m.group(1)) + int(m.group(2)) / int(m.group(3))
        try:
            return float(re.sub(r"[^0-9.]", "", s))
        except ValueError:
            return None


class RecipeContent(BaseModel):
    """Champs produits par l'IA et modifiables par l'utilisateur."""

    title: str = "Recette sans titre"
    category: str = "plat"
    tags: list[str] = Field(default_factory=list)
    servings: Optional[int] = 4
    prep_time_min: Optional[int] = None
    cook_time_min: Optional[int] = None
    main_protein: Optional[str] = None
    cuisine: Optional[str] = None
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    notes: Optional[str] = None

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, v: Any) -> str:
        v = re.sub(r"\s+", " ", str(v or "")).strip()
        return v[:140] or "Recette sans titre"

    @field_validator("category", mode="before")
    @classmethod
    def _cat(cls, v: Any) -> str:
        return normalize_category(v if v is None else str(v))

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, v: Any) -> list[str]:
        if not v:
            return []
        if isinstance(v, str):
            v = re.split(r"[,;\n]", v)
        out: list[str] = []
        for t in v:
            nt = normalize_tag(str(t))
            if nt and nt not in out:
                out.append(nt)
        return out[:25]

    @field_validator("servings", mode="before")
    @classmethod
    def _servings(cls, v: Any) -> Optional[int]:
        try:
            n = int(round(float(str(v).replace(",", "."))))
        except (TypeError, ValueError):
            return None
        return max(1, min(n, 50))

    @field_validator("prep_time_min", "cook_time_min", mode="before")
    @classmethod
    def _time(cls, v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            n = int(round(float(str(v).replace(",", "."))))
        except (TypeError, ValueError):
            return None
        return max(0, min(n, 24 * 60 * 3))

    @field_validator("main_protein", "cuisine", "notes", mode="before")
    @classmethod
    def _opt(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    @field_validator("steps", mode="before")
    @classmethod
    def _steps(cls, v: Any) -> list[str]:
        if not v:
            return []
        if isinstance(v, str):
            v = [s for s in re.split(r"\n+", v)]
        out = []
        for s in v:
            if isinstance(s, dict):
                s = s.get("text") or s.get("step") or s.get("description") or ""
            s = re.sub(r"^\s*(?:étape|etape|step)?\s*\d+\s*[.):\-–]\s*", "", str(s).strip(), flags=re.I).strip()
            if s:
                out.append(s[:1500])
        return out[:60]

    @model_validator(mode="after")
    def _clean_ingredients(self) -> "RecipeContent":
        self.ingredients = [i for i in self.ingredients if i.name][:80]
        if self.main_protein:
            mp = self.main_protein.lower().strip()
            if mp in PROTEINS:
                self.main_protein = mp
            else:
                nmp = normalize_text(mp)
                match = next((p for p in PROTEINS if normalize_text(p) == nmp or nmp in normalize_text(p)), None)
                self.main_protein = match or mp[:40]
        return self

    @property
    def total_time_min(self) -> Optional[int]:
        if self.prep_time_min is None and self.cook_time_min is None:
            return None
        return (self.prep_time_min or 0) + (self.cook_time_min or 0)


class RecipeSources(BaseModel):
    caption: Optional[str] = None
    transcript: Optional[str] = None
    ocr_text: Optional[str] = None
    media_type: Optional[str] = None
    used_caption_only: Optional[bool] = None
    llm_model: Optional[str] = None
    confidence: Optional[str] = None


class Recipe(RecipeContent):
    id: str = Field(default_factory=new_id)
    source_url: Optional[str] = None
    source_platform: str = "instagram"
    author: Optional[str] = None
    author_url: Optional[str] = None
    thumbnail: Optional[str] = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    favorite: bool = False
    sources: Optional[RecipeSources] = None

    def search_text(self) -> str:
        parts = [self.title, self.category, self.author or "", self.cuisine or "", self.main_protein or ""]
        parts += self.tags
        parts += [i.name for i in self.ingredients]
        return normalize_text(" ".join(p for p in parts if p))


# ---------------------------------------------------------------------------
# Schéma JSON strict transmis à Ollama (sorties structurées)
# ---------------------------------------------------------------------------

LLM_RECIPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_recipe": {"type": "boolean"},
        "confidence": {"type": "string", "enum": ["haute", "moyenne", "basse"]},
        "title": {"type": "string"},
        "category": {"type": "string", "enum": CATEGORIES},
        "tags": {"type": "array", "items": {"type": "string"}},
        "servings": {"type": "integer"},
        "prep_time_min": {"type": "integer"},
        "cook_time_min": {"type": "integer"},
        "main_protein": {"type": "string", "enum": PROTEINS},
        "cuisine": {"type": "string"},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit": {"type": ["string", "null"]},
                    "estimated": {"type": "boolean"},
                    "note": {"type": ["string", "null"]},
                },
                "required": ["name", "quantity", "unit", "estimated", "note"],
            },
        },
        "steps": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
    "required": [
        "is_recipe", "confidence", "title", "category", "tags", "servings", "prep_time_min", "cook_time_min",
        "main_protein", "cuisine", "ingredients", "steps", "notes",
    ],
}


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------

DAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


class MenuSlot(BaseModel):
    day: int = 0            # 0 = lundi … 6 = dimanche
    moment: str = "soir"    # "midi" | "soir" | ""
    recipe_id: Optional[str] = None
    locked: bool = False

    @property
    def label(self) -> str:
        d = DAYS_FR[self.day % 7]
        return f"{d} {self.moment}".strip()


class MenuFilters(BaseModel):
    categories: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    max_total_time: Optional[int] = None
    exclude_recipe_ids: list[str] = Field(default_factory=list)


class Menu(BaseModel):
    id: str = Field(default_factory=new_id)
    name: str = "Menu de la semaine"
    created_at: str = Field(default_factory=now_iso)
    week_start: Optional[str] = None
    slots: list[MenuSlot] = Field(default_factory=list)
    filters: MenuFilters = Field(default_factory=MenuFilters)
    checked_items: list[str] = Field(default_factory=list)
    servings: Optional[int] = None


class MenuGenerateRequest(BaseModel):
    count: int = 7
    moments: str = "soir"      # "soir" | "midi" | "midi_soir"
    filters: MenuFilters = Field(default_factory=MenuFilters)
    week_start: Optional[str] = None
    name: Optional[str] = None
    servings: Optional[int] = None

    @field_validator("count")
    @classmethod
    def _count(cls, v: int) -> int:
        return max(1, min(int(v), 21))


class MenuRerollRequest(BaseModel):
    slot_index: int


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

class ImportRequest(BaseModel):
    url: Optional[str] = None
    manual_caption: Optional[str] = None
    manual_author: Optional[str] = None
    force_video_analysis: bool = False


class ImportLog(BaseModel):
    time: str
    message: str
