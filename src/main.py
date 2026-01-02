from pprint import pprint
import argparse
import json
import sys
import tomllib

from ollama import chat

from model import MealPlan
from tools import ToolExecutor
import db


def print_green(s, **kwargs):
    green = "\033[92;40m"
    reset = "\033[0m"
    print(green, **{**kwargs, "flush": False, "end": ""})
    print(s, **{**kwargs, "flush": False, "end": ""})
    print(reset, **kwargs)


def main():
    def process_tool_calls():
        nonlocal tool_calls
        response = chat(
            **payload,
            tools=ToolExecutor.tools(),
            stream=True,
        )
        tool_calls = False
        for name, result in ToolExecutor(process_chunks(response)):
            payload["messages"].append(
                {"role": "tool", "tool_name": name, "content": result}
            )
            tool_calls = True

    def process_content():
        print_green("Collecting structured response")
        response = chat(
            **payload,
            format=MealPlan.model_json_schema(),
        )
        mealplan = MealPlan.model_validate_json(response.message.content)
        mealplan.print()
        payload["messages"].append(
            {
                "role": "assistant",
                "content": response.message.content,
            }
        )

    for message in get_user_messages(get_user_contents()):
        payload["messages"].append(message)
        tool_calls = True
        while tool_calls:
            process_tool_calls()
        process_content()


def get_initial_prompt():
    try:
        with open("config.toml", "rb") as f:
            config = tomllib.load(f)
    except Exception:
        config = {}

    pantry = config.get("pantry", [])
    equipment = config.get("equipment", [])

    initial = (
        "Provide a minimal meal plan that is cheap, nutrient-rich, and calorie dense. "
        "Meals should be a combination of a few wholefoods, I don't want too much prep work. "
        "Avoid meats. Don't get too many ingredients in the same category. "
        "The meal plan should come in the form of a grocery list that should "
        "last roughly 1-2 weeks and 3 meal ideas. "
        "I should be able to finish all perishables without worrying about anything going bad. "
        "Prioritize ingredients I already have in my pantry.\n"
        f"Cooking equipment: {equipment}.\n"
        f"Ingredients in pantry: {pantry}."
        # "If you decide a tool is needed:\n"
        # "- DO NOT mention the tool in text\n"
        # "- DO NOT explain that you are calling it\n"
        # "- ONLY emit a tool call using the tool schema\n"
        # "- The assistant message must contain no content"
    )

    print(initial)
    print_green("===")
    return initial


def get_user_contents():
    should_save = False

    if not payload["messages"]:
        should_save = True
        yield get_initial_prompt()

    while True:
        print_green(">>>", end=" ")
        try:
            content = input()
        except EOFError:
            break
        if not content:
            break
        should_save = True
        yield content

    if should_save:
        db.insert_chat(payload["messages"])


def get_user_messages(user_contents):
    return ({"role": "user", "content": content} for content in user_contents)


def process_chunks(stream):
    try:
        for chunk in stream:
            if chunk.message.tool_calls:
                yield from chunk.message.tool_calls
            else:
                break
    except KeyboardInterrupt:
        print()
        print("Interrupted LLM")


def rewind(messages):
    payload["messages"] = messages
    for message in messages:
        print(f"<{message['role']}>")
        if message["role"] == "tool":
            print(message["tool_name"])
            pprint(json.loads(message["content"]))
        elif message["role"] == "assistant":
            mealplan = MealPlan.model_validate_json(message["content"])
            mealplan.print()
        else:
            print(message["content"])
        print(f"</{message['role']}>")


def get_note() -> str:
    print_green("Note", end=": ")
    return input()


if __name__ == "__main__":
    _sentinel = object()
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    # rewinding a chat brings up the old chat history and allows you to continue the conversation
    # saved as a duplicate chat, to prevent invalidating context for notes
    mode.add_argument("-r", "--rewind", nargs='?', const=None, default=_sentinel)
    mode.add_argument("-n", "--note", nargs='?', const=None, default=_sentinel)
    mode.add_argument("-f", "--final", nargs='?', const=None, default=_sentinel)
    args = parser.parse_args()

    db.initialize()
    if args.final is not _sentinel:
        message = json.loads(db.get_final_chat(args.final))
        mealplan = MealPlan.model_validate_json(message["content"])
        mealplan.print()
        sys.exit(0)

    payload = {
        "model": "llama3.1",
        "messages": [],
    }

    if args.rewind is not _sentinel:
        rewind_id = args.rewind
    elif args.note is not _sentinel:
        rewind_id = args.note
    else:
        rewind_id = _sentinel

    if rewind_id is not _sentinel:
        rewind(json.loads(db.get_chat(rewind_id)))

    if args.note is not _sentinel:
        db.insert_note(args.note, get_note())
    else:
        main()
