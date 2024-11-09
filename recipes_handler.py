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

translator = Translator()

@router.message(Command("category_search_random"))
async def category_search_random(message: types.Message, state: FSMContext):
    args = message.text.split()

    if len(args) < 2:
        await message.answer("Пожалуйста, укажите количество рецептов. Пример: /category_search_random 3")
        return

    try:
        num_recipes = int(args[1])
    except ValueError:
        await message.answer("Ошибка: укажите целое число для количества рецептов.")
        return

    await state.set_data({'num_recipes': num_recipes})

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{THEMEALDB_API_URL}/categories.php") as response:
                data = await response.json()

                if 'categories' not in data or not data['categories']:
                    await message.answer("Не удалось получить категории. Попробуйте позже.")
                    return

                categories = [category['strCategory'] for category in data['categories']]
                buttons = [types.KeyboardButton(text=category) for category in categories]

                keyboard = types.ReplyKeyboardMarkup(
                    resize_keyboard=True,
                    one_time_keyboard=True,
                    keyboard=[[button] for button in buttons]
                )

                await message.answer("Выберите категорию блюда:", reply_markup=keyboard)
                await state.set_state(RecipeStates.waiting_for_category.state)

        except Exception as e:
            await message.answer("Произошла ошибка при получении категорий. Попробуйте позже.")

@router.message(RecipeStates.waiting_for_category)
async def category_selected(message: types.Message, state: FSMContext):
    category = message.text
    num_recipes = (await state.get_data()).get('num_recipes', 1)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{THEMEALDB_API_URL}/filter.php?c={category}") as response:
                data = await response.json()

                if 'meals' not in data or not data['meals']:
                    await message.answer("Рецепты не найдены для этой категории.")
                    return

                meals = random.sample(data['meals'], min(len(data['meals']), num_recipes))

                meal_names = [meal['strMeal'] for meal in meals]
                meal_ids = [meal['idMeal'] for meal in meals]

                await state.set_data({'meal_ids': meal_ids, 'meals': meals})

                translated_names = [translator.translate(name, dest='ru').text for name in meal_names]
                buttons = [types.KeyboardButton(text=name) for name in translated_names]
                keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True,
                                                     keyboard=[[button] for button in buttons])

                await message.answer("Выберите рецепт для подробностей:", reply_markup=keyboard)
                await state.set_state(RecipeStates.waiting_for_recipes.state)

        except Exception as e:
            await message.answer("Произошла ошибка при получении рецептов. Попробуйте позже.")

@router.message(RecipeStates.waiting_for_recipes)
async def recipe_selected(message: types.Message, state: FSMContext):
    selected_recipe_name = message.text
    logging.info(f"User selected recipe: {selected_recipe_name}")

    data = await state.get_data()
    meal_ids = data.get('meal_ids')
    meals = data.get('meals', [])

    if not meal_ids:
        await message.answer("Не удалось получить список рецептов.")
        return

    selected_id = None
    for meal in meals:
        translated_name = translator.translate(meal['strMeal'], dest='ru').text
        if translated_name == selected_recipe_name:
            selected_id = meal['idMeal']
            break

    if selected_id is None:
        await message.answer("Не удалось найти выбранный рецепт.")
        return

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{THEMEALDB_API_URL}/lookup.php?i={selected_id}") as response:
                data = await response.json()

                if 'meals' not in data or not data['meals']:
                    await message.answer("Не удалось найти рецепт.")
                    return

                meal = data['meals'][0]

                translated_name = translator.translate(meal['strMeal'], dest='ru').text
                translated_instructions = translator.translate(meal['strInstructions'], dest='ru').text

                ingredients = []
                for i in range(1, 21):
                    ingredient = meal.get(f"strIngredient{i}")
                    measure = meal.get(f"strMeasure{i}")
                    if ingredient:
                        translated_ingredient = translator.translate(ingredient, dest='ru').text  # Переводим ингредиент
                        ingredients.append(f"{translated_ingredient} ({measure})" if measure else translated_ingredient)

                response_message = f"Рецепт: {translated_name}\n\nОписание: {translated_instructions}\n\nИнгредиенты:\n" + "\n".join(
                    ingredients)

                await message.answer(response_message)

        except Exception as e:
            logging.error(f"Error while fetching details for recipe {selected_recipe_name}: {e}")
            await message.answer("Произошла ошибка при получении подробностей о рецепте. Попробуйте позже.")