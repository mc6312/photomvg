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


from gi import require_version as gi_require_version
gi_require_version('GExiv2', '0.10')
from gi.repository import GExiv2, GLib

import os, os.path
import datetime
from collections import namedtuple
import re


class FileTypes():
    """Вспомогательный класс для определения типа файла по расширению."""

    DIRECTORY, IMAGE, RAW_IMAGE, VIDEO = range(4)
    # тип "DIRECTORY" в этом модуле не используется, нужен для GUI

    STR = {IMAGE:'p', RAW_IMAGE:'p', VIDEO:'v'}
    LONGSTR = {IMAGE:'photo', RAW_IMAGE:'raw', VIDEO:'video'}

    STR_TO_TYPE = dict(map(lambda v: (v[1], v[0]), LONGSTR.items()))

    DEFAULT_FILE_EXTENSIONS = {
        # список форматов RAW, спионеренный из RawTherapee
        RAW_IMAGE: {'.nef', '.cr2', '.cr3', '.crf',
            '.crw', '.3fr', '.arw', '.dcr', '.dng', '.fff', '.iiq', '.kdc',
            '.mef', '.mos', '.mrw', '.nrw', '.orf', '.pef', '.raf', '.raw',
            '.rw2', '.rwl', '.rwz', '.sr2', '.srf', '.srw', '.x3f', '.arq'},
        # список обычных картиночных форматов
        IMAGE: {'.tif', '.tiff', '.jpg', '.jpeg', '.png'},
        # и видео, какое удалось вспомнить
        VIDEO: {'.mov', '.avi', '.mpg', '.vob', '.ts',
            '.mp4', '.m4v', '.mkv', '.mts'}
        }

    def __init__(self):
        self.knownExtensions = self.DEFAULT_FILE_EXTENSIONS.copy()

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

        # просто так нагляднее
        return None

    def get_file_type_by_name(self, filename):
        """Определяет тип файла по имени filename."""

        return self.get_file_type(os.path.splitext(filename)[1].lower())

    def __repr__(self):
        """Костыль для отладки"""

        return '%s(%s)' % (self.__class__.__name__,
            '\n'.join(map(lambda ft: '%s: %s' % (self.LONGSTR[ft],
                          ', '.join(self.knownExtensions[ft])),
                      self.knownExtensions))
            )


class FileMetadata():
    """Метаданные изображения или видеофайла.

    Содержит только поля, поддерживаемые FileNameTemplate."""

    __EXIF_DT_TAGS = ['Exif.Image.OriginalDateTime', 'Exif.Image.DateTime']
    __EXIF_MODEL = 'Exif.Image.Model'

    __N_FIELDS = 10

    FILETYPE, MODEL, PREFIX, NUMBER, \
    YEAR, MONTH, DAY, HOUR, MINUTE, SECOND = range(__N_FIELDS)

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
        fileSize    - размер файла в байтах
        timestamp   - экземпляр datetime.datetime со значениями из EXIF
                      (если таковые нашлись) или mtime файла

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

        self.timestamp = None

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
                        self.timestamp = datetime.datetime.strptime(dts, u'%Y:%m:%d %H:%M:%S')
                    except Exception as ex:
                        print('* Warning!', str(ex))
                        self.timestamp = None
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
        fstatr = os.stat(filename)

        # размер файла в байтах
        self.fileSize = fstatr.st_size

        #
        # доковыриваем дату
        #
        if self.timestamp:
            # вахЪ! дата нашлась в EXIF!
            if self.timestamp.year < 1800 or self.timestamp.month <1 or self.timestamp.month > 12 or self.timestamp.day <1 or self.timestamp.day > 31:
                # но содержит какую-то херню
                self.timestamp = None

        # фигвам. берём в качестве даты создания mtime файла
        if self.timestamp is None:
            self.timestamp = datetime.datetime.fromtimestamp(fstatr.st_mtime)

        self.fields[self.YEAR]      = '%.4d' % self.timestamp.year
        self.fields[self.MONTH]     = '%.2d' % self.timestamp.month
        self.fields[self.DAY]       = '%.2d' % self.timestamp.day
        self.fields[self.HOUR]      = '%.2d' % self.timestamp.hour
        self.fields[self.MINUTE]    = '%.2d' % self.timestamp.minute
        self.fields[self.SECOND]    = '%.2d' % self.timestamp.second

    __FLD_NAMES = ('FILETYPE', 'MODEL', 'PREFIX', 'NUMBER',
        'YEAR', 'MONTH', 'DAY', 'HOUR', 'MINUTE', 'SECOND')

    def __repr__(self):
        """Для отладки"""

        r = ['fileName="%s"' % self.fileName,
             'fileExt="%s"' % self.fileExt,
             'fileSize=%d' % self.fileSize]

        r += (map(lambda f: '%s="%s"' % (self.__FLD_NAMES[f[0]], f[1]), enumerate(self.fields)))
        return '%s(%s)' % (self.__class__.__name__, '\n'.join(r))


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    #from pmvgcommon import *

    SOURCE_DIR = os.path.expanduser('~/downloads/src')

    try:
        ftypes = FileTypes()

        for root, dirs, files in os.walk(SOURCE_DIR):
            if root.startswith('.'):
                continue

            for fname in files:
                if fname.startswith('.'):
                    continue

                ft = ftypes.get_file_type_by_name(fname)
                print(fname, '->', FileTypes.LONGSTR[ft] if ft is not None else '?')

                try:
                    r = FileMetadata(os.path.join(root, fname), ftypes)
                    #print(r)
                except Exception as ex:
                    print('error getting metadata from "%s" - %s' % (fname, repr(ex)))
                    #print_exception()
                    #break

    except Exception:
        print_exception()
