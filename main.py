import json
import logging
import asyncio
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#states - добавлены 3 новых состояния
(
    CHOOSING_ACTION,
    NEW_STORY_NAME,
    NEW_STORY_SEASON,
    NEW_STORY_SERIES,
    UPLOAD_MEDIA,
    CONFIRM_CANCEL,
    VIEW_STORIES,
    VIEW_SEASON,
    VIEW_SERIES,
    BROADCAST_TEXT,
    BROADCAST_CONFIRM,
    EDIT_STORY_SELECT,
    EDIT_SEASON_SELECT,
    EDIT_SERIES_SELECT,
    EDIT_RENAME_STORY,
    EDIT_RENAME_SEASON,
    EDIT_RENAME_SERIES,
    EDIT_ADD_EPISODE,
    EDIT_ADD_SEASON,           #new
    EDIT_ADD_SERIES_SELECT,    
    EDIT_ADD_SERIES,          
    CONFIRM_DELETE_STORY,
    CONFIRM_DELETE_SEASON,
    CONFIRM_DELETE_SERIES,
    CONFIRM_CLEAR_SERIES,
)=range(25)

#btns
UPLOAD_NAV_BUTTONS = ["❌ Отмена","✅ Готово","💾 Сохранить и выйти",  "📎 Новая серия","🆕 Новый сезон"]
BACK_HOME_BUTTONS = ["← Назад","🏠 Главное меню"]

def load_stories():
    try:
        with open('stories_data.json','r', encoding ='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_stories(data):
    with open('stories_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_users():
    try:
        with open('users.json','r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def create_two_column_keyboard(items):
    if not items:
        return []
    keyboard=[]
    row =[]
    for i, item in enumerate(items):
        row.append(KeyboardButton(item))
        if (i+1) %2==0:
            keyboard.append(row)
            row=[]
    if row:
        keyboard.append(row)
    return keyboard

def build_path(story, season, series):
    return f"{story} > Сезон {season} > Серия {series}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard=create_two_column_keyboard([
        "📤 Рассылка",
        "🆕 Новая история",
        "✏️ Редактировать историю",
        "📚 Все истории"
    ])
    reply_markup =ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("👋 Админ-панель\nВыбери действие:", reply_markup=reply_markup)
    return CHOOSING_ACTION

#main action bttns
async def handle_action_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text.strip()
    if choice =="← Назад":
        return await start(update, context)
    if choice =="🆕 Новая история":
        await update.message.reply_text("Кукусики родная 😎\nНапиши название истории:", reply_markup=ReplyKeyboardRemove())
        return NEW_STORY_NAME
    elif choice== "📚 Все истории":
        data= load_stories()
        if not data:
            await update.message.reply_text("📭 Пока нет историй.")
            return CHOOSING_ACTION
        stories =list(data.keys())
        context.user_data['all_stories']= stories
        keyboard=create_two_column_keyboard(stories + ["← Назад"])
        await update.message.reply_text("📚 Выбери историю:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return VIEW_STORIES
    elif choice=="📤 Рассылка":
        await update.message.reply_text("✉️ Введи текст рассылки (можно добавить фото/видео):")
        return BROADCAST_TEXT
    elif choice=="✏️ Редактировать историю":
        data =load_stories()
        if not data:
            await update.message.reply_text("📭 Нет историй для редактирования.")
            return CHOOSING_ACTION
        stories= list(data.keys())
        keyboard =create_two_column_keyboard(stories + ["← Назад"])
        await update.message.reply_text("✏️ Выбери историю для редактирования:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return EDIT_STORY_SELECT
    else:
        await update.message.reply_text("❌ Неизвестная команда.")
        return CHOOSING_ACTION

#creation
async def new_story_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name=update.message.text.strip()
    if not name:
        await update.message.reply_text("❌ Название не может быть пустым. Попробуй снова:")
        return NEW_STORY_NAME
    context.user_data.update({
        'story_name':name,
        'season':None,
        'series': None,
        'pending_media': []
    })
    await update.message.reply_text(f"✅ Название: {name}\nНапиши номер сезона:")
    return NEW_STORY_SEASON

async def new_story_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    season =update.message.text.strip()
    if not season.isdigit() or int(season) <= 0:
        await update.message.reply_text("❌ Сезон должен быть положительным числом. Попробуй снова:")
        return NEW_STORY_SEASON
    context.user_data['season']= season
    await update.message.reply_text(f"✅ Сезон: {season}\nНапиши номер серии:")
    return NEW_STORY_SERIES

async def new_story_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    series= update.message.text.strip()
    if not series.isdigit() or int(series)<= 0:
        await update.message.reply_text("❌ Серия должна быть положительным числом. Попробуй снова:")
        return NEW_STORY_SERIES
    context.user_data['series'] =series
    context.user_data['pending_media'] = []

    keyboard = create_two_column_keyboard(UPLOAD_NAV_BUTTONS)
    await update.message.reply_text(
        f"✅ Серия: {series}\nПришли фото, видео или документы:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return UPLOAD_MEDIA

async def upload_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text =="← Назад":
        story= context.user_data.get('story_name', '...')
        season= context.user_data.get('season', '...')
        await update.message.reply_text(
            f"Возврат к вводу серии.\nИстория: {story}, Сезон: {season}",
            reply_markup=ReplyKeyboardRemove()
        )
        return NEW_STORY_SERIES

    if text in UPLOAD_NAV_BUTTONS:
        if text=="❌ Отмена":
            await update.message.reply_text("⚠️ Уверена, что хочешь удалить все добавленные файлы?",
                                            reply_markup=ReplyKeyboardMarkup([["Нет", "Да"]], resize_keyboard=True))
            return CONFIRM_CANCEL
        elif text=="✅ Готово":
            await save_pending_media(context)
            await send_summary_message(update, context)
            context.user_data['pending_media'] = []
            await update.message.reply_text("✅ Контент сохранён. Можно прислать ещё файлы или выбрать действие:")
            return UPLOAD_MEDIA
        elif text =="💾 Сохранить и выйти":
            await save_pending_media(context)
            await send_summary_message(update, context)
            return await start(update, context)
        elif text==  "📎 Новая серия":
            await save_pending_media(context)
            current = int(context.user_data['series'])
            context.user_data['series'] = str(current + 1)
            context.user_data['pending_media'] = []
            await update.message.reply_text(f"📎 Серия {context.user_data['series']}. Пришли файлы:")
            return UPLOAD_MEDIA
        elif text=="🆕 Новый сезон":
            await save_pending_media(context)
            current_season = int(context.user_data['season'])
            context.user_data['season'] = str(current_season + 1)
            context.user_data['series'] = "1"
            context.user_data['pending_media'] = []
            await update.message.reply_text(f"🆕 Сезон {context.user_data['season']}, серия 1. Пришли файлы:")
            return UPLOAD_MEDIA
        return UPLOAD_MEDIA



#Media processing
    media_item= None
    if update.message.photo:
        media_item = {"type": "photo", "file_id": update.message.photo[-1].file_id}
    elif update.message.video:
        media_item= {"type": "video", "file_id": update.message.video.file_id}
    elif update.message.document:
        media_item ={"type": "document", "file_id": update.message.document.file_id}
    else:
        await update.message.reply_text("❌ Поддерживаются только фото, видео и документы.")
        return UPLOAD_MEDIA

    context.user_data['pending_media'].append(media_item)
    return UPLOAD_MEDIA

async def confirm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text=="Да":
        context.user_data['pending_media'] = []
        await update.message.reply_text("❌ Все файлы удалены.", reply_markup=ReplyKeyboardRemove())
        return await start(update, context)
    else:
        keyboard = create_two_column_keyboard(UPLOAD_NAV_BUTTONS)
        await update.message.reply_text("Возврат к загрузке:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return UPLOAD_MEDIA

async def save_pending_media(context: ContextTypes.DEFAULT_TYPE):
    data= load_stories()
    story =context.user_data['story_name']
    season=context.user_data['season']
    series= context.user_data['series']
    pending =context.user_data.get('pending_media', [])

    if not pending:
        return



    if story not in data:
        data[story]={}
    if season not in data[story]:
        data[story][season]= {}
    if series not in data[story][season]:
        data[story][season][series]= {"media": []}

    data[story][season][series]["media"].extend(pending)
    save_stories(data)

async def send_summary_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    story=context.user_data['story_name']
    season =context.user_data['season']
    series= context.user_data['series']
    data = load_stories()
    total_media= len(data.get(story, {}).get(season, {}).get(series, {}).get("media", []))

    photos=videos=docs=0
    for item in context.user_data.get('pending_media', []):
        t=item["type"]
        if t =="photo": photos += 1
        elif t== "video": videos +=1
        elif t=="document": docs +=1

    parts = []
    if photos: parts.append(f"Фото: {photos}")
    if videos: parts.append(f"Видео: {videos}")
    if docs: parts.append(f"Документы: {docs}")

    summary= f"✅ Контент добавлен!\n📍 Путь: {build_path(story, season, series)}\n📎 Файлов: {total_media}"
    if parts:
        summary+= f" ({', '.join(parts)})"

    await update.message.reply_text(summary)

#viewing
async def view_stories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice= update.message.text
    if choice=="← Назад":
        return await start(update, context)
    
    data=load_stories()
    if not data or choice not in data:
        await update.message.reply_text("❌ История не найдена")
        return await start(update, context)

    context.user_data['current_story'] = choice
    seasons = list(data[choice].keys())
    keyboard = create_two_column_keyboard(seasons + ["← Назад"])
    await update.message.reply_text(
        f"📖 История: {choice}\nВыбери сезон:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return VIEW_SEASON

async def view_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice= update.message.text
    if choice== "← Назад":
        data=load_stories()
        if not data:
            return await start(update, context)
        stories = list(data.keys())
        keyboard = create_two_column_keyboard(stories+ ["← Назад"])
        await update.message.reply_text("📚 Выбери историю:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return VIEW_STORIES

    story = context.user_data.get('current_story')
    data = load_stories()
    if not story or choice not in data.get(story, {}):
        await update.message.reply_text("❌ Сезон не найден")
        if not data:
            return await start(update, context)
        stories= list(data.keys())
        keyboard=create_two_column_keyboard(stories + ["← Назад"])
        await update.message.reply_text("📚 Выбери историю:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return VIEW_STORIES

    context.user_data['current_season']=choice
    series_list=list(data[story][choice].keys())
    keyboard=create_two_column_keyboard(series_list + ["← Назад"])
    await update.message.reply_text(
        f"📘 История: {story}, Сезон: {choice}\nВыбери серию:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return VIEW_SERIES

async def view_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice= update.message.text
    if choice=="← Назад":
        story = context.user_data.get('current_story')
        if not story:
            return await start(update, context)
        data =load_stories()
        if story not in data:
            return await start(update, context)
        seasons= list(data[story].keys())
        keyboard=create_two_column_keyboard(seasons + ["← Назад"])
        await update.message.reply_text(
            f"📖 История: {story}\nВыбери сезон:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return VIEW_SEASON
    if choice=="🏠 Главное меню":
        return await start(update, context)

    story = context.user_data.get('current_story')
    season = context.user_data.get('current_season')
    if not story or not season:
        return await start(update, context)

    data=load_stories()
    series_data =data.get(story, {}).get(season, {}).get(choice, {})
    media_list=series_data.get("media", [])

    if not media_list:
        await update.message.reply_text("📭 В этой серии пока нет файлов")
    else:
        groups=[media_list[i:i+10] for i in range(0,len(media_list),10)]
        for group in groups:
            media_group =[]
            for idx, item in enumerate(group, 1):
                caption = f"{idx}/{len(media_list)}\n📍 {build_path(story, season, choice)}"
                if item["type"]== "photo":
                    media_group.append(InputMediaPhoto(media=item["file_id"], caption=caption if idx == 1 else ""))
                elif item["type"]== "video":
                    media_group.append(InputMediaVideo(media=item["file_id"], caption=caption if idx == 1 else ""))
                elif item["type"] =="document":
                    await update.message.reply_document(document=item["file_id"], caption=caption)
            if media_group:
                await update.message.reply_media_group(media_group)

    keyboard =create_two_column_keyboard(["🗑 Удалить серию", "🧹 Очистить серию", "✏️ Переименовать серию"] + BACK_HOME_BUTTONS)
    await update.message.reply_text("Выбери действие:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    context.user_data['edit_series'] = choice
    return EDIT_SERIES_SELECT




#changing
async def edit_story_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    if choice =="← Назад":
        return await start(update, context)
    data =load_stories()
    if not data or choice not in data:
        await update.message.reply_text("❌ История не найдена")
        return await start(update, context)
    
    context.user_data['edit_story'] = choice
    context.user_data['story_name'] = choice 
    

    seasons = list(data[choice].keys())
    keyboard = create_two_column_keyboard(
        seasons + ["➕ Добавить сезон", "➕ Добавить серию", "← Назад"]
    )
    await update.message.reply_text(
        f"📖 Редактирование: {choice}\nВыбери сезон или действие:", 
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return EDIT_SEASON_SELECT

async def edit_season_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice =update.message.text
    
    if choice== "← Назад":
        return await start(update, context)
    
    story = context.user_data.get('edit_story')
    if not story:
        return await start(update, context)
    
  
    if choice == "➕ Добавить сезон":
        await update.message.reply_text(
            "🆕 Введи номер нового сезона:", 
            reply_markup=ReplyKeyboardRemove()
        )
        return EDIT_ADD_SEASON
    
    if choice == "➕ Добавить серию":

        data = load_stories()
        seasons = list(data.get(story, {}).keys())
        if not seasons:
            await update.message.reply_text("❌ Сначала создай сезон!")
            return EDIT_SEASON_SELECT
        
        keyboard = create_two_column_keyboard(seasons + ["← Назад"])
        await update.message.reply_text(
            "📎 Выбери сезон для добавления серии:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return EDIT_ADD_SERIES_SELECT

    if choice=="🗑 Удалить историю":
        await update.message.reply_text("⚠️ Уверена? Это удалит ВСЁ содержимое истории!", 
                                        reply_markup=ReplyKeyboardMarkup([["Нет", "Да"]], resize_keyboard=True))
        return CONFIRM_DELETE_STORY
    
    if choice=="✏️ Переименовать историю":
        await update.message.reply_text("Новое название истории:")
        return EDIT_RENAME_STORY
    

    data = load_stories()
    if choice not in data.get(story, {}):
        await update.message.reply_text("❌ Сезон не найден")
        seasons = list(data.get(story, {}).keys())
        keyboard = create_two_column_keyboard(
            seasons + ["➕ Добавить сезон", "➕ Добавить серию", "← Назад"]
        )
        await update.message.reply_text(
            f"📖 Редактирование: {story}\nВыбери сезон или действие:", 
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return EDIT_SEASON_SELECT
    
 
    context.user_data['edit_season'] = choice
    context.user_data['season'] = choice  
    
    series_list = list(data[story][choice].keys())
    keyboard = create_two_column_keyboard([
        "🗑 Удалить сезон",
        "✏️ Переименовать сезон",
        "← Назад"
    ])
    await update.message.reply_text(
        f"📁 Сезон: {choice}\nСерии: {', '.join(series_list) if series_list else 'пока нет'}\nВыбери действие:", 
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return EDIT_SERIES_SELECT



async def edit_add_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод номера нового сезона"""
    season = update.message.text.strip()
    
    if not season.isdigit() or int(season) <= 0:
        await update.message.reply_text("❌ Сезон должен быть положительным числом. Попробуй снова:")
        return EDIT_ADD_SEASON
    
    story = context.user_data['edit_story']
    data = load_stories()
    

    if season in data.get(story, {}):
        await update.message.reply_text(f"❌ Сезон {season} уже существует! Введи другой номер:")
        return EDIT_ADD_SEASON
    
   
    context.user_data['season'] = season
    context.user_data['series'] = "1"
    context.user_data['pending_media'] = []
    
    await update.message.reply_text(
        f"✅ Сезон {season} создан!\nТеперь добавь серию 1.\nПришли фото, видео или документы:",
        reply_markup=ReplyKeyboardMarkup(create_two_column_keyboard(UPLOAD_NAV_BUTTONS), resize_keyboard=True)
    )
    return UPLOAD_MEDIA

async def edit_add_series_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор сезона для добавления новой серии"""
    choice = update.message.text
    
    if choice == "← Назад":
        return await edit_story_select(update, context)
    
    story = context.user_data['edit_story']
    data = load_stories()
    
    if choice not in data.get(story, {}):
        await update.message.reply_text("❌ Сезон не найден")
        seasons = list(data.get(story, {}).keys())
        keyboard = create_two_column_keyboard(seasons + ["← Назад"])
        await update.message.reply_text(
            "📎 Выбери сезон для добавления серии:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return EDIT_ADD_SERIES_SELECT
    
    context.user_data['season'] = choice
    await update.message.reply_text(
        f"📁 Сезон: {choice}\nВведи номер новой серии:",
        reply_markup=ReplyKeyboardRemove()
    )
    return EDIT_ADD_SERIES

async def edit_add_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод номера новой серии в существующем сезоне"""
    series = update.message.text.strip()
    
    if not series.isdigit() or int(series) <= 0:
        await update.message.reply_text("❌ Серия должна быть положительным числом. Попробуй снова:")
        return EDIT_ADD_SERIES
    
    story = context.user_data['edit_story']
    season = context.user_data['season']
    data = load_stories()
    if series in data.get(story, {}).get(season, {}):
        await update.message.reply_text(f"❌ Серия {series} уже существует в этом сезоне! Введи другой номер:")
        return EDIT_ADD_SERIES
    

    context.user_data['story_name'] = story 
    context.user_data['series'] = series
    context.user_data['pending_media'] = []
    
    await update.message.reply_text(
        f"✅ Серия: {series}\nПришли фото, видео или документы:",
        reply_markup=ReplyKeyboardMarkup(create_two_column_keyboard(UPLOAD_NAV_BUTTONS), resize_keyboard=True)
    )
    return UPLOAD_MEDIA



async def edit_series_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice=update.message.text
    if choice=="← Назад":
        return await view_series(update, context)
    if choice =="🏠 Главное меню":
        return await start(update, context)

    if choice=="🗑 Удалить серию":
        await update.message.reply_text("⚠️ Уверена, что хочешь удалить эту серию?", 
                                        reply_markup=ReplyKeyboardMarkup([["Нет", "Да"]], resize_keyboard=True))
        return CONFIRM_DELETE_SERIES
    if choice=="🧹 Очистить серию":
        await update.message.reply_text("⚠️ Уверена, что хочешь удалить ВСЕ файлы из серии (серия останется)?", 
                                        reply_markup=ReplyKeyboardMarkup([["Нет", "Да"]], resize_keyboard=True))
        return CONFIRM_CLEAR_SERIES
    if choice=="✏️ Переименовать серию":
        await update.message.reply_text("Новый номер серии:")
        return EDIT_RENAME_SERIES

    #if sud bttn
    await update.message.reply_text("Выбери действие из меню.")
    return await view_series(update, context)

#Renaming
async def edit_rename_story(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name=update.message.text.strip()
    if not new_name:
        await update.message.reply_text("❌ Название не может быть пустым.")
        return EDIT_RENAME_STORY
    old_name=context.user_data['edit_story']
    data =load_stories()
    if new_name in data:
        await update.message.reply_text("❌ История с таким названием уже существует.")
        return EDIT_RENAME_STORY
    data[new_name] =data.pop(old_name)
    save_stories(data)
    await update.message.reply_text(f"✅ История переименована в: {new_name}")
    return await start(update, context)

async def edit_rename_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name= update.message.text.strip()
    if not new_name.isdigit():
        await update.message.reply_text("❌ Номер сезона должен быть числом.")
        return EDIT_RENAME_SEASON
    story=context.user_data['edit_story']
    old_name = context.user_data['edit_season']
    data =load_stories()
    if new_name in data.get(story, {}):
        await update.message.reply_text("❌ Сезон с таким номером уже существует в этой истории.")
        return EDIT_RENAME_SEASON
    data[story][new_name]=data[story].pop(old_name)
    save_stories(data)
    await update.message.reply_text(f"✅ Сезон переименован в: {new_name}")
    return await start(update, context)

async def edit_rename_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text.strip()
    if not new_name.isdigit():
        await update.message.reply_text("❌ Номер серии должен быть числом.")
        return EDIT_RENAME_SERIES
    story =context.user_data['current_story']
    season=context.user_data['current_season']
    old_name=context.user_data['edit_series']
    data =load_stories()
    if new_name in data.get(story, {}).get(season,{}):
        await update.message.reply_text("❌ Серия с таким номером уже существует в этом сезоне.")
        return EDIT_RENAME_SERIES
    data[story][season][new_name] =data[story][season].pop(old_name)
    save_stories(data)
    await update.message.reply_text(f"✅ Серия переименована в: {new_name}")
    return await start(update, context)



# Deletion Confirmation
async def confirm_delete_story(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text=="Да":
        story= context.user_data['edit_story']
        data =load_stories()
        del data[story]
        save_stories(data)
        await update.message.reply_text(f"✅ История '{story}' удалена.")
    return await start(update, context)

async def confirm_delete_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Да":
        story= context.user_data['edit_story']
        season=context.user_data['edit_season']
        data= load_stories()
        del data[story][season]
        if not data[story]:
            del data[story]
        save_stories(data)
        await update.message.reply_text(f"✅ Сезон '{season}' удалён.")
    return await start(update, context)

async def confirm_delete_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "Да":
        story =context.user_data['current_story']
        season= context.user_data['current_season']
        series =context.user_data['edit_series']
        data =load_stories()
        del data[story][season][series]
        if not data[story][season]:
            del data[story][season]
        if not data[story]:
            del data[story]
        save_stories(data)
        await update.message.reply_text(f"✅ Серия '{series}' удалена.")
    return await start(update, context)

async def confirm_clear_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text=="Да":
        story= context.user_data['current_story']
        season=context.user_data['current_season']
        series =context.user_data['edit_series']
        data  =load_stories()
        data[story][season][series]["media"] = []
        save_stories(data)
        await update.message.reply_text(f"✅ Все файлы из серии '{series}' удалены.")
    return await start(update, context)




#spam
async def broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['broadcast_text'] = update.message.text
    context.user_data['broadcast_media'] = None
    if update.message.photo:
        context.user_data['broadcast_media'] = ("photo", update.message.photo[-1].file_id)
    elif update.message.video:
        context.user_data['broadcast_media'] = ("video", update.message.video.file_id)
    
    await update.message.reply_text("🔍 Превью рассылки:")
    if context.user_data['broadcast_media']:
        media_type, file_id = context.user_data['broadcast_media']
        if media_type =="photo":
            await update.message.reply_photo(photo=file_id, caption=context.user_data['broadcast_text'])
        elif media_type== "video":
            await update.message.reply_video(video=file_id, caption=context.user_data['broadcast_text'])
    else:
        await update.message.reply_text(context.user_data['broadcast_text'])

    await update.message.reply_text(
        "📤 Отправить всем пользователям?",
        reply_markup=ReplyKeyboardMarkup([["Нет", "Да"]], resize_keyboard=True)
    )
    return BROADCAST_CONFIRM

async def broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text !="Да":
        await update.message.reply_text("📧 Рассылка отменена.", reply_markup=ReplyKeyboardRemove())
        return await start(update, context)

    users = load_users()
    if not users:
        await update.message.reply_text("📭 Нет пользователей в users.json")
        return await start(update, context)

    success=fail =0
    text= context.user_data['broadcast_text']
    media =context.user_data.get('broadcast_media')

    for user_id in users:
        try:
            if media:
                media_type, file_id = media
                if media_type=="photo":
                    await context.bot.send_photo(chat_id=user_id, photo=file_id, caption=text)
                elif media_type =="video":
                    await context.bot.send_video(chat_id=user_id, video=file_id, caption=text)
            else:
                await context.bot.send_message(chat_id=user_id, text=text)
            success +=1
        except Exception as e:
            logger.error(f"Ошибка отправки {user_id}: {e}")
            fail+= 1
        await asyncio.sleep(0.15)

    await update.message.reply_text(
        f"✅ Рассылка завершена!\nУспешно: {success}\nОшибок: {fail}",
        reply_markup=ReplyKeyboardRemove()
    )
    return await start(update, context)

#main (looks scary iksde)
def main():
    application=Application.builder().token(config.ADMIN_BOT_TOKEN).build()

    conv_handler= ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_action_selection)],
            NEW_STORY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_story_name)],
            NEW_STORY_SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_story_season)],
            NEW_STORY_SERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, new_story_series)],
            UPLOAD_MEDIA: [
                MessageHandler((filters.PHOTO | filters.VIDEO | filters.Document.ALL | filters.TEXT) & ~filters.COMMAND, upload_media)
            ],
            CONFIRM_CANCEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_cancel)],
            VIEW_STORIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_stories)],
            VIEW_SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_season)],
            VIEW_SERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_series)],
            BROADCAST_TEXT: [MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, broadcast_text)],
            BROADCAST_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_confirm)],
            EDIT_STORY_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_story_select)],
            EDIT_SEASON_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_season_select)],
            EDIT_SERIES_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_series_select)],
            EDIT_RENAME_STORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_rename_story)],
            EDIT_RENAME_SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_rename_season)],
            EDIT_RENAME_SERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_rename_series)],
            #НОВЫЕ ОБРАБОТЧИКИ
            EDIT_ADD_SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_add_season)],
            EDIT_ADD_SERIES_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_add_series_select)],
            EDIT_ADD_SERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_add_series)],
            CONFIRM_DELETE_STORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_story)],
            CONFIRM_DELETE_SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_season)],
            CONFIRM_DELETE_SERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete_series)],
            CONFIRM_CLEAR_SERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_clear_series)],
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)
    print("🚀 Админ-бот запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()