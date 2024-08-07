import aiofiles
import aiohttp
import asyncio
from ctypes import Structure, c_double, c_int, c_char, c_wchar_p, c_bool
import json
import multiprocessing as mp
import os
import random
import requests
from time import sleep, time
import urllib.parse
from lxml import etree
from console import subloop, stdscr, main, asleep, get_main_loop, is_exiting, spawn_mp

globs = []

def proc(send_pipe, t):
    sleep(t)
    z = int(t * 100)
    send_pipe({'result': [x for x in range(z, z+10)]})

async def thing0():
    data = await spawn_mp(proc, 1)
    globs.append((1, data))
    stdscr().addstr(0, 0, json.dumps(data))

async def thing1():
    data = await spawn_mp(proc, 2)
    globs.append((2, data))
    stdscr().addstr(1, 0, json.dumps(data))

async def thing2():
    data = await spawn_mp(proc, 3)
    globs.append((3, data))
    stdscr().addstr(2, 0, json.dumps(data))

async def thing3():
    data = await spawn_mp(proc, 2.2)
    globs.append((4, data))
    stdscr().addstr(3, 0, json.dumps(data))

# def proc2(send_pipe, order, start):
def proc2(order, start):
    z = random.randint(0, 50) / 10
    sleep(z)
    return (order, z, time() - start)
    # send_pipe((order, z, time() - start))

async def add_the_things(order, start):
    data = await spawn_mp(proc2, order, start)
    globs.append(data)

global start
start = None
end = False
@subloop()
async def hi():
    global start
    global end
    if end:
        return
    if not start:
        start = time()
    if len(globs) == 200 or time() - start >= 180:
        with open('data.300.0.01.ndjson', 'w') as f:
            for x in globs:
                f.write(json.dumps({'run': "301", 'id': x[0], 't': x[1], 'timestamp': x[2]}) + '\n')
        globs.clear()
        end = True


if __name__ == '__main__':
    # asyncio.ensure_future(thing0(), loop=get_main_loop())
    # asyncio.ensure_future(thing1(), loop=get_main_loop())
    # asyncio.ensure_future(thing2(), loop=get_main_loop())
    # asyncio.ensure_future(thing3(), loop=get_main_loop())
    for i in range(200):
        asyncio.ensure_future(add_the_things(i, time()), loop=get_main_loop())
    main(use_curses=True)
