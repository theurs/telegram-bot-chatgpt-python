#!/usr/bin/env python3


import io
import html
import os
import re
import time
import threading
import tempfile

import telebot

import cfg
import gpt_basic
import my_dic
import my_log
import my_trans
import my_tts
import my_stt
import utils


# set the working folder = the folder where the script is located
os.chdir(os.path.abspath(os.path.dirname(__file__)))


bot = telebot.TeleBot(cfg.token, skip_pending=True)
BOT_ID = bot.get_me().id


# folder for permanent dictionaries, bot memory
if not os.path.exists('db'):
    os.mkdir('db')

# max GPT request (telegram limit actually)
GPT_MAX = 4000

# saved pairs of {{id:(url, token, lang)}}
DB = gpt_basic.TOKENS

# хранилище для переводов сообщений сделанных гугл переводчиком
AUTO_TRANSLATIONS = my_dic.PersistentDict('db/auto_translations.pkl')


supported_langs_trans = [
        "af","am","ar","az","be","bg","bn","bs","ca","ceb","co","cs","cy","da","de",
        "el","en","eo","es","et","eu","fa","fi","fr","fy","ga","gd","gl","gu","ha",
        "haw","he","hi","hmn","hr","ht","hu","hy","id","ig","is","it","iw","ja","jw",
        "ka","kk","km","kn","ko","ku","ky","la","lb","lo","lt","lv","mg","mi","mk",
        "ml","mn","mr","ms","mt","my","ne","nl","no","ny","or","pa","pl","ps","pt",
        "ro","ru","rw","sd","si","sk","sl","sm","sn","so","sq","sr","st","su","sv",
        "sw","ta","te","tg","th","tl","tr","uk","ur","uz","vi","xh","yi","yo","zh",
        "zh-TW","zu"]


HELP = r'''You need to get a chatGPT API key to talk with chatGPT.

https://www.howtogeek.com/885918/how-to-get-an-openai-api-key/

Paste the key in the bot as [/key xxx...xxx].

You can set a key for group by coping the personal key, use [/key copy] command in chat.
'''


class ShowAction(threading.Thread):
    """A thread that can be stopped. Continuously sends an activity notification to the chat.
    Telegram automatically extinguishes the notification after 5 seconds, so it must be repeated.

    It should be used in code like this
    with ShowAction(message, 'typing'):
        we do something and while we do the notification burning"""

    def __init__(self, message, action):
        """_summary_

        Args:
            chat_id (_type_): ID of the chat in which the notification will be displayed
            action (_type_):  "typing", "upload_photo", "record_video", "upload_video", "record_audio", 
                              "upload_audio", "upload_document", "find_location", "record_video_note", "upload_video_note"
        """
        super().__init__()
        self.actions = [  "typing", "upload_photo", "record_video", "upload_video", "record_audio",
                         "upload_audio", "upload_document", "find_location", "record_video_note", "upload_video_note"]
        assert action in self.actions, f'Допустимые actions = {self.actions}'
        self.chat_id = message.chat.id
        self.thread_id = message.message_thread_id
        self.is_topic = message.is_topic_message
        self.action = action
        self.is_running = True
        self.timerseconds = 1

    def run(self):
        while self.is_running:
            try:
                if self.is_topic:
                    bot.send_chat_action(self.chat_id, self.action, message_thread_id = self.thread_id)
                else:
                    bot.send_chat_action(self.chat_id, self.action)
            except Exception as error:
                my_log.log2(f'tb:show_action:run: {error}')
            n = 50
            while n > 0:
                time.sleep(0.1)
                n = n - self.timerseconds

    def stop(self):
        self.timerseconds = 50
        self.is_running = False
        try:
            bot.send_chat_action(self.chat_id, 'cancel', message_thread_id = self.thread_id)
        except Exception as error:
            my_log.log2(f'tb:show_action: {error}')

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def tr(text: str, lang: str) -> str:
    """
    Translates the given text into the specified language.

    Args:
        text (str): The text to be translated.
        lang (str): The target language for translation.

    Returns:
        str: The translated text. If the target language is 'ru' (Russian), the original text is returned.

    Note:
        The translation is performed using the `my_trans.translate_text2` function.

    """
    key = str((text, lang))
    if key in AUTO_TRANSLATIONS:
        return AUTO_TRANSLATIONS[key]
    translated = my_trans.translate_text2(text, lang)
    if translated:
        AUTO_TRANSLATIONS[key] = translated
    else:
        AUTO_TRANSLATIONS[key] = text
    return AUTO_TRANSLATIONS[key]


@bot.message_handler(commands=['restart']) 
def restart(message: telebot.types.Message):
    """bot stop. after stopping it will have to restart the systemd script"""
    if message.from_user.id in cfg.admins:
        bot.stop_polling()
    else:
        bot.reply_to(message, 'For admins only.')


@bot.message_handler(commands=['start', 'help'])
def send_welcome_start(message: telebot.types.Message):
    # Send hello

    my_log.log_echo(message)

    user_id = message.from_user.id
    lang = DB[user_id][2] if user_id in DB else message.from_user.language_code or 'en'

    default_lang = message.from_user.language_code or 'en'
    token = ''
    if user_id not in DB:
        DB[user_id] = (None, token, default_lang)

    bot.reply_to(message, html.escape(tr(HELP, lang)), parse_mode='HTML',
                 disable_web_page_preview=True)
    my_log.log_echo(message, HELP)


@bot.message_handler(commands=['language', 'lang'])
def language(message: telebot.types.Message):
    """Change language"""
    user_id = message.from_user.id
    if user_id not in DB:
        token = ''
        lang = message.from_user.language_code or 'en'
        DB[user_id] = (None, token, lang)
    else:
        lang = DB[user_id][2]

    help = f'''/language language code

Example:

<code>/language es</code>
<code>/language en</code>
<code>/language ru</code>
<code>/language fr</code>

https://en.wikipedia.org/wiki/Template:Google_translation
'''

    try:
        new_lang = message.text.split(' ')[1].strip().lower()
    except IndexError:
        bot.reply_to(message, tr(help, lang), parse_mode='HTML', disable_web_page_preview=True)
        return

    url = DB[user_id][0]
    token = DB[user_id][1]
    DB[user_id] = (url, token, new_lang)
    bot.reply_to(message, 'Language changed.')


@bot.message_handler(commands=['init'])
def set_default_commands(message: telebot.types.Message):
    thread = threading.Thread(target=set_default_commands_thread, args=(message,))
    thread.start()
def set_default_commands_thread(message: telebot.types.Message):
    """
    Reads a file containing a list of commands and their descriptions,
    and sets the default commands for the bot.
    """
    user_id = message.from_user.id
    user_lang = DB[user_id][2]

    if message.from_user.id not in cfg.admins:
        bot.reply_to(message, tr("For admins only.", user_lang))
        return

    def get_seconds(s):
        match = re.search(r"after\s+(?P<seconds>\d+)", s)
        if match:
            return int(match.group("seconds"))
        else:
            return 0

    bot.reply_to(message,
                 tr("Локализация займет много времени, не повторяйте эту команду",
                    user_lang))
    
    # most_used_langs = ['ar', 'bn', 'da', 'de', 'el', 'en', 'es', 'fa', 'fi', 'fr','hi',
    #                    'hu', 'id', 'in', 'it', 'ja', 'ko', 'nl', 'no', 'pl', 'pt', 'ro',
    #                    'ru', 'sv', 'sw', 'th', 'tr', 'uk', 'ur', 'vi', 'zh']
    most_used_langs = [x for x in supported_langs_trans if len(x) == 2]

    msg_commands = ''
    for lang in most_used_langs:
        commands = []
        with open('commands.txt', encoding='utf-8') as file:
            for line in file:
                try:
                    command, description = line[1:].strip().split(' - ', 1)
                    if command and description:
                        description = tr(description, lang)
                        commands.append(telebot.types.BotCommand(command, description))
                except Exception as error:
                    my_log.log2(f'Не удалось прочитать команды по умолчанию для языка {lang}: {error}')
        result = False
        try:
            l1 = [x.description for x in bot.get_my_commands(language_code=lang)]
            l2 = [x.description for x in commands]
            if l1 != l2:
                result = bot.set_my_commands(commands, language_code=lang)
            else:
                result = True
        except Exception as error_set_command:
            my_log.log2(f'Не удалось установить команды по умолчанию для языка {lang}: {error_set_command} ')
            time.sleep(get_seconds(str(error_set_command)))
            try:
                if l1 != l2:
                    result = bot.set_my_commands(commands, language_code=lang)
                else:
                    result = True
            except Exception as error_set_command2:
                my_log.log2(f'Не удалось установить команды по умолчанию для языка {lang}: {error_set_command2}')
        if result:
            result = '✅'
        else:
            result = '❌'

        msg = f'{result} Установлены команды по умолчанию [{lang}]'
        msg_commands += msg + '\n'
    reply_to_long_message(message, msg_commands)

    new_bot_name = cfg.bot_name.strip()
    new_description = cfg.bot_description.strip()
    new_short_description = cfg.bot_short_description.strip()

    msg_bot_names = ''
    for lang in most_used_langs:
        result = False
        try:
            if bot.get_my_name(language_code=lang).name != tr(new_bot_name, lang):
                result = bot.set_my_name(tr(new_bot_name, lang), language_code=lang)
            else:
                result = True
        except Exception as error_set_name:
            my_log.log2(f'Не удалось установить имя бота: {tr(new_bot_name, lang)}'+'\n\n'+str(error_set_name))
            time.sleep(get_seconds(str(error_set_name)))
            try:
                if bot.get_my_name(language_code=lang).name != tr(new_bot_name, lang):
                    result = bot.set_my_name(tr(new_bot_name, lang), language_code=lang)
                else:
                    result = True
            except Exception as error_set_name2:
                my_log.log2(f'Не удалось установить имя бота: {tr(new_bot_name, lang)}'+'\n\n'+str(error_set_name2))
        if result:
            msg_bot_names += '✅ Установлено имя бота для языка ' + lang + f' [{tr(new_bot_name, lang)}]\n'
        else:
            msg_bot_names += '❌ Установлено имя бота для языка ' + lang + f' [{tr(new_bot_name, lang)}]\n'
    reply_to_long_message(message, msg_bot_names)

    msg_descriptions = ''
    for lang in most_used_langs:
        result = False
        try:
            if bot.get_my_description(language_code=lang).description != tr(new_description, lang):
                result = bot.set_my_description(tr(new_description, lang), language_code=lang)
            else:
                result = True
        except Exception as error_set_description:
            my_log.log2(f'Не удалось установить описание бота {lang}: {tr(new_description, lang)}'+'\n\n'+str(error_set_description))
            time.sleep(get_seconds(str(error_set_description)))
            try:
                if bot.get_my_description(language_code=lang).description != tr(new_description, lang):
                    result = bot.set_my_description(tr(new_description, lang), language_code=lang)
                else:
                    result = bot.set_my_description(tr(new_description, lang), language_code=lang)
            except Exception as error_set_description2:
                my_log.log2(f'Не удалось установить описание бота {lang}: {tr(new_description, lang)}'+'\n\n'+str(error_set_description2))
                msg_descriptions += '❌ Установлено новое описание бота для языка ' + lang + '\n'
                continue
        if result:
            msg_descriptions += '✅ Установлено новое описание бота для языка ' + lang + '\n'
        else:
            msg_descriptions += '❌ Установлено новое описание бота для языка ' + lang + '\n'
    reply_to_long_message(message, msg_descriptions)

    msg_descriptions = ''
    for lang in most_used_langs:
        result = False
        try:
            if bot.get_my_short_description(language_code=lang).short_description != tr(new_short_description, lang):
                result = bot.set_my_short_description(tr(new_short_description, lang), language_code=lang)
            else:
                result = True
        except Exception as error_set_short_description:
            my_log.log2(f'Не удалось установить короткое описание бота: {tr(new_short_description, lang)}'+'\n\n'+str(error_set_short_description))
            time.sleep(get_seconds(str(error_set_short_description)))
            try:
                if bot.get_my_short_description(language_code=lang).short_description != tr(new_short_description, lang):
                    result = bot.set_my_short_description(tr(new_short_description, lang), language_code=lang)
                else:
                    result = bot.set_my_short_description(tr(new_short_description, lang), language_code=lang)
            except Exception as error_set_short_description2:
                my_log.log2(f'Не удалось установить короткое описание бота: {tr(new_short_description, lang)}'+'\n\n'+str(error_set_short_description2))
                msg_descriptions += '❌ Установлено новое короткое описание бота для языка ' + lang + '\n'
                continue
        if result:
            msg_descriptions += '✅ Установлено новое короткое описание бота для языка ' + lang + '\n'
        else:
            msg_descriptions += '❌ Установлено новое короткое описание бота для языка ' + lang + '\n'
    reply_to_long_message(message, msg_descriptions)


@bot.message_handler(commands=['test'])
def test(message: telebot.types.Message) -> None:
    user_id = message.from_user.id
    lang = DB[user_id][2] if user_id in DB else message.from_user.language_code or 'en'
    
    name = bot.get_my_name(lang)
    bot.reply_to(message, name)


@bot.message_handler(commands=['key'])
def key(message: telebot.types.Message) -> None:
    """Key command handler"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    lang = DB[user_id][2] if user_id in DB else message.from_user.language_code or 'en'

    try:
        token = message.text.split(' ')[1].strip()
        if token.lower() == 'copy':
            DB[chat_id] = DB[user_id]
            my_log.log_echo(message)
            bot.reply_to(message, 'OK.')
            return

        url = DB[user_id][0] if user_id in DB else None
        DB[user_id] = (url, token, lang)
        my_log.log_echo(message)
        bot.reply_to(message, 'OK.')
        return
    except IndexError:
        pass

    bot.reply_to(message, html.escape(tr(HELP, lang)), parse_mode='HTML',
                 disable_web_page_preview=True)
    return

@bot.message_handler(commands=['url'])
def url(message: telebot.types.Message) -> None:
    """url command handler"""
    user_id = message.from_user.id

    lang = DB[user_id][2] if user_id in DB else message.from_user.language_code or 'en'

    try:
        url = message.text.split(' ')[1].strip()
        token = DB[user_id][1] if user_id in DB else ''
        DB[user_id] = (url, token, lang)
        my_log.log_echo(message)
        bot.reply_to(message, 'OK.')
        return
    except IndexError:
        pass

    msg = tr("You can provide custom url for chatGPT. Default (original) is https://api.openai.com/v1", lang)
    bot.reply_to(message, html.escape(msg), parse_mode='HTML',
                 disable_web_page_preview=True)
    return


@bot.message_handler(commands=['mem'])
def send_debug_history(message: telebot.types.Message):
    """
    Отправляет текущую историю сообщений пользователю.
    """
    my_log.log_echo(message)

    chat_id = message.chat.id
    lang = DB[chat_id][2] if chat_id in DB else message.from_user.language_code or 'en'

    # создаем новую историю диалогов с юзером из старой если есть
    messages = []
    if chat_id in gpt_basic.CHATS:
        messages = gpt_basic.CHATS[chat_id]
    prompt = '\n'.join(f'{i["role"]} - {i["content"]}\n' for i in messages) or tr('Пусто', lang)
    my_log.log_echo(message, prompt)
    reply_to_long_message(message, prompt, disable_web_page_preview = True)


@bot.message_handler(commands=['image','img'])
def image(message: telebot.types.Message):
    thread = threading.Thread(target=image_thread, args=(message,))
    thread.start()
def image_thread(message: telebot.types.Message):
    """генерирует картинку по описанию"""


    my_log.log_echo(message)

    chat_id = message.chat.id
    lang = DB[chat_id][2] if chat_id in DB else message.from_user.language_code or 'en'

    help = f"/image <{tr('text description of the picture, what to draw', lang)}>"

    try:
        prompt = message.text.split(maxsplit = 1)[1]
    except Exception:
        bot.reply_to(message, tr(help, lang))
        my_log.log_echo(message, tr(help, lang))
        return

    if len(prompt) > 1:
        with ShowAction(message, 'upload_photo'):
            images = gpt_basic.image_gen(prompt, chat_id, amount=4, size='1024x1024')
            medias = [telebot.types.InputMediaPhoto(i) for i in images]
            if len(medias) > 0:
                bot.send_media_group(message.chat.id, medias, reply_to_message_id=message.message_id)

                my_log.log_echo(message, '[image gen] ')

                n = [{'role':'system', 'content':f'user {tr("asked me to draw", lang)}\n{prompt}'}, 
                        {'role':'system', 'content':f'assistant {tr("drawn using DALL-E", lang)}'}]
                if chat_id in gpt_basic.CHATS:
                    gpt_basic.CHATS[chat_id] += n
                else:
                    gpt_basic.CHATS[chat_id] = n
            else:
                bot.reply_to(message, tr("I couldn’t draw anything. Maybe I’m not in the mood, or maybe you need to give a different description.", lang))
                my_log.log_echo(message, '[image gen error] ')
                n = [{'role':'system', 'content':f'user {tr("asked me to draw", lang)}\n{prompt}'}, 
                        {'role':'system', 'content':f'assistant {tr("didn’t want to or couldn’t draw it using DALL-E", lang)}'}]
                if chat_id in gpt_basic.CHATS:
                    gpt_basic.CHATS[chat_id] += n
                else:
                    gpt_basic.CHATS[chat_id] = n


@bot.message_handler(commands=['model'])
def set_new_model(message: telebot.types.Message):
    """меняет модель для гпт, никаких проверок не делает"""
    thread = threading.Thread(target=set_new_model_thread, args=(message,))
    thread.start()
def set_new_model_thread(message: telebot.types.Message):
    """меняет модель для гпт, никаких проверок не делает"""

    chat_id = message.chat.id
    lang = DB[chat_id][2] if chat_id in DB else message.from_user.language_code or 'en'

    if chat_id in gpt_basic.CUSTOM_MODELS:
        current_model = gpt_basic.CUSTOM_MODELS[chat_id]
    else:
        current_model = cfg.model

    if len(message.text.split()) < 2:
        available_models = ''
        for m in gpt_basic.get_list_of_models(chat_id):
            available_models += f'`/model {m}`\n'
        msg = f"""{tr('Change the model for chatGPT.', lang)}

{tr('Selected:', lang)} `/model {current_model}`

{tr('Available models:', lang)}

`/model gpt-4-32k`
`/model gpt-3.5-turbo-16k`

{available_models}
"""
        reply_to_long_message(message, msg, parse_mode='Markdown')
        my_log.log_echo(message, msg)
        return

    model = message.text.split(maxsplit=1)[1]
    msg0 = f'{tr("Prevous model", lang)} `{current_model}`.'
    msg = f'{tr("New model", lang)} `{model}`.'
    gpt_basic.CUSTOM_MODELS[chat_id] = model
    bot.reply_to(message, msg0, parse_mode='Markdown')
    bot.reply_to(message, msg, parse_mode='Markdown')
    my_log.log_echo(message, msg0)
    my_log.log_echo(message, msg)


@bot.message_handler(commands=['removeme'])
def removeme(message: telebot.types.Message):
    """Remove user from DB"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_private = message.chat.type == 'private'
    if not is_private:
        user_id = chat_id
    if user_id in DB:
        del DB[user_id]
        my_log.log_echo(message)
        bot.reply_to(message, 'OK')
        my_log.log_echo(message, 'OK')
        return
    else:
        lang = DB[user_id][2] if user_id in DB else message.from_user.language_code or 'en'
        msg = tr('User not found.', lang)
        bot.reply_to(message, msg)
        my_log.log_echo(message, msg)


@bot.message_handler(commands=['temperature', 'temp'])
def set_new_temperature(message: telebot.types.Message):
    """меняет температуру для chatGPT
    /temperature <0...2>
    по умолчанию 0 - автоматическая
    чем меньше температура тем менее творчейский ответ, меньше бреда и вранья,
    и желания давать ответ
    """

    chat_id = message.chat.id
    lang = DB[chat_id][2] if chat_id in DB else message.from_user.language_code or 'en'

    if len(message.text.split()) == 2:
        try:
            new_temp = float(message.text.split()[1])
        except ValueError:
            new_temp = -1
    else:
        new_temp = -1

    if new_temp < 0 or new_temp > 2:
        new_temp = -1

    if len(message.text.split()) < 2 or new_temp == -1:
        help = f"""/temperature <0-2>

{tr('''Меняет температуру для chatGPT

Температура у ChatGPT - это параметр, который контролирует степень случайности генерируемого текста. Чем выше температура, тем более случайным и креативным будет текст. Чем ниже температура, тем более точным и сфокусированным будет текст.

Например, если вы хотите, чтобы ChatGPT сгенерировал стихотворение, вы можете установить температуру выше 1,5. Это будет способствовать тому, что ChatGPT будет выбирать более неожиданные и уникальные слова. Однако, если вы хотите, чтобы ChatGPT сгенерировал текст, который является более точным и сфокусированным, вы можете установить температуру ниже 0,5. Это будет способствовать тому, что ChatGPT будет выбирать более вероятные и ожидаемые слова.

По-умолчанию 0 - автоматическая''', lang)}

`/temperature 0.1`
`/temperature 1`
`/temperature 1.9` {tr('На таких высоких значения он пишет один сплошной бред', lang)}
"""
        bot.reply_to(message, help, parse_mode='Markdown')
        return

    gpt_basic.TEMPERATURE[chat_id] = new_temp
    bot.reply_to(message, f'{tr("Новая температура для chatGPT установлена:", lang)} {new_temp}',
                 parse_mode='Markdown')


@bot.message_handler(content_types = ['voice', 'audio'])
def handle_voice(message: telebot.types.Message): 
    """voice handler"""
    thread = threading.Thread(target=handle_voice_thread, args=(message,))
    thread.start()
def handle_voice_thread(message: telebot.types.Message):
    """voice handler"""

    my_log.log_media(message)
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_private = message.chat.type == 'private'
    if not is_private:
        user_id = chat_id

    lang = DB[user_id][2] if user_id in DB else message.from_user.language_code or 'en'

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        file_path = temp_file.name
    try:
        file_info = bot.get_file(message.voice.file_id)
    except AttributeError:
        file_info = bot.get_file(message.audio.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    with open(file_path, 'wb') as new_file:
        new_file.write(downloaded_file)

    with ShowAction(message, 'typing'):
        text = my_stt.stt(file_path, lang)
        os.remove(file_path)
        text = text.strip()
        if text:
            reply_to_long_message(message, text)
            my_log.log_echo(message, f'[ASR] {text}')
        else:
            msg = tr('Did not recognize any text.', lang)
            bot.reply_to(message, msg)
            my_log.log_echo(message, '[ASR] no results')

        if text:
            message.text = text
            echo_all(message)


@bot.message_handler(commands=['tts']) 
def tts(message: telebot.types.Message):
    """Text to speech"""
    thread = threading.Thread(target=tts_thread, args=(message,))
    thread.start()
def tts_thread(message: telebot.types.Message):
    """Text to speech"""

    my_log.log_echo(message)

    user_id = message.from_user.id
    chat_id = message.chat.id
    is_private = message.chat.type == 'private'
    if not is_private:
        user_id = chat_id

    lang = DB[user_id][2] if user_id in DB else message.from_user.language_code or 'en'

    text = ''
    try:
        text = message.text.split(' ', 1)[1].strip()
    except IndexError:
        pass

    if not text:
        msg = tr('@tts text to say with google voice', lang)
        msg = msg.replace('@', '/')
        bot.reply_to(message, msg)
        return

    with ShowAction(message, 'record_audio'):
        audio = my_tts.tts(text, lang)
        if audio:
            bot.send_voice(message.chat.id, audio, reply_to_message_id = message.message_id)
            my_log.log_echo(message, '[Send voice message]')
        else:
            msg = tr('TTS failed.', lang)
            bot.reply_to(message, msg)
            my_log.log_echo(message, msg)


@bot.message_handler(commands=['trans'])
def trans(message: telebot.types.Message):
    thread = threading.Thread(target=trans_thread, args=(message,))
    thread.start()
def trans_thread(message: telebot.types.Message):

    my_log.log_echo(message)
    
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_private = message.chat.type == 'private'
    if not is_private:
        user_id = chat_id
    if user_id in DB:
        user_lang = DB[user_id][2]
    else:
        user_lang = message.from_user.language_code or 'en'

    help = """@trans [en|ru|uk|..] text to be translated into the specified language

If not specified, then your language will be used.

@trans de hi, how are you?
@trans was ist das

Supported languages: """
    help = tr(help, user_lang)
    help = help.replace('@', '/')
    help += ' ' + ', '.join(supported_langs_trans)

    pattern = r'^\/trans\s+((?:' + '|'.join(supported_langs_trans) + r')\s+)?\s*(.*)$'

    match = re.match(pattern, message.text, re.DOTALL)

    if match:
        lang = match.group(1) or user_lang
        text = match.group(2) or ''
    else:
        my_log.log_echo(message, help)
        bot.reply_to(message, help)
        return
    lang = lang.strip()

    with ShowAction(message, 'typing'):
        translated = my_trans.translate(text, lang)
        if translated:
            bot.reply_to(message, translated)
            my_log.log_echo(message, translated)
        else:
            msg = tr('Error in translation', user_lang)
            bot.reply_to(message, msg)
            my_log.log_echo(message, msg)


def send_long_message(message: telebot.types.Message, resp: str, parse_mode:str = None, disable_web_page_preview: bool = None,
                      reply_markup: telebot.types.InlineKeyboardMarkup = None):
    """send the message; if it is too long, it splits it into 2 parts or sends it as a text file"""
    reply_to_long_message(message=message, resp=resp, parse_mode=parse_mode,
                          disable_web_page_preview=disable_web_page_preview,
                          reply_markup=reply_markup, send_message = True)


def reply_to_long_message(message: telebot.types.Message, resp: str, parse_mode: str = None,
                          disable_web_page_preview: bool = None,
                          reply_markup: telebot.types.InlineKeyboardMarkup = None, send_message: bool = False):
    """send the message; if it is too long, it splits it into 2 parts or sends it as a text file"""

    if len(resp) < 20000:
        if parse_mode == 'HTML':
            chunks = utils.split_html(resp, 4000)
        else:
            chunks = utils.split_text(resp, 4000)
        counter = len(chunks)
        for chunk in chunks:
            try:
                if send_message:
                    bot.send_message(message.chat.id, chunk, message_thread_id=message.message_thread_id, parse_mode=parse_mode,
                                        disable_web_page_preview=disable_web_page_preview, reply_markup=reply_markup)
                else:
                    bot.reply_to(message, chunk, parse_mode=parse_mode,
                            disable_web_page_preview=disable_web_page_preview, reply_markup=reply_markup)
            except Exception as error:
                print(error)
                my_log.log2(f'tb:reply_to_long_message: {error}')
                if send_message:
                    bot.send_message(message.chat.id, chunk, message_thread_id=message.message_thread_id, parse_mode='',
                                        disable_web_page_preview=disable_web_page_preview, reply_markup=reply_markup)
                else:
                    bot.reply_to(message, chunk, parse_mode='', disable_web_page_preview=disable_web_page_preview, reply_markup=reply_markup)

            counter -= 1
            if counter < 0:
                break
            time.sleep(2)
    else:
        buf = io.BytesIO()
        buf.write(resp.encode())
        buf.seek(0)
        bot.send_document(message.chat.id, document=buf, caption='resp.txt', visible_file_name = 'resp.txt')


@bot.message_handler(commands=['clear'])
def clear(message: telebot.types.Message) -> None:
    """start new dialog"""
    thread = threading.Thread(target=clear_thread, args=(message,))
    thread.start()
def clear_thread(message):
    """start new dialog"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_private = message.chat.type == 'private'
    if not is_private:
        user_id = chat_id
    my_log.log_echo(message)
    lang = DB[user_id][2] if user_id in DB else message.from_user.language_code or 'en'
    if user_id in DB:
        gpt_basic.chat_reset(user_id)
        translated = tr('New dialog started.', lang)
        bot.reply_to(message, translated)
        my_log.log_echo(message, translated)
    else:
        translated = tr('You have to provide a key. Use [/key] command.', lang)
        bot.reply_to(message, translated)
        my_log.log_echo(message, translated)


@bot.message_handler(func=lambda message: True)
def echo_all(message: telebot.types.Message) -> None:
    """Text message handler"""
    thread = threading.Thread(target=do_task, args=(message,))
    thread.start()
def do_task(message):
    """Text message handler threaded"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    is_private = message.chat.type == 'private'
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == BOT_ID
    lang = DB[user_id][2] if user_id in DB else message.from_user.language_code or 'en'
    
    if not is_private:
        user_id = chat_id

    if user_id not in DB or DB[user_id][1] == '':
        if is_private:
            msg = tr('You have to provide a key. Use [/key] command.', lang)
        else:
            msg = tr('You have to provide a key. Use [/key copy] command to copy your private token.', lang)
        bot.reply_to(message, msg, parse_mode='HTML')
        my_log.log_echo(message)
        my_log.log_echo(message, msg)
        return

    # bot can answer it chats if it is reply to his answer or code word was used
    if not (is_private or is_reply or message.text.lower().startswith(cfg.BOT_CALL_WORD)):
        return

    my_log.log_echo(message)
    msg = message.text
    if len(msg) > GPT_MAX:
        msg = f'{tr("Message too long:", lang)} {len(msg)} {tr("of", lang)} {GPT_MAX}'
        bot.reply_to(message, msg)
        my_log.log_echo(message, msg)
        return
    with ShowAction(message, 'typing'):
        try:
            if is_private:
                user_name = (message.from_user.first_name or '') + ' ' + (message.from_user.last_name or '')
            else:
                user_name = '(public chat, it is not person) ' + (message.chat.username or message.chat.first_name or message.chat.title or 'noname')

            chat_name = message.chat.username or message.chat.first_name or message.chat.title or ''
            if chat_name:
                user_name = chat_name

            answer = gpt_basic.chat(user_id, message.text, user_name, lang, is_private,
                                    chat_name)

            answer = utils.bot_markdown_to_html(answer)
            my_log.log_echo(message, answer)
            if answer:
                try:
                    reply_to_long_message(message, answer, parse_mode='HTML',
                                          disable_web_page_preview = True)
                except Exception as error:
                    print(f'tb:do_task: {error}')
                    my_log.log2(f'tb:do_task: {error}')
                    reply_to_long_message(message, answer, parse_mode='',
                                          disable_web_page_preview = True)
            else:
                translated = tr('chatGPT did not answer.', lang)
                bot.reply_to(message, translated)
        except Exception as error3:
            print(error3)
            my_log.log2(str(error3))
        return


def main():
    """
    Runs the main function, which sets default commands and starts polling the bot.
    """
    # set_default_commands()
    bot.polling(timeout=90, long_polling_timeout=90)


if __name__ == '__main__':
    main()
