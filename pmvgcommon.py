#!/usr/bin/env python3
# -*- coding: utf-8 -*-


""" This file is part of PhotoMVG.

    PhotoMVG is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    PhotoMVG is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with PhotoMVG.  If not, see <http://www.gnu.org/licenses/>."""


TITLE = 'PhotoMVG'
VERSION = '2.0'
TITLE_VERSION = '%s v%s' % (TITLE, VERSION)
URL = 'http://github.com/mc6312/photomvg'
COPYRIGHT = '(c) 2019 MC-6312'


import os, os.path
from traceback import format_exception
from sys import exc_info, stderr


def print_exception():
    """Печать текущего исключения"""

    for s in format_exception(*exc_info()):
        print(s, file=stderr)


def make_dirs(path, excpt=None):
    """Создание пути path с подкаталогами.

    В случае успеха возвращает None.
    В случае ошибки:
    - если параметр excpt - экземпляр класса Exception, то генерирует
      соотв. исключение;
    - иначе возвращает строку с сообщением об ошибке."""

    try:
        if not os.path.exists(path):
            os.makedirs(path)

        return None

    except OSError as ex:
        emsg = 'Не удалось создать каталог "%s": %s' % (path, ex)

        if isinstance(excpt, Exception):
            raise excpt(emsg)
        else:
            return emsg


def path_validate(path):
    return os.path.abspath(os.path.expanduser(path))


INVALID_TEMPLATE_CHARS = '\t\n\r*?:"<>|%s' % ('/' if os.path.sep == '\\' else '\\')
INVALID_FNAME_CHARS = '%s%s' % (INVALID_TEMPLATE_CHARS, os.path.sep)


def filename_validate(fname, forceext):
    """Проверка и исправление имени файла.

    fname       - имя файла,
    forceext    - расширение (тип файла), или None;
                  если указано - то расширение, содержащееся в fname,
                  будет заменено на fext.

    Возвращает строку с исправленным именем файла."""

    # не может начинаться и заканчиваться никакими пробельными символами
    fname, fext = map(lambda s: s.strip(), os.path.splitext(fname))

    # не может быть пустым
    if fname == '':
        fname = '_'
    else:
        # не может начинаться с точки - в *nix это признак скрытого
        # файла, а у нас тут не файловый менеджер, чтобы произвольно изгаляться
        if fname.startswith('.'):
            fname = '_%s' % fname[1:]

        # не может заканчиваться точкой -
        # об это спотыкается как минимум rsync и вообще неаккуратно
        if fname.endswith('.'):
            fname = '%s_' % fname[:-1]

        # не может содержать разделителей путей и т.п.
        # (в кое-каких ФС технически может, но это разведение бардака)
        fname = ''.join(map(lambda c: '_' if c in INVALID_FNAME_CHARS else c, fname))

    # при необходимости не даём менять расширение
    if forceext is None:
        forceext = fext

    return '%s%s' % (fname, forceext)


def same_dir(dir1, dir2):
    """Возвращает True, если оба параметра указывают на один каталог,
    или один является подкаталогом другого.
    Для правильности проверки оба пути должны быть абсолютными."""

    dir1 = os.path.abspath(dir1)
    dir2 = os.path.abspath(dir2)

    if dir1 == dir2: #os.path.samefile(dir1, dir2):
        return True

    r = os.path.normpath(os.path.commonprefix((dir1, dir2)))
    return r == dir1 or r == dir2
    #return os.path.samefile(r, dir1) or os.path.samefile(r, dir2)


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    for ix, c in enumerate(INVALID_TEMPLATE_CHARS):
        print(f'{ix}: "{c}"')
    exit(0)

    print(filename_validate('/some/filename:text', None))
    try:
        raise OSError('test')
    except Exception:
        print_exception()
