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
import datetime


from pmvgcommon import *
#from pmvgtemplates import *
#from pmvgmetadata import FileMetadata, FileTypes


ENCODING = getdefaultlocale()[1]
if not ENCODING:
    ENCODING = sys.getfilesystemencoding()


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
    OPT_IF_EXISTS = 'if-exists'
    OPT_CLOSE_IF_SUCCESS = 'close-if-success'

    SEC_SRC_DIRS = 'src-dirs'

    #FileMetadata.FILE_TYPE_IMAGE, FILE_TYPE_RAW_IMAGE, FILE_TYPE_VIDEO
    OPT_KNOWN_FILE_TYPES = ('known-image-types',
        'known-raw-image-types',
        'known-video-types')

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

    DEFAULT_MAX_LOG_SIZE = 10 # максимальный размер файла журнала в мегабайтах

    def setup_work_mode(self):
        """Вызывать после изменения workModeMove (напр. из GUI)"""

        if self.modeMoveFiles:
            self.modeMessages = workmodemsgs('переместить', 'перемещено')
            self.modeFileOp = shutil.move
        else:
            self.modeMessages = workmodemsgs('скопировать', 'скопировано')
            self.modeFileOp = shutil.copy

    def __init__(self, args):
        """Разбор командной строки, поиск и загрузка файла конфигурации.

        args            - аргументы командной строки (список строк),
                          например, значение sys.argv

        В первую очередь пытается определить режим работы
        (перемещение/копирование), и режим интерфейса (консоль/графика).

        В случае успеха self.error устанавливается в None.
        В случае ошибок присваивает self.error строку с сообщением об ошибке."""

        #
        # параметры
        #
        self.modeMoveFiles = None
        self.GUImode = False

        self.modeMessages = None
        self.modeFileOp = None

        # каталоги, из которых копируются (или перемещаются) изображения
        # список экземпляров Environment.SourceDir
        self.sourceDirs = []

        # каталог, в который копируются (или перемещаются) изображения
        self.destinationDir = None

        # поддерживаемые типы файлов (по расширениям)
        self.knownFileTypes = FileTypes()

        # что делать с файлами, которые уже есть в каталоге-приемнике
        self.ifFileExists = self.FEXIST_RENAME

        # показывать ли каталоги-источники
        self.showSrcDir = False

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

        # максимальный размер файла журнала в мегабайтах
        self.maxLogSizeMB = self.DEFAULT_MAX_LOG_SIZE

        #
        # см. далее except!
        #
        self.error = None

        try:
            # определение режима работы - делаем в самом начале,
            # т.к. нужно сразу знать, как именно показывать сообщения
            # об ошибках
            # __detect_work_mode() по возможности НЕ должно генерировать
            # исключений!
            self.__detect_work_mode(args)
            self.setup_work_mode()

            #
            # ищем файл конфигурации
            #
            self.configPath = self.__get_config_path(args[0])
            self.cfg = PMVRawConfigParser()

            with open(self.configPath, 'r', encoding=ENCODING) as f:
                try:
                    self.cfg.read_file(f)
                except ConfigParserError as ex:
                    raise self.Error(self.E_CONFIG % str(ex))

            # прочие исключения пока исключения не проверяем.
            # в документации об обработке ошибок чтения что-то мутно

            #
            # выгребаем настройки
            #

            if self.cfg.has_section(self.SEC_PATHS):
                self.__read_config_paths()
            else:
                raise self.Error(self.E_NOSECTION % (self.configPath, self.SEC_PATHS))

            if self.cfg.has_section(self.SEC_OPTIONS):
                self.__read_config_options()
            else:
                raise self.Error(self.E_NOSECTION % (self.configPath, self.SEC_OPTIONS))

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

            #
            # журналирование операций
            #

            self.logger = PMVLogger(self.__get_log_directory(), self.maxLogSizeMB)

            #
            # ...а вот теперь - разгребаем командную строку, т.к. ее параметры
            # перекрывают файл настроек
            #

            self.__parse_cmdline_options(args)

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

    CMDOPT_GUI = {'-g', '--gui'}
    CMDOPT_NOGUI = {'-n', '--no-gui'}
    CMDOPT_COPY = {'-c', '--copy'}
    CMDOPT_MOVE = {'-m', '--move'}
    CMDOPTS_WORKMODE = CMDOPT_COPY | CMDOPT_MOVE | CMDOPT_GUI | CMDOPT_NOGUI
    __CMDOPT_IF_EXISTS_SHORT = '-e'
    CMDOPT_IF_EXISTS = {__CMDOPT_IF_EXISTS_SHORT, '--if-exists'}

    def __detect_work_mode(self, args):
        """Определение режима работы (перемещение/копирование,
        консольный/графический) по имени исполняемого файла и/или
        по ключам командной строки."""

        #
        # определяем, кто мы такое
        #
        bname = os.path.basename(args[0])

        # имя того, что запущено, в т.ч. если вся куча засунута
        # в архив ZIP

        bnamecmd = os.path.splitext(bname)[0].lower()

        if bnamecmd in (Environment.MODE_MOVE, Environment.MODE_MOVE_GUI):
            self.modeMoveFiles = True
        elif bnamecmd in (Environment.MODE_COPY, Environment.MODE_COPY_GUI):
            self.modeMoveFiles = False
        else:
            # ругаться будем потом, если режим не указан в командной строке
            self.modeMoveFiles = None

        self.GUImode = bnamecmd in (Environment.MODE_MOVE_GUI, Environment.MODE_COPY_GUI)
        # а в непонятных случаях будем считать, что режим морды - консольный

        # предварительный и ограниченный разбор параметров командной строки
        # нужен для определения gui/nogui ДО создания экземпляра Environment,
        # чтобы знать, как отображать потом сообщения об ошибках
        # копирование/перемещение определяем тут же, раз уж именно здесь
        # определяли его по имени исполняемого файла
        for arg in args[1:]:
            if arg.startswith('-'):
                if arg in self.CMDOPT_GUI:
                    self.GUImode = True
                elif arg in self.CMDOPT_NOGUI:
                    self.GUImode = False
                elif arg in self.CMDOPT_MOVE:
                    self.modeMoveFiles = True
                elif arg in self.CMDOPT_COPY:
                    self.modeMoveFiles = False
                # на неизвестные опции ругаемся не здесь, а в __parse_cmdline_options()

        if self.modeMoveFiles is None:
            raise Environment.Error('Меня зовут %s, и я не знаю, что делать.' % bname)

    def __parse_cmdline_options(self, args):
        """Разбор аргументов командной строки"""

        carg = None

        for argnum, arg in enumerate(args[1:], 1):
            if carg:
                if carg in self.CMDOPT_IF_EXISTS:
                    if arg in self.FEXIST_OPTIONS:
                        self.ifFileExists = self.FEXIST_OPTIONS[arg]
                    else:
                        raise self.Error(self.E_CMDLINE % (argnum, 'недопустимое значение параметра "%s"' % carg))
                carg = None
            elif arg.startswith('-'):
                if arg in self.CMDOPTS_WORKMODE:
                    # режим междумордия и работы с файлами был определён ранее, вызовом __detect_work_mode()
                    pass
                elif arg in self.CMDOPT_IF_EXISTS:
                    carg = self.__CMDOPT_IF_EXISTS_SHORT
                else:
                    raise self.Error(self.E_CMDLINE % (argnum, 'параметр "%s" не поддерживается' % arg))
            else:
                raise self.Error(self.E_CMDLINE % (argnum, 'ненужное имя файла'))

        if carg:
            raise self.Error(self.E_CMDLINE % (argnum, 'не указано значение параметра "%s"' % carg))

    def __read_config_paths(self):
        """Разбор секции paths файла настроек"""

        #
        # каталоги с исходными файлами
        #

        rawSrcDirs = map(lambda s: s.strip(), self.cfg.getstr(self.SEC_PATHS, self.OPT_SRC_DIRS).split(':'))

        for ixsd, srcdir in enumerate(rawSrcDirs, 1):
            if srcdir:
                # пустые строки пропускаем - опухнешь на каждую мелочь ругаться

                if srcdir.startswith('-'):
                    srcdirignore = True
                    srcdir = srcdir[1:]
                else:
                    srcdirignore = False

                srcdir = validate_path(srcdir)

                # путь добавляем во внутренний список, если он не совпадает
                # с каким-то из уже добавленных;
                # существование каталога будет проверено при обработке файлов

                if self.same_src_dir(srcdir):
                    raise self.Error(self.E_BADVAL % (self.OPT_SRC_DIRS, self.SEC_PATHS, self.configPath,
                        'путь %d (%s) совпадает с одним из уже указанных' % (ixsd, srcdir)))

                self.sourceDirs.append(self.SourceDir(srcdir, srcdirignore))

        if not self.sourceDirs:
            raise self.Error(self.E_BADVAL % (self.OPT_SRC_DIRS, self.SEC_PATHS, self.configPath, 'не указано ни одного существующего исходного каталога'))

        #
        # каталог назначения
        #

        self.destinationDir = self.cfg.getstr(self.SEC_PATHS, self.OPT_DEST_DIR)

        # здесь теперь наличие каталога проверять не будем - оно будет проверяться при запуске
        # файловых операций

        #if not self.destinationDir:
        #    raise self.Error(self.E_NOVAL % (self.OPT_DEST_DIR, self.SEC_PATHS, self.configPath))

        self.destinationDir = validate_path(self.destinationDir)

        #if not os.path.exists(self.destinationDir):
        #    raise self.Error(self.E_BADVAL % (self.OPT_DEST_DIR, self.SEC_PATHS, self.configPath,
        #        'путь "%s" не существует' % self.destinationDir))

        if os.path.exists(self.destinationDir):
            # если он есть - можно кой-каких проверок таки провернуть
            if not os.path.isdir(self.destinationDir):
                raise self.Error(self.E_BADVAL % (self.OPT_DEST_DIR, self.SEC_PATHS, self.configPath,
                    'путь "%s" указывает не на каталог' % self.destinationDir))

            # а это проверять ща не будем
            #if self.check_dest_is_same_with_src_dir():
            #    raise self.Error(self.E_BADVAL % (self.OPT_DEST_DIR, self.SEC_PATHS, self.configPath,
            #        'каталог назначения совпадает с одним из исходных каталогов'))

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
        # show-src-dir
        #
        self.showSrcDir = self.cfg.getboolean(self.SEC_OPTIONS, self.OPT_SHOW_SRC_DIR, fallback=False)

        #
        # close-if-success
        #
        self.closeIfSuccess = self.cfg.getboolean(self.SEC_OPTIONS, self.OPT_CLOSE_IF_SUCCESS, fallback=True)

        #
        # known-*-types
        #
        for ixopt, optname in enumerate(self.OPT_KNOWN_FILE_TYPES):
            kts = filter(None, self.cfg.getstr(self.SEC_OPTIONS, optname).lower().split(None))

            exts = set()

            for ktype in kts:
                if not ktype.startswith('.'):
                    ktype = '.%s' % ktype

                exts.add(ktype)

            self.knownFileTypes.add_extensions(ixopt, exts)

        #
        # max-log-size
        #
        mls = self.cfg.getint(self.SEC_OPTIONS, self.OPT_MAX_LOG_SIZE, fallback=self.DEFAULT_MAX_LOG_SIZE)
        if mls < 0:
            mls = self.DEFAULT_MAX_LOG_SIZE

        self.maxLogSizeMB = mls

    def __read_config_aliases(self):
        """Разбор секции aliases файла настроек"""

        anames = self.cfg.options(self.SEC_ALIASES)

        for aname in anames:
            astr = self.cfg.getstr(self.SEC_ALIASES, aname)

            if not astr:
                raise self.Error(self.E_NOVAL % (aname, self.SEC_ALIASES, self.configPath))

            # проверку на повтор не делаем - RawConfigParser ругнётся раньше на одинаковые опции
            self.aliases[aname.lower()] = normalize_filename(astr)

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

        При отсутствии - создание файла со значениями по умолчанию
        и завершение работы."""

        cfgpath = os.path.join(os.path.split(me)[0], self.CFG_FILE)

        if not os.path.exists(cfgpath):
            cfgdir = os.path.expanduser('~/.config/photomv')
            cfgpath = os.path.join(cfgdir, self.CFG_FILE)

            if not os.path.exists(cfgpath):
                # создаём файл настроек

                make_dirs(cfgdir, self.Error)

                try:
                    with open(cfgpath, 'w+', encoding=ENCODING) as f:
                        f.write(DEFAULT_CONFIG)
                except OSError as ex:
                    raise self.Error('Не удалось создать новый файл настроек "%s" - %s' % (cfgpath, repr(ex)))

                raise self.Error('Файл настроек не найден, создан новый файл "%s".\nДля продолжения работы файл настроек должен быть отредактирован.' % cfgpath)

        return cfgpath

    def save(self):
        """Сохранение настроек.
        В случае ошибки генерирует исключение."""

        # секция paths
        self.cfg.set(self.SEC_PATHS, self.OPT_SRC_DIRS, ':'.join(map(lambda sd: '%s%s' % ('-' if sd.ignore else '', sd.path), self.sourceDirs)))
        self.cfg.set(self.SEC_PATHS, self.OPT_DEST_DIR, self.destinationDir)

        # секция options
        self.cfg.set(self.SEC_OPTIONS, self.OPT_IF_EXISTS, self.FEXISTS_OPTIONS_STR[self.ifFileExists])
        self.cfg.set(self.SEC_OPTIONS, self.OPT_SHOW_SRC_DIR, str(self.showSrcDir))
        self.cfg.set(self.SEC_OPTIONS, self.OPT_CLOSE_IF_SUCCESS, str(self.closeIfSuccess))

        # секции aliases и templates не трогаем, т.к. они из гуя не изменяются

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

    def __repr__(self):
        """Для отладки"""
        return '''cfg = %s
modeMoveFiles = %s
GUImode = %s
modeMessages = %s
modeFileOp = %s
sourceDirs = %s
destinationDir = "%s"
ifFileExists = %s
knownFileTypes:%s
showSrcDir = %s
aliases = %s
templates = %s
maxLogSizeMB = %d,
logger = "%s"''' % (self.cfg,
    self.modeMoveFiles,
    self.GUImode,
    self.modeMessages,
    self.modeFileOp,
    str(self.sourceDirs),
    self.destinationDir,
    self.FEXISTS_OPTIONS_STR[self.ifFileExists],
    self.knownFileTypes,
    self.showSrcDir,
    self.aliases,
    ', '.join(map(str, self.templates.values())),
    self.maxLogSizeMB,
    self.logger)


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    try:
        sys.argv[0] = 'photocpg.py'
        print(sys.argv)
        env = Environment(sys.argv)
        if env.error:
            raise Exception(env.error)
        #env.save()

    except Environment.Error as ex:
        print('** %s' % str(ex))
        exit(1)

    print(env)
    #tpl = env.get_template('')
    #print('template:', tpl, repr(tpl))

    #env.save()

    print(env.knownFileTypes.get_file_type_by_name('filename.m4v'))

    env.logger.open()
    try:
        env.logger.write(None, env.logger.KW_CP, True, 'oldfile', 'newfile')
        env.logger.write(None, env.logger.KW_MSG, True, 'some\nmessage', '')
        env.logger.write(None, env.logger.KW_MSG, True, 'some other message', '')
    finally:
        env.logger.close()
