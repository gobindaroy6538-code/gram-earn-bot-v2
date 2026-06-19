import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 স্বাগতম *Gram Earn Bot* এ!\n\n"
        "🎉 আপনি নতুন ইউজার হিসেবে যোগ দিয়েছেন।\n\n"
        "এখানে টাস্ক করে আয় করতে পারবেন। শীঘ্রই আরো ফিচার আসছে!"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("✅ বট চালু হয়েছে...")
    app.run_polling()


if __name__ == "__main__":
    main()
