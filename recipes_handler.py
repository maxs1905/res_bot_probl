import random
import aiohttp
import logging
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from googletrans import Translator
from token_data import THEMEALDB_API_URL

router = Router()
class RecipeStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_recipes = State()
    showing_recipe_details = State()

@router.message(Command("category_search_random"))
async def category_search_random(message: types.Message, state: FSMContext):
    logging.info(f"Command /category_search_random received from {message.from_user.id}")

    args = message.text.split()

    if len(args) < 2:
        await message.answer("Пожалуйста, укажите количество рецептов. Пример: /category_search_random 3")
        return

    try:
        num_recipes = int(args[1])  # Преобразуем аргумент в число
    except ValueError:
        await message.answer("Ошибка: укажите целое число для количества рецептов.")
        return

    await state.set_data({'num_recipes': num_recipes})
    logging.info(f"Number of recipes to fetch: {num_recipes}")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{THEMEALDB_API_URL}/categories.php") as response:
                data = await response.json()

                logging.info(f"Categories API Response: {data}")


                if 'categories' not in data or not data['categories']:
                    logging.error("No categories found in the API response.")
                    await message.answer("Не удалось получить категории. Попробуйте позже.")
                    return

                categories = [category['strCategory'] for category in data['categories']]


                buttons = [types.KeyboardButton(text=category) for category in categories]
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[buttons])

                await message.answer("Выберите категорию блюда:", reply_markup=keyboard)
                await state.set_state(RecipeStates.waiting_for_category.state)

        except Exception as e:
            logging.error(f"Error while fetching categories: {e}")
            await message.answer("Произошла ошибка при получении категорий. Попробуйте позже.")


@router.message(RecipeStates.waiting_for_category)
async def category_selected(message: types.Message, state: FSMContext):
    logging.info(f"Category selected: {message.text}")

    category = message.text

    await state.set_data({'category': category})

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{THEMEALDB_API_URL}/filter.php?c={category}") as response:
                data = await response.json()

                logging.info(f"Recipes by category response: {data}")

                if 'meals' not in data or not data['meals']:
                    logging.error(f"No meals found for category: {category}")
                    await message.answer("Рецепты не найдены для этой категории.")
                    return

                meals = data['meals']
                num_recipes = await state.get_data()
                num_recipes = num_recipes.get('num_recipes', 1)

                selected_meals = random.sample(meals, min(len(meals), num_recipes))

                meal_names = [meal['strMeal'] for meal in selected_meals]

                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
                for name in meal_names:
                    keyboard.add(types.KeyboardButton(name))

                await message.answer("Выберите рецепт для подробностей:", reply_markup=keyboard)
                await state.set_state(RecipeStates.waiting_for_recipes.state)

        except Exception as e:
            logging.error(f"Error while fetching recipes for category {category}: {e}")
            await message.answer("Произошла ошибка при получении рецептов. Попробуйте позже.")


@router.message(RecipeStates.waiting_for_recipes)
async def recipe_selected(message: types.Message, state: FSMContext):
    selected_recipe_name = message.text
    logging.info(f"Recipe selected: {selected_recipe_name}")

    data = await state.get_data()
    category = data.get('category')

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{THEMEALDB_API_URL}/search.php?s={selected_recipe_name}") as response:
                data = await response.json()

                logging.info(f"Recipe details API Response: {data}")

                meal = data.get('meals', [])[0] if data.get('meals') else None
                if not meal:
                    await message.answer("Не удалось найти рецепт.")
                    return

                translator = Translator()
                translated_name = translator.translate(meal['strMeal'], dest='ru').text
                translated_instructions = translator.translate(meal['strInstructions'], dest='ru').text

                ingredients = []
                for i in range(1, 21):
                    ingredient = meal.get(f"strIngredient{i}")
                    measure = meal.get(f"strMeasure{i}")
                    if ingredient:
                        ingredients.append(f"{ingredient} ({measure})")

                response = f"Рецепт: {translated_name}\n\nОписание: {translated_instructions}\n\nИнгредиенты:\n" + "\n".join(
                    ingredients)

                await message.answer(response)
                await state.set_state(RecipeStates.showing_recipe_details.state)

        except Exception as e:
            logging.error(f"Error while fetching details for recipe {selected_recipe_name}: {e}")
            await message.answer("Произошла ошибка при получении подробностей о рецепте. Попробуйте позже.")