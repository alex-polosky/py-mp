import aiofiles
import aiohttp
import asyncio
from ctypes import Structure, c_double, c_int, c_char, c_wchar_p, c_bool
import curses
import multiprocessing as mp
import os
import requests
from time import sleep, time
import urllib.parse
from lxml import etree
from console import subloop, stdscr, main, asleep, get_main_loop, is_exiting, spawn_mp, _mp_p, get_errors

BASE_DIR = os.path.join(os.path.dirname(__file__), 'Books')
BASE_URL = ''

parser = etree.HTMLParser()

start = time()
active_dir = mp.Value(c_int, 0)
active_fil = mp.Value(c_int, 0)
DIR_LIMIT = mp.Value(c_int, 5)
FIL_LIMIT = mp.Value(c_int, 8)
LIMIT_LINES = mp.Value(c_int, DIR_LIMIT.value + FIL_LIMIT.value)
DIR_LOCK = mp.Lock()

TOTAL = []
DONE = []
CURRENT = []
ALL_SIZE = 0
DONE_SIZE = 0

class Object:
    def __init__(self, name, path, size):
        self.name = name
        self.path = path
        self.size = size
    def __repr__(self):
        return f'<({self.__class__.__name__}) [{self.name}] @ {self.path}'

class FileObj(Object): pass
class FolderObj(Object):
    def __init__(self, name, path, size):
        super().__init__(name, path, size)
        self.children = []

def start_mp(counter, limit, max_attempt=4, attempt_timeout=1, active_timeout=0.1, cb_fn=None):
    def outer(func):

        async def inner(*args, **kwargs):
            while counter.value >= limit.value:
                await asleep(active_timeout)
            with counter.get_lock():
                counter.value += 1

            if len(args) == 1:
                cur_val = f'{func.__name__}', f'{args[0]}'
            else:
                cur_val = f'{func.__name__}', f'{args[-1].name}'

            CURRENT.append(cur_val)

            attempt = max_attempt
            while attempt:
                try:
                    result = await spawn_mp(func, *args, **kwargs)
                    break
                except KeyboardInterrupt:
                    return
                except BaseException as ex:
                    await asleep(attempt_timeout)
                    attempt -= 1

            CURRENT.pop(CURRENT.index(cur_val))

            with counter.get_lock():
                counter.value -= 1

            if not attempt:
                raise

            if cb_fn:
                cb_fn(result, args, kwargs)

            return result

        inner.__name__ = func.__name__
        inner.__qualname__ = func.__qualname__

        return inner

    return outer

@start_mp(active_dir, DIR_LIMIT)
def get_dir(url):
    response = requests.get(url)
    if not response.ok:
        raise BaseException(response.text)

    try:
        content = etree.fromstring(response.text, parser)
    except BaseException as ex:
        raise

    results = []
    aaas = content.findall('.//a')
    if not aaas:
        raise BaseException('no a"s')
    for each in aaas:
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

        # if type(size) == str:
        #     print(size, url, text)
        #     raise
        results.append(cls(text, link, size))

    return results

def _save_file_cb(returned, args, kwargs):
    global DONE_SIZE
    url, root, result = args
    result: FileObj
    if not is_exiting():
        DONE_SIZE += result.size
        DONE.append(result)

@start_mp(active_fil, FIL_LIMIT, cb_fn=_save_file_cb)
def save_file(url, root, result: FileObj):
    file_path = os.path.join(root, urllib.parse.unquote(result.path))
    if os.path.exists(file_path):
        return
    response = requests.get(url + result.path, stream=True)
    if not response.ok:
        raise BaseException(response.text)
    with open(file_path, 'wb') as f:
        for chunk in response.iter_content(1024 * 1024):
            if chunk:
                f.write(chunk)

async def fetch(url, root, obj: FolderObj):
    global ALL_SIZE

    DIR_LOCK.acquire()
    try:
        if not os.path.exists(root):
            os.mkdir(root)
    finally:
        DIR_LOCK.release()

    results = await get_dir(url)
    if not results:
        DONE.append(obj)
        return

    to_run = []
    for result in results:
        result.parent = obj
        obj.children.append(result)
        TOTAL.append(result)
        if type(result) is FolderObj:
            to_run.append(fetch(url + result.path, os.path.join(root, result.name), result))
        else:
            ALL_SIZE += result.size
            to_run.append(save_file(url, root, result))

    if is_exiting():
        return

    asyncio.ensure_future(asyncio.gather(*to_run), loop=get_main_loop())

    DONE.append(obj)

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

@subloop(0.5)
async def counting():
    stdscr().addstr(0, 0, f'URLS: {len(DONE)} / {len(TOTAL)} : {(len(DONE) / len(TOTAL) if len(TOTAL) else 0) :.2%}         ')
    if TOTAL and ALL_SIZE:
        stdscr().addstr(1, 0, f'FILE: {to_bytes(DONE_SIZE)} / {to_bytes(ALL_SIZE)} : {DONE_SIZE / ALL_SIZE :.2%}         ')

@subloop(0.5)
def active_threads():
    pending = {x for x in asyncio.all_tasks(get_main_loop()) if not x.done()}
    stdscr().addstr(2, 0, f'THREADS: {len(pending)}')

@subloop(0.3)
def active_processes():
    m = _mp_p.copy()
    stdscr().addstr(3, 0, f'PROCESSES: {len(m) - m.count(None)}  ')

@subloop(0.5)
def get_error_count():
    errors = get_errors()
    stdscr().addstr(4, 0, f'PROCESS_ERRORS: {len(errors)}   ')

@subloop(0.1)
def key_display():
    stdscr().addstr(10, 0, f'DIR_LIMIT: {active_dir.value} / {DIR_LIMIT.value}\tFILE_LIMIT: {active_fil.value} / {FIL_LIMIT.value}\tEXITING: {is_exiting()}     ')

@subloop(0.5)
def active_process_names():
    for i in range(LIMIT_LINES.value):
        stdscr().addstr(i, 80, (' '*80))
    for i, x in enumerate(sorted(CURRENT)):
        stdscr().addstr(i, 80, x[0] + ': ' + x[1][-65:])

@subloop(0.01)
def key_check():
    global DIR_LIMIT, FIL_LIMIT
    h = stdscr().getch()
    if h == curses.KEY_LEFT:
        with DIR_LIMIT.get_lock():
            if DIR_LIMIT.value > 1:
                DIR_LIMIT.value -= 1
                with LIMIT_LINES.get_lock():
                    LIMIT_LINES.value -= 1
    if h == curses.KEY_RIGHT:
        with DIR_LIMIT.get_lock():
            if DIR_LIMIT.value < 20:
                DIR_LIMIT.value += 1
                with LIMIT_LINES.get_lock():
                    LIMIT_LINES.value += 1
    if h == curses.KEY_DOWN:
        with FIL_LIMIT.get_lock():
            if FIL_LIMIT.value > 1:
                FIL_LIMIT.value -= 1
                with LIMIT_LINES.get_lock():
                    LIMIT_LINES.value -= 1
    if h == curses.KEY_UP:
        with FIL_LIMIT.get_lock():
            if FIL_LIMIT.value < 50:
                FIL_LIMIT.value += 1
                with LIMIT_LINES.get_lock():
                    LIMIT_LINES.value += 1

if __name__ == '__main__':
    root = FolderObj(BASE_DIR, BASE_URL, 0)
    TOTAL.append(root)
    asyncio.ensure_future(fetch(BASE_URL, BASE_DIR, root), loop=get_main_loop())
    main()
