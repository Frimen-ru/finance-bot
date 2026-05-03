import logging
import os
import random
import asyncio
from threading import Thread
from datetime import datetime, timedelta
from calendar import monthrange
from flask import Flask
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "8320620850:AAE5TK8M2lYJrs9NJaB-uxbjT1S3jJUsSBM"
ADMIN_ID = 1908770107

user_data = defaultdict(lambda: {
    "balance": 0.0,
    "transactions": [],
    "salary": None,
    "advance": None,
    "last_surprise": None,
    "profile": {"first_name": "", "username": "", "platform": "unknown"},
    "last_active": None,
    "last_cron_sent": None   # время последнего cron-сообщения
})

telegram_app = None

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Бот работает!"

@web_app.route('/cron')
def cron():
    """Вызывается cron-job.org каждые 10 минут, чтобы Render не засыпал.
    Рассылает сообщение не чаще раза в сутки."""
    if telegram_app is None:
        return "bot not ready", 503
    now = datetime.now()
    for uid in list(user_data.keys()):
        data = user_data[uid]
        last_sent = data.get("last_cron_sent")
        # Отправляем сообщение, если прошло больше 23 часов
        if not last_sent or (now - last_sent).total_seconds() > 23 * 3600:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(maybe_surprise(uid, telegram_app, force=True))
                loop.close()
            except Exception as e:
                logging.error(f"Ошибка при отправке cron-сообщения пользователю {uid}: {e}")
        data["last_cron_sent"] = now
    return "ok"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

def next_occurrence(day: int):
    today = datetime.now().date()
    year, month = today.year, today.month
    try:
        candidate = today.replace(day=day)
    except ValueError:
        last_day = monthrange(year, month)[1]
        candidate = today.replace(day=last_day)
    if candidate >= today:
        return candidate
    month += 1
    if month > 12:
        month = 1
        year += 1
    last_day = monthrange(year, month)[1]
    if day > last_day:
        day = last_day
    return datetime(year, month, day).date()

MORNING_GREETINGS = [
    "🌅 Доброе утро! Новый день — новые возможности для бюджета.",
    "☀️ С первыми лучами солнца! Как настроение?",
    "🌞 Утро вечера мудренее, особенно когда финансы под контролем.",
    "⏰ Подъём! Самое время проверить баланс."
]
DAY_GREETINGS = [
    "🌤 День в разгаре! Не забудь записать расходы.",
    "💼 Рабочий день — самое время для финансовых подвигов.",
    "🚀 Вперёд к целям! Деньги любят учёт."
]
EVENING_GREETINGS = [
    "🌙 Вечер — время подвести итоги. Как прошёл день?",
    "🌆 Закат намекает: пора сверить баланс.",
    "🛋 Комфортный вечер. Может, глянем на историю?"
]
NIGHT_GREETINGS = [
    "🌃 Ночь на дворе, но я не сплю. Проверим счета?",
    "🦉 Полуночникам скидка на финансовые ошибки не распространяется.",
    "💤 Перед сном полезно знать, сколько потрачено."
]

MOTIVATION = [
    "💪 Каждая запись приближает тебя к финансовой свободе.",
    "📈 Твой баланс скажет спасибо за учёт.",
    "🧠 Умные привычки создают богатство.",
    "🔍 Учёт — это суперсила. Продолжай!"
]

COMPLIMENTS = [
    "🌟 Ты отлично ведёшь учёт!",
    "🎯 Твоя финансовая дисциплина впечатляет.",
    "📊 С такими записями можно планировать покорение мира.",
    "🧮 Ты просто гроссмейстер бюджета."
]

JOKES = [
    "— Почему деньги не растут на деревьях?\n— Потому что их съедают инфляции.",
    "— Как назвать бюджет, который сошёлся?\n— Фантастика.",
    "— Чем занимается оптимист в конце месяца?\n— Считает, сколько осталось до зарплаты.",
    "— Если расходы превышают доходы, это не дыра в бюджете, это образ жизни.",
    "— Банкомат спросил: «Внести или снять?» Я ответил: «Просто поговорить»."
]

NOW = datetime.now

def guess_platform(update: Update):
    return 'unknown'

def update_user_profile(user_id, update: Update):
    user = user_data[user_id]
    user["last_active"] = NOW()
    if update.effective_user:
        user["profile"]["first_name"] = update.effective_user.first_name or ""
        user["profile"]["username"] = update.effective_user.username or ""
    if user["profile"].get("platform", "unknown") == "unknown":
        guessed = guess_platform(update)
        if guessed != "unknown":
            user["profile"]["platform"] = guessed

async def maybe_surprise(user_id, app, force=False):
    data = user_data[user_id]
    last = data["last_surprise"]
    now = NOW()

    if not force and last and (now - last).total_seconds() < 7200:
        return

    data["last_surprise"] = now

    hour = now.hour
    if 6 <= hour < 12:
        greeting = random.choice(MORNING_GREETINGS)
    elif 12 <= hour < 18:
        greeting = random.choice(DAY_GREETINGS)
    elif 18 <= hour < 23:
        greeting = random.choice(EVENING_GREETINGS)
    else:
        greeting = random.choice(NIGHT_GREETINGS)

    extra = ""
    r = random.random()
    if r < 0.4:
        extra = "\n" + random.choice(MOTIVATION)
    elif r < 0.7:
        extra = "\n" + random.choice(COMPLIMENTS)

    reminder = ""
    today = now.date()
    for name, key, emoji in [("зарплата", "salary", "💼"), ("аванс", "advance", "💸")]:
        info = data.get(key)
        if info:
            next_day = next_occurrence(info["day"])
            days_left = (next_day - today).days
            if days_left == 0:
                reminder += f"\n{emoji} Сегодня день {name}! Не забудь записать доход."
            elif days_left == 1:
                reminder += f"\n{emoji} Завтра день {name} ({info['amount']:.2f}). Готовься!"

    message = greeting + extra + reminder
    if message.strip():
        await app.bot.send_message(chat_id=user_id, text=message)

# --- Обработчики команд ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_user_profile(user_id, update)
    await maybe_surprise(user_id, context.application)
    if user_id == ADMIN_ID:
        await update.message.reply_text(
            "💰 Привет, хозяин! Я твой финансовый помощник.\n\n"
            "Основные команды для всех:\n"
            "/add 1000 Зарплата — доход\n"
            "/spend 300 Кофе — расход\n"
            "/balance — баланс и статистика\n"
            "/history — последние операции\n"
            "/setsalary 50000 15\n"
            "/setadvance 20000 28\n"
            "/upcoming — когда ждать выплат\n\n"
            "Только для тебя:\n"
            "/joke — анекдот\n"
            "/hello — поздороваться\n"
            "/users — кто пользуется ботом\n"
            "/setplatform android/iphone — указать свою платформу (для статистики)"
        )
    else:
        await update.message.reply_text(
            "💰 Привет! Я бот для учёта доходов и расходов.\n\n"
            "Команды:\n"
            "/add 1000 Зарплата — добавить доход\n"
            "/spend 300 Кофе — добавить расход\n"
            "/balance — баланс и статистика\n"
            "/history — последние операции\n"
            "/setsalary 50000 15\n"
            "/setadvance 20000 28\n"
            "/upcoming — когда ждать выплат\n"
            "/setplatform android/iphone — указать свою платформу"
        )

async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_user_profile(user_id, update)
    await maybe_surprise(user_id, context.application)
    try:
        amount = float(context.args[0])
        category = " ".join(context.args[1:]) if len(context.args) > 1 else "Без категории"
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Формат: /add <сумма> <категория>\nПример: /add 1000 Зарплата")
        return
    user_data[user_id]["balance"] += amount
    transaction = {
        "type": "доход",
        "amount": amount,
        "category": category,
        "date": NOW().strftime("%d.%m.%Y %H:%M")
    }
    user_data[user_id]["transactions"].append(transaction)
    if amount >= 50000:
        reaction = random.choice(["🔥 Крупное поступление! Красавчик!", "💼 Серьёзный доход. Так держать!"])
    elif amount >= 10000:
        reaction = random.choice(["✅ Отлично! Копилка пополняется.", "👍 Хороший плюс в бюджет."])
    else:
        reaction = random.choice(["➕ Мелочь, а приятно.", "📌 Записал, не потеряется."])
    await update.message.reply_text(f"{reaction} Доход {amount:.2f} ({category}) добавлен.")

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_user_profile(user_id, update)
    await maybe_surprise(user_id, context.application)
    try:
        amount = float(context.args[0])
        category = " ".join(context.args[1:]) if len(context.args) > 1 else "Без категории"
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Формат: /spend <сумма> <категория>\nПример: /spend 250 Кофе")
        return
    user_data[user_id]["balance"] -= amount
    transaction = {
        "type": "расход",
        "amount": amount,
        "category": category,
        "date": NOW().strftime("%d.%m.%Y %H:%M")
    }
    user_data[user_id]["transactions"].append(transaction)
    if amount > 5000:
        reaction = random.choice(["💸 Ничего себе траты! Надеюсь, оно того стоило.", "🛑 Крупный расход зафиксирован."])
    else:
        reaction = random.choice(["🛒 Расход учтён. Бюджет под контролем.", "📉 Минус, но ты знаешь, куда ушли деньги."])
    await update.message.reply_text(f"{reaction} Расход {amount:.2f} ({category}) учтён.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_user_profile(user_id, update)
    await maybe_surprise(user_id, context.application)
    data = user_data[user_id]
    bal = data["balance"]

    expenses_by_cat = defaultdict(float)
    for t in data["transactions"]:
        if t["type"] == "расход":
            expenses_by_cat[t["category"]] += t["amount"]

    if bal > 50000:
        mood = "🤑 Отличный баланс! Ты на коне."
    elif bal > 10000:
        mood = "😊 Всё стабильно, можно жить."
    elif bal > 0:
        mood = "🙂 Нормально, но лучше не расслабляться."
    elif bal == 0:
        mood = "😐 По нулям. Пора что-то менять?"
    else:
        mood = "😟 Минус... Надо срочно спасать бюджет."

    msg = f"📊 Текущий баланс: {bal:.2f}\n{mood}\n\n"
    if expenses_by_cat:
        msg += "Расходы по категориям:\n"
        for cat, total in expenses_by_cat.items():
            msg += f"  • {cat}: {total:.2f}\n"
    else:
        msg += "Расходов пока нет.\n"

    if data["salary"]:
        s = data["salary"]
        msg += f"\n💼 Зарплата: {s['amount']:.2f}, {s['day']}-е число"
    if data["advance"]:
        a = data["advance"]
        msg += f"\n💸 Аванс: {a['amount']:.2f}, {a['day']}-е число"

    await update.message.reply_text(msg)

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_user_profile(user_id, update)
    await maybe_surprise(user_id, context.application)
    transactions = user_data[user_id]["transactions"][-10:]
    if not transactions:
        await update.message.reply_text("📭 История пуста. Но ты можешь это исправить!")
        return
    msg = "📋 Последние операции:\n"
    for t in reversed(transactions):
        sign = "+" if t["type"] == "доход" else "-"
        msg += f"{sign} {t['amount']:.2f} | {t['category']} | {t['date']}\n"
    await update.message.reply_text(msg)

async def set_salary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_user_profile(user_id, update)
    await maybe_surprise(user_id, context.application)
    try:
        amount = float(context.args[0])
        day = int(context.args[1])
        if not (1 <= day <= 31):
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Формат: /setsalary <сумма> <день>\nПример: /setsalary 50000 15")
        return
    user_data[user_id]["salary"] = {"amount": amount, "day": day}
    await update.message.reply_text(f"💼 Зарплата {amount:.2f} установлена на {day}-е число каждого месяца. Жду пополнения!")

async def set_advance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_user_profile(user_id, update)
    await maybe_surprise(user_id, context.application)
    try:
        amount = float(context.args[0])
        day = int(context.args[1])
        if not (1 <= day <= 31):
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Формат: /setadvance <сумма> <день>\nПример: /setadvance 20000 28")
        return
    user_data[user_id]["advance"] = {"amount": amount, "day": day}
    await update.message.reply_text(f"💸 Аванс {amount:.2f} установлен на {day}-е число каждого месяца. Буду напоминать!")

async def upcoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_user_profile(user_id, update)
    await maybe_surprise(user_id, context.application)
    data = user_data[user_id]
    if not data["salary"] and not data["advance"]:
        await update.message.reply_text("Сначала установите зарплату или аванс через /setsalary и /setadvance.")
        return

    msg = "📅 Ближайшие ожидаемые поступления:\n"
    today = NOW().date()

    for name, key, emoji in [("Зарплата", "salary", "💼"), ("Аванс", "advance", "💸")]:
        info = data.get(key)
        if info:
            next_date = next_occurrence(info["day"])
            days_left = (next_date - today).days
            if days_left == 0:
                msg += f"\n{emoji} {name} {info['amount']:.2f} — СЕГОДНЯ! 🎉"
            elif days_left == 1:
                msg += f"\n{emoji} {name} {info['amount']:.2f} — завтра ({next_date.strftime('%d.%m.%Y')})"
            else:
                msg += f"\n{emoji} {name} {info['amount']:.2f} — {next_date.strftime('%d.%m.%Y')} (через {days_left} дн.)"

    await update.message.reply_text(msg)

# --- Команды для админа ---
async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    await update.message.reply_text(random.choice(JOKES))

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    update_user_profile(user_id, update)
    await maybe_surprise(user_id, context.application, force=True)

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    if not user_data:
        await update.message.reply_text("Пока никого нет.")
        return

    msg = "👥 Пользователи бота:\n\n"
    for uid, data in user_data.items():
        profile = data["profile"]
        name = profile["first_name"] or "Без имени"
        username = f" (@{profile['username']})" if profile["username"] else ""
        platform = profile.get("platform", "unknown")
        if platform == "unknown":
            platform_str = "не указано"
        elif platform == "android":
            platform_str = "🤖 Android"
        elif platform == "iphone":
            platform_str = "📱 iPhone"
        else:
            platform_str = platform
        last = data["last_active"]
        if last:
            last_str = last.strftime("%d.%m.%Y %H:%M")
        else:
            last_str = "неизвестно"
        msg += f"• {name}{username}\n  ID: `{uid}`\n  Платформа: {platform_str}\n  Последняя активность: {last_str}\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def set_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    update_user_profile(user_id, update)
    try:
        platform = context.args[0].lower()
        if platform not in ("android", "iphone"):
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Формат: /setplatform android или /setplatform iphone")
        return
    user_data[user_id]["profile"]["platform"] = platform
    await update.message.reply_text(f"✅ Платформа установлена: {'Android' if platform == 'android' else 'iPhone'}")

# --- Запуск ---
def main():
    global telegram_app
    app = Application.builder().token(BOT_TOKEN).build()
    telegram_app = app

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_income))
    app.add_handler(CommandHandler("spend", add_expense))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("setsalary", set_salary))
    app.add_handler(CommandHandler("setadvance", set_advance))
    app.add_handler(CommandHandler("upcoming", upcoming))
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(CommandHandler("hello", hello))
    app.add_handler(CommandHandler("users", users))
    app.add_handler(CommandHandler("setplatform", set_platform))

    Thread(target=run_web).start()
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
