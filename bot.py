import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from database import Database

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
REFERRAL_BONUS = 5

db = Database()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referrer_id = int(args[0]) if args and args[0].isdigit() and int(args[0]) != user.id else None

    is_new = db.register_user(user.id, user.first_name, user.username, referrer_id)

    if is_new and referrer_id:
        db.add_balance(referrer_id, REFERRAL_BONUS)
        try:
            await context.bot.send_message(
                referrer_id,
                f"🎉 আপনার রেফারেলে নতুন ইউজার যোগ দিয়েছে!\n+{REFERRAL_BONUS} টাকা বোনাস পেয়েছেন।"
            )
        except Exception:
            pass

    text = (
        "👋 স্বাগতম *Gram Earn Bot* এ!\n\n"
        "🎉 আপনি নতুন ইউজার হিসেবে যোগ দিয়েছেন।\n\n" if is_new else "👋 আবার স্বাগতম!\n\n"
    )
    text += "এখানে টাস্ক করে আয় করতে পারবেন। শীঘ্রই আরো ফিচার আসছে!"

    keyboard = [[InlineKeyboardButton("👥 রেফার করুন", callback_data="referral")]]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = db.get_user(user_id)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user_id}"
    count = db.get_referral_count(user_id)
    balance = user["balance"] if user else 0

    text = (
        f"👥 *রেফারেল প্রোগ্রাম*\n\n"
        f"প্রতি রেফারেলে: *{REFERRAL_BONUS} টাকা*\n"
        f"আপনার রেফারেল: *{count}জন*\n"
        f"আপনার ব্যালেন্স: *{balance:.2f} টাকা*\n\n"
        f"আপনার লিংক:\n`{link}`\n\n"
        f"এই লিংক বন্ধুদের পাঠান!"
    )
    await query.edit_message_text(text, parse_mode="Markdown")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_referral, pattern="^referral$"))
    print("✅ বট চালু হয়েছে...")
    app.run_polling()


if __name__ == "__main__":
    main()
