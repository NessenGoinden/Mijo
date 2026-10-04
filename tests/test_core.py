"""Tests rapides (sans Instagram ni Ollama)."""
from __future__ import annotations

import os
import tempfile

import pytest

from nourriture.db import Database
from nourriture.menu import generate_menu, normalize_unit, reroll_slot, shopping_list
from nourriture.models import Ingredient, MenuFilters, MenuGenerateRequest, Recipe, RecipeContent, normalize_category
from nourriture.pipeline import caption_has_recipe
from nourriture.fetch.instagram import FetchError, parse_url


def test_normalize_category():
    assert normalize_category("Plat principal") == "plat"
    assert normalize_category("Breakfast") == "petit-déjeuner"
    assert normalize_category("truc inconnu") == "autre"


def test_ingredient_parsing():
    i = Ingredient(name="  farine ", quantity="1/2", unit="c. à s.")
    assert i.name == "farine" and i.quantity == 0.5 and i.unit == "c. à soupe"
    assert Ingredient(name="œufs", quantity="3", unit="pièces").unit is None
    assert normalize_unit("tbsp") == "c. à soupe" and normalize_unit("gr") == "g"


def test_recipe_content_cleanup():
    rc = RecipeContent(title="  Poulet  curry ", category="main", tags=["Rapide", "#rapide", "Poulet"],
                       steps=["1. Couper", "Étape 2 : cuire", ""], servings="4", prep_time_min="10", main_protein="Poulet")
    assert rc.title == "Poulet curry" and rc.category == "plat"
    assert rc.tags == ["rapide", "poulet"] and rc.steps == ["Couper", "cuire"]
    assert rc.servings == 4 and rc.prep_time_min == 10 and rc.main_protein == "poulet"


def test_caption_heuristic():
    assert not caption_has_recipe("Trop bon ce plat ! #recette #food")
    assert caption_has_recipe("Ingrédients :\n- 200 g de farine\n- 3 œufs\n- 50 cl de lait\n- 1 pincée de sel\nPréparation : mélangez tout et cuisez 2 min par face.")


def test_parse_url():
    assert parse_url("https://www.instagram.com/reel/ABC123/?igsh=x")[1] == "ABC123"
    assert parse_url("instagram.com/p/XyZ_-9/")[0] == "https://www.instagram.com/p/XyZ_-9/"
    with pytest.raises(FetchError):
        parse_url("https://example.com/")


@pytest.fixture
def db():
    d = Database(os.path.join(tempfile.mkdtemp(), "t.db"))
    data = [("Poulet curry", "poulet", "asiatique", ["rapide"]), ("Bœuf bourguignon", "bœuf", "française", []),
            ("Saumon teriyaki", "poisson", "japonaise", ["rapide"]), ("Dahl", "légumineuses", "indienne", ["végétarien"]),
            ("Carbonara", "porc", "italienne", ["rapide"]), ("Omelette", "œufs", "française", ["rapide", "végétarien"])]
    for t, p, c, tags in data:
        d.upsert_recipe(Recipe(title=t, main_protein=p, cuisine=c, tags=tags, prep_time_min=10, cook_time_min=20, servings=2,
                               ingredients=[Ingredient(name="oignon", quantity=1), Ingredient(name="sel", quantity=1, unit="pincée", estimated=True)]))
    return d


def test_db_search_and_filters(db):
    assert [r.title for r in db.list_recipes(query="curry")] == ["Poulet curry"]
    assert len(db.list_recipes(tags=["rapide"])) == 4
    assert len(db.list_recipes(tags=["rapide", "végétarien"])) == 1
    assert len(db.list_recipes(max_total_time=25)) == 0
    assert db.tag_counts()[0]["tag"] == "rapide"


def test_menu_variety_and_shopping(db):
    menu, warnings = generate_menu(db, MenuGenerateRequest(count=6, servings=4))
    ids = [s.recipe_id for s in menu.slots]
    assert len(ids) == 6 and len(set(ids)) == 6 and not warnings
    recipes = db.get_recipes(ids)
    assert len({recipes[i].main_protein for i in ids}) == 6  # six protéines différentes
    db.save_menu(menu)
    before = menu.slots[0].recipe_id
    menu2, w = generate_menu(db, MenuGenerateRequest(count=10, filters=MenuFilters(tags=["rapide"])))
    assert w and len([s for s in menu2.slots if s.recipe_id]) == 4
    items = shopping_list(db, menu)
    onion = next(i for i in items if i["name"] == "oignon")
    assert onion["quantity"] == 12 and onion["label"] == "12 oignon"  # 6 recettes × 1 oignon × (4/2 portions)
    with pytest.raises(ValueError):
        reroll_slot(db, menu, 0)  # toutes les recettes sont déjà dans le menu
