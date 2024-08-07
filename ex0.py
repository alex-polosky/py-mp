import asyncio
from ctypes import Structure, c_double, c_int, c_char, c_wchar_p, c_bool
import multiprocessing as mp
import os
from time import sleep
from console import subloop, stdscr, main, asleep, get_main_loop, is_exiting, spawn_mp


_lastpress = 0
@subloop(0.01)
async def keyinputwatch():
    global _keybuffer
    global _lastpress
    if _keybuffer:
        _lastpress = _keybuffer[-1]
    s = ' '.join([str(x) for x in _keybuffer if x >= 0]).ljust(100, ' ')
    _keybuffer.clear()
    stdscr().addstr(15, 0, str(_lastpress).rjust(4))
    stdscr().addstr(15, 5, ':')
    stdscr().addstr(15, 7, s)

_keybuffer = []
@subloop(0.001)
async def keyinput():
    h = stdscr().getch()
    global _keybuffer
    if h >= 0:
        _keybuffer.append(h)

class _toadd(Structure):
    _fields_ = [('active', c_bool), ('line', c_int), ('ppid', c_int), ('pid', c_int)]
_toadd_mp = mp.Array(_toadd, 500)
_toadd_i = mp.Value(c_int, 0)
@subloop(0.01)
async def loop_info_dump():
    with _toadd_i.get_lock(), _toadd_mp.get_lock():
        while _toadd_i.value >= 1:
            toadd = _toadd_mp[_toadd_i.value]
            if toadd.active:
                toadd.active = False
                stdscr().addstr(toadd.line, 0, f'[P{toadd.ppid: 7}:{toadd.pid: 7}]')
            _toadd_i.value -= 1

def _info_dump(line, ppid, pid):
    with _toadd_i.get_lock(), _toadd_mp.get_lock():
        _toadd_i.value += 1
        toadd = _toadd_mp[_toadd_i.value]
        toadd.line = line
        toadd.ppid = ppid
        toadd.pid = pid
        toadd.active = True

def info(title, line, delay):
    stdscr().addstr(line, 20, title)
    sleep(delay)
    _info_dump(line, os.getppid(), os.getpid())

async def spawn(title, line, delay):
    stdscr().addstr(line, 0, f'starting')
    try:
        stdscr().addstr(line, 20, title)
        await spawn_mp(info, (title, line, delay), {})
    except BaseException as ex:
        stdscr().addstr(line, 0, f'{ex}')

_f = False
@subloop(1)
async def _():
    global _f
    if not _f:
        _f = True
        info('1 secs', 0, 0)
        asyncio.ensure_future(spawn('s1', 1, 1), loop=get_main_loop())
        asyncio.ensure_future(spawn('s2', 2, 2), loop=get_main_loop())
        asyncio.ensure_future(spawn('s3', 3, 3), loop=get_main_loop())
        asyncio.ensure_future(spawn('s4', 4, 4), loop=get_main_loop())
        asyncio.ensure_future(spawn('s5', 5, 5), loop=get_main_loop())
        asyncio.ensure_future(spawn('s6', 6, 6), loop=get_main_loop())
        asyncio.ensure_future(spawn('s7', 7, 7), loop=get_main_loop())
        asyncio.ensure_future(spawn('s8', 8, 8), loop=get_main_loop())

if __name__ == '__main__':
    main()
