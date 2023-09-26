#!/usr/bin/env python3


import html
import random
import re
import string
import platform as platform_module

import prettytable
import telebot
from bs4 import BeautifulSoup
from pylatexenc.latex2text import LatexNodes2Text


gpt_start_message1 = 'You are an artificial intelligence that responds to user requests in the Telegram messenger'


def split_text(text: str, chunk_limit: int = 1500):
    """ Splits one string into multiple strings, with a maximum amount of chars_per_string
        characters per string. This is very useful for splitting one giant message into multiples.
        If chars_per_string > 4096: chars_per_string = 4096. Splits by '\n', '. ' or ' ' in exactly
        this priority.

        :param text: The text to split
        :type text: str

        :param chars_per_string: The number of maximum characters per part the text is split to.
        :type chars_per_string: int

        :return: The splitted text as a list of strings.
        :rtype: list of str
    """
    return telebot.util.smart_split(text, chunk_limit)


def split_html(text: str, max_length: int = 1500) -> list:
    """
    Split the given HTML text into chunks of maximum length, while preserving the integrity
    of HTML tags. The function takes two arguments:
    
    Parameters:
        - text (str): The HTML text to be split.
        - max_length (int): The maximum length of each chunk. Default is 1500.
        
    Returns:
        - list: A list of chunks, where each chunk is a part of the original text.
        
    Raises:
        - AssertionError: If the length of the text is less than or equal to 299.
    """

    if len(text) < 300:
        return [text,]

    #find and replace all links (<a> tag) with random words with the same length
    links = []
    soup = BeautifulSoup(text, 'html.parser')
    a_tags = soup.find_all('a')
    for tag in a_tags:
        tag = str(tag)
        random_string = ''.join(random.choice(string.ascii_uppercase+string.ascii_lowercase) for _ in range(len(tag)))
        links.append((random_string, tag))
        text = text.replace(tag, random_string)

    # split text into chunks
    chunks = telebot.util.smart_split(text, max_length)
    chunks2 = []
    next_chunk_is_b = False
    next_chunk_is_code = False
    # in each piece, check if the number of opening and closing parts matches
    # <b> <code> tags and replace random words back with links
    for chunk in chunks:
        for random_string, tag in links:
            chunk = chunk.replace(random_string, tag)

        b_tags = chunk.count('<b>')
        b_close_tags = chunk.count('</b>')
        code_tags = chunk.count('<code>')
        code_close_tags = chunk.count('</code>')

        if b_tags > b_close_tags:
            chunk += '</b>'
            next_chunk_is_b = True
        elif b_tags < b_close_tags:
            chunk = '<b>' + chunk
            next_chunk_is_b = False

        if code_tags > code_close_tags:
            chunk += '</code>'
            next_chunk_is_code = True
        elif code_tags < code_close_tags:
            chunk = '<code>' + chunk
            next_chunk_is_code = False

        # if there are no opening and closing <code> tags in the previous chunk
        # a closing tag was added, so this chunk is entirely - code
        if code_close_tags == 0 and code_tags == 0 and next_chunk_is_code:
            chunk = '<code>' + chunk
            chunk += '</code>'

        # if there are no opening and closing <b> tags in the previous chunk
        # a closing tag has been added, which means this entire chunk is <b>
        if b_close_tags == 0 and b_tags == 0 and next_chunk_is_b:
            chunk = '<b>' + chunk
            chunk += '</b>'

        chunks2.append(chunk)

    return chunks2


def bot_markdown_to_html(text: str) -> str:
    """
    Converts markdown text from chatbots into HTML for Telegram.
    
    Args:
        text (str): The markdown text to be converted.
        
    Returns:
        str: The converted HTML text.
    """
    # reworks markdown from chatbots in HTML for telegram
    # do full escaping first
    # then the markdown tags and design are changed to the same in HTML
    # this does not affect the code inside the tags, there is only escaping
    # latex code in $ and $$ tags changes to Unicode text

    # escape all text for html
    text = html.escape(text)
    
    # find all pieces of code between ``` and replace with hashes
    # hide the code during transformations
    matches = re.findall('```(.*?)```', text, flags=re.DOTALL)
    list_of_code_blocks = []
    for match in matches:
        random_string = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(16))
        list_of_code_blocks.append([match, random_string])
        text = text.replace(f'```{match}```', random_string)
    matches = re.findall('`(.*?)`', text, flags=re.DOTALL)
    list_of_code_blocks2 = []
    for match in matches:
        random_string = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(16))
        list_of_code_blocks2.append([match, random_string])
        text = text.replace(f'`{match}`', random_string)

    # we remake the lists into more beautiful ones
    new_text = ''
    for i in text.split('\n'):
        ii = i.strip()
        if ii.startswith('* '):
            i = i.replace('* ', '• ', 1)
        if ii.startswith('- '):
            i = i.replace('- ', '• ', 1)
        new_text += i + '\n'
    text = new_text.strip()

    # 1 or 2 * to 3 stars
    # *bum* -> ***bum***
    text = re.sub('\*\*(.+?)\*\*', '<b>\\1</b>', text)

    # tex to unicode
    matches = re.findall("\$\$?(.*?)\$\$?", text, flags=re.DOTALL)
    for match in matches:
        new_match = LatexNodes2Text().latex_to_text(match.replace('\\\\', '\\'))
        text = text.replace(f'$${match}$$', new_match)
        text = text.replace(f'${match}$', new_match)

    # markdown to html
    text = re.sub(r'\[([^\]]*)\]\(([^\)]*)\)', r'<a href="\2">\1</a>', text)
    # we change all links to links in the HTML tag except those that are already designed like that
    text = re.sub(r'(?<!<a href=")(https?://\S+)(?!">[^<]*</a>)', r'<a href="\1">\1</a>', text)

    # hash to codes
    for match, random_string in list_of_code_blocks2:
        new_match = match
        text = text.replace(random_string, f'<code>{new_match}</code>')

    # hash to code blocks
    for match, random_string in list_of_code_blocks:
        new_match = match
        text = text.replace(random_string, f'<code>{new_match}</code>')

    text = replace_tables(text)
    return text


def platform() -> str:
    """
    Return the platform information.
    """
    return platform_module.platform()


def count_tokens(messages):
    """
    Count the number of tokens in the given messages.

    Parameters:
        messages (list): A list of messages.

    Returns:
        int: The number of tokens in the messages. Returns 0 if messages is empty.
    """
    # токенты никто из пиратов не считает, так что просто считаем символы
    if messages:
       return len(str(messages))
    return 0


def split_long_string(long_string: str, header = False, MAX_LENGTH = 24) -> str:
    if len(long_string) <= MAX_LENGTH:
        return long_string
    if header:
        return long_string[:MAX_LENGTH-2] + '..'
    split_strings = []
    while len(long_string) > MAX_LENGTH:
        split_strings.append(long_string[:MAX_LENGTH])
        long_string = long_string[MAX_LENGTH:]

    if long_string:
        split_strings.append(long_string)

    result = "\n".join(split_strings) 
    return result


def replace_tables(text: str) -> str:
    text += '\n'
    state = 0
    table = ''
    results = []
    for line in text.split('\n'):
        if line.count('|') > 2 and len(line) > 4:
            if state == 0:
                state = 1
            table += line + '\n'
        else:
            if state == 1:
                results.append(table[:-1])
                table = ''
                state = 0

    for table in results:
        x = prettytable.PrettyTable(align = "l",
                                    set_style = prettytable.MSWORD_FRIENDLY,
                                    hrules = prettytable.HEADER,
                                    junction_char = '|')
        
        lines = table.split('\n')
        header = [x.strip().replace('<b>', '').replace('</b>', '') for x in lines[0].split('|') if x]
        header = [split_long_string(x, header = True) for x in header]
        try:
            x.field_names = header
        except Exception as error:
            my_log.log2(f'tb:replace_tables: {error}')
            continue
        for line in lines[2:]:
            row = [x.strip().replace('<b>', '').replace('</b>', '') for x in line.split('|') if x]
            row = [split_long_string(x) for x in row]
            try:
                x.add_row(row)
            except Exception as error2:
                my_log.log2(f'tb:replace_tables: {error2}')
                continue
        new_table = x.get_string()
        text = text.replace(table, f'<code>{new_table}</code>')

    return text


if __name__ == '__main__':
    pass