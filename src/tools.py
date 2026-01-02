from pprint import pprint
import json

from tool_constraints import call_limit, unique_args, InvalidToolCall
import db


TOOLS = {}

# TODO revise tool calls
# TODO revise return types?


def tool(f):
    TOOLS[f.__name__] = f
    return f


@tool
@call_limit(1)
def get_meal_notes(
    n: int = 3,
) -> list[dict]:
    """Get a random sample of notes from past meal plans

    Use this tool once at the start of the conversation to get an idea of past preferences

    :param n: The max number of meal plan summaries to return

    :returns: An array of the meal plan notes with their corresponding chat_id
    """
    return db.get_random_chat_notes(n)


# Only giving the user messages
# When I tried giving the full chat history, the model would repeat past recipes verbatim
# @tool
@unique_args
def get_meal_chat(chat_id: int) -> list[str]:
    """Get the user's chat messages given a chat_id

    Use this tool after get_meal_notes if you want to check
    for any related context from that chat_id

    :param chat_id: The chat_id to fetch from the database

    :returns: A list of messages from the user, not including the initial prompt
    """
    pass


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

    def tools():
        return [t.func for t in TOOLS.values()]

    def __iter__(self):
        for call in self.calls:
            try:
                name = call.function.name
                args = call.function.arguments
                try:
                    tool = TOOLS[name]
                except KeyError:
                    continue
                print(f"Calling tool {name}")
                pprint(args)
                try:
                    result = tool.func(**args)
                except InvalidToolCall as e:
                    print(e)
                    continue
                pprint(result)
                if not isinstance(result, str):
                    result = json.dumps(result)
                yield name, result
            except KeyboardInterrupt:
                print()
                print("Interrupted Tool Call")
                self.interrupted = True
