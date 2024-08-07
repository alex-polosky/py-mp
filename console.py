import curses
import asyncio
from ctypes import Structure, c_bool
import multiprocessing as mp
from multiprocessing.connection import Connection
import signal
import time

_MAIN_LOOP = asyncio.new_event_loop()

def tsleep(t=0.1):
    try:
        loop = asyncio.get_running_loop()
        loop.run_until_complete(asyncio.sleep(t))
    except RuntimeError:
        time.sleep(t)

async def asleep(t=0.1):
    await asyncio.sleep(t)

def is_exiting():
    return _SHOULD_EXIT

def stdscr():
    return _STDSCR

def get_main_loop():
    return _MAIN_LOOP

_mp_errors = []
def get_errors():
    return _mp_errors.copy()

_MAINLOOPS = []
def subloop(timeout=0.1):
    def outer(func):

        async def inner(*args, **kwargs):
            global _SHOULD_EXIT
            while True:
                try:
                    result = func(*args, **kwargs)
                    if asyncio.iscoroutine(result):
                        result = await result

                    pending = asyncio.all_tasks(loop=_MAIN_LOOP)
                    if pending and not len(pending) > len(_MAINLOOPS):
                        if _SHOULD_EXIT:
                            break

                    await asleep(timeout)
                except KeyboardInterrupt:
                    _SHOULD_EXIT = True
                except:
                    _SHOULD_EXIT = True
                    raise

            return result

        inner.__name__ = func.__name__
        inner.__qualname__ = func.__qualname__

        global _MAINLOOPS
        _MAINLOOPS.append(inner)

        return inner

    return outer

def handle_exit(signame):
    global _SHOULD_EXIT
    # _STDSCR.addstr(0, 0, 'Should be quitting')
    _SHOULD_EXIT = True

class _mp(Structure):
    _fields_ = [('active', c_bool), ('has_result', c_bool)]
_mp_LIMIT = 20
_mp_LOOP_TIMEOUT = 0.005
_mp_a = mp.Array(_mp, _mp_LIMIT)
# The following should probably be ids, and we should probably use an id on the _mp as well?
_mp_p = [None for i in range(_mp_LIMIT)]
_mp_cb = [None for i in range(_mp_LIMIT)]
_mp_cn = [None for i in range(_mp_LIMIT)]
_mp_exit = False
async def _loop_mp_exit():
    while True:
        if _mp_exit:
            break
        await asleep(0.1)
asyncio.ensure_future(_loop_mp_exit(), loop=get_main_loop())
@subloop(_mp_LOOP_TIMEOUT)
def loop_mp():
    any_active = False
    for i in range(0, _mp_LIMIT):
        if not _mp_a[i].active:
            continue

        a, p, cb, cn = _mp_a[i], _mp_p[i], _mp_cb[i], _mp_cn[i]

        any_active = True

        is_p_alive = p.is_alive()
        does_p_have_result = a.has_result

        if is_p_alive and does_p_have_result:
            cn_r: Connection = cn[0]
            data = cn_r.recv()
            cb(data)
            with _mp_a.get_lock():
                a.has_result = False

        elif not is_p_alive:
            if not does_p_have_result:
                cb(None)
            else:
                raise Exception
            with _mp_a.get_lock():
                a.active = False
                a.has_result = False
            p.join()
            global _mp_count_done
            _mp_count_done += 1
            _mp_p[i] = None
            _mp_cb[i] = None
            _mp_cn[i] = None

    if is_exiting() and not any_active:
        global _mp_exit
        _mp_exit = True


_mp_count_total = 0
_mp_count_done = 0
async def spawn_mp(func, *args, **kwargs) -> int:
    cn_r, cn_s = mp.Pipe(duplex=False)

    def _mp_cn_s(data):
        cn_s.send(data)
        with _mp_a.get_lock():
            _mp_a[i].has_result = True

    post_cb = {
        'got_response': False,
        'data': None
    }
    def _fn_cb(data):
        post_cb['got_response'] = True
        post_cb['data'] = data

    def _wrapper():
        result = func(*args, **kwargs)
        _mp_cn_s(result)

    p = mp.Process(target=_wrapper)

    global _mp_count_total
    _mp_count_total += 1

    while None not in _mp_p:
        await asleep(_mp_LOOP_TIMEOUT)

    if _SHOULD_EXIT:
        return

    i = _mp_p.index(None)
    with _mp_a.get_lock():
        a = _mp_a[i]
        if a.active:
            a = 20
        a.active = True
        _mp_p[i] = p
        _mp_cn[i] = (cn_r, cn_s)
        _mp_cb[i] = _fn_cb

    p.start()

    while not post_cb['got_response']:
        if _mp_p[i] != p and p.is_alive():
            _mp_errors.append(((func, args, kwargs), i, p))
            return
        await asleep(_mp_LOOP_TIMEOUT)
        if _SHOULD_EXIT:
            return

    return post_cb['data']

@subloop(0.005)
async def display():
    _STDSCR.move(0, 0)
    _STDSCR.refresh()

def main(use_curses=True):
    global _SHOULD_EXIT
    _SHOULD_EXIT = False

    if use_curses:
        global _STDSCR
        _STDSCR = curses.initscr()
        _STDSCR.clear()
        _STDSCR.refresh()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        _STDSCR.keypad(True)
        _STDSCR.nodelay(True)

    if not use_curses:
        _MAINLOOPS.remove(display)

    for signal_enum in [signal.SIGINT, signal.SIGTERM]:
        _MAIN_LOOP.add_signal_handler(signal_enum, handle_exit, signal_enum)

    _MAIN_LOOP.run_until_complete(asyncio.gather(
        *[_MAIN_LOOP.create_task(x()) for x in _MAINLOOPS]
    ))

    if use_curses:
        _STDSCR.nodelay(False)
        _STDSCR.keypad(False)
        curses.curs_set(1)
        curses.nocbreak()
        curses.echo()
        curses.endwin()

if __name__ == '__main__':
    main()
