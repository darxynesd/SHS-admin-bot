import json
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CHOOSING_ACTION, NEW_STORY_NAME, NEW_STORY_SEASON, NEW_STORY_SERIES, UPLOAD_PHOTOS, CONFIRM_CANCEL, VIEW_STORIES, VIEW_SEASON, VIEW_SERIES = range(9)

NAV_BUTTONS = ["Отмена", "Готово", "Новый сезон", "Новая серия"]

def load_data():
    try:
        with open('stories_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data):
    with open('stories_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def create_two_column_keyboard(items):
    keyboard = []
    row = []
    for i, item in enumerate(items):
        row.append(KeyboardButton(item))
        if (i + 1) % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    return keyboard

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = create_two_column_keyboard([
        "Рассылка", "Новая история",
        "Редактировать историю", "Все истории"
    ])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Привет! Админ-меню:\nВыбери действие:",
        reply_markup=reply_markup
    )
    return CHOOSING_ACTION

async def handle_action_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    data = load_data()

    if choice == "Новая история":
        await update.message.reply_text("Кукусики родная 😎\nНапиши название истории:", reply_markup=ReplyKeyboardRemove())
        return NEW_STORY_NAME

    elif choice == "Все истории":
        if not data:
            await update.message.reply_text("📭 Пока нет историй.")
            return CHOOSING_ACTION
        else:
            stories = list(data.keys())
            context.user_data['all_stories'] = stories
            keyboard = create_two_column_keyboard(stories + ["← Назад"])
            await update.message.reply_text("📚 Выбери историю:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
            return VIEW_STORIES

    elif choice == "Рассылка":
        await update.message.reply_text("✉️ Функция рассылки ещё не реализована.")
        return CHOOSING_ACTION

    elif choice == "Редактировать историю":
        await update.message.reply_text("🛠 Функция редактирования пока не реализована.")
        return CHOOSING_ACTION

    else:
        await update.message.reply_text("❌ Неизвестная команда. Выбери из меню.")
        return CHOOSING_ACTION

async def view_stories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice == "← Назад":
        return await start(update, context)

    data = load_data()
    if choice not in data:
        await update.message.reply_text("❌ История не найдена")
        return VIEW_STORIES

    context.user_data['current_story'] = choice
    seasons = list(data[choice].keys())
    keyboard = create_two_column_keyboard(seasons + ["← Назад"])
    await update.message.reply_text(f"📖 История: {choice}\nВыбери сезон:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return VIEW_SEASON

async def view_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    story = context.user_data.get('current_story')
    data = load_data()

    if choice == "← Назад":
        return await handle_action_selection(update, context)

    if story is None or choice not in data.get(story, {}):
        await update.message.reply_text("❌ Сезон не найден")
        return VIEW_SEASON

    context.user_data['current_season'] = choice
    series_list = list(data[story][choice].keys())
    keyboard = create_two_column_keyboard(series_list + ["← Назад"])
    await update.message.reply_text(f"📘 История: {story}, Сезон: {choice}\nВыбери серию:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return VIEW_SERIES

async def view_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    story = context.user_data.get('current_story')
    season = context.user_data.get('current_season')
    data = load_data()

    if choice == "← Назад":
        return await view_stories(update, context)

    if story is None or season is None or choice not in data.get(story, {}).get(season, {}):
        await update.message.reply_text("❌ Серия не найдена")
        return VIEW_SERIES

    photos = data[story][season][choice].get('photos', [])
    if photos:
        for i, file_id in enumerate(photos, 1):
            await update.message.reply_photo(photo=file_id, caption=f"📸 Фото {i}/{len(photos)}\n📖 {story} > Сезон {season} > Серия {choice}")
    else:
        await update.message.reply_text("📭 В этой серии пока нет фото")


    keyboard = create_two_column_keyboard(["← Назад", "🏠 Главное меню"])
    await update.message.reply_text("Выбери действие:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    return VIEW_SERIES


async def new_story_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    story_name = update.message.text.strip()
    if not story_name:
        await update.message.reply_text("❌ Название не может быть пустым. Попробуй снова:")
        return NEW_STORY_NAME

    context.user_data['story_name'] = story_name
    context.user_data['season'] = None
    context.user_data['series'] = None
    context.user_data['photos'] = []

    await update.message.reply_text(f"Название истории установлено: {story_name}\nНапиши номер сезона:")
    return NEW_STORY_SEASON

async def new_story_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    season = update.message.text.strip()
    if not season.isdigit():
        await update.message.reply_text("❌ Сезон должен быть числом. Попробуй снова:")
        return NEW_STORY_SEASON

    context.user_data['season'] = season
    await update.message.reply_text(f"Сезон {season} выбран. Напиши номер серии:")
    return NEW_STORY_SERIES

async def new_story_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    series = update.message.text.strip()
    if not series.isdigit():
        await update.message.reply_text("❌ Серия должна быть числом. Попробуй снова:")
        return NEW_STORY_SERIES

    context.user_data['series'] = series
    context.user_data['photos'] = []

    keyboard = create_two_column_keyboard(NAV_BUTTONS)
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"Серия {series} сезона {context.user_data['season']}.\nПришли фото для этой серии:",
        reply_markup=reply_markup
    )
    return UPLOAD_PHOTOS


async def upload_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text in NAV_BUTTONS:
        if text == "Отмена":
            await update.message.reply_text("❌ Уверена, что хочешь удалить все добавленные фото?", 
                                            reply_markup=ReplyKeyboardMarkup([["Нет", "Да"]], resize_keyboard=True))
            return CONFIRM_CANCEL
        elif text == "Готово":
            await save_current_story(context)
            await update.message.reply_text("✅ Серия сохранена!", reply_markup=ReplyKeyboardRemove())
            return await start(update, context)
        elif text == "Новая серия":
            context.user_data['series'] = str(int(context.user_data['series']) + 1)
            context.user_data['photos'] = []
            await update.message.reply_text(f"Серия {context.user_data['series']}.\nПришли фото:")
            return UPLOAD_PHOTOS
        elif text == "Новый сезон":
            context.user_data['season'] = str(int(context.user_data['season']) + 1)
            context.user_data['series'] = "1"
            context.user_data['photos'] = []
            await update.message.reply_text(f"Сезон {context.user_data['season']}, серия {context.user_data['series']}.\nПришли фото:")
            return UPLOAD_PHOTOS
        return UPLOAD_PHOTOS

    if not update.message.photo:
        await update.message.reply_text("❌ Нужно отправить фото.")
        return UPLOAD_PHOTOS


    for photo in update.message.photo:
        file_id = update.message.photo[-1].file_id
        
        context.user_data['photos'].append(file_id)
        break

    await update.message.reply_text(f"📸 {len(context.user_data['photos'])} фото добавлено.")
    return UPLOAD_PHOTOS

async def confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Да":
        context.user_data['photos'] = []
        await update.message.reply_text("❌ Все добавленные фото удалены.", reply_markup=ReplyKeyboardRemove())
        return await start(update, context)
    else:
        keyboard = create_two_column_keyboard(NAV_BUTTONS)
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Возврат к загрузке фото:", reply_markup=reply_markup)
        return UPLOAD_PHOTOS

async def save_current_story(context):
    story_name = context.user_data['story_name']
    season = context.user_data['season']
    series = context.user_data['series']
    photos = context.user_data.get('photos', [])

    if not photos:
        return

    data = load_data()
    if story_name not in data:
        data[story_name] = {}
    if season not in data[story_name]:
        data[story_name][season] = {}
    if series not in data[story_name][season]:
        data[story_name][season][series] = {"photos": []}

    data[story_name][season][series]['photos'].extend(photos)
    save_data(data)

# ===================== MAIN =====================
def main():
    application = Application.builder().token(config.ADMIN_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_action_selection)],
            NEW_STORY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_story_name)],
            NEW_STORY_SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_story_season)],
            NEW_STORY_SERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_story_series)],
            UPLOAD_PHOTOS: [MessageHandler((filters.PHOTO | filters.TEXT) & ~filters.COMMAND, upload_photos)],
            CONFIRM_CANCEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_cancel)],
            VIEW_STORIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_stories)],
            VIEW_SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_season)],
            VIEW_SERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_series)],
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)

    print("Админ-бот запущен и прослушивает вас...")
    application.run_polling()

if __name__ == '__main__':
    main()
