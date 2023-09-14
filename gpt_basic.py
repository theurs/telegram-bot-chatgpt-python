#!/usr/bin/env python3

import datetime
import json
import threading

import openai

import cfg
import utils
import my_dic

import my_log
import my_trans


CUSTOM_MODELS = my_dic.PersistentDict('db/custom_models.pkl')

# память диалогов {id:messages: list}
CHATS = my_dic.PersistentDict('db/dialogs.pkl')
# системные промты для чатов, роли или инструкции что и как делать в этом чате
# {id:prompt}
PROMPTS = my_dic.PersistentDict('db/prompts.pkl')
# температура chatGPT {id:float(0-2)}
TEMPERATURE = my_dic.PersistentDict('db/temperature.pkl')
# замки диалогов {id:lock}
CHAT_LOCKS = {}

# хранилище юзерских ключей и адресов
# {id:(url, token, lang)}
TOKENS = my_dic.PersistentDict('db/servers.pkl')


def ai(prompt: str = '', temp: float = 0.1, max_tok: int = 2000, timeou: int = 120,
       messages = None, chat_id = None, model_to_use: str = '') -> str:
    """Сырой текстовый запрос к GPT чату, возвращает сырой ответ
    """

    if messages == None:
        assert prompt != '', 'prompt не может быть пустым'
        messages = [{"role": "system", "content": "You are an artificial intelligence that responds to user requests in the Telegram messenger"},
                    {"role": "user", "content": prompt}]

    current_model = cfg.model
    if chat_id and chat_id in CUSTOM_MODELS:
        current_model = CUSTOM_MODELS[chat_id]

    # использовать указанную модель если есть
    current_model = current_model if not model_to_use else model_to_use

    openai.api_base = TOKENS[chat_id][0] or 'https://api.openai.com/v1'
    openai.api_key = TOKENS[chat_id][1]

    response = ''
    try:
        completion = openai.ChatCompletion.create(
            model = current_model,
            messages=messages,
            max_tokens=max_tok,
            temperature=temp,
            timeout=timeou
        )
        response = completion.choices[0].message.content
    except Exception as unknown_error1:
        if str(unknown_error1).startswith('HTTP code 200 from API'):
                # ошибка парсера json?
                text = str(unknown_error1)[24:]
                lines = [x[6:] for x in text.split('\n') if x.startswith('data:') and ':{"content":"' in x]
                content = ''
                for line in lines:
                    parsed_data = json.loads(line)
                    content += parsed_data["choices"][0]["delta"]["content"]
                if content:
                    response = content
        else:
            response = str(unknown_error1)
        print(unknown_error1)
        my_log.log2(f'gpt_basic.ai: {unknown_error1}\n\nServer: {openai.api_base}')

    return response


def ai_compress(prompt: str, max_prompt: int  = 300, origin: str = 'user', force: bool = False) -> str:
    """сжимает длинное сообщение в чате для того что бы экономить память в контексте
    origin - чье сообщение, юзера или это ответ помощника. 'user' или 'assistant'
    force - надо ли сжимать сообщения которые короче чем заданная максимальная длинна. это надо что бы не сжать а просто резюмировать,
            превратить диалог в такое предложение что бы бинг его принял вместо диалога
    """
    assert origin in ('user', 'assistant', 'dialog')
    if len(prompt) > max_prompt or force:
        try:
            if origin == 'user':
                compressed_prompt = ai(f'Сократи текст до {max_prompt} символов так что бы сохранить смысл и важные детали. \
Этот текст является запросом юзера в переписке между юзером и ИИ. Используй короткие слова. Текст:\n{prompt}', max_tok = max_prompt)
            elif origin == 'assistant':
                compressed_prompt = ai(f'Сократи текст до {max_prompt} символов так что бы сохранить смысл и важные детали. \
Этот текст является ответом ИИ в переписке между юзером и ИИ. Используй короткие слова. Текст:\n{prompt}', max_tok = max_prompt)
            elif origin == 'dialog':
                compressed_prompt = ai(f'Резюмируй переписку между юзером и ассистентом до {max_prompt} символов, весь негативный контент исправь на нейтральный:\n{prompt}', max_tok = max_prompt)
            if len(compressed_prompt) < len(prompt) or force:
                return compressed_prompt
        except Exception as error:
            print(error)

        if len(prompt) > max_prompt:
            ziped = zip_text(prompt)
            if len(ziped) <= max_prompt:
                prompt = ziped
            else:
                prompt = prompt[:max_prompt]

    return prompt


def zip_text(text: str) -> str:
    """
    Функция для удаления из текста русских и английских гласных букв типа "а", "о", "e" и "a".
    Так же удаляются идущие подряд одинаковые символы
    """
    vowels = [  'о', 'О',        # русские
                'o', 'O']        # английские. не стоит наверное удалять слишком много

    # заменяем гласные буквы на пустую строку, используя метод translate и функцию maketrans
    text = text.translate(str.maketrans('', '', ''.join(vowels)))

    # убираем повторяющиеся символы
    # используем генератор списков для создания нового текста без повторов
    # сравниваем каждый символ с предыдущим и добавляем его, если они разные 
    new_text = "".join([text[i] for i in range(len(text)) if i == 0 or text[i] != text[i-1]])
    
    return new_text


def image_gen(prompt: str, chat_id: str, amount: int = 10, size: str ='1024x1024'):
    """
    Generates a specified number of images based on a given prompt.

    Parameters:
        - prompt (str): The text prompt used to generate the images.
        - amount (int, optional): The number of images to generate. Defaults to 10.
        - size (str, optional): The size of the generated images. Must be one of '1024x1024', '512x512', or '256x256'. Defaults to '1024x1024'.

    Returns:
        - list: A list of URLs pointing to the generated images.
    """

    openai.api_base = TOKENS[chat_id][0] or 'https://api.openai.com/v1'
    openai.api_key = TOKENS[chat_id][1]

    assert amount <= 10, 'Too many images to gen'
    assert size in ('1024x1024','512x512','256x256'), 'Wrong image size'

    results = []

    try:
        response = openai.Image.create(
            prompt = prompt,
            n = amount,
            size=size,
        )
        if response:
            results += [x['url'] for x in response["data"]]
    except AttributeError:
        pass
    except Exception as error:
        print(error)
        my_log.log2(f'gpt_basic:image_gen: {error}\n\nServer: {server[0]}')

    return results


def get_list_of_models(chat_id: str):
    """
    Retrieves a list of models from the OpenAI servers.

    Returns:
        list: A list of model IDs.
    """
    openai.api_base = TOKENS[chat_id][0] or 'https://api.openai.com/v1'
    openai.api_key = TOKENS[chat_id][1]

    result = []

    openai.api_base = TOKENS[chat_id][0] or 'https://api.openai.com/v1'
    openai.api_key = TOKENS[chat_id][1]
    try:
        model_lst = openai.Model.list()
        for i in model_lst['data']:
            result += [i['id'],]
    except Exception as error:
        print(error)
        my_log.log2(f'gpt_basic:get_list_of_models: {error}\n\nServer: {server[0]}')

    return sorted(list(set(result)))


def tr(text: str, lang: str = 'ru') -> str:
    """
    Translates text from one language to another.
    """
    return my_trans.translate_text2(text, lang)


def chat(chat_id: str, query: str, user_name: str = 'noname', lang: str = 'ru',
         is_private: bool = True, chat_name: str = 'noname chat') -> str:
    """
    The chat function is responsible for handling user queries and generating responses
    using the ChatGPT model.

    Parameters:
    - chat_id: str, the ID of the chat
    - query: str, the user's query
    - user_name: str, the user's name (default: 'noname')
    - lang: str, the language of the chat (default: 'ru')
    - is_private: bool, indicates whether the chat is private or not (default: True)
    - chat_name: str, the name of the chat (default: 'noname chat')

    Returns:
    - str, the response generated by the ChatGPT model
    """
    if chat_id in CHAT_LOCKS:
        lock = CHAT_LOCKS[chat_id]
    else:
        lock = threading.Lock()
        CHAT_LOCKS[chat_id] = lock

    with lock:
        # в каждом чате своя история диалога бота с юзером
        if chat_id in CHATS:
            messages = CHATS[chat_id]
        else:
            messages = []
        # теперь ее надо почистить что бы влезла в запрос к GPT
        # просто удаляем все кроме max_hist_lines последних
        if len(messages) > cfg.max_hist_lines:
            messages = messages[cfg.max_hist_lines:]
        # удаляем первую запись в истории до тех пор пока общее количество токенов не
        # станет меньше cfg.max_hist_bytes
        # удаляем по 2 сразу так как первая - промпт для бота
        while utils.count_tokens(messages) > cfg.max_hist_bytes:
            messages = messages[2:]
        # добавляем в историю новый запрос и отправляем
        messages = messages + [{"role":    "user",
                                "content": query}]

        formatted_date = datetime.datetime.now().strftime("%d %B %Y %H:%M")

        # в каждом чате своя температура
        if chat_id in TEMPERATURE:
            temp = TEMPERATURE[chat_id]
        else:
            temp = 1

        # в каждом чате свой собственный промт
        curr_place = tr('приватный телеграм чат', lang) if is_private else \
tr('публичный телеграм чат', lang)
        if not is_private:
            curr_place = f'{curr_place} "{chat_name}"'
        sys_prompt = f'{tr("Сейчас ", lang)} {formatted_date} , \
{tr("ты находишься в ", lang)} {curr_place} \
{tr("и отвечаешь пользователю с ником", lang)} "{user_name}", \
{tr("локаль пользователя: ", lang)} "{lang}"'
        if chat_id in PROMPTS:
            current_prompt = PROMPTS[chat_id]
        else:
            # по умолчанию формальный стиль
            PROMPTS[chat_id] = [{"role": "system",
                                 "content": tr(utils.gpt_start_message1, lang)}]
            current_prompt =   [{"role": "system",
                                 "content": tr(utils.gpt_start_message1, lang)}]
        current_prompt = [{"role": "system", "content": sys_prompt}] + current_prompt

        # пытаемся получить ответ
        resp = ''
        try:
            resp = ai(prompt = '', temp = temp, messages = current_prompt + messages,
                      chat_id=chat_id)
            if resp:
                messages = messages + [{"role":    "assistant",
                                        "content": resp}]
            else:
                # не сохраняем диалог, нет ответа
                # если в последнем сообщении нет текста (глюк) то убираем его
                if messages[-1]['content'].strip() == '':
                    messages = messages[:-1]
                CHATS[chat_id] = messages or []
                return tr('ChatGPT не ответил.', lang)
        # бот не ответил или обиделся
        except AttributeError:
            # не сохраняем диалог, нет ответа
            return tr('Не хочу говорить об этом. Или не могу.', lang)
        # произошла ошибка переполнения ответа
        except openai.error.InvalidRequestError as error2:
            if """This model's maximum context length is""" in str(error2):
                # чистим историю, повторяем запрос
                p = '\n'.join(f'{i["role"]} - {i["content"]}\n' for i in messages) or \
                    tr('Пусто', lang)
                # сжимаем весь предыдущий разговор до cfg.max_hist_compressed символов
                r = ai_compress(p, cfg.max_hist_compressed, 'dialog')
                messages = [{'role':'system','content':r}] + messages[-1:]
                # и на всякий случай еще
                while utils.count_tokens(messages) > cfg.max_hist_compressed:
                    messages = messages[2:]

                try:
                    resp = ai(prompt = '', temp=temp,
                              messages = current_prompt + messages,
                              chat_id=chat_id)
                except Exception as error3:
                    print(error3)
                    return tr('ChatGPT не ответил.', lang)

                # добавляем в историю новый запрос и отправляем в GPT, если он не
                # пустой, иначе удаляем запрос юзера из истории
                if resp:
                    messages = messages + [{"role":    "assistant",
                                            "content": resp}]
                else:
                    return tr('ChatGPT не ответил.', lang)
            else:
                print(error2)
                return tr('ChatGPT не ответил.', lang)

        # сохраняем диалог, на данном этапе в истории разговора должны быть 2 последних 
        # записи несжатыми
        messages = messages[:-2]
        # если запрос юзера был длинным то в истории надо сохранить его коротко
        if len(query) > cfg.max_hist_mem:
            new_text = ai_compress(query, cfg.max_hist_mem, 'user')
            # заменяем запрос пользователя на сокращенную версию
            messages += [{"role":    "user",
                          "content": new_text}]
        else:
            messages += [{"role":    "user",
                          "content": query}]
        # если ответ бота был длинным то в истории надо сохранить его коротко
        if len(resp) > cfg.max_hist_mem:
            new_resp = ai_compress(resp, cfg.max_hist_mem, 'assistant')
            messages += [{"role":    "assistant",
                          "content": new_resp}]
        else:
            messages += [{"role":    "assistant",
                          "content": resp}]
        CHATS[chat_id] = messages or []

        return resp or tr('ChatGPT не ответил.', lang)


def chat_reset(chat_id: str):
    """
    Reset the chat with the given chat_id.
    
    Parameters:
        chat_id (str): The ID of the chat to reset.
    
    Returns:
        None
    """
    if chat_id in CHATS:
        CHATS[chat_id] = []


if __name__ == '__main__':
    pass
