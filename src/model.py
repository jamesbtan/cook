from typing import Annotated

from pydantic import BaseModel, Field


class Meal(BaseModel):
    name: str
    ingredients: list[str]
    steps: list[str] = Field(description="Preparation instructions")


class MealPlan(BaseModel):
    grocery_list: list[str]
    meals: Annotated[list[Meal], Field(min_length=3, max_length=3)]

    def print(self):
        print("# Grocery list")
        for grocery in self.grocery_list:
            print(f"- {grocery}")
        print()
        print("# Meals")
        for i, meal in enumerate(self.meals):
            if i != 0:
                print()
            print(f"## {meal.name}")
            print("### Ingredients")
            for ingredient in meal.ingredients:
                print(f"- {ingredient}")
            print("### Steps")
            for j, step in enumerate(meal.steps, 1):
                print(f"{j}. {step}")
