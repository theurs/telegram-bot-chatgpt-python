# Free chatGPT with users API keys
Free self-hosted Telegram bot for ChatGPT

Free ChatGPT is a Telegram bot that allows users to chat with ChatGPT, a large language model from OpenAI. ChatGPT can generate text, translate languages, write different creative content, and answer your questions in an informative way.

To start chatting with Free ChatGPT, you first need to get an API key. An API key is a unique identifier that allows you to authenticate with ChatGPT.

After setting the API key, you will be able to start chatting with Free ChatGPT.


# How to get key?

1. Go to the OpenAI website and create an account.
2. Once you have created an account, log in and click on the "API keys" tab.
3. Click on the "Create new key" button.
4. Give your key a name and click on the "Create" button.
5. Your API key will be displayed. Copy it and keep it safe.

Once you have your API key, you can use it to connect to the ChatGPT API.


# How to use Free chatGPT?

To start chatting with Free chatGPT, send a message to the bot. You can send voice messages too.

In a group you can send a message to the bot using **.gpt** command and with reply to bots messages.

**.gpt who is your daddy**

Special command **/token copy** may be used in chat to copy your private key.

# Description of commands:

**/start** - This command greets you and briefly describes the features of Free Google Bard.

**/key** - This command allows you to set your personal API key. The key is necessary to access chatGPT.

**/url** - Set openai URL (if not original), free proxies

**/clear** - This command clears the current dialog and starts a new one. This is useful if you want to start with a clean 
slate or if you want to forget about what was said before.

**/image** - draw a pictures

**/tts** - This command allows you to say text with google voice.

**/trans** - This command allows you to translate text with google translate.

**/lang** - This command allows you to change the language.

**/removeme** - This command allows you to remove your account from bot.

**/mem** - show context memory

**/model** - change chatGPT model

**/temperature** - set chatGPT creative level, floating point [0-2]

# Install on self-hosted server
Python 3.8+

sudo apt-get update
sudo apt install translate-shell python3-venv ffmpeg


git clone https://github.com/theurs/telegram-bot-chatgpt-python.git

python -m venv .tb-tr
source ~/.tb/bin/activate

pip install -r requirements.txt

config file

cfg.py
```
# Bot description, up to 512 symbols.
bot_description = """Free telegram-bot for chatting with chatGPT

You only need to get your own chatGPT token and then you can talk to chatGPT in telegram.

https://www.howtogeek.com/885918/how-to-get-an-openai-api-key/

Bug reports send to @theurs"""


# a short description of the bot that is displayed on the bot's profile page and submitted
# along with a link when users share the bot. Up to 120 characters.
bot_short_description = """Free telegram-bot for chatting with chatGPT"""


# Bot name (pseudonym), this is not a unique name, you can call it whatever you like,
# is not the name of the bot it responds to. Up to 64 characters.
bot_name = "Free chatGPT"

# bot call word, use it in chats for ask bot
# Example - .gpt how are you
BOT_CALL_WORD = '.gpt'

# list of admins who can use admin commands (/restart etc)
admins = [xxx,]


# telegram bot token
token   = "xxx"


# chatGPT default model
model = 'gpt-3.5-turbo-16k'

# 16k
max_hist_lines = 10
max_hist_bytes = 8000
max_hist_compressed=1500
max_hist_mem = 2500
```

start ./tb.py


**Commands for admins**

**/restart** - This command restarts Free Google Bard. This is useful if Free Google Bard is stuck or not working properly.

**/init** - This command initializes Free Google Bard. This is necessary to do if you are using Free Google Bard for the first time or if you have changed the settings of the bot.
