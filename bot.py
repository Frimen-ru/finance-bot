import logging
import os
from threading import Thread
from datetime import datetime, timedelta
from calendar import monthrange
from flask import Flask
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "8320620850:AAE5TK8M2lYJrs9NJaB-uxbjT1S3jJUsSBM"

user_data = defaultdict(lambda: {
    "balance": 0.0,
    "transactions": [],
    "salary": None,      # {"amount": float, "day": int}
    "advance": None      # {"amount": float, "day": int}
})

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# Веб-заглушка для Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Бот работает!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host="0.0.0.0", port=port)

# --- Вспомогательная функция для расчёта ближайшей даты ---
def next_occurrence(day: int):
    """Возвращает дату следующего события (число month)."""
    today = datetime.now().date()
    year, month = today.year, today.month
    # Попробуем в этом месяце
    try:
        candidate = today.replace(day=day)
    except ValueError:
        # Если день слишком большой для месяца (например, 31 февраля)
        last_day = monthrange(year, month)[1]
        candidate = today.replace(day=last_day)
    if candidate >= today:
        return candidate
    # Иначе в следующем месяце
    month += 1
    if month > 12:
        month = 1
        year += 1
    last_day = monthrange(year, month)[1]
    if day > last_day:
        day = last_day
    return datetime(year, month, day).date()

# --- Обработчики команд Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 Привет! Я бот для учёта доходов и расходов.\n\n"
        "Команды:\n"
        "/add 1000 Зарплата — добавить доход\n"
        "/spend 300 Кофе — добавить расход\n"
        "/balance — баланс и категории\n"
        "/history — последние операции\n"
        "/setsalary <сумма> <день> — установить день зарплаты\n"
        "/setadvance <сумма> <день> — установить день аванса\n"
        "/upcoming — когда ждать зарплату и аванс"
    )

async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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
        "date": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    user_data[user_id]["transactions"].append(transaction)
    await update.message.reply_text(f"✅ Доход {amount:.2f} ({category}) добавлен.")

async def add_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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
        "date": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    user_data[user_id]["transactions"].append(transaction)
    await update.message.reply_text(f"🔻 Расход {amount:.2f} ({category}) учтён.")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data[user_id]
    balance = data["balance"]

    expenses_by_cat = defaultdict(float)
    for t in data["transactions"]:
        if t["type"] == "расход":
            expenses_by_cat[t["category"]] += t["amount"]

    msg = f"📊 Текущий баланс: {balance:.2f}\n\n"
    if expenses_by_cat:
        msg += "Расходы по категориям:\n"
        for cat, total in expenses_by_cat.items():
            msg += f"  • {cat}: {total:.2f}\n"
    else:
        msg += "Расходов пока нет.\n"

    # Информация о зарплате и авансе
    if data["salary"]:
        s = data["salary"]
        msg += f"\n💼 Зарплата: {s['amount']:.2f}, день выплаты: {s['day']}-е число"
    if data["advance"]:
        a = data["advance"]
        msg += f"\n💸 Аванс: {a['amount']:.2f}, день выплаты: {a['day']}-е число"

    await update.message.reply_text(msg)

async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    transactions = user_data[user_id]["transactions"][-10:]
    if not transactions:
        await update.message.reply_text("📭 История пуста.")
        return
    msg = "📋 Последние операции:\n"
    for t in reversed(transactions):
        sign = "+" if t["type"] == "доход" else "-"
        msg += f"{sign} {t['amount']:.2f} | {t['category']} | {t['date']}\n"
    await update.message.reply_text(msg)

async def set_salary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        amount = float(context.args[0])
        day = int(context.args[1])
        if not (1 <= day <= 31):
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Формат: /setsalary <сумма> <день>\nПример: /setsalary 50000 15")
        return
    user_data[user_id]["salary"] = {"amount": amount, "day": day}
    await update.message.reply_text(f"💼 Зарплата {amount:.2f} установлена на {day}-е число каждого месяца.")

async def set_advance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        amount = float(context.args[0])
        day = int(context.args[1])
        if not (1 <= day <= 31):
            raise ValueError
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Формат: /setadvance <сумма> <день>\nПример: /setadvance 20000 28")
        return
    user_data[user_id]["advance"] = {"amount": amount, "day": day}
    await update.message.reply_text(f"💸 Аванс {amount:.2f} установлен на {day}-е число каждого месяца.")

async def upcoming(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data[user_id]
    if not data["salary"] and not data["advance"]:
        await update.message.reply_text("Сначала установите зарплату или аванс через /setsalary и /setadvance.")
        return

    msg = "📅 Ближайшие ожидаемые поступления:\n"
    today = datetime.now().date()

    if data["salary"]:
        s = data["salary"]
        next_date = next_occurrence(s["day"])
        days_left = (next_date - today).days
        msg += f"\n💼 Зарплата {s['amount']:.2f} — {next_date.strftime('%d.%m.%Y')} (через {days_left} дн.)"

    if data["advance"]:
        a = data["advance"]
        next_date = next_occurrence(a["day"])
        days_left = (next_date - today).days
        msg += f"\n💸 Аванс {a['amount']:.2f} — {next_date.strftime('%d.%m.%Y')} (через {days_left} дн.)"

    await update.message.reply_text(msg)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_income))
    app.add_handler(CommandHandler("spend", add_expense))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("setsalary", set_salary))
    app.add_handler(CommandHandler("setadvance", set_advance))
    app.add_handler(CommandHandler("upcoming", upcoming))

    Thread(target=run_web).start()
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
