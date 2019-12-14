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


from gtktools import *

from gi.repository import Gtk, Gdk, GObject, Pango, GLib
from gi.repository.GdkPixbuf import Pixbuf, InterpType as GdkPixbufInterpType
from gi.repository.GLib import markup_escape_text

from pmvgcommon import *
from pmvgconfig import *
from pmvgtemplates import *
#from pmvgmetadata import FileTypes

from os.path import sep as os_path_sep


class SettingsDialog():
    TPLCOL_MASK, TPLCOL_DISPLAY, TPLCOL_TEMPLATE = range(3)

    ALCOL_MODEL, ALCOL_ALIAS = range(2)

    DDCOL_DESTDIR = 0

    def wnd_destroy(self, widget):
        Gtk.main_quit()

    def __init__(self, parent, env):
        self.env = env

        resldr = get_resource_loader()
        uibldr = get_gtk_builder(resldr, 'pmvgsettings.ui')
        #
        #
        #
        self.dlg = uibldr.get_object('dlgSettings')
        self.dlg.set_transient_for(parent)

        #
        # templates
        #
        self.templatelist = TreeViewShell(uibldr.get_object('templatesview'))
        self.templatelist.sortColumn = self.TPLCOL_MASK

        #
        # диалог редактора шаблона
        #
        self.dlgTemplate = uibldr.get_object('dlgTemplate')

        uibldr.get_object('txtTemplateMaskHelp').set_markup('''Маска шаблона может содержать символы подстановки:
"?" (любой одиночный символ) и "*" (группа любых символов).''')

        uibldr.get_object('txtTemplateHelp').set_markup('''Шаблон может содержать текст, символы разделения путей "<b>%s</b>",
а также макросы подстановки, заключённые в фигурные скобки.''' % os_path_sep)

        self.tplmaskentry, self.templateentry = get_ui_widgets(uibldr, ('tplmaskentry', 'templateentry'))

        self.templatefields = TreeViewShell(uibldr.get_object('templatefields'))

        for fparm in FileNameTemplate.FIELDS:
            self.templatefields.store.append((fparm.longname, fparm.description))

        #
        # aliases
        #
        self.aliaslist = TreeViewShell(uibldr.get_object('aliasesview'))
        self.aliaslist.sortColumn = self.ALCOL_ALIAS

        #
        # диалог редактора сокращений
        #
        self.dlgAlias = uibldr.get_object('dlgAlias')
        self.cameramodelentry, self.aliasentry = get_ui_widgets(uibldr, ('cameramodelentry', 'aliasentry'))

        #
        # destdirs
        #
        self.dlgDDirChoose = uibldr.get_object('dlgDDirChoose')
        self.destdirlist = TreeViewShell(uibldr.get_object('destdirsview'))
        self.destdirlist.sortColumn = self.DDCOL_DESTDIR

        #
        self.cbtnCloseIfSuccess = uibldr.get_object('cbtnCloseIfSuccess')

        uibldr.connect_signals(self)

    def templatefields_row_activated(self, tv, path, col):
        """Вставка названия поля шаблона, выбранного в списке templatefields,
        в поле ввода templateentry в текущей позиции курсора."""

        itr = self.templatefields.store.get_iter(path)
        tplfld = '{%s}' % self.templatefields.store.get_value(itr, self.TPLCOL_MASK)

        pos = self.templateentry.get_position()

        self.templateentry.insert_text(tplfld, pos)
        self.templateentry.set_position(pos + len(tplfld))

    def __template_edit(self, itrtpl):
        """Редактирование шаблона, указанного itr (экземпляром TreeIter).
        Если itr = None, создаётся новый шаблон.

        Возвращает True, если нажата кнопка ОК, введённые данные правильны
        и внесены в self.templatelist.store, и False, если окно редактора
        закрыто без изменений."""

        if itrtpl is None:
            ts = 'Новый шаблон'
            stplmask = ''
            stemplate = ''
        else:
            ts = 'Изменение шаблона'

            stplmask, stemplate = self.templatelist.store.get(itrtpl, self.TPLCOL_MASK, self.TPLCOL_TEMPLATE)

        self.dlgTemplate.set_title(ts)

        def __template_edit_error(msg):
            msg_dialog(self.dlgTemplate, ts, msg)

        self.tplmaskentry.set_text(stplmask)
        self.templateentry.set_text(stemplate)

        self.dlgTemplate.show()

        retc = False

        while not retc:
            r = self.dlgTemplate.run()

            if r != Gtk.ResponseType.OK:
                break

            #
            # проверяем введённые значения
            #

            # маска
            # обязательно заменяем последовательности из нескольких
            # пробельных символов одним пробелом!
            stplmask = ' '.join(self.tplmaskentry.get_text().lower().strip().split(None))

            if not stplmask:
                __template_edit_error('Маска шаблона пуста')
                continue

            if self.templates_has_same_mask(stplmask, itrtpl):
                __template_edit_error('В списке уже есть шаблон с указанной маской')
                continue

            # сам шаблон
            try:
                template = FileNameTemplate(self.templateentry.get_text())
            except FileNameTemplate.Error as ex:
                __template_edit_error(ex)
                continue

            # а теперь можно уже пихать новый или изменённый шаблон в список
            rowdata = (stplmask, template.get_display_str(), str(template))

            if itrtpl is None:
                self.templatelist.store.append(rowdata)
            else:
                self.templatelist.store.set_row(itrtpl, rowdata)

            retc = True

        self.dlgTemplate.hide()

        return retc

    def templates_has_same_mask(self, smask, itrexclude):
        """Поиск в templatelist.store шаблона по маске.

        smask       - строка маски,
        itrexclude  - экземпляр Gtk.TreeIter, соответствующая которому
                      строка store не проверяется;
                      если itrexclude is None, проверяются все строки.

        Возвращает True (при успешном поиске) или False."""

        # Gtk.TreeIter напрямую сравнить не получится - несколько экземпляров
        # Gtk.TreeIter могут указывать на один элемент Gtk.TreeModel
        pathexclude = None if itrexclude is None else self.templatelist.store.get_path(itrexclude)

        itr = self.templatelist.store.get_iter_first()

        while itr is not None:
            path = self.templatelist.store.get_path(itr)
            if (pathexclude is None or path.compare(pathexclude) != 0)\
                and self.templatelist.store.get_value(itr, self.TPLCOL_MASK) == smask:
                return True

            itr = self.templatelist.store.iter_next(itr)

        return False

    def templates_new(self, wgt):
        self.__template_edit(None)

    def templates_edit(self, wgt):
        itr = self.templatelist.get_selected_iter()
        self.__template_edit(itr)

    def templates_delete(self, wgt):
        itr = self.templatelist.get_selected_iter()

        if itr is not None:
            smask = self.templatelist.store.get_value(itr, self.TPLCOL_MASK)

            if msg_dialog(self.dlg, 'Удаление шаблона',
                'Удалить шаблон "%s"?' % smask,
                Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO) != Gtk.ResponseType.YES:
                return

            self.templatelist.store.remove(itr)

    def templatelist_row_activated(self, tv, path, col):
        self.templates_edit(tv)

    def aliaslist_row_activated(self, tv, path, col):
        self.aliases_edit(tv)

    def __alias_edit(self, itralias):
        """Редактирование или создание нового сокращения.

        Если itralias = None, создаётся новое сокращение.

        Возвращает True, если нажата кнопка ОК, введённые данные правильны
        и внесены в self.aliaslist.store, и False, если окно редактора
        закрыто без изменений."""

        if itralias is None:
            ts = 'Новое сокращение'
            smodel = ''
            salias = ''
        else:
            ts = 'Изменение сокращения'

            smodel, salias = self.aliaslist.store.get(itralias, self.ALCOL_MODEL, self.ALCOL_ALIAS)

        self.dlgAlias.set_title(ts)

        self.cameramodelentry.set_text(smodel)
        self.aliasentry.set_text(salias)

        def __alias_edit_error(msg):
            msg_dialog(self.dlgAlias, ts, msg)

        #
        self.dlgAlias.show()

        retc = False

        while not retc:
            r = self.dlgAlias.run()

            if r != Gtk.ResponseType.OK:
                break

            # модель камеры
            smodel = self.cameramodelentry.get_text().strip().lower()

            if not smodel:
                __alias_edit_error('Модель камеры не указана.')
                continue

            if self.aliases_has_same_model(smodel, itralias):
                __alias_edit_error('В списке сокращений уже есть указанная модель камеры.')
                continue

            salias = self.aliasentry.get_text().strip()

            if not salias:
                __alias_edit_error('Сокращённое название не указано.')
                continue

            # а теперь можно уже пихать новое или изменённое сокращение в список
            rowdata = (smodel, salias)

            if itralias is None:
                self.aliaslist.store.append(rowdata)
            else:
                self.aliaslist.store.set_row(itralias, rowdata)

            retc = True

        self.dlgAlias.hide()

        return retc

    def aliases_has_same_model(self, smodel, itrexclude):
        """Поиск в aliaslist.store сокращения по маске.

        smodel      - строка с названием модели камеры,
        itrexclude  - экземпляр Gtk.TreeIter, соответствующая которому
                      строка store не проверяется;
                      если itrexclude is None, проверяются все строки.

        Возвращает True (при успешном поиске) или False."""

        pathexclude = None if itrexclude is None else self.aliaslist.store.get_path(itrexclude)

        itr = self.aliaslist.store.get_iter_first()

        while itr is not None:
            path = self.aliaslist.store.get_path(itr)
            if (pathexclude is None or path.compare(pathexclude) != 0)\
                and self.aliaslist.store.get_value(itr, self.ALCOL_MODEL) == smodel:
                return True

            itr = self.aliaslist.store.iter_next(itr)

        return False

    def aliases_edit(self, wgt):
        itr = self.aliaslist.get_selected_iter()
        self.__alias_edit(itr)

    def aliases_new(self, wgt):
        self.__alias_edit(None)

    def aliases_delete(self, wgt):
        itr = self.aliaslist.get_selected_iter()

        if itr is not None:
            smodel = self.aliaslist.store.get_value(itr, self.ALCOL_MODEL)

            if msg_dialog(self.dlg, 'Удаление сокращения',
                'Удалить сокращение названия для камеры "%s"?' % smodel,
                Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO) != Gtk.ResponseType.YES:
                return

            self.aliaslist.store.remove(itr)

    def __templatelist_from_env(self):
        """Заполнение templatelist.store данными из env"""

        self.templatelist.refresh_begin()

        for tplname in self.env.templates:
            tpl = self.env.templates[tplname]
            # в store хранятся:
            # маска шаблона, строка отображения шаблона, сам шаблон в виде строки
            self.templatelist.store.append((tplname, tpl.get_display_str(), str(tpl)))

        self.templatelist.refresh_end()

    def __aliaslist_from_env(self):
        """Заполнение aliaslist.store данными из env"""

        self.aliaslist.refresh_begin()

        for alname in self.env.aliases:
            self.aliaslist.store.append((alname, self.env.aliases[alname]))

        self.aliaslist.refresh_end()

    def __templatelist_to_env(self):
        """Заменяет env.templates данными из templatelist.store."""

        self.env.templates.clear()

        itr = self.templatelist.store.get_iter_first()

        while itr is not None:
            smask, stemplate = self.templatelist.store.get(itr, self.TPLCOL_MASK, self.TPLCOL_TEMPLATE)

            # если конструктор FileNameTemplate рухнет здесь -
            # у нас как минимум осыпалось ОЗУ, потому что
            # правильность шаблона уже была проверена в редакторе
            self.env.templates[smask] = FileNameTemplate(stemplate)

            itr = self.templatelist.store.iter_next(itr)

    def __aliaslist_to_env(self):
        """Заменяет env.aliases данными из aliaslist.store."""

        self.env.aliases.clear()

        itr = self.aliaslist.store.get_iter_first()

        while itr is not None:
            scamera, salias = self.aliaslist.store.get(itr, self.ALCOL_MODEL, self.ALCOL_ALIAS)

            self.env.aliases[scamera] = salias

            itr = self.aliaslist.store.iter_next(itr)

    def __destdirlist_from_env(self):
        """Заполнение destdirlist.store данными из env"""

        self.destdirlist.refresh_begin()

        for destdir in self.env.destinationDirs:
            self.destdirlist.store.append((destdir, ))

        self.destdirlist.refresh_end()

    def __destdirlist_to_env(self):
        """Заменяет env.destinationDirs данными из destdirlist.store."""

        self.env.destinationDirs.clear()

        itr = self.destdirlist.store.get_iter_first()

        while itr is not None:
            self.env.destinationDirs.add(self.destdirlist.store.get_value(itr, self.DDCOL_DESTDIR))

            itr = self.destdirlist.store.iter_next(itr)

    def destdir_add(self, btn):
        self.dlgDDirChoose.show()
        r = self.dlgDDirChoose.run()
        self.dlgDDirChoose.hide()

        if r != Gtk.ResponseType.OK:
            return

        destdir = path_validate(self.dlgDDirChoose.get_current_folder())
        if not destdir:
            return

        itr = self.destdirlist.store.get_iter_first()

        while itr is not None:
            ddrec = self.destdirlist.store.get_value(itr, self.DDCOL_DESTDIR)

            # НЕ same_dir(), т.к. в списке каталогов назначения
            # не допускаются только полностью совпадающие пути
            if os.path.samefile(ddrec, destdir):
                msg_dialog(self.dlg, 'Добавление каталога назначения',
                    'Каталог "%s" уже есть в списке.' % destdir,
                    Gtk.MessageType.WARNING)
                return

            itr = self.destdirlist.store.iter_next(itr)

        self.destdirlist.store.append((destdir, ))

    def destdir_remove(self, btn):
        itr = self.destdirlist.get_selected_iter()

        if itr is not None:
            destdir = self.destdirlist.store.get_value(itr, self.DDCOL_DESTDIR)

            if msg_dialog(self.dlg, 'Удаление каталога назначения',
                'Удалить каталог "%s" из списка?' % destdir,
                Gtk.MessageType.QUESTION, Gtk.ButtonsType.YES_NO) != Gtk.ResponseType.YES:
                return

            self.destdirlist.store.remove(itr)

    def run(self):
        """Запускает диалог настроек.
        Возвращает True, если в настройки внесены изменения,
        иначе возвращает False."""

        # заполнение виджетов данными
        self.__templatelist_from_env()
        self.__aliaslist_from_env()
        self.__destdirlist_from_env()

        self.cbtnCloseIfSuccess.set_active(self.env.closeIfSuccess)

        #
        self.dlg.show()
        r = self.dlg.run()
        self.dlg.hide()

        r = r == Gtk.ResponseType.OK
        if r:
            # получение данных из виджетов
            self.__templatelist_to_env()
            self.__aliaslist_to_env()
            self.__destdirlist_to_env()
            self.env.closeIfSuccess = self.cbtnCloseIfSuccess.get_active()
            #!!!
            self.env.save()

        return r


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    env = Environment(sys.argv)
    if env.error:
        raise Environment.Error(env.error)

    dlg = SettingsDialog(None, env)
    if dlg.run():
        print(env)

    print
