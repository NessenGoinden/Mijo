"""Stockage local SQLite des recettes et des menus."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable, Optional

from .models import Menu, Recipe, normalize_text, now_iso

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS recipes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    source_url TEXT,
    author TEXT,
    main_protein TEXT,
    cuisine TEXT,
    total_time INTEGER,
    favorite INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    search_text TEXT NOT NULL DEFAULT '',
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category);
CREATE INDEX IF NOT EXISTS idx_recipes_source ON recipes(source_url);
CREATE INDEX IF NOT EXISTS idx_recipes_created ON recipes(created_at);

CREATE TABLE IF NOT EXISTS recipe_tags (
    recipe_id TEXT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (recipe_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON recipe_tags(tag);

CREATE TABLE IF NOT EXISTS menus (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    week_start TEXT,
    data TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ recettes

    def upsert_recipe(self, recipe: Recipe) -> Recipe:
        recipe.updated_at = now_iso()
        data = recipe.model_dump(mode="json")
        with self._lock:
            self._conn.execute(
                """INSERT INTO recipes (id, title, category, source_url, author, main_protein, cuisine, total_time,
                                        favorite, created_at, updated_at, search_text, data)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                        title=excluded.title, category=excluded.category, source_url=excluded.source_url,
                        author=excluded.author, main_protein=excluded.main_protein, cuisine=excluded.cuisine,
                        total_time=excluded.total_time, favorite=excluded.favorite, updated_at=excluded.updated_at,
                        search_text=excluded.search_text, data=excluded.data""",
                (
                    recipe.id, recipe.title, recipe.category, recipe.source_url, recipe.author, recipe.main_protein,
                    recipe.cuisine, recipe.total_time_min, int(recipe.favorite), recipe.created_at, recipe.updated_at,
                    recipe.search_text(), json.dumps(data, ensure_ascii=False),
                ),
            )
            self._conn.execute("DELETE FROM recipe_tags WHERE recipe_id=?", (recipe.id,))
            self._conn.executemany(
                "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag) VALUES (?,?)",
                [(recipe.id, t) for t in recipe.tags],
            )
            self._conn.commit()
        return recipe

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        with self._lock:
            row = self._conn.execute("SELECT data FROM recipes WHERE id=?", (recipe_id,)).fetchone()
        return Recipe.model_validate_json(row["data"]) if row else None

    def get_recipes(self, ids: Iterable[str]) -> dict[str, Recipe]:
        ids = list(ids)
        if not ids:
            return {}
        out: dict[str, Recipe] = {}
        with self._lock:
            for i in range(0, len(ids), 500):
                chunk = ids[i : i + 500]
                q = f"SELECT data FROM recipes WHERE id IN ({','.join('?' * len(chunk))})"
                for row in self._conn.execute(q, chunk):
                    r = Recipe.model_validate_json(row["data"])
                    out[r.id] = r
        return out

    def find_by_source_url(self, url: str) -> Optional[Recipe]:
        if not url:
            return None
        with self._lock:
            row = self._conn.execute("SELECT data FROM recipes WHERE source_url=? LIMIT 1", (url,)).fetchone()
        return Recipe.model_validate_json(row["data"]) if row else None

    def delete_recipe(self, recipe_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM recipes WHERE id=?", (recipe_id,))
            self._conn.execute("DELETE FROM recipe_tags WHERE recipe_id=?", (recipe_id,))
            self._conn.commit()
        return cur.rowcount > 0

    def list_recipes(
        self,
        query: str = "",
        category: Optional[str] = None,
        categories: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        max_total_time: Optional[int] = None,
        favorites_only: bool = False,
        sort: str = "recent",
        limit: int = 2000,
    ) -> list[Recipe]:
        where: list[str] = []
        params: list[Any] = []
        if category:
            where.append("category = ?")
            params.append(category)
        if categories:
            where.append(f"category IN ({','.join('?' * len(categories))})")
            params.extend(categories)
        if favorites_only:
            where.append("favorite = 1")
        if max_total_time is not None:
            where.append("(total_time IS NOT NULL AND total_time <= ?)")
            params.append(int(max_total_time))
        for word in normalize_text(query).split():
            where.append("search_text LIKE ?")
            params.append(f"%{word}%")
        for tag in tags or []:
            where.append("id IN (SELECT recipe_id FROM recipe_tags WHERE tag = ?)")
            params.append(tag)
        order = {
            "recent": "created_at DESC",
            "oldest": "created_at ASC",
            "title": "title COLLATE NOCASE ASC",
            "time": "total_time IS NULL, total_time ASC",
        }.get(sort, "created_at DESC")
        sql = "SELECT data FROM recipes"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {order} LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [Recipe.model_validate_json(r["data"]) for r in rows]

    def count_recipes(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM recipes").fetchone()[0])

    def tag_counts(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT tag, COUNT(*) AS n FROM recipe_tags GROUP BY tag ORDER BY n DESC, tag ASC"
            ).fetchall()
        return [{"tag": r["tag"], "count": r["n"]} for r in rows]

    def category_counts(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute("SELECT category, COUNT(*) AS n FROM recipes GROUP BY category").fetchall()
        return {r["category"]: r["n"] for r in rows}

    def all_recipes(self) -> list[Recipe]:
        return self.list_recipes(limit=100000)

    # ------------------------------------------------------------------ menus

    def save_menu(self, menu: Menu) -> Menu:
        with self._lock:
            self._conn.execute(
                """INSERT INTO menus (id, name, created_at, week_start, data) VALUES (?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name, week_start=excluded.week_start, data=excluded.data""",
                (menu.id, menu.name, menu.created_at, menu.week_start, menu.model_dump_json()),
            )
            self._conn.commit()
        return menu

    def get_menu(self, menu_id: str) -> Optional[Menu]:
        with self._lock:
            row = self._conn.execute("SELECT data FROM menus WHERE id=?", (menu_id,)).fetchone()
        return Menu.model_validate_json(row["data"]) if row else None

    def list_menus(self, limit: int = 50) -> list[Menu]:
        with self._lock:
            rows = self._conn.execute("SELECT data FROM menus ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [Menu.model_validate_json(r["data"]) for r in rows]

    def delete_menu(self, menu_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM menus WHERE id=?", (menu_id,))
            self._conn.commit()
        return cur.rowcount > 0

    def recent_usage(self, menus_limit: int = 6) -> dict[str, int]:
        """Nombre d'apparitions de chaque recette dans les derniers menus (pour varier)."""
        usage: dict[str, int] = {}
        for i, menu in enumerate(self.list_menus(limit=menus_limit)):
            weight = menus_limit - i  # les menus récents pèsent plus lourd
            for slot in menu.slots:
                if slot.recipe_id:
                    usage[slot.recipe_id] = usage.get(slot.recipe_id, 0) + weight
        return usage
