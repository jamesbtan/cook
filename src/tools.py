from typing import Any
from collections import UserDict
from pprint import pprint

import db

# TODO revise docstrings


class ToolContext(UserDict):
    def __init__(self):
        super().__init__()
        self.con = None

    def __setitem__(self, key, val):
        self.data[key] = val

    def __getitem__(self, key):
        return self.data[key]


TOOLS = ToolContext()

def tool(f):
    TOOLS[f.__name__] = f
    return f


@tool
def get_meal_summaries(
    n: int = 3,
) -> list[list[dict]]:
    """Get a random sample of likes and dislikes from past meal plans

    The list may have less than the requested number
    if there are not enough historical entries.

    :param n: The max number of meal plan summaries to return

    :returns: An array of the meal plan summaries, formatted with likes and dislikes
    """
    return db.get_random_chat_summaries(n)


def get_food_details() -> str:
    """Query an API to get details about a particular food item"""
    # TODO find a nutrition details API
    # https://www.eatfresh.tech/blog/top-8-nutrition-apis-for-meal-planning-2024 (list)
    # https://nutrition.avocavo.app/pricing
    # https://api-ninjas.com/pricing
    # https://www.edamam.com/
    # https://platform.fatsecret.com/platform-api
    raise NotImplementedError


def fallback(**kwargs: Any) -> str:
    return "Unknown tool"
