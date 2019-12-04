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


from pmvgmetadata import FileMetadata, FileTypes
from pmvgcommon import *

import os.path
from collections import namedtuple


class FileNameTemplate():
    """Шаблон для переименования файлов"""

    # поля шаблона
    YEAR, MONTH, DAY, HOUR, MINUTE, SECOND, \
    MODEL, ALIAS, PREFIX, NUMBER, FILETYPE, LONGFILETYPE, \
    FILENAME = range(13)

    fldparm = namedtuple('fldparm', 'shortname longname dispname description')

    # параметры полей шаблонов; индекс в списке соответствует константам выше
    # элементы списка - экземпляры fldparm:
    # (короткое имя, длинное имя, строка для отображения в UI, описание для UI)

    FIELDS = (
        # YEAR - год (в виде четырёхзначного числа)
        fldparm('y',  'year', 'ГГГГ', 'год (четыре цифры)'),
        # MONTH - месяц (в виде двухзначного числа, день и т.п. - тоже)
        fldparm('mon', 'month', 'ММ', 'месяц (две цифры)'),
        # DAY - день
        fldparm('d', 'day', 'ДД', 'день (две цифры)'),
        # HOUR - час
        fldparm('h', 'hour', 'ЧЧ', 'час (две цифры)'),
        # MINUTE - минута
        fldparm('m', 'minute', 'ММ', 'минута (две цифры)'),
        # SECOND - секунда
        fldparm('s', 'second', 'СС', 'секунда (две цифры)'),
        # MODEL - модель камеры
        fldparm('o', 'model', 'МОДЕЛЬ', 'модель камеры (полностью)'),
        # ALIAS - сокращенное название модели (если есть в Environment.aliases)
        fldparm('a', 'alias', 'МСОКР', 'модель камеры (сокращённо)'),
        # PREFIX - префикс из оригинального имени файла
        fldparm('p', 'prefix', 'ПРЕФИКС', 'префикс исходного имени файла'),
        # NUMBER - номер снимка из оригинального имени файла или EXIF
        fldparm('n', 'number', 'НОМЕР', 'номер из исходного имени файла'),
        # FILETYPE - тип файла, односимвольный вариант
        fldparm('t', 'type', 'Т', 'тип файла (одним символом)'),
        # LONGFILETYPE - тип файла, длинный вариант
        fldparm('l', 'longtype', 'ТИПФАЙЛА', 'тип файла (полностью)'),
        # FILENAME - оригинальное имя файла (без расширения)
        fldparm('f', 'filename', 'ИМЯФАЙЛА', 'исходное имя файла (без расширения)'),
        )

    # маппинг полей экземпляра FileMetadata в поля FileNameTemplate
    # для полей FileNameTemplate.ALIAS, .FILETYPE и .FILENAME - будет спец. обработка
    __METADATA_FIELDS = {YEAR:FileMetadata.YEAR, MONTH:FileMetadata.MONTH,
        DAY:FileMetadata.DAY, HOUR:FileMetadata.HOUR, MINUTE:FileMetadata.MINUTE, SECOND:FileMetadata.SECOND,
        MODEL:FileMetadata.MODEL,
        PREFIX:FileMetadata.PREFIX, NUMBER:FileMetadata.NUMBER}

    class Error(Exception):
        pass

    ERROR = 'ошибка в позиции %d шаблона - %s'

    def __init__(self, tplstr):
        """Разбор строки s с шаблоном имени файла"""

        self.fields = []
        # список может содержать строки и целые числа
        # строки помещаются в новое имя файла как есть,
        # целые числа (константы FileMetadata.xxx) заменяются соответствующими
        # полями метаданных

        tpllen = len(tplstr)
        tplend = tpllen - 1

        tplix = 0

        # принудительная чистка: строка не должна начинаться с разделителя каталогов
        while tplix < tplend and tplstr[tplix] == os.path.sep: tplix += 1

        # ...а также начинаться и заканчиваться точками
        if tplstr.startswith('.') or tplstr.endswith('.'):
            raise self.Error('текст шаблона не должен начинаться с точки и/или заканчиваться точкой')

        if tplix > tplend:
            raise self.Error(self.ERROR % (tplix, 'пустой шаблон'))

        tstop = '{'
        tplstart = tplix
        tbracket = False
        c = None

        def flush_word(tbracket, tword):
            if tbracket:
                # проверяем макрос
                tword = tword.strip()
                if not tword:
                    raise self.Error(self.ERROR % (tplix, 'пустое имя макроса'))

                tword = tword.lower()

                fldixfound = -1
                for fldix, fparm in enumerate(self.FIELDS):
                    if tword == fparm.shortname or tword == fparm.longname:
                        fldixfound = fldix
                        break

                if fldixfound < 0:
                    raise self.Error(self.ERROR % (tplix, 'недопустимое имя макроса - "%s"' % tword))
                else:
                    # добавляем макрос
                    self.fields.append(fldixfound)
            else:
                # добавляем простой текст, проверяя его на недопустимые в имени файла символы
                # разделитель каталогов - допустим, он позволяет с помощью шаблонов создавать подкаталоги

                if tword:
                    badchars = ''.join(filter(lambda c: c in INVALID_TEMPLATE_CHARS, tword))
                    if badchars:
                        raise self.Error(self.ERROR % (tplix, 'текст шаблона "%s" содержит недопустимые символы "%s"' % (tword, badchars)))

                    self.fields.append(tword)

        while tplix <= tplend:
            while tplix <= tplend:
                c = tplstr[tplix]

                if c in '{}':
                    if tplix < tplend:
                        if tplstr[tplix+1] == c:
                            tplix += 2
                            continue

                    if c != tstop:
                        raise self.Error(self.ERROR % (tplix, 'недопустимое появление "%s"' % c))

                    if c == '}':
                        tbracket = True

                    tstop = '}' if tstop == '{' else '{'
                    break

                tplix += 1

            if tplix >= tplend:
                break

            flush_word(tbracket, tplstr[tplstart:tplix])
            if tbracket:
                tbracket = False

            tplix += 1
            tplstart = tplix

        if tplstart < tplend:
            if tstop == '}':
                raise self.Error(self.ERROR % (tplix, 'незавершённый макрос'))
            else:
                flush_word(tbracket, tplstr[tplstart:tplix])

    def get_field_str(self, env, metadata, fldix):
        """Возвращает поле шаблона в виде строки.

        env         - экземпляр pmvconfig.Environment;
        metadata    - экземпляр pmvmetadata.FileMetadata;
        fldix       - номер поля (см. константы в начале класса);

        возвращает строку со значением поля, если поле имеется
        в метаданных, иначе возвращает символ "_"."""

        fv = None

        if fldix in self.__METADATA_FIELDS:
            fv = metadata.fields[self.__METADATA_FIELDS[fldix]]
        elif fldix == self.ALIAS:
            if metadata.fields[FileMetadata.MODEL]:
                model = metadata.fields[FileMetadata.MODEL].lower()

                if model in env.aliases:
                    fv = env.aliases[model]
        elif fldix == self.FILENAME:
            fv = metadata.fileName
        elif fldix == self.FILETYPE:
            nfx = metadata.fields[FileMetadata.FILETYPE]
            fv = FileTypes.STR[nfx] if nfx in FileTypes.STR else None
        elif fldix == self.LONGFILETYPE:
            nfx = metadata.fields[FileMetadata.FILETYPE]
            fv = FileTypes.LONGSTR[nfx] if nfx in FileTypes.LONGSTR else None

        return '_' if not fv else fv

    def get_new_file_name(self, env, metadata):
        """Создаёт имя файла на основе шаблона и метаданных файла.

        env         - экземпляр pmvconfig.Environment
        metadata    - экземпляр pmvmetadata.FileMetadata

        Возвращает кортеж из трёх элементов:
        1. относительный путь (если шаблон содержал разделители каталогов),
           или пустая строка;
        2. имя файла без расширения;
        3. расширение."""

        r = []
        for fld in self.fields:
            if isinstance(fld, str):
                # простой текст в шаблоне
                r.append(fld)
            else:
                r.append(self.get_field_str(env, metadata, fld))

        rawpath = os.path.split(''.join(r))
        return (*rawpath, metadata.fileExt)

    def get_display_str(self):
        """Преобразование внутреннего представления в строку для
        отображения в UI."""

        return ''.join(map(lambda f: f if isinstance(f, str) else self.FIELDS[f].dispname, self.fields))

    def __str__(self):
        """Преобразование внутреннего представления в строку,
        пригодную для разбора (при создании нового экземпляра FileNameTemplate)."""

        return ''.join(map(lambda f: f if isinstance(f, str) else '{%s}' % self.FIELDS[f].longname, self.fields))

    def __repr__(self):
        """Для отладки"""

        return '%s("%s")' % (self.__class__.__name__, str(self))


defaultFileNameTemplate = FileNameTemplate('{filename}')


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    import sys, os
    from pmvgconfig import Environment
    env = Environment(sys.argv)


    for root, dirs, files in os.walk(os.path.expanduser('~/downloads/src')):
        for fname in files:
            fpath = os.path.join(root, fname)

            try:
                metadata = FileMetadata(fpath, env.knownFileTypes)
                template = env.get_template_from_metadata(metadata)
                d, n, e = template.get_new_file_name(env, metadata)
                s = os.path.join(d, n+e)
            except Exception as ex:
                s = f'invalid file or unsupported metadata format ({ex})'

            print(f'{fname} -> {s}')
