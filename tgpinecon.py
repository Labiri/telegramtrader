import logging
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
import requests
import os

# Initialize logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = "https://pineconnector.net/webhook/"
DATABASE_URL = os.environ['DATABASE_URL']

# States
APIKEY, TRADESIDE, SYMBOL, RISK, STOPPRICE, TAKEPROFIT, COMMENT, SKIP, MANAGE_PRESETS, ADD_PRESET, ADD_PRESET_NAME, DELETE_PRESET = range(12)

user_states = {}

# Database utility functions
def connect_db():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

def add_api_key_preset(user_id, preset_name, api_key):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO presets (user_id, preset_name, api_key) VALUES (%s, %s, %s) ON CONFLICT (user_id, preset_name) DO UPDATE SET api_key = EXCLUDED.api_key;", (user_id, preset_name, api_key))
    conn.commit()
    cur.close()
    conn.close()

def get_all_presets(user_id):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT preset_name, api_key FROM presets WHERE user_id = %s;", (user_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {row[0]: row[1] for row in rows}

def delete_api_key_preset(user_id, preset_name):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM presets WHERE user_id = %s AND preset_name = %s;", (user_id, preset_name))
    conn.commit()
    cur.close()
    conn.close()

def preset_exists(user_id, preset_name):
    with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT EXISTS(SELECT 1 FROM presets WHERE user_id = %s AND preset_name = %s)", (user_id, preset_name))
            return cursor.fetchone()[0]

def fetch_api_key_for_preset(user_id, preset_name):
    with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT api_key FROM presets WHERE user_id = %s AND preset_name = %s", (user_id, preset_name))
            result = cursor.fetchone()
            if result:
                return result[0]
    return ""

def fetch_api_key_presets(user_id):
    with psycopg2.connect(DATABASE_URL, sslmode='require') as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT preset_name FROM presets WHERE user_id = %s", (user_id,))
            presets = cursor.fetchall()
            return [preset[0] for preset in presets]

# Telegram Commands
def newsignal_command(update: Update, context: CallbackContext):
    user_states[update.message.from_user.id] = APIKEY
    keyboard = [
        [InlineKeyboardButton(preset_name, callback_data=f'preset_{preset_name}') for preset_name in fetch_api_key_presets(update.message.from_user.id)],
        [InlineKeyboardButton("Input manually", callback_data='input_manually')],
        [InlineKeyboardButton("Back to Main", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("Select a preset or input the license manually:", reply_markup=reply_markup)


def managepresets_command(update: Update, context: CallbackContext):
    manage_presets(update, context)




def start(update: Update, context: CallbackContext):
    main_menu(update, context)

def main_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("New Signal", callback_data='new_signal')],
        [InlineKeyboardButton("Manage API Key Presets", callback_data='manage_presets')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        update.message.reply_text("Choose an option:", reply_markup=reply_markup)
    except AttributeError:
        update.callback_query.edit_message_text("Choose an option:", reply_markup=reply_markup)

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = update.effective_user.id

    if query.data == "new_signal":
        user_states[user_id] = APIKEY
        keyboard = [
            [InlineKeyboardButton(preset_name, callback_data=f'preset_{preset_name}') for preset_name in fetch_api_key_presets(user_id)],
            [InlineKeyboardButton("Input manually", callback_data='input_manually')],
            [InlineKeyboardButton("Back to Main", callback_data='back_to_main')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("Select a preset or input the license manually:", reply_markup=reply_markup)

    elif query.data.startswith("preset_"):
        preset_name = query.data.split('_')[1]
        context.user_data['apikey'] = fetch_api_key_for_preset(user_id, preset_name)
        user_states[update.effective_user.id] = TRADESIDE
        query.edit_message_text("Enter trade side (long/short):")

    elif query.data == "input_manually":
        user_states[update.effective_user.id] = APIKEY
        query.edit_message_text("Enter API key:")

    elif query.data == "manage_presets":
        manage_presets(update, context)

    elif query.data == "add_preset":
        add_preset(update, context)

    elif query.data == "list_presets":
        list_presets(update, context)

    elif query.data == "main_menu":
        main_menu(update, context)

    elif query.data == "delete_preset":
        delete_preset_prompt(update, context)

    elif query.data.startswith("delete_"):
        preset_name = query.data.split('_')[1]
        if preset_exists(user_id, preset_name):
            delete_api_key_preset(user_id, preset_name)
            query.edit_message_text(f"Preset '{preset_name}' deleted.")
        else:
            query.edit_message_text("Error deleting preset. Preset does not exist.")


    elif query.data == "back_to_main":
        main_menu(update, context)

    elif query.data == "skip_sl":
        user_states[user_id] = TAKEPROFIT
        keyboard = [
            [InlineKeyboardButton("Skip", callback_data='skip_tp')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("Enter take profit:", reply_markup=reply_markup)
        
    elif query.data == "skip_tp":
        user_states[user_id] = COMMENT
        keyboard = [
            [InlineKeyboardButton("Skip", callback_data='skip_comment')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text("Enter comment:", reply_markup=reply_markup)

    elif query.data == "skip_comment":
        send_signal_message(update, context)
        del user_states[user_id]

def manage_presets(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("Add New Preset", callback_data='add_preset')],
        [InlineKeyboardButton("List Presets", callback_data='list_presets')],
        [InlineKeyboardButton("Delete Preset", callback_data='delete_preset')],
        [InlineKeyboardButton("Back to Main", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        # If this is a result of a callback query, edit the existing message.
        update.callback_query.edit_message_text("Manage your presets:", reply_markup=reply_markup)
    else:
        # If this is a result of a message update, send a new message.
        update.message.reply_text("Manage your presets:", reply_markup=reply_markup)

def add_preset(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    user_states[user_id] = ADD_PRESET
    keyboard = [
        [InlineKeyboardButton("Back to Main", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.edit_message_text("Please enter the API Key:", reply_markup=reply_markup)

def add_preset_name(update: Update, context: CallbackContext):
    friendly_name = update.message.text
    api_key = context.user_data.get('apikey_for_preset')
    if api_key:
        add_api_key_preset(update.message.from_user.id, friendly_name, api_key)
        del context.user_data['apikey_for_preset']
        update.message.reply_text(f"API Key preset saved with name: {friendly_name}")

def list_presets(update: Update, context: CallbackContext):
    user_presets = get_all_presets(update.effective_user.id)
    message = "Saved API Key Presets:\n"
    for name, api_key in user_presets.items():
        message += f"Name: {name}, API Key: {api_key}\n"
    keyboard = [
        [InlineKeyboardButton("Back to Manage Presets", callback_data='manage_presets')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.edit_message_text(message, reply_markup=reply_markup)

def delete_preset_prompt(update: Update, context: CallbackContext):
    user_presets = get_all_presets(update.effective_user.id)
    keyboard = [[InlineKeyboardButton(preset_name, callback_data=f'delete_{preset_name}')] for preset_name in user_presets]
    keyboard.append([InlineKeyboardButton("Back to Manage Presets", callback_data='manage_presets')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.callback_query.edit_message_text("Select the preset you want to delete:", reply_markup=reply_markup)

def process_input(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_state = user_states.get(user_id)

    try:
        if user_state == ADD_PRESET:
            context.user_data['apikey_for_preset'] = update.message.text
            user_states[user_id] = ADD_PRESET_NAME
            update.message.reply_text("Please provide a friendly name for this API Key:")

        elif user_state == ADD_PRESET_NAME:
            add_preset_name(update, context)
            del user_states[user_id]
    
        elif user_state == APIKEY:
            api_key_or_name = update.message.text
            api_key = fetch_api_key_for_preset(user_id, api_key_or_name)
            if api_key:
                context.user_data['apikey'] = api_key
            else:
                context.user_data['apikey'] = api_key_or_name
            user_states[user_id] = TRADESIDE
            update.message.reply_text("Enter trade side (long/short):")
            
        elif user_state == TRADESIDE:
            context.user_data['customtradeside'] = update.message.text
            user_states[user_id] = SYMBOL
            update.message.reply_text("Enter symbol:")
    
        elif user_state == SYMBOL:
            context.user_data['customsymbol'] = update.message.text
            user_states[user_id] = RISK
            update.message.reply_text("Enter risk:")
    
        elif user_state == RISK:
            context.user_data['risk'] = update.message.text
            user_states[user_id] = STOPPRICE
            keyboard = [
                [InlineKeyboardButton("Skip", callback_data='skip_sl')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text("Enter stop price:", reply_markup=reply_markup)
    
        elif user_state == STOPPRICE:
            context.user_data['stopprice'] = update.message.text
            user_states[user_id] = TAKEPROFIT
            keyboard = [
                [InlineKeyboardButton("Skip", callback_data='skip_tp')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text("Enter take profit:", reply_markup=reply_markup)
    
        elif user_state == TAKEPROFIT:
            context.user_data['takeprofit'] = update.message.text
            user_states[user_id] = COMMENT
            keyboard = [
                [InlineKeyboardButton("Skip", callback_data='skip_comment')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text("Enter comment:", reply_markup=reply_markup)

        elif user_state == COMMENT:
            context.user_data['comment'] = update.message.text
            send_signal_message(update, context)
            del user_states[user_id]  # Explicitly remove the user's state after processing

    except error.NetworkError:
        update.message.reply_text("Oops! Something went wrong with the network. Please try again later.")
        logger.error("Telegram API NetworkError occurred.")
        
    except Exception as e:
        update.message.reply_text(f"An unexpected error occurred: {str(e)}. Please retry.")
        logger.error(f"An unexpected error occurred: {str(e)}")

def send_signal_message(update, context):
    # Build the message to send to the webhook
    message_parts = [
        context.user_data.get('apikey', ""),
        context.user_data.get('customtradeside', ""),
        context.user_data.get('customsymbol', ""),
        f"risk={context.user_data.get('risk', '')}"
    ]
    
    if 'stopprice' in context.user_data:
        message_parts.append(f"sl={context.user_data['stopprice']}")
        
    if 'takeprofit' in context.user_data:
        message_parts.append(f"tp={context.user_data['takeprofit']}")
        
    if 'comment' in context.user_data:
        message_parts.append(f'comment="{context.user_data["comment"]}"')
    
    message = ','.join(message_parts)

    headers = {
        "Content-Type": "text/plain"
    }
    try:
        response = requests.post(WEBHOOK_URL, data=message, headers=headers)
        response.raise_for_status()
        feedback_message = f"Trading signal sent.\nOpen {context.user_data['customtradeside']} position for {context.user_data['customsymbol']} with a risk of {context.user_data['risk']}.\nStop Loss: {context.user_data.get('stopprice', 'Not Provided')}\nTake Profit: {context.user_data.get('takeprofit', 'Not Provided')}"
        logger.info(f"Successfully sent message to webhook. Response: {response.text}")
    except requests.RequestException as e:
        feedback_message = "Failed to send trading signal. Please try again later."
        logger.error(f"Error occurred while sending message to webhook: {e}")

    # Check if it's a callback query or a direct message
    if update.callback_query:
        update.callback_query.edit_message_text(feedback_message)
    else:
        update.message.reply_text(feedback_message)


def main():
    updater = Updater(TOKEN)
    updater.dispatcher.add_handler(CommandHandler('newsignal', newsignal_command))
    updater.dispatcher.add_handler(CommandHandler('managepresets', managepresets_command))
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))
    updater.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, process_input))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
