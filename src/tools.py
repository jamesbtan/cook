from dataclasses import dataclass
from pprint import pprint
from typing import Callable
import json

import db


TOOLS = {}


@dataclass
class Tool:
    func: Callable
    limit: int | None = None


def tool(limit=None):
    def wrapper(f):
        TOOLS[f.__name__] = Tool(f, limit)
        return f

    return wrapper


@tool(limit=1)
def get_meal_notes(
    n: int = 3,
) -> list[dict]:
    """Get a random sample of likes and dislikes from past meal plans

    The list may have less than the requested number
    if there are not enough historical entries.

    :param n: The max number of meal plan summaries to return

    :returns: An array of the meal plan summaries, formatted with likes and dislikes
    """
    return db.get_random_chat_notes(n)


def get_food_details() -> str:
    """Query an API to get details about a particular food item"""
    # TODO find a nutrition details API
    # https://www.eatfresh.tech/blog/top-8-nutrition-apis-for-meal-planning-2024 (list)
    # https://nutrition.avocavo.app/pricing
    # https://api-ninjas.com/pricing
    # https://www.edamam.com/
    # https://platform.fatsecret.com/platform-api
    raise NotImplementedError


class ToolExecutor:
    def __init__(self, calls):
        self.interrupted = False
        self.calls = calls

    def __iter__(self):
        for call in self.calls:
            try:
                name = call.function.name
                args = call.function.arguments
                try:
                    tool = TOOLS[name]
                except KeyError:
                    continue
                if tool.limit == 0:
                    print(f"Hit tool limit for {name}")
                    continue
                elif tool.limit is not None:
                    tool.limit -= 1
                print(f"Calling tool {name}")
                pprint(args)
                result = tool.func(**args)
                pprint(result)
                if not isinstance(result, str):
                    result = json.dumps(result)
                yield name, result
            except KeyboardInterrupt:
                print()
                print("Interrupted Tool Call")
                self.interrupted = True
