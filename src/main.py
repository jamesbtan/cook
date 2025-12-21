from typing import TypedDict, NamedTuple
import itertools as it
import json
import operator as op
import tomllib
import argparse

from ollama import chat
from pydantic import BaseModel

from tools import TOOLS, fallback
import db


class Payload(TypedDict):
    model: str
    messages: list[dict[str, str]]


def get_payload() -> Payload:
    return {
        "model": "llama3.1",
        "messages": [],
    }


payload = {**get_payload(), "tools": TOOLS.values(), "stream": True}
green = "\033[92;40m"
reset = "\033[0m"


class Meal(BaseModel):
    name: str
    ingredients: list[str]
    steps: list[str]


class MealPlan(BaseModel):
    grocery_list: list[str]
    meals: list[Meal]

    def print(self):
        print("# Grocery list")
        for grocery in self.grocery_list:
            print(f"- {grocery}")
        print()
        print("# Meals")
        for meal in self.meals:
            print(f"## {meal.name}")
            print("Ingredients")
            for ingredient in meal.ingredients:
                print(f"- {ingredient}")
            print("Steps")
            for i, step in enumerate(meal.steps, 1):
                print(f"{i}. {step}")


def main():
    for message in get_user_messages(get_user_contents()):
        payload["messages"].append(message)
        while True:
            stream = chat(**payload, format=MealPlan.model_json_schema())
            output = process_chunks(stream)

            try:
                content = "".join(output["content"])
                mealplan = MealPlan.model_validate_json(content)
                mealplan.print()
                payload["messages"].append({"role": "assistant", "content": content})
            except KeyError:
                pass

            try:
                tool_processor = ToolProcessor(output["tool_calls"])
            except KeyError:
                break

            for name, result in tool_processor:
                payload["messages"].append(
                    {"role": "tool", "tool_name": name, "content": result}
                )
            if tool_processor.interrupted:
                break


def get_initial_prompt():
    with open("config.toml", "rb") as f:
        config = tomllib.load(f)
    pantry = ", ".join(config["pantry"])
    equipment = ", ".join(config["equipment"])
    initial = (
        "Provide a minimal meal plan that is cheap, nutrient-rich, and calorie dense. "
        "Meals should be a combination of a few wholefoods, I don't want too much prep work. "
        "Avoid meats. Don't get too many ingredients in the same category. "
        "The meal plan should come in the form of a grocery list that should "
        "last roughly 1-2 weeks and 3 meal ideas. "
        "Do not provide new meal ideas per day, provide 3 meal ideas total. "
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
    print(f"{green}==={reset}")
    return initial


def get_user_contents():
    should_save = False

    if not payload["messages"]:
        should_save = True
        yield get_initial_prompt()

    while True:
        print(f"{green}>>>{reset}", end=" ")
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
    output = {}
    phases = ["content", "tool_calls"]
    new_line_phases = {"tool_calls"}

    def get_chunks():
        phase_iter = iter(phases)
        phase = next(phase_iter)
        for chunk in stream:
            while phase is not None:
                content = getattr(chunk.message, phase)
                if content:
                    yield phase, content
                    break
                phase = next(phase_iter, None)

    chunks = get_chunks()
    chunks = it.groupby(chunks, op.itemgetter(0))

    try:
        for phase, chunk in chunks:
            print(f"<{phase}>")
            contents = []
            output[phase] = contents
            for _, content in chunk:
                if phase in new_line_phases:
                    contents.extend(content)
                    for item in content:
                        print(item)
                else:
                    contents.append(content)
                    print(content, end="", flush=True)
            if phase not in new_line_phases:
                print()
            print(f"</{phase}>")
    except KeyboardInterrupt:
        print()
        print("Interrupted LLM")

    return output


class ToolProcessor:
    def __init__(self, tool_calls):
        self.interrupted = False
        self.calls = tool_calls

    def __iter__(self):
        for call in self.calls:
            print(f"Calling tool {call.function.name}")
            try:
                name = call.function.name
                args = call.function.arguments
                result = TOOLS.get(name, fallback)(**args)
                if not isinstance(result, str):
                    result = json.dumps(result)
                yield name, result
            except KeyboardInterrupt:
                print()
                print("Interrupted Tool Call")
                self.interrupted = True


def rewind(messages):
    payload["messages"] = messages
    for message in messages:
        print(f"<{message['role']}>")
        if message["role"] == "tool":
            key = "tool_name"
        else:
            key = "content"
        print(f"{message[key]}")
        print(f"</{message['role']}>")


class Summary(NamedTuple):
    likes: str
    dislikes: str


def get_summary() -> Summary:
    return Summary(
        likes=input(f"{green}Likes{reset}: "),
        dislikes=input(f"{green}Dislikes{reset}: "),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("-r", "--rewind")
    mode.add_argument("-n", "--note")
    args = parser.parse_args()

    db.initialize()
    if args.rewind is not None:
        rewind_id = args.rewind
    elif args.note is not None:
        rewind_id = args.note
    else:
        rewind_id = None
    if rewind_id is not None:
        rewind(json.loads(db.get_chat(rewind_id)))
    if args.note:
        db.insert_summary(args.note, get_summary())
    else:
        main()
