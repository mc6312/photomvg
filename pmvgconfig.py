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


import os, os.path
import sys
from locale import getdefaultlocale
from configparser import RawConfigParser, Error as ConfigParserError
from collections import namedtuple
import shutil
import subprocess
import datetime


from pmvgcommon import *
from pmvgtemplates import *
from pmvgmetadata import FileMetadata, FileTypes


ENCODING = getdefaultlocale()[1]
if not ENCODING:
    ENCODING = sys.getfilesystemencoding()


#
# шматок кроссплатформенности на всякий случай
#

def __get_os_parameters():
    """Возвращает кортеж из двух элементов:
    1й: полный путь к каталогу настроек, включая имя подкаталога PhotoMVG,
    2й: ОС-специфичная команда открытия файлового менеджера."""

    cfgDirPrefix = ''

    if sys.platform == 'linux':
        # подразумевается, что моё поделие запускается из-под дистрибутива
        # Linux, соблюдающего XDG
        # ошмётки поддержки всего прочего - лишь бы хоть как-то работало

        try:
            from xdg.BaseDirectory import xdg_config_home
            cfgDir = xdg_config_home
        except ImportError:
            cfgDir = os.path.expanduser('~/.config')

        # тут наличие модулей XDG уже не проверяем, всё на совести дистроклепателей
        shellCmd = 'xdg-open'

    elif sys.platform == 'win32':
        shellCmd = 'start'

        # XPюндель про LOCALAPPDATA не знает!
        ES_LAD = 'LOCALAPPDATA'
        cfgDir = os.environ[ES_LAD] if ES_LAD in os.environ else os.environ['APPDATA']

    elif sys.platform == 'darwin':
        shellCmd = 'open'

        # плевал я на однокнопочные стандарты
        cfgDir = os.path.expanduser('~/.config')
        cfgDirPefix = '.'

    else:
        # не сработает - не мои проблемы
        shellCmd = None

        cfgDir = os.path.expanduser('~/')
        cfgDirPefix = '.'

    cfgDir = os.path.abspath(os.path.join(cfgDir, '%sphotomvg' % cfgDirPrefix))

    return (cfgDir, shellCmd)


__cfg_dir, __shell_cmd = __get_os_parameters()


def shell_open(fpath):
    """Пытается открыть файл или каталог fpath в файловом менеджере"""

    subprocess.Popen([__shell_cmd, fpath])


class PMVRawConfigParser(RawConfigParser):
    def getstr(self, secname, varname):
        """В отличие от RawConfigParser.get возвращает пустую строку
        при отсутствии переменной varname в секции secname."""

        if self.has_option(secname, varname):
            return self.get(secname, varname).strip()
        else:
            return ''


class Environment():
    """Все настройки"""

    CFG_FILE = 'settings.ini'

    class Error(Exception):
        pass

    class SourceDir():
        __slots__ = 'path', 'use'

        def __init__(self, path, use):
            self.path = path
            self.use = use

        def __repr__(self):
            return '%s(path="%s", use=%s)' % (self.__class__.__name__,
                self.path, self.use)

    FEXIST_SKIP, FEXIST_RENAME, FEXIST_OVERWRITE = range(3)
    FEXISTS_OPTIONS_STR = ('skip', 'rename', 'overwrite')

    FEXIST_OPTIONS = {'skip':FEXIST_SKIP,
                      's':FEXIST_SKIP,
                      'rename':FEXIST_RENAME,
                      'r':FEXIST_RENAME,
                      'overwrite':FEXIST_OVERWRITE,
                      'o':FEXIST_OVERWRITE}

    SEC_OPTIONS = 'options'
    OPT_DEST_DIR = 'dest-dir'
    OPT_MOVE_FILES = 'move-files'
    OPT_IF_EXISTS = 'if-exists'
    OPT_CLOSE_IF_SUCCESS = 'close-if-success'

    SEC_SRC_DIRS = 'src-dirs'

    # FileTypes.IMAGE, RAW_IMAGE, VIDEO
    # а FileTypes.DIRECTORY здесь НЕ используется!
    OPT_KNOWN_FILE_TYPES = {FileTypes.IMAGE:'known-image-types',
        FileTypes.RAW_IMAGE:'known-raw-image-types',
        FileTypes.VIDEO:'known-video-types'}

    SEC_TEMPLATES = 'templates'
    DEFAULT_TEMPLATE_NAME = '*'

    SEC_ALIASES = 'aliases'

    E_BADVAL = 'Неправильное значение параметра "%s" в секции "%s" файла настроек "%s" - %s'
    E_BADVAL2 = 'Неправильное значение параметра "%s" в секции "%s" файла настроек "%s"'
    E_DUPVAL = 'Имя параметра "%s" использовано более одного раза в секции "%s" файла настроек "%s"'
    E_NOVAL = 'Отсутствует значение параметра "%s" в секции "%s" файла настроек "%s"'
    E_NOSECTION = 'В файле настроек "%s" отсутствует секция "%s"'
    E_CONFIG = 'Ошибка обработки файла настроек - %s'
    E_CMDLINE = 'параметр %d командной строки: %s'

    def __init__(self, args):
        """Поиск и загрузка файла конфигурации.

        args            - аргументы командной строки (список строк),
                          например, значение sys.argv;
                          !!!оставлено на будущее, в текущей версии не используется

        В случае успеха self.error устанавливается в None.
        В случае ошибок присваивает self.error строку с сообщением об ошибке."""

        #
        # параметры
        #

        # режим работы - копирование или перемещение файлов
        self.modeMoveFiles = False

        # каталоги, из которых копируются (или перемещаются) изображения
        # список экземпляров Environment.SourceDir
        self.sourceDirs = []

        # каталог, в который копируются (или перемещаются) изображения
        self.destinationDir = None

        # поддерживаемые типы файлов (по расширениям)
        self.knownFileTypes = FileTypes()

        # что делать с файлами, которые уже есть в каталоге-приемнике
        self.ifFileExists = self.FEXIST_RENAME

        # закрывать ли программу в случае успешного завершения (копирования)
        self.closeIfSuccess = True

        # сокращенные псевдонимы камер
        # ключи словаря - названия камер, соответствующие соотв. полю EXIF
        # значения - строки псевдонимов
        self.aliases = {}

        # индивидуальные шаблоны
        # общий шаблон по умолчанию также будет воткнут сюда при
        # вызове __read_config_templates()
        # ключи словаря - названия камер из EXIF, или "*" для общего
        # шаблона;
        # значения словаря - экземпляры класса FileNameTemplate
        self.templates = {}

        #
        # см. далее except!
        #
        self.error = None

        try:
            #
            # ищем файл конфигурации
            #
            self.configPath = self.__get_config_path(args[0])
            self.cfg = PMVRawConfigParser()

            # при отсутствии файла конфигурации - оставляем значения по умолчанию
            if os.path.exists(self.configPath):
                with open(self.configPath, 'r', encoding=ENCODING) as f:
                    try:
                        self.cfg.read_file(f)
                    except ConfigParserError as ex:
                        raise self.Error(self.E_CONFIG % str(ex))

                # прочие исключения пока исключения не проверяем.
                # в документации configparser об обработке ошибок чтения что-то мутно

                #
                # выгребаем настройки
                #
                if self.cfg.has_section(self.SEC_OPTIONS):
                    self.__read_config_options()

                #
                # каталоги-источники
                #
                if self.cfg.has_section(self.SEC_SRC_DIRS):
                    self.__read_config_srcdirs()

                #
                # сокращённые имена камер
                #

                if self.cfg.has_section(self.SEC_ALIASES):
                    self.__read_config_aliases()

                #
                # шаблоны
                #

                if self.cfg.has_section(self.SEC_TEMPLATES):
                    self.__read_config_templates()

        except self.Error as ex:
            # конструктор НЕ ДОЛЖЕН падать от self.Error - оно будет
            # обработано снаружи по содержимому self.error
            # с прочими исключениями - падаем, ибо это предположительно
            # что-то более серьёзное
            # на этом этапе поля self.modeMoveFiles,
            # self.GUImode уже установлены в известные значения
            # и сообщение об ошибке где-то снаружи должно быть показано
            # в правильном режиме
            self.error = str(ex)

    def __read_config_srcdirs(self):
        """Разбор секции src-dirs файла настроек"""

        #
        # каталоги с исходными файлами
        #

        for _vname, vvalue in self.cfg.items(self.SEC_SRC_DIRS):
            suse, ssep, srcdir = map(lambda s: s.strip(), vvalue.partition(','))
            if not suse or ssep != ',' or not srcdir:
                raise self.Error(self.E_BADVAL2 % (_vname, self.SEC_SRC_DIRS, self.configPath))

            srcdiruse = suse.lower() in ('true', 'yes', '1') # вот какого фига нет готовой функции?

            srcdir = path_validate(srcdir)

            # путь добавляем во внутренний список, если он не совпадает
            # с каким-то из уже добавленных;
            # реальное существование каталога будет проверено при обработке файлов

            if self.same_src_dir(srcdir):
                raise self.Error(self.E_BADVAL % (_vname, self.SEC_SRC_DIRS, self.configPath,
                    'путь "%s" совпадает с одним из уже указанных' % srcdir))

            self.sourceDirs.append(self.SourceDir(srcdir, srcdiruse))

        # на пустой список self.sourceDirs лаяться не будем - их можно потом добавить из GUI

    def check_dest_is_same_with_src_dir(self):
        """Проверка, не является ли каталог назначения одним из каталогов-
        источников.

        Возвращает True, если случилась такая досада..."""
        return self.same_src_dir(self.destinationDir)

    def same_src_dir(self, dirname):
        """Возвращает True, если каталог dirname совпадает с одним из
        каталогов списка self.sourceDirs."""

        for sd in self.sourceDirs:
            if same_dir(sd.path, dirname):
                return True

        return False

    def __read_config_options(self):
        """Разбор секции options файла настроек"""

        self.modeMoveFiles = self.cfg.getboolean(self.SEC_OPTIONS, self.OPT_MOVE_FILES, fallback=False)

        #
        # каталог назначения
        #

        self.destinationDir = path_validate(self.cfg.getstr(self.SEC_OPTIONS, self.OPT_DEST_DIR))

        # здесь на отсутствие каталога гавкать не будем - оно будет проверяться при запуске
        # файловых операций

        if os.path.exists(self.destinationDir):
            # ...но если он есть - можно кой-каких проверок таки провернуть
            if not os.path.isdir(self.destinationDir):
                raise self.Error(self.E_BADVAL % (self.OPT_DEST_DIR, self.SEC_OPTIONS, self.configPath,
                    'путь "%s" указывает не на каталог' % self.destinationDir))

            # а это проверять ща не будем
            #if self.check_dest_is_same_with_src_dir():
            #    raise self.Error(self.E_BADVAL % (self.OPT_DEST_DIR, self.SEC_PATHS, self.configPath,
            #        'каталог назначения совпадает с одним из исходных каталогов'))

        #
        # if-exists
        #
        ieopt = self.cfg.getstr(self.SEC_OPTIONS, self.OPT_IF_EXISTS).lower()
        if not ieopt:
            raise self.Error(self.E_NOVAL % (self.OPT_IF_EXISTS, self.SEC_OPTIONS, self.configPath))

        if ieopt not in self.FEXIST_OPTIONS:
            raise self.Error(self.E_BADVAL2 % (self.OPT_IF_EXISTS, self.SEC_OPTIONS, self.configPath))

        self.ifFileExists = self.FEXIST_OPTIONS[ieopt]

        #
        # close-if-success
        #
        self.closeIfSuccess = self.cfg.getboolean(self.SEC_OPTIONS, self.OPT_CLOSE_IF_SUCCESS, fallback=True)

        #
        # known-*-types
        #
        for ftype in self.OPT_KNOWN_FILE_TYPES:
            optname = self.OPT_KNOWN_FILE_TYPES[ftype]

            kts = filter(None, self.cfg.getstr(self.SEC_OPTIONS, optname).lower().split(None))

            exts = set()

            for ktype in kts:
                if not ktype.startswith('.'):
                    ktype = '.%s' % ktype

                exts.add(ktype)

            self.knownFileTypes.add_extensions(ftype, exts)

    def __read_config_aliases(self):
        """Разбор секции aliases файла настроек"""

        anames = self.cfg.options(self.SEC_ALIASES)

        for aname in anames:
            astr = self.cfg.getstr(self.SEC_ALIASES, aname)

            if not astr:
                raise self.Error(self.E_NOVAL % (aname, self.SEC_ALIASES, self.configPath))

            # проверку на повтор не делаем - RawConfigParser ругнётся раньше на одинаковые опции
            self.aliases[aname.lower()] = filename_validate(astr, None)

    def __read_config_templates(self):
        """Разбор секции templates файла настроек"""

        tnames = self.cfg.options(self.SEC_TEMPLATES)

        for tname in tnames:
            tstr = self.cfg.getstr(self.SEC_TEMPLATES, tname)

            if not tstr:
                raise self.Error(self.E_NOVAL % (tname, self.SEC_TEMPLATES, self.configPath))

            tplname = tname.lower()

            # проверку на повтор не делаем - RawConfigParser ругнётся раньше на одинаковые опции
            try:
                self.templates[tplname] = FileNameTemplate(tstr)
            except Exception as ex:
                raise self.Error(self.E_BADVAL % (tname, self.SEC_TEMPLATES, self.configPath, repr(ex)))

        # если в файле настроек не был указан общий шаблон с именем "*",
        # то добавляем в templates встроенный шаблон pmvtemplates.defaultFileNameTemplate
        # под именем "*"

        if self.DEFAULT_TEMPLATE_NAME not in self.templates:
            self.templates[self.DEFAULT_TEMPLATE_NAME] = defaultFileNameTemplate

    def __get_log_directory(self):
        """Возвращает полный путь к каталогу файлов журналов операций.
        При отсутствии каталога - создаёт его."""

        logdir = os.path.expanduser('~/.cache/photomv')
        if not os.path.exists(logdir):
            make_dirs(logdir, self.Error)

        return logdir

    def __get_config_path(self, me):
        """Поиск файла конфигурации.

        При необходимости - создание каталога, где будет храниться
        файл конфигурации.
        Отсутствие файла ошибкой не считается, в этом случае используются
        значения по умолчанию."""

        # сначала ищем файл в том же каталоге, что и сама программа
        cfgpath = os.path.join(os.path.split(me)[0], self.CFG_FILE)

        if not os.path.exists(cfgpath):
            # если нету - лезем в ОС-специфический каталог (см. __get_os_parameters)

            cfgdir = __cfg_dir
            if not os.path.exists(cfgdir):
                make_dirs(cfgdir, self.Error)

            cfgpath = os.path.join(cfgdir, self.CFG_FILE)
            # ...а проверку на существование файла будем делать уже при попытке загрузки...

        return cfgpath

    def save(self):
        """Сохранение настроек.
        В случае ошибки генерирует исключение."""

        # секция paths
        for ixsd, (srcdir, sduse) in enumerate(self.sourceDirs, 1):
            self.cfg.set(self.SEC_SRC_DIRS, str(ixsd), '%s, %s' % (sduse, srcdir))

        # секция options
        self.cfg.set(self.SEC_OPTIONS, self.OPT_DEST_DIR, self.destinationDir)
        self.cfg.set(self.SEC_OPTIONS, self.OPT_IF_EXISTS, self.FEXISTS_OPTIONS_STR[self.ifFileExists])
        self.cfg.set(self.SEC_OPTIONS, self.OPT_CLOSE_IF_SUCCESS, str(self.closeIfSuccess))

        # секции aliases и templates ПОКА не трогаем, т.к. для их настроек ещё гуЯ нету
        print('%s.save(): aliases/templates saving not yet implemented!' % self.__class__.__name__, file=sys.stderr)

        # сохраняем
        with open(self.configPath, 'w+', encoding=ENCODING) as f:
            self.cfg.write(f)

    def get_template(self, cameraModel):
        """Получение экземпляра pmvtemplates.FileNameTemplate для
        определённой камеры.

        cameraModel - название модели из метаданных файла
                      (pmvmetadata.FileMetadata.fields[pmvmetadata.MODEL]),
                      пустая строка, или None;
                      в последних двух случаях возвращает общий шаблон
                      из файла настроек, если он указан, иначе возвращает
                      встроенный общий шаблон программы."""

        if cameraModel:
            cameraModel = cameraModel.lower()

            if cameraModel in self.templates:
                return self.templates[cameraModel]

        return self.templates[self.DEFAULT_TEMPLATE_NAME]

    def get_template_from_metadata(self, metadata):
        """Получение экземпляра pmvtemplates.FileNameTemplate для
        определённой камеры, модель которой определяется по
        соответствующему полю metadata - экземпляра FileMetadata."""

        if not metadata.fields[metadata.MODEL]:
            return self.templates[self.DEFAULT_TEMPLATE_NAME]
        else:
            return self.get_template(metadata.fields[metadata.MODEL])

    def __repr__(self):
        """Для отладки"""
        return '''%s(cfg = %s
modeMoveFiles = %s
closeIfSuccess = %s
sourceDirs = %s
destinationDir = "%s"
ifFileExists = %s
knownFileTypes:%s
aliases = %s
templates = %s)''' % (self.__class__.__name__,
    self.cfg,
    self.modeMoveFiles,
    self.closeIfSuccess,
    str(self.sourceDirs),
    self.destinationDir,
    self.FEXISTS_OPTIONS_STR[self.ifFileExists],
    self.knownFileTypes,
    self.aliases,
    self.templates)


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    try:
        env = Environment(sys.argv)
        if env.error:
            raise Environment.Error(env.error)
        #env.save()

    except Environment.Error as ex:
        print('** %s' % str(ex))
        exit(1)

    print(env.configPath)
    print(env)
    #tpl = env.get_template('')
    #print('template:', tpl, repr(tpl))

    #env.save()

    print(env.knownFileTypes.get_file_type_by_name('filename.m4v'))
