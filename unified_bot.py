import json
import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Состояния
SELECTING_STORY, SELECTING_SEASON, SELECTING_SERIES = range(3)

def load_stories():
    """Загружает истории из файла admin бота"""
    try:
        with open('stories_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_users():
    """Загружает список пользователей"""
    try:
        with open('users.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_users(users):
    """Сохраняет список пользователей"""
    with open('users.json', 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def create_two_column_keyboard(items):
    """Создает клавиатуру в 2 колонки"""
    if not items:
        return []
    
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

def build_path(story, season, series):
    """Строит путь для отображения"""
    return f"{story} > Сезон {season} > Серия {series}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало работы - регистрация и показ историй"""
    # Регистрация пользователя
    users = load_users()
    user_id = str(update.effective_user.id)
    
    if user_id not in users:
        users.append(user_id)
        save_users(users)
        logger.info(f"Новый пользователь: {user_id}")
    
    # Загрузка историй
    data = load_stories()
    
    if not data:
        await update.message.reply_text(
            '📭 Пока нет историй! Загляни позже.',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Сброс пути
    context.user_data['path'] = {}
    
    # Показываем список историй
    stories = list(data.keys())
    keyboard = create_two_column_keyboard(stories + ["🏠 Главное меню"])
    
    await update.message.reply_text(
        '📚 Добро пожаловать! Выбери историю:',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return SELECTING_STORY

async def handle_story_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора истории"""
    choice = update.message.text.strip()
    
    if choice == "🏠 Главное меню":
        return await start(update, context)
    
    data = load_stories()
    
    if choice not in data:
        await update.message.reply_text("❌ История не найдена")
        return await start(update, context)
    
    # Сохраняем выбор
    context.user_data['path'] = {'story': choice}
    
    # Показываем сезоны
    seasons = list(data[choice].keys())
    keyboard = create_two_column_keyboard(seasons + ["← Назад", "🏠 Главное меню"])
    
    await update.message.reply_text(
        f"📖 История: {choice}\nВыбери сезон:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return SELECTING_SEASON

async def handle_season_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора сезона"""
    choice = update.message.text.strip()
    path = context.user_data.get('path', {})
    
    if choice == "🏠 Главное меню":
        return await start(update, context)
    
    if choice == "← Назад":
        return await start(update, context)
    
    data = load_stories()
    story = path.get('story')
    
    if not story or choice not in data.get(story, {}):
        await update.message.reply_text("❌ Сезон не найден")
        return SELECTING_SEASON
    
    # Сохраняем выбор
    path['season'] = choice
    context.user_data['path'] = path
    
    # Показываем серии
    series_list = list(data[story][choice].keys())
    keyboard = create_two_column_keyboard(series_list + ["← Назад", "🏠 Главное меню"])
    
    await update.message.reply_text(
        f"📘 История: {story}, Сезон: {choice}\nВыбери серию:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return SELECTING_SERIES

async def handle_series_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора серии и показ медиа"""
    choice = update.message.text.strip()
    path = context.user_data.get('path', {})
    
    if choice == "🏠 Главное меню":
        return await start(update, context)
    
    if choice == "← Назад":
        # Возврат к выбору сезона
        story = path.get('story')
        data = load_stories()
        seasons = list(data.get(story, {}).keys())
        keyboard = create_two_column_keyboard(seasons + ["← Назад", "🏠 Главное меню"])
        
        await update.message.reply_text(
            f"📖 История: {story}\nВыбери сезон:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return SELECTING_SEASON
    
    data = load_stories()
    story = path.get('story')
    season = path.get('season')
    
    if not story or not season or choice not in data.get(story, {}).get(season, {}):
        await update.message.reply_text("❌ Серия не найдена")
        return SELECTING_SERIES
    
    # Получаем медиа
    series_data = data[story][season][choice]
    media_list = series_data.get("media", [])
    
    if not media_list:
        await update.message.reply_text("📭 В этой серии пока нет файлов")
    else:
        # Отправляем медиа группами по 10
        groups = [media_list[i:i+10] for i in range(0, len(media_list), 10)]
        
        for group in groups:
            media_group = []
            for idx, item in enumerate(group, 1):
                caption = f"{idx}/{len(media_list)}\n📍 {build_path(story, season, choice)}"
                
                if item["type"] == "photo":
                    media_group.append(InputMediaPhoto(
                        media=item["file_id"], 
                        caption=caption if idx == 1 else ""
                    ))
                elif item["type"] == "video":
                    media_group.append(InputMediaVideo(
                        media=item["file_id"], 
                        caption=caption if idx == 1 else ""
                    ))
                elif item["type"] == "document":
                    # Документы отправляем отдельно
                    await update.message.reply_document(
                        document=item["file_id"], 
                        caption=caption
                    )
            
            if media_group:
                await update.message.reply_media_group(media_group)
                await asyncio.sleep(0.5)  # Небольшая задержка между группами
    
    # Предлагаем выбрать другую серию или вернуться
    keyboard = create_two_column_keyboard(["← Назад", "🏠 Главное меню"])
    await update.message.reply_text(
        "Выбери действие:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    
    # Остаемся в том же состоянии для повторного выбора
    return SELECTING_SERIES

def main():
    application = Application.builder().token(config.USER_BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECTING_STORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_story_selection)
            ],
            SELECTING_SEASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_season_selection)
            ],
            SELECTING_SERIES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_series_selection)
            ],
        },
        fallbacks=[CommandHandler('start', start)],
    )
    
    application.add_handler(conv_handler)
    
    print("🤖 Юзер-бот запущен! Ожидает пользователей...")
    application.run_polling()

if __name__ == '__main__':
    main()