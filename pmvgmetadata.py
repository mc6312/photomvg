#!/usr/bin/env python3
# -*- coding: utf-8 -*-


""" This file is part of PhotoMV.

    PhotoMV is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    PhotoMV is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with PhotoMV.  If not, see <http://www.gnu.org/licenses/>."""


from gi import require_version as gi_require_version
gi_require_version('GExiv2', '0.10')
from gi.repository import GExiv2, GLib

import os, os.path
import datetime
from collections import namedtuple
import re


class FileTypes():
    """Вспомогательный класс для определения типа файла по расширению."""

    IMAGE, RAW_IMAGE, VIDEO = range(3)

    STR = {IMAGE:'p', RAW_IMAGE:'p', VIDEO:'v'}
    LONGSTR = {IMAGE:'photo', RAW_IMAGE:'raw', VIDEO:'video'}

    DEFAULT_FILE_EXTENSIONS = {
        # список форматов RAW, спионеренный в RawTherapee
        RAW_IMAGE: {'.nef', '.cr2', '.cr3', '.crf',
            '.crw', '.3fr', '.arw', '.dcr', '.dng', '.fff', '.iiq', '.kdc',
            '.mef', '.mos', '.mrw', '.nrw', '.orf', '.pef', '.raf', '.raw',
            '.rw2', '.rwl', '.rwz', '.sr2', '.srf', '.srw', '.x3f', '.arq'},
        # список обычных картиночных форматов
        IMAGE: {'.tif', '.tiff', '.jpg', '.jpeg', '.png'},
        # и видео, какое удалось вспомнить
        VIDEO: {'.mov', '.avi', '.mpg', '.vob', '.ts',
            '.mp4', '.m4v', '.mkv'}
        }

    def __init__(self):
        self.knownExtensions = self.DEFAULT_FILE_EXTENSIONS

    def add_extensions(self, ftype, extensions):
        """Добавление расширений в словарь известных расширений.

        ftype       - тип файла, FileMetadata.FILE_TYPE_xxx,
        extensions  - множество строк вида '.расширение'."""

        self.knownExtensions[ftype].update(extensions)


    def get_file_type(self, fileext):
        """Определяет по расширению fileext, известен ли программе
        тип файла, а также подтип - изображение или видео.
        Возвращает значение FileType.IMAGE|RAW|VIDEO, если тип известен,
        иначе возвращает None."""

        for ft in self.knownExtensions:
            if fileext in self.knownExtensions[ft]:
                return ft

        return None

    def get_file_type_by_name(self, filename):
        """Определяет тип файла по имени filename."""

        return self.get_file_type(os.path.splitext(filename)[1].lower())

    def __str__(self):
        """Костыль для отладки"""

        t = '\n'.join(map(lambda ft: '  %s: %s' % (self.LONGSTR[ft],
                            ', '.join(self.knownExtensions[ft])),
                        self.knownExtensions))
        print(t)
        return t


class FileMetadata():
    """Метаданные изображения или видеофайла.

    Содержит только поля, поддерживаемые FileNameTemplate."""

    __EXIF_DT_TAGS = ['Exif.Image.OriginalDateTime', 'Exif.Image.DateTime']
    __EXIF_MODEL = 'Exif.Image.Model'

    __N_FIELDS = 9

    FILETYPE, MODEL, PREFIX, NUMBER, \
    YEAR, MONTH, DAY, HOUR, MINUTE = range(__N_FIELDS)

    # выражение для выделения префикса и номера из имени файла
    # может не работать на файлах от некоторых камер - производители
    # с именами изгаляются как могут
    __rxFNameParts = re.compile(r'^(.*?)[-_]?(\d+)?$', re.UNICODE)

    def __init__(self, filename, ftypes):
        """Извлечение метаданных из файла filename.

        Параметры:
        filename    - полный путь и имя файла с расширением
        ftype       - экземпляр класса FileTypes

        Поля:
        fields      - поля с метаданными (см. константы xxx)
                      содержат значения в виде строк или None
        fileName    - имя файла без расширения
        fileExt     - и расширение

        В случае неизвестного типа файлов всем полям присваивается
        значение None.
        В случае прочих ошибок генерируются исключения."""

        self.fields = [None] * self.__N_FIELDS

        self.fileName, self.fileExt = os.path.splitext(os.path.split(filename)[1])

        # при копировании или перемещении в новом имени файла расширение
        # в любом случае будет в нижнем регистре, ибо ваистену
        self.fileExt = self.fileExt.lower()

        self.fields[self.FILETYPE] = ftypes.get_file_type(self.fileExt)

        #
        # поля PREFIX, NUMBER
        #
        rm = self.__rxFNameParts.match(self.fileName)
        if rm:
            rmg = rm.groups()

            if rmg[0]:
                s = rmg[0].strip()
                if s:
                    self.fields[self.PREFIX] = s;

            self.fields[self.NUMBER] = rmg[1] # м.б. None

        #
        # Получение метаданных из EXIF
        # сделано для pyexiv2/gexiv v0.1.x
        # (т.к. оно на момент написания было в пузиториях убунты),
        # м.б. несовместимо с более поздними версиями?
        #

        md = None
        if self.fields[self.FILETYPE] != FileTypes.VIDEO:
            # пытаемся выковыривать exif только из изображений,
            # если видеофайлы и могут его содержать, один фиг exiv2
            # на обычных видеофайлах спотыкается, а универсальной,
            # кроссплатформенной И имеющейся в репозиториях
            # Debian/Ubuntu/... библиотеки что-то пока не нашлось;
            # тащить зависимости ручками из PIP, GitHub и т.п.
            # не считаю допустимым

            md = GExiv2.Metadata.new()
            md.open_path(filename)

            # except GLib.Error as ex:
            # исключения тут обрабатывать не будем - пусть вылетают
            # потому как на правильных файлах известных типов оне вылетать не должны,
            # даже если в файле нет EXIF
            #    print('GLib.Error: %s - %s' % (GLib.strerror(ex.code), ex.message))

        dt = None

        if md:
            # ковыряемся в тэгах:

            #
            # сначала дату
            #
            for tagname in self.__EXIF_DT_TAGS:
                if md.has_tag(tagname):
                    # 2016:07:11 20:28:50
                    dts = md.get_tag_string(tagname)
                    try:
                        dt = datetime.datetime.strptime(dts, u'%Y:%m:%d %H:%M:%S')
                    except Exception as ex:
                        print('* Warning!', str(ex))
                        dt = None
                        continue
                    break

            #
            # MODEL
            #
            if md.has_tag(self.__EXIF_MODEL):
                model = md.get_tag_string(self.__EXIF_MODEL).strip()
                if model:
                    self.fields[self.MODEL] = model

        #
        # доковыриваем дату
        #
        if dt:
            # вахЪ! дата нашлась в EXIF!
            if dt.year < 1800 or dt.month <1 or dt.month > 12 or dt.day <1 or dt.day > 31:
                # но содержит какую-то херню
                dt = None
        else:
            # фигвам. берём в качестве даты создания mtime файла
            dt = datetime.datetime.fromtimestamp(os.stat(filename).st_mtime)

        self.fields[self.YEAR]      = '%.4d' % dt.year
        self.fields[self.MONTH]     = '%.2d' % dt.month
        self.fields[self.DAY]       = '%.2d' % dt.day
        self.fields[self.HOUR]      = '%.2d' % dt.hour
        self.fields[self.MINUTE]    = '%.2d' % dt.minute

    __FLD_NAMES = ('FILETYPE', 'MODEL', 'PREFIX', 'NUMBER',
        'YEAR', 'MONTH', 'DAY', 'HOUR', 'MINUTE')

    def __str__(self):
        """Для отладки"""

        r = ['fileName="%s"' % self.fileName, 'fileExt="%s"' % self.fileExt]
        r += (map(lambda f: '%s="%s"' % (self.__FLD_NAMES[f[0]], f[1]), enumerate(self.fields)))
        return '\n'.join(r)


if __name__ == '__main__':
    print('[%s test]' % __file__)

    from pmvcommon import *

    SOURCE_DIR = os.path.expanduser('~/downloads/src')

    try:
        ftypes = FileTypes()

        for root, dirs, files in os.walk(SOURCE_DIR):
            if root.startswith('.'):
                continue

            for fname in files:
                if fname.startswith('.'):
                    continue

                try:
                    r = FileMetadata(os.path.join(root, fname), ftypes)
                    ft = ftypes.get_file_type_by_name(fname)
                    print(fname, '->', FileTypes.LONGSTR[ft] if ft is not None else '?')
                    print(r)
                except Exception as ex:
                    print('error getting metadata from "%s" - %s' % (fname, repr(ex)))
                    #print_exception()
                    #break

    except Exception:
        print_exception()
