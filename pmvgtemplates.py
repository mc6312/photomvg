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
import os.path


class FileNameTemplate():
    """Шаблон для переименования файлов"""

    # поля шаблона
    YEAR, MONTH, DAY, HOUR, MINUTE, SECOND, \
    MODEL, ALIAS, PREFIX, NUMBER, FILETYPE, LONGFILETYPE, \
    FILENAME = range(13)

    # отображение полей экземпляра FileMetadata в поля FileNameTemplate
    # для полей FileNameTemplate.ALIAS, .FILETYPE и .FILENAME - будет спец. обработка
    __METADATA_FIELDS = {YEAR:FileMetadata.YEAR, MONTH:FileMetadata.MONTH,
        DAY:FileMetadata.DAY, HOUR:FileMetadata.HOUR, MINUTE:FileMetadata.MINUTE, SECOND:FileMetadata.SECOND,
        MODEL:FileMetadata.MODEL,
        PREFIX:FileMetadata.PREFIX, NUMBER:FileMetadata.NUMBER}

    FLD_NAMES = {'y':YEAR, 'year':YEAR,     # год (в виде четырёхзначного числа)
        'mon':MONTH, 'month':MONTH,         # месяц - двухзначный, день и т.п. - тоже
        'd':DAY, 'day':DAY,                 # день
        'h':HOUR, 'hour':HOUR,              # час
        'm':MINUTE, 'minute':MINUTE,        # минута
        's':SECOND, 'second':SECOND,        # секунда
        'model':MODEL,                      # модель камеры
        'a':ALIAS, 'alias':ALIAS,           # сокращенное название модели (если есть в Environment.aliases)
        'p':PREFIX, 'prefix':PREFIX,        # префикс из оригинального имени файла
        'n':NUMBER, 'number':NUMBER,        # номер снимка из оригинального имени файла или EXIF
        't':FILETYPE, 'type':FILETYPE,      # тип файла, односимвольный вариант
        'l':LONGFILETYPE, 'longtype':LONGFILETYPE, # тип файла, длинный вариант
        'f':FILENAME, 'filename':FILENAME}  # оригинальное имя файла (без расширения)

    __FLD_STRS = ('year', 'month', 'day', 'hour', 'minute', 'second',
        'model', 'alias', 'prefix', 'number', 'filetype', 'longfiletype',
        'filename')

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

        # принудительная чистка
        while tplix < tplend and tplstr[tplix] in '/\\': tplix += 1

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

                if tword not in self.FLD_NAMES:
                    raise self.Error(self.ERROR % (tplix, 'недопустимое имя макроса - "%s"' % tword))
                else:
                    # добавляем макрос
                    self.fields.append(self.FLD_NAMES[tword])
            else:
                # добавляем простой текст
                if tword:
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

    def __str__(self):
        """Преобразование внутреннего представления в строку (в т.ч. для GUI)"""

        return ''.join(map(lambda f: f if isinstance(f, str) else '{%s}' % self.__FLD_STRS[f], self.fields))

    def __repr__(self):
        """Для отладки"""

        return '%s(%s)' % (self.__class__.__name__, str(self))


defaultFileNameTemplate = FileNameTemplate('{filename}')


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    import sys, os
    from pmvgconfig import Environment
    env = Environment(sys.argv)

    template = FileNameTemplate('{year}/{month}/{day}/{longtype}/{type}{year}{month}{day}_{ hour}{M}{s}_{n}')

    for root, dirs, files in os.walk(os.path.expanduser('~/downloads/src')):
        for fname in files:
            fpath = os.path.join(root, fname)

            try:
                metadata = FileMetadata(fpath, env.knownFileTypes)

                d, n, e = template.get_new_file_name(env, metadata)
                s = os.path.join(d, n+e)
            except Exception:
                s = 'invalid file or unsupported metadata format'

            print(f'{fname} -> {s}')
