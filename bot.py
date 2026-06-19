import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from database import Database

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
REFERRAL_BONUS = 5
DAILY_BONUS = 2
TASK_REWARD = 5  # টাস্ক কমপ্লিট করলে ইউজার যত টাকা পাবে

MIN_WITHDRAW = 20
ADMIN_ID = 8012544346
CHANNEL_ID = -1004375418813  # আপনার দেওয়া চ্যানেলের আইডি

WITHDRAW_METHODS = ["bKash", "Nagad", "Rocket"]

# Conversation States
ASK_METHOD, ASK_NUMBER, ASK_AMOUNT = range(3)
ASK_TASK_PROOF = 4  # স্ক্রিনশট নেওয়ার জন্য স্টেট

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
        [InlineKeyboardButton("🎁 DAILY BONUS", callback_data="daily_bonus"),
         InlineKeyboardButton("💵 উইথড্র", callback_data="withdraw_start")],
        [InlineKeyboardButton("🎯 টাস্ক করুন", callback_data="task_menu")],
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


# ---------------- 🎯 SCREENSHOT TASK SYSTEM ----------------

async def show_task_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        f"🎯 *ইউটিউব সাবস্ক্রাইব টাস্ক*\n\n"
        f"📌 *কাজ:* নিচের লিংকে গিয়ে চ্যানেলটি সাবস্ক্রাইব করুন এবং একটি স্ক্রিনশট নিন।\n\n"
        f"💰 বোনাস: *{TASK_REWARD} টাকা*\n\n"
        f"👇 নিচে 'স্ক্রিনশট জমা দিন' বাটনে ক্লিক করে প্রুফ পাঠান।"
    )
    keyboard = [
        [InlineKeyboardButton("🔗 চ্যানেলে যান", url="https://youtube.com/@yourchannel")],
        [InlineKeyboardButton("📤 স্ক্রিনশট জমা দিন", callback_data="submit_proof_start")],
        [InlineKeyboardButton("🏠 মেনু", callback_data="menu")]
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def submit_proof_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if db.has_pending_task(query.from_user.id, "task_1"):
        await query.edit_message_text(
            "⚠️ আপনার একটি প্রুফ অলরেডি অ্যাডমিন রিভিউতে আছে। ধৈর্য ধরুন।", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]])
        )
        return ConversationHandler.END

    await query.edit_message_text("📸 এখন আপনার কাজের *স্ক্রিনশটটি (Photo)* এখানে পাঠিয়ে দিন:")
    return ASK_TASK_PROOF


async def task_proof_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo_file_id = update.message.photo[-1].file_id
    
    success, result = db.submit_task_proof(user.id, "task_1", photo_file_id, TASK_REWARD)
    
    if not success:
        if result == "approved":
            await update.message.reply_text("⚠️ আপনি এই টাস্কটি ইতিমধ্যেই সম্পন্ন করেছেন।")
        else:
            await update.message.reply_text("⚠️ আপনার প্রুফ ইতিমধ্যেই পেন্ডিং লিস্টে আছে।")
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ আপনার স্ক্রিনশট জমা হয়েছে! অ্যাডমিন চেক করে ব্যালেন্স যোগ করে দেবে।",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]])
    )

    # অ্যাডমিন প্যানেলে ফটোসহ নোটিফিকেশন পাঠানো
    admin_keyboard = [[
        InlineKeyboardButton("✅ এপ্রুভ টাস্ক", callback_data=f"tk_approve_{result}"),
        InlineKeyboardButton("❌ রিজেক্ট টাস্ক", callback_data=f"tk_reject_{result}")
    ]]
    
    try:
        await context.bot.send_photo(
            chat_id=ADMIN_ID,
            photo=photo_file_id,
            caption=f"🎯 *নতুন টাস্ক সাবমিশন!*\n\n👤 ইউজার: {user.first_name} (`{user.id}`)\n💰 বোনাস: {TASK_REWARD} টাকা",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
    except Exception as e:
        logging.error(f"Admin task notify failed: {e}")
        
    return ConversationHandler.END


# ---------------- 🛠️ ADMIN APPROVE / REJECT FOR TASK ----------------

async def admin_handle_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    is_approve = query.data.startswith("tk_approve_")
    sub_id = int(query.data.replace("tk_approve_", "") if is_approve else query.data.replace("tk_reject_", ""))

    if is_approve:
        res = db.approve_task_submission(sub_id)
        if res:
            u_id, reward, t_id = res
            await query.edit_message_caption(caption="✅ টাস্কটি এপ্রুভ করা হয়েছে এবং ইউজারকে টাকা দেওয়া হয়েছে।")
            try:
                await context.bot.send_message(u_id, f"🎉 আপনার পাঠানো স্ক্রিনশটটি এপ্রুভ হয়েছে!\n+{reward} টাকা ব্যালেন্সে যোগ হয়েছে।")
            except: pass
        else:
            await query.edit_message_caption(caption="⚠️ ইতিমধ্যে অ্যাকশন নেওয়া হয়েছে বা ডাটা পাওয়া যায়নি।")
    else:
        res = db.reject_task_submission(sub_id)
        if res:
            u_id, t_id = res
            await query.edit_message_caption(caption="❌ টাস্কটি রিজেক্ট করা হয়েছে।")
            try:
                await context.bot.send_message(u_id, "❌ আপনার পাঠানো টাস্ক স্ক্রিনশটটি বাতিল (Reject) করা হয়েছে। সঠিক নিয়মে আবার চেষ্টা করুন।")
            except: pass
        else:
            await query.edit_message_caption(caption="⚠️ ইতিমধ্যে অ্যাকশন নেওয়া হয়েছে।")


# ---------------- Withdraw Conversation ----------------

async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = db.get_user(user_id)

    if user is None:
        await query.edit_message_text("⚠️ অ্যাকাউন্ট পাওয়া যায়নি। /start চাপুন।")
        return ConversationHandler.END

    if db.has_pending_withdrawal(user_id):
        keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
        await query.edit_message_text(
            "⏳ আপনার একটি উইথড্র রিকোয়েস্ট আগে থেকেই পেন্ডিং আছে।\n"
            "অ্যাডমিন রিভিউ করার পর নতুন রিকোয়েস্ট করতে পারবেন।",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    if user["balance"] < MIN_WITHDRAW:
        keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
        await query.edit_message_text(
            f"⚠️ *উইথড্র করতে পারছেন না*\n\n"
            f"মিনিমাম উইথড্র: *{MIN_WITHDRAW} টাকা*\n"
            f"আপনার ব্যালেন্স: *{user['balance']:.2f} টাকা*\n\n"
            f"আরও আয় করে আবার চেষ্টা করুন।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(m, callback_data=f"wd_method_{m}")] for m in WITHDRAW_METHODS]
    keyboard.append([InlineKeyboardButton("❌ বাতিল", callback_data="wd_cancel")])
    await query.edit_message_text(
        f"💵 *উইথড্র রিকোয়েস্ট*\n\n"
        f"💰 আপনার ব্যালেন্স: *{user['balance']:.2f} টাকা*\n"
        f"📌 মিনিমাম: {MIN_WITHDRAW} টাকা\n\n"
        f"পেমেন্ট মেথড সিলেক্ট করুন:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ASK_METHOD


async def withdraw_method_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("wd_method_", "")
    context.user_data["wd_method"] = method

    await query.edit_message_text(
        f"✅ মেথড: *{method}*\n\n"
        f"এখন আপনার *{method} নাম্বার* লিখে পাঠান:\n"
        f"(উদাহরণ: 01XXXXXXXXX)",
        parse_mode="Markdown"
    )
    return ASK_NUMBER


async def withdraw_number_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text.strip()

    if not (number.isdigit() and 9 <= len(number) <= 15):
        await update.message.reply_text(
            "⚠️ সঠিক নাম্বার লিখুন (শুধু সংখ্যা, যেমন: 01XXXXXXXXX)।"
        )
        return ASK_NUMBER

    context.user_data["wd_number"] = number
    user = db.get_user(update.effective_user.id)

    await update.message.reply_text(
        f"💰 আপনার ব্যালেন্স: *{user['balance']:.2f} টাকা*\n\n"
        f"কত টাকা উইথড্র করতে চান লিখুন (মিনিমাম {MIN_WITHDRAW} টাকা):",
        parse_mode="Markdown"
    )
    return ASK_AMOUNT


async def withdraw_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    try:
        amount = float(text)
    except ValueError:
        await update.message.reply_text("⚠️ সঠিক সংখ্যা লিখুন। যেমন: 50")
        return ASK_AMOUNT

    method = context.user_data.get("wd_method")
    number = context.user_data.get("wd_number")

    success, reason, wd_id = db.request_withdrawal(user_id, amount, method, number, MIN_WITHDRAW)

    if not success:
        messages = {
            "account_not_found": "⚠️ অ্যাকাউন্ট পাওয়া যায়নি। /start চাপুন।",
            "already_pending": "⏳ আপনার আগের একটি রিকোয়েস্ট এখনও পেন্ডিং আছে।",
            "below_minimum": f"⚠️ মিনিমাম {MIN_WITHDRAW} টাকা উইথড্র করতে হবে।",
            "insufficient_balance": "⚠️ আপনার ব্যালেন্সে এই পরিমাণ টাকা নেই।",
        }
        keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
        await update.message.reply_text(
            messages.get(reason, "⚠️ একটি সমস্যা হয়েছে, আবার চেষ্টা করুন।"),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data.clear()
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
    await update.message.reply_text(
        f"✅ *উইথড্র রিকোয়েস্ট জমা হয়েছে!*\n\n"
        f"💵 পরিমাণ: {amount:.2f} টাকা\n"
        f"📱 মেথড: {method}\n"
        f"🔢 নাম্বার: {number}\n\n"
        f"অ্যাডমিন এপ্রুভ করার পর টাকা পাঠানো হবে। ধৈর্য ধরুন।",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    # 📢 চ্যানেলে নতুন উইথড্র রিকোয়েস্টের নোটিফিকেশন পাঠানো
    try:
        channel_text = (
            f"🔔 *নতুন উইথড্র রিকোয়েস্ট!*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 ইউজার: {update.effective_user.first_name}\n"
            f"💵 পরিমাণ: *{amount:.2f} টাকা*\n"
            f"📱 মেথড: *{method}*\n"
            f"⏰ স্ট্যাটাস: ⏳ Pending (পেন্ডিং)\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🤖 Bot: @{(await context.bot.get_me()).username}"
        )
        await context.bot.send_message(chat_id=CHANNEL_ID, text=channel_text, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Channel notify failed: {e}")

    # অ্যাডমিনকে নোটিফাই করা
    admin_keyboard = [[
        InlineKeyboardButton("✅ এপ্রুভ", callback_data=f"wd_approve_{wd_id}"),
        InlineKeyboardButton("❌ রিজেক্ট", callback_data=f"wd_reject_{wd_id}"),
    ]]
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🔔 *নতুন উইথড্র রিকোয়েস্ট* #{wd_id}\n\n"
            f"👤 ইউজার: {update.effective_user.first_name} (@{update.effective_user.username or 'নাই'})\n"
            f"🆔 ID: `{update.effective_user.id}`\n"
            f"💵 পরিমাণ: {amount:.2f} টাকা\n"
            f"📱 মেথড: {method}\n"
            f"🔢 নাম্বার: {number}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
    except Exception as e:
        logging.error(f"Admin notify failed: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def withdraw_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    context.user_data.clear()
    await show_main_menu(update, context)
    return ConversationHandler.END


async def admin_handle_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ আপনি এডমিন নন।", show_alert=True)
        return

    is_approve = query.data.startswith("wd_approve_")
    wd_id = int(query.data.replace("wd_approve_", "") if is_approve else query.data.replace("wd_reject_", ""))

    wd = db.get_withdrawal(wd_id)
    if wd is None:
        await query.edit_message_text("⚠️ রিকোয়েস্ট খুঁজে পাওয়া যায়নি।")
        return
    if wd["status"] != "pending":
        await query.edit_message_text(f"ℹ️ এই রিকোয়েস্ট আগেই '{wd['status']}' করা হয়েছে।")
        return

    if is_approve:
        db.approve_withdrawal(wd_id)
        status_text = "✅ *এপ্রুভ করা হয়েছে*"
        user_msg = (
            f"✅ *আপনার উইথড্র রিকোয়েস্ট এপ্রুভ হয়েছে!*\n\n"
            f"💵 {wd['amount']:.2f} টাকা {wd['method']} ({wd['account_no']}) এ পাঠানো হচ্ছে।"
        )
    else:
        db.reject_withdrawal(wd_id)
        status_text = "❌ *রিজেক্ট করা হয়েছে (টাকা ব্যালেন্সে ফেরত)*"
        user_msg = (
            f"❌ *আপনার উইথড্র রিকোয়েস্ট রিজেক্ট হয়েছে।*\n\n"
            f"💵 {wd['amount']:.2f} টাকা আপনার ব্যালেন্সে ফেরত দেওয়া হয়েছে।"
        )

    await query.edit_message_text(
        f"{status_text}\n\n"
        f"👤 User ID: `{wd['user_id']}`\n"
        f"💵 পরিমাণ: {wd['amount']:.2f} টাকা\n"
        f"📱 মেথড: {wd['method']} ({wd['account_no']})",
        parse_mode="Markdown"
    )

    try:
        await context.bot.send_message(wd["user_id"], user_msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"User notify failed: {e}")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    withdraw_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(withdraw_start, pattern="^withdraw_start$")],
        states={
            ASK_METHOD: [
                CallbackQueryHandler(withdraw_method_chosen, pattern="^wd_method_"),
                CallbackQueryHandler(withdraw_cancel, pattern="^wd_cancel$"),
            ],
            ASK_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_number_received)],
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount_received)],
        },
        fallbacks=[CallbackQueryHandler(withdraw_cancel, pattern="^wd_cancel$")],
        per_message=False,
    )

    # 📸 স্ক্রিনশটের জন্য নতুন কনভারসেশন হ্যান্ডলার 
    task_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(submit_proof_start, pattern="^submit_proof_start$")],
        states={
            ASK_TASK_PROOF: [MessageHandler(filters.PHOTO, task_proof_received)],
        },
        fallbacks=[CallbackQueryHandler(withdraw_cancel, pattern="^menu$")],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(withdraw_conv)
    app.add_handler(task_conv)
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(show_balance, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(show_referral, pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(daily_bonus, pattern="^daily_bonus$"))
    app.add_handler(CallbackQueryHandler(show_task_menu, pattern="^task_menu$"))
    app.add_handler(CallbackQueryHandler(admin_handle_task, pattern="^tk_(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(admin_handle_withdrawal, pattern="^wd_(approve|reject)_"))

    print("✅ বট চালু হয়েছে...")
    app.run_polling()


if __name__ == "__main__":
    main()
