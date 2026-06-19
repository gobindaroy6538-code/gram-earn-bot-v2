import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from database import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
REFERRAL_BONUS = 5
DAILY_BONUS = 2

MIN_WITHDRAW = 20
ADMIN_ID = 8012544346

# --- FORCE JOIN CONFIGURATION ---
FORCE_CHANNELS = [
    -1004462605202,
]
CHANNEL_LINK = "https://t.me/gramearnbotV2"

CHANNEL_ID = FORCE_CHANNELS[0] 
WITHDRAW_LOG_ID = CHANNEL_ID  

WITHDRAW_METHODS = ["bKash", "Nagad", "Rocket"]

# --- Conversation States ---
ASK_METHOD, ASK_NUMBER, ASK_AMOUNT, ASK_WD_PHOTO = range(4)
ASK_TASK_PROOF = 4

# এডমিন প্যানেল স্টেট
ASK_ADMIN_CHECK_USER = 5
ASK_ADMIN_CHANGE_BAL_ID = 6
ASK_ADMIN_CHANGE_BAL_AMT = 7
ASK_ADMIN_BROADCAST = 8
ASK_ADMIN_ADD_TASK_DATA = 9
ASK_ADMIN_BAN_USER = 10
ASK_ADMIN_UNBAN_USER = 11

db = Database()


async def is_user_joined_all(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    for channel in FORCE_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logger.error(f"Force Join Check Error for channel {channel}: {e}")
            continue
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if db.is_user_banned(user.id):
        await update.message.reply_text("❌ দুঃখিত, আপনার অ্যাকাউন্টটি ব্যান করা হয়েছে।")
        return

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

    if not await is_user_joined_all(user.id, context):
        await show_force_join_msg(update, context)
        return

    await show_main_menu(update, context)


async def show_force_join_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚠️ *আমাদের অফিসিয়াল চ্যানেলে জয়েন করুন!*\n\n"
        "বটের মূল মেনু দেখতে এবং টাকা আয় করতে নিচের চ্যানেলে জয়েন করা বাধ্যতামূলক। "
        "জয়েন করার পর নিচে '✅ জয়েন করেছি' বাটনে ক্লিক করুন।"
    )
    keyboard = [
        [InlineKeyboardButton("📢 চ্যানেলে জয়েন করুন", url=CHANNEL_LINK)],
        [InlineKeyboardButton("✅ জয়েন করেছি", callback_data="check_joined")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)


async def check_joined_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if db.is_user_banned(user_id):
        await query.answer("❌ আপনার অ্যাকাউন্টটি ব্যানড!", show_alert=True)
        return

    if await is_user_joined_all(user_id, context):
        await query.answer("🎉 ধন্যবাদ! আপনি সফলভাবে জয়েন করেছেন।", show_alert=True)
        await show_main_menu(update, context)
    else:
        await query.answer("❌ আপনি এখনো চ্যানেলে জয়েন করেননি! দয়া করে জয়েন করুন।", show_alert=True)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_user_banned(user_id):
        if update.callback_query:
            await update.callback_query.answer("❌ আপনার অ্যাকাউন্টটি ব্যানড!", show_alert=True)
        else:
            await update.message.reply_text("❌ আপনার অ্যাকাউন্টটি ব্যানড!")
        return

    if not await is_user_joined_all(user_id, context):
        await show_force_join_msg(update, context)
        return

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
    user_id = query.from_user.id
    if db.is_user_banned(user_id):
        await query.answer("❌ আপনার অ্যাকাউন্টটি ব্যানড!", show_alert=True)
        return

    await query.answer()
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
    user_id = query.from_user.id
    if db.is_user_banned(user_id):
        await query.answer("❌ আপনার অ্যাকাউন্টটি ব্যানড!", show_alert=True)
        return

    await query.answer()
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
    user_id = query.from_user.id
    if db.is_user_banned(user_id):
        await query.answer("❌ আপনার অ্যাকাউন্টটি ব্যানড!", show_alert=True)
        return

    await query.answer()
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


# ---------------- TASK SYSTEM ----------------

async def show_task_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if db.is_user_banned(user_id):
        await query.answer("❌ আপনার অ্যাকাউন্টটি ব্যানড!", show_alert=True)
        return

    await query.answer()
    tasks = db.get_all_tasks()

    if not tasks:
        text = "🎯 *টাস্ক লিস্ট*\n\nবর্তমানে কোনো কাজ উপলব্ধ নেই। দয়া করে পরে চেষ্টা করুন।"
        keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = "🎯 *টাস্ক লিস্ট*\n\nনিচের যেকোনো একটি টাস্ক সিলেক্ট করে কাজ সম্পন্ন করুন:"
    keyboard = []
    for task in tasks:
        keyboard.append([InlineKeyboardButton(f"{task['title']} ({task['reward']} টাকা)", callback_data=f"view_task_{task['task_id']}")])
    keyboard.append([InlineKeyboardButton("🏠 মেনু", callback_data="menu")])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def view_single_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if db.is_user_banned(query.from_user.id):
        await query.answer("❌ আপনার অ্যাকাউন্টটি ব্যানড!", show_alert=True)
        return

    await query.answer()
    task_id = int(query.data.replace("view_task_", ""))
    task = db.get_task(task_id)

    if not task:
        await query.edit_message_text("⚠️ টাস্কটি খুঁজে পাওয়া যায়নি।")
        return

    text = (
        f"*{task['title']}*\n\n"
        f"📌 *কাজ:* {task['desc']}\n\n"
        f"💰 বোনাস: *{task['reward']} টাকা*\n\n"
        f"👇 নিচে 'স্ক্রিনশট জমা দিন' বাটনে ক্লিক করে প্রুফ পাঠান।"
    )
    keyboard = [
        [InlineKeyboardButton("🔗 লিংকে যান", url=task["url"])],
        [InlineKeyboardButton("📤 স্ক্রিনশট জমা দিন", callback_data=f"submit_proof_{task_id}")],
        [InlineKeyboardButton("🔙 পিছনে যান", callback_data="task_menu")]
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def submit_proof_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if db.is_user_banned(user_id):
        await query.answer("❌ আপনার অ্যাকাউন্টটি ব্যানড!", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    task_id = int(query.data.replace("submit_proof_", ""))
    context.user_data["current_task_id"] = task_id

    if db.has_pending_task(user_id, task_id):
        await query.edit_message_text(
            "⚠️ আপনার এই কাজের একটি প্রুফ অলরেডি অ্যাডমিন রিভিউতে আছে।",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]])
        )
        return ConversationHandler.END

    await query.edit_message_text("📸 এখন আপনার কাজের *স্ক্রিনশটটি (Photo)* এখানে পাঠিয়ে দিন:")
    return ASK_TASK_PROOF


async def task_proof_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if db.is_user_banned(user.id):
        await update.message.reply_text("❌ আপনার অ্যাকাউন্টটি ব্যানড!")
        return ConversationHandler.END

    if not update.message.photo:
        await update.message.reply_text("⚠️ দয়া করে একটি স্ক্রিনশট (Photo) পাঠান:")
        return ASK_TASK_PROOF

    photo_file_id = update.message.photo[-1].file_id
    task_id = context.user_data.get("current_task_id")

    task = db.get_task(task_id)
    if not task:
        await update.message.reply_text("⚠️ টাস্কটি সিস্টেম থেকে ডিলিট করা হয়েছে।")
        return ConversationHandler.END

    success, result = db.submit_task_proof(user.id, task_id, photo_file_id, task["reward"])

    if not success:
        if result == "approved":
            await update.message.reply_text("⚠️ আপনি এই টাস্কটি ইতিমধ্যেই সম্পন্ন করেছেন।")
        else:
            await update.message.reply_text("⚠️ আপনার প্রুফ ইতিমধ্যেই পেন্ডিং লিস্টে আছে।")
        return ConversationHandler.END

    await update.message.reply_text(
        "✅ আপনার স্ক্রিনশট জমা হয়েছে! অ্যাডমিন চেক করে ব্যালেন্স যোগ করে দেবে।",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]])
    )

    admin_keyboard = [[
        InlineKeyboardButton("✅ এপ্রুভ টাস্ক", callback_data=f"tk_approve_{result}"),
        InlineKeyboardButton("❌ রিজেক্ট টাস্ক", callback_data=f"tk_reject_{result}")
    ]]

    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=photo_file_id,
            caption=f"🎯 *নতুন টাস্ক সাবমিশন!*\n\n📌 কাজ: {task['title']}\n👤 ইউজার: {user.first_name} (`{user.id}`)\n💰 বোনাস: {task['reward']} টাকা\nStatus: ⏳ Pending",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(admin_keyboard)
        )
    except Exception as e:
        logger.error(f"❌ Channel task notify failed: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def channel_task_adder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.channel_post.chat.id != CHANNEL_ID:
        return
    text = update.channel_post.text
    if text and text.startswith("#addtask"):
        try:
            lines = text.split("\n")
            title = lines[1].strip()
            desc = lines[2].strip()
            reward = float(lines[3].strip())
            url = lines[4].strip()
            db.add_new_task(title, desc, reward, url)
            await update.channel_post.reply_text(f"✅ *নতুন টাস্ক সফলভাবে যুক্ত হয়েছে!*\n\n📋 {title}")
        except Exception as e:
            logger.error(f"Channel task parsing error: {e}")
            await update.channel_post.reply_text(
                "⚠️ সঠিক ফরম্যাট ব্যবহার করুন:\n#addtask\nটাইটেল\nকাজের বিবরণ\nটাকা\nলিংক"
            )


async def admin_handle_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.answer("⛔ আপনি এই বটের মূল এডমিন নন!", show_alert=True)
        return

    is_approve = query.data.startswith("tk_approve_")
    sub_id = int(query.data.replace("tk_approve_", "") if is_approve else query.data.replace("tk_reject_", ""))

    if is_approve:
        res = db.approve_task_submission(sub_id)
        if res:
            u_id, reward, t_id = res
            await query.edit_message_caption(caption="✅ এই টাস্কটি এপ্রুভ করা হয়েছে।")
            try:
                await context.bot.send_message(u_id, f"🎉 আপনার পাঠানো স্ক্রিনশটটি এপ্রুভ হয়েছে!\n+{reward} টাকা ব্যালেন্সে যোগ হয়েছে।")
            except Exception:
                pass
        else:
            await query.edit_message_caption(caption="⚠️ ইতিমধ্যে অ্যাকশন নেওয়া হয়েছে।")
    else:
        res = db.reject_task_submission(sub_id)
        if res:
            u_id, t_id = res
            await query.edit_message_caption(caption="❌ এই টাস্কটি রিজেক্ট করা হয়েছে।")
            try:
                await context.bot.send_message(u_id, "❌ আপনার পাঠানো টাস্ক স্ক্রিনশটটি বাতিল (Reject) করা হয়েছে।")
            except Exception:
                pass
        else:
            await query.edit_message_caption(caption="⚠️ ইতিমধ্যে অ্যাকশন নেওয়া হয়েছে।")


# ---------------- WITHDRAW ----------------

async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if db.is_user_banned(user_id):
        await query.answer("❌ আপনার অ্যাকাউন্টটি ব্যানড!", show_alert=True)
        return ConversationHandler.END

    if not await is_user_joined_all(user_id, context):
        await show_force_join_msg(update, context)
        return ConversationHandler.END

    user = db.get_user(user_id)
    if user is None:
        await query.edit_message_text("⚠️ অ্যাকাউন্ট পাওয়া যায়নি। /start চাপুন।")
        return ConversationHandler.END

    if db.has_pending_withdrawal(user_id):
        keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
        await query.edit_message_text(
            "⏳ আপনার একটি উইথড্র রিকোয়েস্ট আগে থেকেই পেন্ডিং আছে।",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    if user["balance"] < MIN_WITHDRAW:
        keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
        await query.edit_message_text(
            f"⚠️ *উইথড্র করতে পারছেন না*\n\nমিনিমাম উইথড্র: *{MIN_WITHDRAW} টাকা*\nআপনার ব্যালেন্স: *{user['balance']:.2f} টাকা*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(m, callback_data=f"wd_method_{m}")] for m in WITHDRAW_METHODS]
    keyboard.append([InlineKeyboardButton("❌ বাতিল", callback_data="wd_cancel")])
    await query.edit_message_text(
        f"💵 *উইথড্র রিকোয়েস্ট*\n\nআপনার ব্যালেন্স: *{user['balance']:.2f} টাকা*\n\nপেমেন্ট মেথড সিলেক্ট করুন:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ASK_METHOD


async def withdraw_method_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("wd_method_", "")
    context.user_data["wd_method"] = method
    await query.edit_message_text(f"✅ মেথড: *{method}*\n\nএখন আপনার *{method} নাম্বার* লিখে পাঠান:")
    return ASK_NUMBER


async def withdraw_number_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text.strip()
    if not (number.isdigit() and 9 <= len(number) <= 15):
        await update.message.reply_text("⚠️ সঠিক নাম্বার লিখুন (শুধু সংখ্যা)।")
        return ASK_NUMBER

    context.user_data["wd_number"] = number
    await update.message.reply_text(f"💰 কত টাকা উইথড্র করতে চান লিখুন (মিনিমাম {MIN_WITHDRAW} টাকা):")
    return ASK_AMOUNT


async def withdraw_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        amount = float(text)
        context.user_data["wd_amount"] = amount
    except ValueError:
        await update.message.reply_text("⚠️ সঠিক সংখ্যা লিখুন।")
        return ASK_AMOUNT

    if amount < MIN_WITHDRAW:
        await update.message.reply_text(f"⚠️ মিনিমাম {MIN_WITHDRAW} টাকা উইথড্র করতে হবে। আবার লিখুন:")
        return ASK_AMOUNT

    user = db.get_user(update.effective_user.id)
    if user["balance"] < amount:
        await update.message.reply_text("⚠️ আপনার ব্যালেন্সে পর্যাপ্ত টাকা নেই। আবার লিখুন:")
        return ASK_AMOUNT

    await update.message.reply_text("📸 উইথড্র করার প্রমাণ বা পেমেন্ট প্রুফ হিসেবে একটি স্ক্রিনশট/ছবি (Photo) পাঠান:")
    return ASK_WD_PHOTO


async def withdraw_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if db.is_user_banned(user_id):
        await update.message.reply_text("❌ আপনার অ্যাকাউন্টটি ব্যানড!")
        return ConversationHandler.END

    if not update.message.photo:
        await update.message.reply_text("⚠️ দয়া করে একটি বৈধ ছবি (Photo) পাঠান:")
        return ASK_WD_PHOTO

    photo_id = update.message.photo[-1].file_id
    amount = context.user_data.get("wd_amount")
    method = context.user_data.get("wd_method")
    number = context.user_data.get("wd_number")

    success, reason, wd_id = db.request_withdrawal(user_id, amount, method, number, photo_id, MIN_WITHDRAW)

    if not success:
        messages = {
            "account_not_found": "⚠️ অ্যাকাউন্ট পাওয়া যায়নি।",
            "already_pending": "⏳ আপনার একটি উইথড্র রিকোয়েস্ট পেন্ডিং আছে।",
            "insufficient_balance": "⚠️ পর্যাপ্ত ব্যালেন্স নেই।",
        }
        keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
        await update.message.reply_text(messages.get(reason, "⚠️ সমস্যা হয়েছে।"), reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data.clear()
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton("🏠 মেনু", callback_data="menu")]]
    await update.message.reply_text(
        f"✅ *উইথড্র রিকোয়েস্ট স্ক্রিনশটসহ জমা হয়েছে!*\n\n💵 পরিমাণ: {amount:.2f} টাকা\n📱 মেথড: {method}\n🔢 নাম্বার: {number}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    admin_keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ এপ্রুভ উইথড্র", callback_data=f"wd_approve_{wd_id}"),
        InlineKeyboardButton("❌ রিজেক্ট উইথড্র", callback_data=f"wd_reject_{wd_id}"),
    ]])

    bot_username = (await context.bot.get_me()).username
    channel_text = (
        f"🔔 *নতুন উইথড্র সাবমিশন (প্রুফসহ)!* #{wd_id}\n\n"
        f"👤 ইউজার: {update.effective_user.first_name}\n"
        f"🆔 ID: `{user_id}`\n"
        f"💵 পরিমাণ: {amount:.2f} টাকা\n"
        f"📱 মেথড: {method}\n"
        f"🔢 নাম্বার: {number}\n"
        f"🤖 Bot: @{bot_username}"
    )

    try:
        await context.bot.send_photo(
            chat_id=WITHDRAW_LOG_ID,
            photo=photo_id,
            caption=channel_text,
            parse_mode="Markdown",
            reply_markup=admin_keyboard
        )
    except Exception as e:
        logger.error(f"❌ FAILED to send withdraw notification: {e}")

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
        await query.answer("⛔ আপনি এই বটের মূল এডমিন নন!", show_alert=True)
        return

    is_approve = query.data.startswith("wd_approve_")
    wd_id = int(query.data.replace("wd_approve_", "") if is_approve else query.data.replace("wd_reject_", ""))

    wd = db.get_withdrawal(wd_id)
    if wd is None:
        await query.edit_message_caption(caption="⚠️ রিকোয়েস্ট খুঁজে পাওয়া যায়নি।")
        return
    if wd["status"] != "pending":
        await query.edit_message_caption(caption=f"ℹ️ এই রিকোয়েস্ট আগেই '{wd['status']}' করা হয়েছে।")
        return

    if is_approve:
        db.approve_withdrawal(wd_id)
        await query.edit_message_caption(caption="✅ উইথড্র রিকোয়েস্ট এপ্রুভ করা হয়েছে।")
        try:
            await context.bot.send_message(
                wd["user_id"], 
                f"✅ *আপনার উইথড্র রিকোয়েস্ট এপ্রুভ হয়েছে!*\n\n💵 {wd['amount']:.2f} টাকা {wd['method']} ({wd['account_no']}) এ পাঠানো হয়েছে।",
                parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        db.reject_withdrawal(wd_id)
        await query.edit_message_caption(caption="❌ উইথড্র রিকোয়েস্ট রিজেক্ট করা হয়েছে। টাকা ফেরত দেওয়া হয়েছে।")
        try:
            await context.bot.send_message(
                wd["user_id"], 
                f"❌ *আপনার উইথড্র রিকোয়েস্ট রিজেক্ট হয়েছে!*\n\n💵 {wd['amount']:.2f} টাকা আপনার মেইন ব্যালেন্সে ফেরত দেওয়া হয়েছে।",
                parse_mode="Markdown"
            )
        except Exception:
            pass


# ---------------- ADMIN PANEL SYSTEM ----------------

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        if update.message:
            await update.message.reply_text("⛔ আপনি এই বটের অ্যাডমিন নন!")
        return ConversationHandler.END

    text = "👑 *Gram Earn Bot - এডমিন প্যানেল*"
    keyboard = [
        [InlineKeyboardButton("🔍 ইউজার চেক", callback_data="adm_check_user"),
         InlineKeyboardButton("💰 ব্যালেন্স পরিবর্তন", callback_data="adm_change_bal")],
        [InlineKeyboardButton("🚫 ইউজার ব্যান", callback_data="adm_ban_user"),
         InlineKeyboardButton("✅ ইউজার আনব্যান", callback_data="adm_unban_user")],
        [InlineKeyboardButton("📢 ব্রডকাস্ট নোটিশ", callback_data="adm_broadcast"),
         InlineKeyboardButton("🎯 নতুন টাস্ক যোগ", callback_data="adm_add_task")],
        [InlineKeyboardButton("❌ প্যানেল বন্ধ করুন", callback_data="adm_close")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)
    return ConversationHandler.END


async def adm_check_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("🔍 Use ID পাঠান:")
    return ASK_ADMIN_CHECK_USER


async def adm_check_user_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text.strip())
        user = db.get_user(target_id)
        if not user:
            await update.message.reply_text("❌ ইউজার পাওয়া যায়নি।")
            return ConversationHandler.END
        
        ref_count = db.get_referral_count(target_id)
        is_ban = "🚫 Banned" if db.is_user_banned(target_id) else "✅ Active"
        text = (
            f"👤 *ইউজার ইনফো: {user['name']}*\n\n"
            f"🆔 ID: `{target_id}`\n"
            f"🚦 স্ট্যাটাস: *{is_ban}*\n"
            f"💰 ব্যালেন্স: {user['balance']:.2f} টাকা\n"
            f"👥 মোট রেফার: {ref_count} জন"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
    except ValueError:
        return ASK_ADMIN_CHECK_USER
    return ConversationHandler.END


async def adm_change_bal_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("💰 User ID দিন:")
    return ASK_ADMIN_CHANGE_BAL_ID


async def adm_change_bal_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text.strip())
        if not db.get_user(target_id):
            await update.message.reply_text("❌ ইউজার পাওয়া যায়নি।")
            return ASK_ADMIN_CHANGE_BAL_ID
        
        context.user_data["adm_target_id"] = target_id
        await update.message.reply_text("👉 কত টাকা যোগ/বিয়োগ করতে চান লিখুন (যেমন 50 বা -50):")
        return ASK_ADMIN_CHANGE_BAL_AMT
    except ValueError:
        return ASK_ADMIN_CHANGE_BAL_ID


async def adm_change_bal_amt_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        target_id = context.user_data.get("adm_target_id")
        db.add_balance(target_id, amount)
        await update.message.reply_text(f"✅ সফলভাবে ব্যালেন্স আপডেট করা হয়েছে।")
    except ValueError:
        return ASK_ADMIN_CHANGE_BAL_AMT
    context.user_data.clear()
    return ConversationHandler.END


async def adm_ban_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("🚫 ব্যান করার জন্য User ID পাঠান:")
    return ASK_ADMIN_BAN_USER

async def adm_ban_user_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text.strip())
        if target_id == ADMIN_ID:
            await update.message.reply_text("❌ নিজেকে ব্যান করা সম্ভব নয়।")
            return ConversationHandler.END
        if not db.get_user(target_id):
            await update.message.reply_text("❌ ইউজার পাওয়া যায়নি।")
            return ConversationHandler.END
        db.ban_user(target_id)
        await update.message.reply_text("✅ ইউজার ব্যান করা হয়েছে।")
    except ValueError:
        return ASK_ADMIN_BAN_USER
    return ConversationHandler.END


async def adm_unban_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("✅ আনব্যান করার জন্য User ID পাঠান:")
    return ASK_ADMIN_UNBAN_USER

async def adm_unban_user_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text.strip())
        if not db.get_user(target_id):
            await update.message.reply_text("❌ ইউজার পাওয়া যায়নি।")
            return ConversationHandler.END
        db.unban_user(target_id)
        await update.message.reply_text("✅ ইউজার আনব্যান করা হয়েছে।")
    except ValueError:
        return ASK_ADMIN_UNBAN_USER
    return ConversationHandler.END


async def adm_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("📢 নোটিফিকেশন মেসেজটি লিখুন:")
    return ASK_ADMIN_BROADCAST


async def adm_broadcast_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_text = update.message.text
    users = db.get_all_users()
    if not users:
        await update.message.reply_text("❌ কোনো ইউজার নেই।")
        return ConversationHandler.END

    sent_count = 0
    for u in users:
        try:
            await context.bot.send_message(chat_id=u['user_id'], text=f"📢 *নোটিশ:*\n\n{msg_text}", parse_mode="Markdown")
            sent_count += 1
        except Exception:
            continue
    await update.message.reply_text(f"✅ মোট {sent_count} জনকে পাঠানো হয়েছে।")
    return ConversationHandler.END


async def adm_add_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🎯 *নতুন টাস্ক যোগ করার সঠিক নিয়ম*\n\n"
        "নিচের ফরম্যাটে তথ্যটি একসাথে লিখে পাঠান (মাঝখানে `||` চিহ্ন ব্যবহার করুন):\n\n"
        "`টাইটেল || কাজের বিবরণ || টাকা || লিংক` \n\n"
        "*উদাহরণ:*\n"
        "`ইউটিউব সাবস্ক্রাইব || চ্যানেলটি সাবস্ক্রাইব করে স্ক্রিনশট দিন || 5.00 || https://youtube.com`",
        parse_mode="Markdown"
    )
    return ASK_ADMIN_ADD_TASK_DATA


async def adm_add_task_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        parts = [p.strip() for p in update.message.text.split("||")]
        
        if len(parts) < 4:
            await update.message.reply_text("⚠️ ফরম্যাট ভুল হয়েছে! ৪টি তথ্যই থাকতে হবে এবং মাঝে || দিতে হবে। আবার চেষ্টা করুন:")
            return ASK_ADMIN_ADD_TASK_DATA
        
        title = parts[0]
        desc = parts[1]
        reward = float(parts[2])
        url = parts[3]
        
        db.add_new_task(title, desc, reward, url)
        await update.message.reply_text(f"✅ *নতুন টাস্ক সফলভাবে যুক্ত হয়েছে!*\n\n📌 টাইটেল: {title}\n💰 রিওয়ার্ড: {reward} টাকা")
    except ValueError:
        await update.message.reply_text("⚠️ টাকার পরিমাণটি শুধু সংখ্যায় লিখুন (যেমন: 5.00 বা 3)। আবার চেষ্টা করুন:")
        return ASK_ADMIN_ADD_TASK_DATA
    except Exception as e:
        logger.error(f"Task add error: {e}")
        await update.message.reply_text("⚠️ একটি সমস্যা হয়েছে। আবার চেষ্টা করুন।")
    return ConversationHandler.END


async def adm_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("🔒 প্যানেল বন্ধ।")
    return ConversationHandler.END


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
            ASK_WD_PHOTO: [MessageHandler(filters.PHOTO, withdraw_photo_received)],
        },
        fallbacks=[CallbackQueryHandler(withdraw_cancel, pattern="^wd_cancel$")],
        per_message=False,
    )

    task_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(submit_proof_start, pattern="^submit_proof_")],
        states={
            ASK_TASK_PROOF: [MessageHandler(filters.PHOTO, task_proof_received)],
        },
        fallbacks=[CallbackQueryHandler(withdraw_cancel, pattern="^menu$")],
        per_message=False,
    )

    admin_conv = ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_menu),
            CallbackQueryHandler(adm_check_user_start, pattern="^adm_check_user$"),
            CallbackQueryHandler(adm_change_bal_start, pattern="^adm_change_bal$"),
            CallbackQueryHandler(adm_ban_user_start, pattern="^adm_ban_user$"),
            CallbackQueryHandler(adm_unban_user_start, pattern="^adm_unban_user$"),
            CallbackQueryHandler(adm_broadcast_start, pattern="^adm_broadcast$"),
            CallbackQueryHandler(adm_add_task_start, pattern="^adm_add_task$"),
        ],
        states={
            ASK_ADMIN_CHECK_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_check_user_received)],
            ASK_ADMIN_CHANGE_BAL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_change_bal_id_received)],
            ASK_ADMIN_CHANGE_BAL_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_change_bal_amt_received)],
            ASK_ADMIN_BAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_ban_user_received)],
            ASK_ADMIN_UNBAN_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_unban_user_received)],
            ASK_ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_broadcast_received)],
            ASK_ADMIN_ADD_TASK_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, adm_add_task_received)],
        },
        fallbacks=[CallbackQueryHandler(adm_close, pattern="^adm_close$"), CommandHandler("admin", admin_menu)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(withdraw_conv)
    app.add_handler(task_conv)
    app.add_handler(admin_conv)

    app.add_handler(CallbackQueryHandler(check_joined_callback, pattern="^check_joined$"))
    app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(show_balance, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(show_referral, pattern="^referral$"))
    app.add_handler(CallbackQueryHandler(daily_bonus, pattern="^daily_bonus$"))
    app.add_handler(CallbackQueryHandler(show_task_menu, pattern="^task_menu$"))
    app.add_handler(CallbackQueryHandler(view_single_task, pattern="^view_task_"))
    app.add_handler(CallbackQueryHandler(admin_handle_task, pattern="^tk_(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(admin_handle_withdrawal, pattern="^wd_(approve|reject)_"))
    app.add_handler(CallbackQueryHandler(adm_close, pattern="^adm_close$"))

    app.add_handler(MessageHandler(filters.ChatType.CHANNEL & filters.TEXT, channel_task_adder))

    print("✅ বট চালু হয়েছে...")
    app.run_polling()

if __name__ == "__main__":
    main()
