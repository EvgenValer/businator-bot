import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import database as db
import pytz
from datetime import time

TOKEN = os.environ.get("TOKEN")

KHABAROVSK = pytz.timezone("Asia/Vladivostok")

waiting_for_name = {}

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Вот что я умею:\n\n"
        "/register — зарегистрироваться\n"
        "/bead — добавить 1 бусинку 🔴\n"
        "/bead 3 — добавить несколько бусинок\n"
        "/stats — моя статистика\n"
        "/group — статистика группы (только в группе)\n"
        "/leave — выйти из группы (только в группе)\n"
        "/reset — сбросить свою статистику (только в личке)"
    )

async def register(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    chat = update.effective_chat
    group_id = chat.id if chat.type in ("group", "supergroup") else None

    existing = db.get_user_full_name(u.id)
    if existing:
        if group_id:
            already_in_group = db.get_user_groups(u.id)
            if group_id in already_in_group:
                await update.message.reply_text(
                    f"Ты уже зарегистрирован как {existing}.\n"
                    f"Хочешь изменить имя? Напиши /register Новое Имя"
                )
                return
        else:
            await update.message.reply_text(
                f"Ты уже зарегистрирован как {existing}.\n"
                f"Хочешь изменить имя? Напиши /register Новое Имя"
            )
            return

    if ctx.args and len(ctx.args) >= 2:
        full_name = " ".join(ctx.args)
        db.register_user(u.id, u.username or str(u.id), full_name, group_id)
        await update.message.reply_text(f"✅ Ты зарегистрирован как {full_name}")
        return

    waiting_for_name[u.id] = chat.id
    await update.message.reply_text("Напиши своё имя и фамилию:")

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    chat = update.effective_chat

    if u.id in waiting_for_name:
        full_name = update.message.text.strip()
        if len(full_name) < 2:
            await update.message.reply_text("Слишком короткое имя. Напиши имя и фамилию:")
            return

        original_chat_id = waiting_for_name.pop(u.id)
        group_id = original_chat_id if original_chat_id != chat.id else (
            chat.id if chat.type in ("group", "supergroup") else None
        )
        db.register_user(u.id, u.username or str(u.id), full_name, group_id)
        await update.message.reply_text(f"✅ Ты зарегистрирован как {full_name}")

async def bead(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat = update.effective_chat
    count = 1

    if ctx.args:
        try:
            count = int(ctx.args[0])
            if count < 1:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Укажи целое число: /bead 3")
            return

    ok = db.add_beads(uid, count)
    if not ok:
        await update.message.reply_text("Сначала зарегистрируйся: /register")
        return

    msg = f"🔴 Добавлено бусинок: {count}" if count > 1 else "🔴 Бусинка добавлена"
    await update.message.reply_text(msg)

    if chat.type == "private":
        full_name = db.get_user_full_name(uid)
        groups = db.get_user_groups(uid)
        for group_id in groups:
            try:
                if count == 1:
                    text = f"🔴 {full_name} добавил бусинку"
                elif count < 5:
                    text = f"🔴 {full_name} добавил {count} бусинки"
                else:
                    text = f"🔴 {full_name} добавил {count} бусинок"
                await ctx.bot.send_message(chat_id=group_id, text=text)
            except:
                pass

async def stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    d = db.get_stats(uid, 1)
    w = db.get_stats(uid, 7)
    a = db.get_stats(uid)
    if a is None:
        await update.message.reply_text("Ты ещё не зарегистрирован. Напиши /register")
        return
    await update.message.reply_text(
        f"📊 Твоя статистика:\n"
        f"Сегодня: {d} 🔴\n"
        f"За неделю: {w} 🔴\n"
        f"За всё время: {a} 🔴"
    )

async def group(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эта команда работает только в группе.")
        return
    rows = db.get_group_stats(chat.id)
    if not rows:
        await update.message.reply_text("В группе пока никто не зарегистрирован.")
        return

    total = len(rows)
    text = "📊 Статистика группы (за всё время):\n\n"
    for i, (name, cnt) in enumerate(rows):
        if i == 0:
            icon = "🥇"
        elif i == 1:
            icon = "🥈"
        elif i == 2:
            icon = "🥉"
        elif i == total - 1:
            icon = "💨"
        else:
            icon = "😐"
        text += f"{icon} {name}: {cnt} 🔴\n"
    await update.message.reply_text(text)

async def leave(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эта команда работает только в группе.")
        return
    uid = update.effective_user.id
    db.leave_group(uid, chat.id)
    await update.message.reply_text("✅ Ты вышел из группы. Твоя статистика здесь больше не отображается.")

async def reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type in ("group", "supergroup"):
        await update.message.reply_text("Сброс доступен только в личке с ботом.")
        return
    ok = db.reset_user(update.effective_user.id)
    if ok:
        await update.message.reply_text("✅ Твоя статистика обнулена.")
    else:
        await update.message.reply_text("Ты ещё не зарегистрирован. Напиши /register")

async def daily_stats(ctx: ContextTypes.DEFAULT_TYPE):
    groups = db.get_all_groups()
    for group_id in groups:
        rows = db.get_group_stats(group_id, days=1)
        if not rows:
            continue
        total = len(rows)
        text = "📊 Итог дня:\n\n"
        for i, (name, cnt) in enumerate(rows):
            if i == 0:
                icon = "🥇"
            elif i == 1:
                icon = "🥈"
            elif i == 2:
                icon = "🥉"
            elif i == total - 1:
                icon = "💨"
            else:
                icon = "😐"
            text += f"{icon} {name}: {cnt} 🔴\n"
        try:
            await ctx.bot.send_message(chat_id=group_id, text=text)
        except:
            pass

db.init_db()
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("register", register))
app.add_handler(CommandHandler("bead", bead))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("group", group))
app.add_handler(CommandHandler("leave", leave))
app.add_handler(CommandHandler("reset", reset))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.job_queue.run_daily(
    daily_stats,
    time=time(hour=22, minute=0, tzinfo=KHABAROVSK)
)

app.run_polling()