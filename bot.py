import logging
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import BOT_TOKEN, ADMIN_CHAT_ID, CONTACT_EMAIL
from questions import questions
from animals import animals

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

class QuizState(StatesGroup):
    waiting_for_answer = State()
    current_question = State()

user_answers = {}

def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🎯 Найти своё тотемное животное", callback_data="start_quiz"),
        InlineKeyboardButton("🐾 Что такое программа опеки?", callback_data="about_opeka"),
        InlineKeyboardButton("📞 Связаться с зоопарком", callback_data="contact")
    )
    return keyboard

def get_question_keyboard(question_id):
    q = questions[question_id - 1]
    keyboard = InlineKeyboardMarkup(row_width=1)
    for option in q["options"].keys():
        keyboard.add(InlineKeyboardButton(option, callback_data=f"ans_{question_id}_{option[:50]}"))
    return keyboard

def get_result_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🐾 Как стать опекуном?", callback_data="about_opeka"),
        InlineKeyboardButton("🔄 Пройти ещё раз", callback_data="restart"),
        InlineKeyboardButton("📤 Поделиться", callback_data="share")
    )
    return keyboard

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_answers[message.from_user.id] = {}
    
    welcome_text = (
        "🐘 *Добро пожаловать в викторину Московского зоопарка!*\n\n"
        "Ты когда-нибудь задумывался, какое животное — твой настоящий тотем?\n\n"
        "Ответь на 6 вопросов, и мы подскажем, кто живёт в твоей душе. "
        "А ещё ты узнаешь, как можешь помочь этому животному через программу опеки!\n\n"
        "👇 Нажми на кнопку, чтобы начать"
    )
    
    await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@dp.callback_query_handler(lambda c: c.data == "start_quiz")
async def start_quiz(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    user_answers[user_id] = {"scores": {}}
    
    await callback_query.message.edit_text(
        "🎯 *Вопрос 1 из 6*\n\n" + questions[0]["text"],
        reply_markup=get_question_keyboard(1),
        parse_mode="Markdown"
    )
    await state.set_state(QuizState.waiting_for_answer.state)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("ans_"), state=QuizState.waiting_for_answer)
async def process_answer(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    data = callback_query.data
    parts = data.split("_")
    question_id = int(parts[1])
    answer_text = "_".join(parts[2:])
    
    q = questions[question_id - 1]
    selected_option = None
    for option, scores in q["options"].items():
        if option.startswith(answer_text) or answer_text in option:
            selected_option = option
            break
    
    if selected_option and user_id in user_answers:
        scores = q["options"][selected_option]
        if "scores" not in user_answers[user_id]:
            user_answers[user_id]["scores"] = {}
        
        for animal, points in scores.items():
            user_answers[user_id]["scores"][animal] = user_answers[user_id]["scores"].get(animal, 0) + points
    
    if question_id < len(questions):
        next_q = questions[question_id]
        await callback_query.message.edit_text(
            f"🎯 *Вопрос {question_id + 1} из {len(questions)}*\n\n{next_q['text']}",
            reply_markup=get_question_keyboard(question_id + 1),
            parse_mode="Markdown"
        )
    else:
        scores = user_answers[user_id].get("scores", {})
        if scores:
            winner = max(scores, key=scores.get)
        else:
            winner = "manul"
        
        animal_info = animals.get(winner, animals["manul"])
        
        result_text = (
            f"🎉 *Твоё тотемное животное — {animal_info['emoji']} {animal_info['name']} {animal_info['emoji']}*\n\n"
            f"{animal_info['description']}\n\n"
            f"{animal_info['fact']}\n\n"
            "👇 Что дальше?"
        )
        
        user_answers[user_id]["result"] = winner
        
        try:
            with open(animal_info['image'], 'rb') as photo:
                await callback_query.message.delete()
                await callback_query.message.answer_photo(
                    photo=InputFile(photo),
                    caption=result_text,
                    reply_markup=get_result_keyboard(),
                    parse_mode="Markdown"
                )
        except FileNotFoundError:
            await callback_query.message.edit_text(
                result_text,
                reply_markup=get_result_keyboard(),
                parse_mode="Markdown"
            )
    
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "about_opeka")
async def about_opeka(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    result = user_answers.get(user_id, {}).get("result", "животного")
    animal_name = animals.get(result, animals["manul"])["name"] if result != "животного" else "животного"
    
    opeka_text = (
        "🐘 *Что такое программа «Возьми животное под опеку»?*\n\n"
        "Это возможность помочь Московскому зоопарку заботиться об обитателях. "
        "Сейчас в зоопарке живёт около 6000 животных, представляющих 1100 видов.\n\n"
        "Став опекуном, ты:\n"
        "• Получаешь почётный статус\n"
        "• Можешь круглый год навещать подопечного\n"
        "• Помогаешь улучшать условия для животных\n\n"
        f"🌟 *Стань опекуном для {animal_name} или другого животного!*\n\n"
        "💰 Стоимость опеки рассчитывается из ежедневного рациона питания.\n\n"
        "[Узнать больше на сайте](https://moscowzoo.ru/join/guardianship/)"
    )
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🦒 Перейти на сайт", url="https://moscowzoo.ru/join/guardianship/"),
        InlineKeyboardButton("📞 Связаться с сотрудником", callback_data="contact"),
        InlineKeyboardButton("« Назад к результату", callback_data="back_to_result")
    )
    
    await callback_query.message.edit_text(
        opeka_text,
        reply_markup=keyboard,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "contact")
async def contact(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    result = user_answers.get(user_id, {}).get("result", "")
    animal_name = animals.get(result, animals["manul"])["name"] if result else ""
    
    contact_text = (
        "📞 *Связаться с Московским зоопарком*\n\n"
        f"Вы прошли викторину и ваше тотемное животное — {animal_name}.\n\n"
        "📧 Email: opeka@moscowzoo.ru\n"
        "📞 Телефон: +7 499 255-00-93\n\n"
        "Если вы хотите оставить заявку на опеку, напишите на почту или позвоните. "
        "Сотрудники свяжутся с вами в ближайшее время.\n\n"
        "💡 *Совет:* при обращении укажите, что вы узнали о программе из Telegram-бота!"
    )
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("« Назад к результату", callback_data="back_to_result")
    )
    
    await callback_query.message.edit_text(
        contact_text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "back_to_result")
async def back_to_result(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    result = user_answers.get(user_id, {}).get("result", "manul")
    animal_info = animals.get(result, animals["manul"])
    
    result_text = (
        f"🎉 *Твоё тотемное животное — {animal_info['emoji']} {animal_info['name']} {animal_info['emoji']}*\n\n"
        f"{animal_info['description']}\n\n"
        f"{animal_info['fact']}\n\n"
        "👇 Что дальше?"
    )
    
    await callback_query.message.edit_text(
        result_text,
        reply_markup=get_result_keyboard(),
        parse_mode="Markdown"
    )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "restart")
async def restart(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    user_answers[user_id] = {"scores": {}}
    
    await callback_query.message.edit_text(
        "🎯 *Новая викторина!*\n\n" + questions[0]["text"],
        reply_markup=get_question_keyboard(1),
        parse_mode="Markdown"
    )
    await state.set_state(QuizState.waiting_for_answer.state)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "share")
async def share(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    result = user_answers.get(user_id, {}).get("result", "manul")
    animal_info = animals.get(result, animals["manul"])
    
    share_text = (
        f"Я прошёл(а) викторину Московского зоопарка!\n"
        f"Моё тотемное животное — {animal_info['emoji']} {animal_info['name']} {animal_info['emoji']}!\n\n"
        f"А ты знаешь, кто твой тотем? Пройди викторину:\n"
        f"https://t.me/YourBotUsername"
    )
    
    await callback_query.answer("Текст скопирован! Отправь его друзьям 📤", show_alert=True)
    await callback_query.message.answer(
        "📤 *Поделиться результатом:*\n\n"
        "Скопируй этот текст и отправь друзьям:\n"
        f"```\n{share_text}\n```\n"
        "Не забудь добавить картинку с животным!",
        parse_mode="Markdown"
    )

@dp.errors_handler()
async def errors_handler(update, exception):
    logging.error(f"Ошибка: {exception}")
    if ADMIN_CHAT_ID:
        await bot.send_message(ADMIN_CHAT_ID, f"Ошибка в боте: {exception}")
    return True

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
