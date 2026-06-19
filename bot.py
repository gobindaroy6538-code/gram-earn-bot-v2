import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from database import Database

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
REFERRAL_BONUS = 5
DAILY_BONUS = 2

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

    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    balance = user["balance"] if user else 0

    text = (
        f"👋 স্বাগতম *Gram Earn Bot* এ!\n\n"
        f"💰 আপনার ব্যালেন্স: *{balance:.2f} টাকা*\n\n"
        f"টাস্ক করুন, টাকা আয় করুন!"
    )
    keyboard = [
        [InlineKeyboardButton("💼 আমার ব্যালেন্স", callback_data="balance"),
         InlineKeyboardButton("👥 রেফার করুন", callback_data="referral")],
        [InlineKeyboardButton("🎁 ডেইলি বোনাস", callback_data="daily_bonus")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = db.get_user(user_id)
    referral_count = db.get_referral_count(user_id)

    text = (
        f"💼 *আমার অ্যাকাউন্ট*\n\n"
        f"👤 নাম: {user['name']}\n"
        f"💰 ব্যালেন্স: *{user['balance']:.2f} টাকা*\n"
        f"👥 রেফারেল: {referral_count}জন\n"
        f"📅 যোগ দিয়েছেন: {user['joined_date']}"
    )
    keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user_id}"
    count = db.get_referral_count(user_id)

    text = (
        f"👥 *রেফারেল প্রোগ্রাম*\n\n"
        f"প্রতি রেফারেলে: *{REFERRAL_BONUS} টাকা*\n"
        f"আপনার রেফারেল: *{count}জন*\n\n"
        f"আপনার লিংক:\n`{link}`\n\n"
        f"এই লিংক বন্ধুদের পাঠান!"
    )
    keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    success, info = db.claim_daily_bonus(user_id, DAILY_BONUS)

    if success:
        text = (
            f"🎁 *ডেইলি বোনাস পেয়েছেন!*\n\n"
            f"+{DAILY_BONUS} টাকা যুক্ত হয়েছে।\n"
            f"💰 নতুন ব্যালেন্স: *{info:.2f} টাকা*\n\n"
            f"আবার 24 ঘণ্টা পর ক্লেইম করতে পারবেন।"
        )
    else:
        if info is None:
            text = "⚠️ আপনার অ্যাকাউন্ট খুঁজে পাওয়া যায়নি। /start চাপুন।"
        else:
            total_seconds = int(info.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            text = (
                f"⏳ *এখনও বোনাস ক্লেইম করার সময় হয়নি!*\n\n"
                f"আবার ক্লেইম করতে পারবেন: *{hours} ঘণ্টা {minutes} মিনিট* পর।"
            )

    keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(show_balance, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(show_referral, pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(daily_bonus, pattern="^daily_bonus$"))
    print("✅ বট চালু হয়েছে...")
    app.run_polling()


if __name__ == "__main__":
    main()
