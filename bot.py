import logging
from collections import defaultdict
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "8320620850:AAE5TK8M2lYJrs9NJaB-uxbjT1S3jJUsSBM"

user_data = defaultdict(lambda: {"balance": 0.0, "transactions": []})

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 Привет! Я бот для учёта доходов и расходов.\n\n"
        "Команды:\n"
        "/add 1000 Зарплата — добавить доход\n"
        "/spend 300 Кофе — добавить расход\n"
        "/balance — баланс и категории\n"
        "/history — последние операции"
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
        msg += "Расходов пока нет."
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

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_income))
    app.add_handler(CommandHandler("spend", add_expense))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("history", history))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()