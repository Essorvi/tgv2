from fastapi import FastAPI, APIRouter, HTTPException, Request, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import requests
import json
import hashlib
import secrets
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# API Configuration
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN']
WEBHOOK_SECRET = os.environ['WEBHOOK_SECRET']
USERSBOX_TOKEN = os.environ['USERSBOX_TOKEN']
USERSBOX_BASE_URL = os.environ['USERSBOX_BASE_URL']
ADMIN_USERNAME = os.environ['ADMIN_USERNAME']

# Create the main app
app = FastAPI(title="Usersbox Telegram Bot API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Models
class User(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    attempts_remaining: int = 1
    referred_by: Optional[int] = None
    referral_code: str
    total_referrals: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_admin: bool = False
    last_active: datetime = Field(default_factory=datetime.utcnow)

class Search(BaseModel):
    user_id: int
    query: str
    results: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    attempt_used: bool = True
    success: bool = True

class Referral(BaseModel):
    referrer_id: int
    referred_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    attempt_given: bool = True

class TelegramMessage(BaseModel):
    chat_id: int
    text: str
    parse_mode: str = "Markdown"

# Helper Functions
def generate_referral_code(telegram_id: int) -> str:
    """Generate unique referral code"""
    data = f"{telegram_id}_{secrets.token_hex(8)}"
    return hashlib.md5(data.encode()).hexdigest()[:8]

def format_search_results(results: Dict[str, Any], query: str) -> str:
    """Format usersbox API results for Telegram"""
    if results.get('status') == 'error':
        return f"❌ *Ошибка поиска:* {results.get('error', {}).get('message', 'Неизвестная ошибка')}"
    
    data = results.get('data', {})
    total_count = data.get('count', 0)
    
    if total_count == 0:
        return f"🔍 *Поиск по запросу:* `{query}`\n\n❌ *Результатов не найдено*"
    
    formatted_text = f"🔍 *Поиск по запросу:* `{query}`\n\n"
    formatted_text += f"📊 *Всего найдено:* {total_count} записей\n\n"
    
    # Format search results from /search endpoint
    if 'items' in data and isinstance(data['items'], list):
        formatted_text += "📋 *Результаты поиска:*\n\n"
        
        for i, source_data in enumerate(data['items'][:5], 1):  # Limit to 5 sources
            if 'source' in source_data and 'hits' in source_data:
                source = source_data['source']
                hits = source_data['hits']
                hits_count = hits.get('hitsCount', hits.get('count', 0))
                
                formatted_text += f"*{i}. База данных:* {source.get('database', 'N/A')}\n"
                formatted_text += f"   *Коллекция:* {source.get('collection', 'N/A')}\n"
                formatted_text += f"   *Найдено записей:* {hits_count}\n"
                
                # Format individual items if available
                if 'items' in hits and hits['items']:
                    formatted_text += "   *Данные:*\n"
                    for item in hits['items'][:2]:  # Show first 2 items per source
                        for key, value in item.items():
                            if key.startswith('_'):
                                continue  # Skip internal fields
                            if key in ['phone', 'телефон', 'tel']:
                                formatted_text += f"   📞 Телефон: `{value}`\n"
                            elif key in ['email', 'почта', 'mail']:
                                formatted_text += f"   📧 Email: `{value}`\n"
                            elif key in ['full_name', 'name', 'имя', 'фио']:
                                formatted_text += f"   👤 Имя: `{value}`\n"
                            elif key in ['birth_date', 'birthday', 'дата_рождения']:
                                formatted_text += f"   🎂 Дата рождения: `{value}`\n"
                            elif key in ['address', 'адрес']:
                                if isinstance(value, dict):
                                    addr_parts = []
                                    for addr_key, addr_val in value.items():
                                        if addr_val:
                                            addr_parts.append(f"{addr_val}")
                                    if addr_parts:
                                        formatted_text += f"   🏠 Адрес: `{', '.join(addr_parts)}`\n"
                                else:
                                    formatted_text += f"   🏠 Адрес: `{value}`\n"
                            else:
                                # Generic field formatting
                                if isinstance(value, (str, int, float)) and len(str(value)) < 100:
                                    formatted_text += f"   • {key}: `{value}`\n"
                formatted_text += "\n"
    
    # Format explain results
    elif 'count' in data and isinstance(data.get('items'), list):
        formatted_text += "📋 *Распределение по базам:*\n\n"
        for i, item in enumerate(data['items'][:10], 1):  # Show top 10
            source = item.get('source', {})
            hits = item.get('hits', {})
            count = hits.get('count', 0)
            
            formatted_text += f"*{i}.* {source.get('database', 'N/A')} / {source.get('collection', 'N/A')}: {count} записей\n"
    
    # Add usage note
    formatted_text += "\n💡 *Примечание:* Показаны основные результаты. Полная информация может содержать больше данных."
    
    return formatted_text

async def send_telegram_message(chat_id: int, text: str, parse_mode: str = "Markdown") -> bool:
    """Send message to Telegram user"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")
        return False

async def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None, last_name: str = None) -> User:
    """Get existing user or create new one"""
    user_data = await db.users.find_one({"telegram_id": telegram_id})
    
    if user_data:
        # Update last active and user info
        await db.users.update_one(
            {"telegram_id": telegram_id},
            {
                "$set": {
                    "last_active": datetime.utcnow(),
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name
                }
            }
        )
        return User(**user_data)
    else:
        # Create new user
        referral_code = generate_referral_code(telegram_id)
        is_admin = username == ADMIN_USERNAME if username else False
        
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            referral_code=referral_code,
            is_admin=is_admin,
            attempts_remaining=1 if not is_admin else 999  # Admin gets unlimited
        )
        
        await db.users.insert_one(user.dict())
        return user

async def process_referral(referred_user_id: int, referral_code: str) -> bool:
    """Process referral and give attempt to referrer"""
    try:
        # Find referrer by code
        referrer = await db.users.find_one({"referral_code": referral_code})
        if not referrer or referrer['telegram_id'] == referred_user_id:
            return False
        
        # Check if referral already exists
        existing_referral = await db.referrals.find_one({
            "referrer_id": referrer['telegram_id'],
            "referred_id": referred_user_id
        })
        
        if existing_referral:
            return False
        
        # Create referral record
        referral = Referral(
            referrer_id=referrer['telegram_id'],
            referred_id=referred_user_id
        )
        await db.referrals.insert_one(referral.dict())
        
        # Give attempt to referrer and update referral count
        await db.users.update_one(
            {"telegram_id": referrer['telegram_id']},
            {
                "$inc": {
                    "attempts_remaining": 1,
                    "total_referrals": 1
                }
            }
        )
        
        # Update referred user
        await db.users.update_one(
            {"telegram_id": referred_user_id},
            {"$set": {"referred_by": referrer['telegram_id']}}
        )
        
        # Notify referrer
        await send_telegram_message(
            referrer['telegram_id'],
            f"🎉 *Поздравляем!* Пользователь присоединился по вашей реферальной ссылке!\n\n"
            f"💎 Вы получили +1 попытку поиска\n"
            f"👥 Всего рефералов: {referrer['total_referrals'] + 1}"
        )
        
        return True
    except Exception as e:
        logging.error(f"Referral processing error: {e}")
        return False

# API Routes
@api_router.get("/")
async def root():
    return {"message": "Usersbox Telegram Bot API", "status": "running"}

@api_router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    """Handle Telegram webhook"""
    if secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    
    try:
        update_data = await request.json()
        await handle_telegram_update(update_data)
        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")

async def handle_telegram_update(update_data: Dict[str, Any]):
    """Process incoming Telegram update"""
    message = update_data.get('message')
    if not message:
        return
    
    chat = message.get('chat', {})
    chat_id = chat.get('id')
    text = message.get('text', '')
    user_info = message.get('from', {})
    
    if not chat_id:
        return
    
    # Get or create user
    user = await get_or_create_user(
        telegram_id=user_info.get('id', chat_id),
        username=user_info.get('username'),
        first_name=user_info.get('first_name'),
        last_name=user_info.get('last_name')
    )
    
    # Handle commands
    if text.startswith('/start'):
        await handle_start_command(chat_id, text, user)
    elif text.startswith('/search'):
        await handle_search_command(chat_id, text, user)
    elif text.startswith('/balance'):
        await handle_balance_command(chat_id, user)
    elif text.startswith('/referral'):
        await handle_referral_command(chat_id, user)
    elif text.startswith('/help'):
        await handle_help_command(chat_id, user)
    elif text.startswith('/admin') and user.is_admin:
        await handle_admin_command(chat_id, text, user)
    elif text.startswith('/give') and user.is_admin:
        await handle_give_attempts_command(chat_id, text, user)
    elif text.startswith('/stats') and user.is_admin:
        await handle_stats_command(chat_id, user)
    else:
        # Treat as search query if user has attempts
        if user.attempts_remaining > 0 or user.is_admin:
            await handle_search_command(chat_id, f"/search {text}", user)
        else:
            await send_telegram_message(
                chat_id,
                "❌ У вас закончились попытки поиска!\n\n"
                "🔗 Пригласите друзей по реферальной ссылке, чтобы получить больше попыток.\n"
                "Используйте /referral для получения ссылки."
            )

async def handle_start_command(chat_id: int, text: str, user: User):
    """Handle /start command"""
    # Check for referral code
    parts = text.split()
    if len(parts) > 1:
        referral_code = parts[1]
        await process_referral(user.telegram_id, referral_code)
    
    welcome_text = f"👋 *Добро пожаловать, {user.first_name or 'пользователь'}!*\n\n"
    welcome_text += "🔍 *Usersbox Bot* - поиск информации по базам данных\n\n"
    welcome_text += f"💎 *Доступно попыток:* {user.attempts_remaining}\n"
    welcome_text += f"👥 *Рефералов:* {user.total_referrals}\n\n"
    welcome_text += "*Доступные команды:*\n"
    welcome_text += "• `/search [запрос]` - поиск информации\n"
    welcome_text += "• `/balance` - проверить баланс попыток\n"
    welcome_text += "• `/referral` - получить реферальную ссылку\n"
    welcome_text += "• `/help` - помощь\n\n"
    welcome_text += "📝 *Просто отправьте мне любой текст для поиска!*"
    
    if user.is_admin:
        welcome_text += "\n\n🔧 *Админ команды:*\n"
        welcome_text += "• `/admin` - админ панель\n"
        welcome_text += "• `/give [user_id] [attempts]` - выдать попытки\n"
        welcome_text += "• `/stats` - статистика бота"
    
    await send_telegram_message(chat_id, welcome_text)

async def handle_search_command(chat_id: int, text: str, user: User):
    """Handle search command"""
    # Extract query
    query = text.replace('/search', '', 1).strip()
    if not query:
        await send_telegram_message(
            chat_id,
            "❌ *Ошибка:* Укажите запрос для поиска\n\n"
            "*Пример:* `/search +79123456789`\n"
            "или просто отправьте: `+79123456789`"
        )
        return
    
    # Check attempts
    if user.attempts_remaining <= 0 and not user.is_admin:
        await send_telegram_message(
            chat_id,
            "❌ У вас закончились попытки поиска!\n\n"
            "🔗 Пригласите друзей по реферальной ссылке:\n"
            "Используйте /referral для получения ссылки."
        )
        return
    
    # Send searching message
    await send_telegram_message(chat_id, "🔍 *Выполняю поиск...* Подождите немного.")
    
    try:
        # Call usersbox API
        headers = {"Authorization": USERSBOX_TOKEN}
        response = requests.get(
            f"{USERSBOX_BASE_URL}/search",
            headers=headers,
            params={"q": query},
            timeout=30
        )
        
        results = response.json()
        
        # Format and send results
        formatted_results = format_search_results(results, query)
        await send_telegram_message(chat_id, formatted_results)
        
        # Save search record
        search = Search(
            user_id=user.telegram_id,
            query=query,
            results=results,
            success=response.status_code == 200
        )
        await db.searches.insert_one(search.dict())
        
        # Deduct attempt (except for admin)
        if not user.is_admin and response.status_code == 200:
            await db.users.update_one(
                {"telegram_id": user.telegram_id},
                {"$inc": {"attempts_remaining": -1}}
            )
            
            # Update user object
            user.attempts_remaining -= 1
            
            # Show remaining attempts
            if user.attempts_remaining > 0:
                await send_telegram_message(
                    chat_id,
                    f"💎 *Осталось попыток:* {user.attempts_remaining}"
                )
            else:
                await send_telegram_message(
                    chat_id,
                    "❌ Попытки закончились!\n\n"
                    "🔗 Получите больше попыток, пригласив друзей:\n"
                    "Используйте /referral"
                )
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Usersbox API error: {e}")
        await send_telegram_message(
            chat_id,
            "❌ *Ошибка при выполнении поиска*\n\n"
            "Сервис временно недоступен. Попробуйте позже."
        )
    except Exception as e:
        logging.error(f"Search error: {e}")
        await send_telegram_message(
            chat_id,
            "❌ *Произошла ошибка при поиске*\n\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )

async def handle_balance_command(chat_id: int, user: User):
    """Handle balance command"""
    balance_text = f"💎 *Ваш баланс попыток*\n\n"
    balance_text += f"🔍 *Доступно поисков:* {user.attempts_remaining}\n"
    balance_text += f"👥 *Приглашено друзей:* {user.total_referrals}\n"
    balance_text += f"📅 *Регистрация:* {user.created_at.strftime('%d.%m.%Y')}\n\n"
    
    if user.attempts_remaining == 0:
        balance_text += "🔗 *Получите больше попыток:*\n"
        balance_text += "Используйте /referral для получения реферальной ссылки"
    
    await send_telegram_message(chat_id, balance_text)

async def handle_referral_command(chat_id: int, user: User):
    """Handle referral command"""
    bot_username = "YourBotUsername"  # Replace with actual bot username
    referral_link = f"https://t.me/{bot_username}?start={user.referral_code}"
    
    referral_text = f"🔗 *Ваша реферальная ссылка:*\n\n"
    referral_text += f"`{referral_link}`\n\n"
    referral_text += "💰 *Условия:*\n"
    referral_text += "• За каждого приглашенного друга вы получаете +1 попытку\n"
    referral_text += "• Друг должен перейти по вашей ссылке\n"
    referral_text += "• Самореферальные переходы не засчитываются\n\n"
    referral_text += f"👥 *Уже приглашено:* {user.total_referrals} друзей"
    
    await send_telegram_message(chat_id, referral_text)

async def handle_help_command(chat_id: int, user: User):
    """Handle help command"""
    help_text = "📖 *Справка по командам*\n\n"
    help_text += "*Основные команды:*\n"
    help_text += "• `/search [запрос]` - поиск по базам данных\n"
    help_text += "• `/balance` - проверить количество попыток\n"
    help_text += "• `/referral` - получить реферальную ссылку\n"
    help_text += "• `/help` - эта справка\n\n"
    help_text += "*Примеры поиска:*\n"
    help_text += "• `+79123456789` - поиск по номеру телефона\n"
    help_text += "• `ivan@mail.ru` - поиск по email\n"
    help_text += "• `Иван Петров` - поиск по имени\n\n"
    help_text += "*Получение попыток:*\n"
    help_text += "• Каждый новый пользователь получает 1 попытку\n"
    help_text += "• За каждого приглашенного друга +1 попытка\n"
    help_text += "• Используйте /referral для получения ссылки"
    
    await send_telegram_message(chat_id, help_text)

async def handle_admin_command(chat_id: int, text: str, user: User):
    """Handle admin commands"""
    admin_text = "🔧 *Админ панель*\n\n"
    admin_text += "*Доступные команды:*\n"
    admin_text += "• `/give [user_id] [attempts]` - выдать попытки пользователю\n"
    admin_text += "• `/stats` - статистика бота\n\n"
    admin_text += "*Примеры:*\n"
    admin_text += "• `/give 123456789 5` - выдать 5 попыток пользователю\n"
    
    await send_telegram_message(chat_id, admin_text)

async def handle_give_attempts_command(chat_id: int, text: str, user: User):
    """Handle give attempts admin command"""
    parts = text.split()
    if len(parts) != 3:
        await send_telegram_message(
            chat_id,
            "❌ *Неверный формат команды*\n\n"
            "*Использование:* `/give [user_id] [attempts]`\n"
            "*Пример:* `/give 123456789 5`"
        )
        return
    
    try:
        target_user_id = int(parts[1])
        attempts_to_give = int(parts[2])
        
        # Check if user exists
        target_user = await db.users.find_one({"telegram_id": target_user_id})
        if not target_user:
            await send_telegram_message(
                chat_id,
                f"❌ Пользователь с ID {target_user_id} не найден"
            )
            return
        
        # Give attempts
        await db.users.update_one(
            {"telegram_id": target_user_id},
            {"$inc": {"attempts_remaining": attempts_to_give}}
        )
        
        # Notify admin
        await send_telegram_message(
            chat_id,
            f"✅ Пользователю {target_user_id} выдано {attempts_to_give} попыток"
        )
        
        # Notify user
        await send_telegram_message(
            target_user_id,
            f"🎁 *Вам выданы попытки!*\n\n"
            f"💎 Получено попыток: {attempts_to_give}\n"
            f"Можете продолжать поиск!"
        )
        
    except ValueError:
        await send_telegram_message(
            chat_id,
            "❌ Неверный формат ID пользователя или количества попыток"
        )
    except Exception as e:
        logging.error(f"Give attempts error: {e}")
        await send_telegram_message(
            chat_id,
            "❌ Ошибка при выдаче попыток"
        )

async def handle_stats_command(chat_id: int, user: User):
    """Handle stats admin command"""
    try:
        # Get statistics
        total_users = await db.users.count_documents({})
        total_searches = await db.searches.count_documents({})
        total_referrals = await db.referrals.count_documents({})
        successful_searches = await db.searches.count_documents({"success": True})
        
        # Recent activity
        recent_users = await db.users.count_documents({
            "created_at": {"$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
        })
        
        recent_searches = await db.searches.count_documents({
            "timestamp": {"$gte": datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)}
        })
        
        stats_text = "📊 *Статистика бота*\n\n"
        stats_text += f"👥 *Всего пользователей:* {total_users}\n"
        stats_text += f"🔍 *Всего поисков:* {total_searches}\n"
        stats_text += f"✅ *Успешных поисков:* {successful_searches}\n"
        stats_text += f"🔗 *Рефералов:* {total_referrals}\n\n"
        stats_text += f"📈 *За сегодня:*\n"
        stats_text += f"• Новых пользователей: {recent_users}\n"
        stats_text += f"• Поисков: {recent_searches}\n\n"
        
        if total_searches > 0:
            success_rate = (successful_searches / total_searches) * 100
            stats_text += f"📊 *Успешность поисков:* {success_rate:.1f}%"
        
        await send_telegram_message(chat_id, stats_text)
        
    except Exception as e:
        logging.error(f"Stats error: {e}")
        await send_telegram_message(
            chat_id,
            "❌ Ошибка при получении статистики"
        )

# Usersbox API endpoints for admin dashboard
@api_router.post("/search")
async def api_search(query: str = Query(...)):
    """Search via usersbox API"""
    headers = {"Authorization": USERSBOX_TOKEN}
    
    try:
        response = requests.get(
            f"{USERSBOX_BASE_URL}/search",
            headers=headers,
            params={"q": query},
            timeout=30
        )
        
        # Handle different response status codes
        if response.status_code == 400:
            # Bad request - likely invalid query format
            return {
                "status": "error",
                "error": {
                    "code": "INVALID_QUERY",
                    "message": f"Invalid search query format. Please use phone numbers (+79123456789), emails, or names."
                }
            }
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"API request failed: {str(e)}")

@api_router.get("/users")
async def get_users():
    """Get all users for admin dashboard"""
    users = await db.users.find().to_list(1000)
    for user in users:
        user["_id"] = str(user["_id"])
    return users

@api_router.get("/searches")
async def get_searches():
    """Get search history"""
    searches = await db.searches.find().sort("timestamp", -1).limit(100).to_list(100)
    for search in searches:
        search["_id"] = str(search["_id"])
    return searches

@api_router.post("/give-attempts")
async def give_attempts_api(user_id: int, attempts: int):
    """Give attempts to user via API"""
    try:
        result = await db.users.update_one(
            {"telegram_id": user_id},
            {"$inc": {"attempts_remaining": attempts}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Notify user
        await send_telegram_message(
            user_id,
            f"🎁 *Вам выданы попытки!*\n\n"
            f"💎 Получено попыток: {attempts}\n"
            f"Можете продолжать поиск!"
        )
        
        return {"status": "success", "message": f"Gave {attempts} attempts to user {user_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/stats")
async def get_stats():
    """Get bot statistics"""
    try:
        total_users = await db.users.count_documents({})
        total_searches = await db.searches.count_documents({})
        total_referrals = await db.referrals.count_documents({})
        successful_searches = await db.searches.count_documents({"success": True})
        
        return {
            "total_users": total_users,
            "total_searches": total_searches,
            "total_referrals": total_referrals,
            "successful_searches": successful_searches,
            "success_rate": (successful_searches / total_searches * 100) if total_searches > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()