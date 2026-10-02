import json

import httpx
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("TheMealDB Meals Server")

BASE_URL = "https://www.themealdb.com/api/json/v1/1"


def get_mealdb(path: str, params: dict | None = None) -> dict:
    response = httpx.get(
        f"{BASE_URL}/{path}",
        params=params,
        timeout=15.0,
    )
    response.raise_for_status()
    return response.json()


@mcp.tool()
def search_meals_by_name(query: str, limit: int = 5) -> str:
    """Search meals by name."""
    if not query.strip():
        return json.dumps({"ok": False, "data": None, "error": "query is required"})

    result = get_mealdb("search.php", {"s": query.strip()})
    meals = result.get("meals") or []

    return json.dumps({
        "ok": True,
        "data": meals[:limit],
        "error": None,
    })


@mcp.tool()
def meals_by_ingredient(ingredient: str, limit: int = 12) -> str:
    """Find meals using an ingredient."""
    if not ingredient.strip():
        return json.dumps({
            "ok": False,
            "data": None,
            "error": "ingredient is required",
        })

    result = get_mealdb("filter.php", {"i": ingredient.strip()})
    meals = result.get("meals") or []

    return json.dumps({
        "ok": True,
        "data": meals[:limit],
        "error": None,
    })


@mcp.tool()
def random_meal() -> str:
    """Return one random meal."""
    result = get_mealdb("random.php")
    meals = result.get("meals") or []

    return json.dumps({
        "ok": bool(meals),
        "data": meals[0] if meals else None,
        "error": None if meals else "No meal returned",
    })


@mcp.tool()
def meal_details(id: str) -> str:
    """Return details for one meal ID."""
    if not id.strip():
        return json.dumps({
            "ok": False,
            "data": None,
            "error": "id is required",
        })

    result = get_mealdb("lookup.php", {"i": id.strip()})
    meals = result.get("meals") or []

    return json.dumps({
        "ok": bool(meals),
        "data": meals[0] if meals else None,
        "error": None if meals else "Meal not found",
    })


if __name__ == "__main__":
    mcp.run(transport="stdio")