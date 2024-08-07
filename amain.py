# import aioconsole
import curses
import aiofiles
import aiohttp
import asyncio
import os
import random
# import requests
import signal
from threading import Thread
import urllib.parse
import time
from lxml import etree

BASE_DIR = os.path.join(os.path.dirname(__file__), 'RPG')
BASE_URL = ''

parser = etree.HTMLParser()

start = time.time()
active_dir = 0
active_fil = 0
DIR_LIMIT = 5
FIL_LIMIT = 2

TOTAL = []
DONE = []
ALL_SIZE = 0
DONE_SIZE = 0

SHOULD_EXIT = False

class Object:
    def __init__(self, name, path, size):
        self.name = name
        self.path = path
        self.size = size
    def __repr__(self):
        return f'<({self.__class__.__name__}) [{self.name}] @ {self.path}'

class FileObj(Object): pass
class FolderObj(Object): pass

async def sleep(t=0.1):
    global SHOULD_EXIT
    global STDSCR
    # print(f'Time: {time.time() - start:.2f}')
    await asyncio.sleep(t)

async def get_dir(url):
    global SHOULD_EXIT
    global STDSCR
    if SHOULD_EXIT:
        return

    # print(f'Time: {time.time() - start:.2f} ; Url: {url}')

    global active_dir
    while active_dir >= DIR_LIMIT:
        await sleep()
    active_dir += 1
    async with aiohttp.ClientSession() as session:
        attempt = 4
        while attempt:
            try:
                async with session.get(url) as response:
                    attempt = 0
                    res_text = await response.text()
                    content = etree.fromstring(res_text, parser)
                    for each in content.findall('.//a'):
                        if not (link := each.attrib.get('href', '')):
                            continue
                        if (text := urllib.parse.unquote(link)) == '../':
                            continue
                        if text.endswith('/'):
                            cls = FolderObj
                            text = text[:-1]
                        else:
                            cls = FileObj
                        size = each.tail.split()[-1]

                        if size == '-':
                            size = 0
                        else:
                            end = size[-1]
                            if len(size) == 1:
                                size = int(size)
                            else:
                                num = int(size[:-1])

                            if end == 'K':
                                size = num * 1024
                            elif end == 'M':
                                size = num * 1024 * 1024
                            elif end == 'G':
                                size = num * 1024 * 1024 * 1024
                            else:
                                size = int(size)

                        if type(size) == str:
                            print(size, url, text)
                            raise
                        yield cls(text, link, size)
            except KeyboardInterrupt:
                print('Should be quitting')
                SHOULD_EXIT = True
            except BaseException as ex:
                print(f'{url}: {ex}')
                await sleep()
                attempt -= 1
                if attempt == 0:
                    raise
    active_dir -= 1

async def save_file(url, root, result: FileObj):
    global SHOULD_EXIT
    global STDSCR
    if SHOULD_EXIT:
        return

    fpath = os.path.join(root, result.name)
    if os.path.exists(fpath):
        return

    TOTAL.append(result)
    global ALL_SIZE, DONE_SIZE
    ALL_SIZE += result.size

    global active_fil
    while active_fil >= FIL_LIMIT:
        await sleep()
    active_fil += 1
    async with aiohttp.ClientSession() as session:
        attempt = 4
        while attempt:
            try:
                async with session.get(url + result.path) as response:
                    attempt = 0
                    async with aiofiles.open(fpath, 'wb') as f:
                        while True:
                            chunk = await response.content.read(1024 * 1024)
                            if not chunk:
                                break
                            await f.write(chunk)
                            DONE_SIZE += len(chunk)
            except KeyboardInterrupt:
                print('Should be quitting')
                SHOULD_EXIT = True
            except BaseException as ex:
                print(f'{url + result.path}: {ex}')
                await sleep()
                attempt -= 1
                if attempt <= 0:
                    raise
    active_fil -= 1
    DONE.append(result)

async def fetch(url, root, loop):
    global SHOULD_EXIT
    global STDSCR
    if not os.path.exists(root):
        os.mkdir(root)
    async for result in get_dir(url):
        if type(result) is FolderObj:
            asyncio.ensure_future(fetch(url + result.path, os.path.join(root, result.name), loop), loop=loop)
        else:
            asyncio.ensure_future(save_file(url, root, result), loop=loop)

async def key_input(loop):
    global SHOULD_EXIT
    global STDSCR
    curses.noecho()
    curses.cbreak()
    STDSCR.keypad(True)
    STDSCR.nodelay(True)
    while True:
        try:
            STDSCR.addstr(2, 0, 'key_input')

            h = STDSCR.getch()
            STDSCR.addstr(2, len('key_input'), str(h))

            pending = asyncio.all_tasks(loop=loop)
            if pending and not len(pending) <= 3:
                if SHOULD_EXIT:
                    break
                else:
                    await sleep(0.1)
        except KeyboardInterrupt:
            SHOULD_EXIT = True
    STDSCR.nodelay(False)
    STDSCR.keypad(False)
    curses.nocbreak()
    curses.echo()
    curses.endwin()

async def checker(loop):
    global SHOULD_EXIT
    global STDSCR
    def to_bytes(n):
        if n > 1024 * 1024 * 1024 * 1024:
            return f'{n / (1024 * 1024 * 1024) :.2f}T'
        if n > 1024 * 1024 * 1024:
            return f'{n / (1024 * 1024 * 1024) :.2f}G'
        if n > 1024 * 1024:
            return f'{n / (1024 * 1024) :.2f}M'
        if n > 1024:
            return f'{n / (1024) :.2f}K'
        return f'{n}'
    while True:
        try:
            if TOTAL and ALL_SIZE:
                STDSCR.addstr(1, 0, f'FILE: {len(DONE)} / {len(TOTAL)} : {len(DONE) / len(TOTAL):.2%}\tSIZE: FILE: {to_bytes(DONE_SIZE)} / {to_bytes(ALL_SIZE)} : {DONE_SIZE / ALL_SIZE :.2%}')
            else:
                STDSCR.addstr(1, 0, f'Currently 0')
            pending = asyncio.all_tasks(loop=loop)
            if pending and not len(pending) <= 3:
                if SHOULD_EXIT:
                    break
                else:
                    await sleep(2)
        except KeyboardInterrupt:
            SHOULD_EXIT = True

async def display(loop):
    global SHOULD_EXIT
    global STDSCR
    while True:
        try:
            STDSCR.addstr(9, 0, str(random.randint(0, 9000)))
            STDSCR.move(10, 0)
            STDSCR.refresh()
            pending = asyncio.all_tasks(loop=loop)
            if pending and not len(pending) <= 3:
                if SHOULD_EXIT:
                    break
                else:
                    await sleep(0.1)
        except KeyboardInterrupt:
            SHOULD_EXIT = True

async def main(loop):
    global SHOULD_EXIT
    global STDSCR
    # await fetch(BASE_URL, BASE_DIR, loop)
    STDSCR.addstr(3, 0, 'main')
    while True:
        try:
            pending = asyncio.all_tasks(loop=loop)
            if pending and not len(pending) <= 3:
                if SHOULD_EXIT:
                    break
                else:
                    await sleep(1)
        except KeyboardInterrupt:
            SHOULD_EXIT = True

def handle_exit(*args):#signame, loop):
    global SHOULD_EXIT
    global STDSCR
    STDSCR.addstr(0, 0, 'Should be quitting')
    SHOULD_EXIT = True


if __name__ == '__main__':
    global STDSCR
    STDSCR = curses.initscr()
    STDSCR.clear()
    STDSCR.refresh()

    loop = asyncio.new_event_loop()
    for signal_enum in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(signal_enum, handle_exit, loop)

    loop.run_until_complete(asyncio.gather(
        loop.create_task(main(loop)),
        loop.create_task(checker(loop)),
        loop.create_task(key_input(loop)),
        loop.create_task(display(loop))
    ))
