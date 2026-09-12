import os
import time
import threading
from dotenv import load_dotenv
import telebot
from telebot import types
from database import init_db, get_top_proxies
from extractor import extract_from_all_channels
from checker import check_all_active_proxies

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PROXY_CHANNELS = os.getenv("PROXY_CHANNELS", "").split(",")
CHECK_INTERVAL_SECONDS = 30 * 60

bot = telebot.TeleBot(BOT_TOKEN)


def safe_edit_message(text, chat_id, message_id, **kwargs):
    try:
        bot.edit_message_text(text, chat_id, message_id, **kwargs)
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" not in str(e):
            print(f"[warning] edit_message_text failed: {e}")


def safe_answer_callback(call_id):
    try:
        bot.answer_callback_query(call_id)
    except telebot.apihelper.ApiTelegramException as e:
        print(f"[warning] answer_callback_query failed: {e}")


def build_start_menu_text_and_markup():
    text = "Hi!\nWelcome to ProxySender Bot.\nPlease choose the type of your proxies:"
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("MTProto", callback_data="proxy_mtproto"),
        types.InlineKeyboardButton("SOCKS5", callback_data="proxy_socks5"),
    )
    markup.row(types.InlineKeyboardButton("Both", callback_data="proxy_both"))
    return text, markup


@bot.message_handler(commands=["start"])
def start_command(message):
    text, markup = build_start_menu_text_and_markup()
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("proxy_"))
def proxy_type_selected(call):
    proxy_type = call.data.split("_", 1)[1]
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("MCI", callback_data=f"op_{proxy_type}_mci"),
        types.InlineKeyboardButton("Irancell", callback_data=f"op_{proxy_type}_irancell"),
    )
    markup.row(
        types.InlineKeyboardButton("Rightel", callback_data=f"op_{proxy_type}_rightel"),
        types.InlineKeyboardButton("WiFi", callback_data=f"op_{proxy_type}_wifi"),
    )
    safe_answer_callback(call.id)
    safe_edit_message("Please choose your operator:", call.message.chat.id, call.message.id, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("op_"))
def operator_selected(call):
    _, proxy_type, operator = call.data.split("_", 2)
    safe_answer_callback(call.id)

    proxies = get_top_proxies(operator=operator, proxy_type=proxy_type, limit=5)

    if not proxies:
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🔄 Try again", callback_data="restart"))
        safe_edit_message(
            "Sorry.I couldn't find any active proxies for your selection.\nLet's try again:",
            call.message.chat.id, call.message.id,
            reply_markup=markup
        )
        return

    markup = types.InlineKeyboardMarkup()
    for proxy in proxies:
        label = f"⚡ {proxy['ping_ms']}ms - {proxy['server']}"
        markup.row(types.InlineKeyboardButton(label, url=proxy["proxy_url"]))
    markup.row(types.InlineKeyboardButton("🔄 Try again", callback_data="restart"))

    safe_edit_message(
        f"✅ {len(proxies)} proxies found:\nClick on any to connect.",
        call.message.chat.id, call.message.id,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "restart")
def restart_flow(call):
    safe_answer_callback(call.id)
    text, markup = build_start_menu_text_and_markup()
    safe_edit_message(text, call.message.chat.id, call.message.id, reply_markup=markup)


def background_worker():
    time.sleep(CHECK_INTERVAL_SECONDS)
    while True:
        try:
            print("Start extracting and testing proxies...")
            extract_from_all_channels(PROXY_CHANNELS)
            check_all_active_proxies()
            print("Done")
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    init_db()

    print("Start extracting and testing proxies...")
    extract_from_all_channels(PROXY_CHANNELS)
    check_all_active_proxies()

    worker_thread = threading.Thread(target=background_worker, daemon=True)
    worker_thread.start()

    print("Starting the bot...")

    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except Exception as e:
            print(f"Error: {e}\nTrying again in 5 seconds...")
            time.sleep(5)