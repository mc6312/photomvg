#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""photomvg.py

  Copyright 2019 mc6312

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>."""



from gtktools import *

from gi.repository import Gtk, Gdk, GObject, Pango, GLib
from gi.repository.GdkPixbuf import Pixbuf, InterpType as GdkPixbufInterpType

import sys
import os, os.path

from pmvgcommon import *
from pmvgconfig import *
from pmvgmetadata import *
from pmvgtemplates import *


class MainWnd():
    # номера страниц в pages
    PAGE_SRCDIRS, PAGE_PROGRESS, PAGE_DESTFNAMES, PAGE_FINAL = range(4)
    PAGE_START = PAGE_SRCDIRS

    # столбцы в filetree.store
    FTCOL_INFO, FTCOL_ICON, FTCOL_FNAME, FTCOL_TOOLTIP = range(4)

    # типы элементов дерева в filetree.store
    # внимание, времянка!
    # потом будет переделано или дополнено для поддержки файла настроек
    # (которого ещё нет)
    FTYPE_DIR, FTYPE_IMAGE, FTYPE_VIDEO, FTYPE_OTHER = range(4)
    ICONNAMES = (
        (FTYPE_DIR, 'folder'),
        (FTYPE_IMAGE, 'image-x-generic'),
        (FTYPE_VIDEO, 'video-x-generic'),
        (FTYPE_OTHER, 'gtk-file')) # 'dialog-question'

    # столбцы в srcdirlist.store
    SDCOL_SEL, SDCOL_DIRNAME = range(2)

    class FileInfo():
        """Вспомогательный костыль, экземпляр которого кладётся
        в столбец FTCOL_INFO treemodel, дабы не плодить мильён вызовов
        treemodel.get_/set_ на произвольное кол-во столбцов.
        А вот fname придётся-таки держать в treemodel..."""

        __slots__ = 'fext', 'ftype', 'isbad', 'srcfname'

        def __init__(self, fext, ftype, isbad, srcfname):
            self.fext = fext
            self.ftype = ftype
            self.isbad = isbad
            self.srcfname = srcfname

        def __repr__(self):
            """Для отладки"""

            return '%s(fext="%s", ftype=%d, isbad=%s, srcfname="%s")' % (self.__class__.__name__,
                self.fext, self.ftype, self.isbad, self.srcfname)

    def wnd_destroy(self, widget):
        Gtk.main_quit()

    def wnd_delete_event(self, wnd, event):
        return self.jobRunning

    def wnd_configure_event(self, wnd, event):
        """Сменились размер/положение окна"""
        pass

    def wnd_state_event(self, widget, event):
        """Сменилось состояние окна"""
        pass

    def do_exit(self, widget):
        if not self.jobRunning:
            self.wnd_destroy(widget)

    def __init__(self, env):
        self.env = env

        resldr = get_resource_loader()
        uibldr = get_gtk_builder(resldr, 'photomvg.ui')
        #
        #
        #
        appicon = resldr.load_pixbuf_icon_size('images/photomvg.svg', Gtk.IconSize.DIALOG)

        self.wndMain = uibldr.get_object('wndMain')

        self.wndMain.set_icon(appicon)

        self.headerBar = uibldr.get_object('headerBar')
        self.headerBar.set_title('PhotoMVG prototype')

        uibldr.get_object('imgMainMenu').set_from_pixbuf(
            resldr.load_pixbuf_icon_size('images/menu.svg', Gtk.IconSize.MENU))

        self.mnuMainCloseIfSuccess = uibldr.get_object('mnuMainCloseIfSuccess')
        self.mnuMainCloseIfSuccess.set_active(env.closeIfSuccess)

        #
        sizeIcon = Gtk.IconSize.MENU
        sizeIconPx = Gtk.IconSize.lookup(sizeIcon)[1]
        iconError = resldr.load_pixbuf('images/badfilename.svg',
            sizeIconPx, sizeIconPx, 'dialog-error')

        def __icon_with_error_overlay(name):
            icon = load_system_icon(name, sizeIcon)

            erricon = icon.copy()
            iconError.composite(erricon,
                0, 0, sizeIconPx, sizeIconPx,
                0.0, 0.0, 1.0, 1.0,
                GdkPixbufInterpType.BILINEAR, 255)

            return {False:icon, True:erricon}

        # словарь, где ключи - значения FTYPE_*, а значения -
        # словари, где ключи - булевские значения (соотв. FileInfo.isbad),
        # а значения - экземпляры Pixbuf
        self.icons = dict()

        for ftype, iconname in self.ICONNAMES:
            self.icons[ftype] = __icon_with_error_overlay(iconname)

        #
        self.pages = uibldr.get_object('pages')
        #self.pages.set_show_tabs(False) # в .ui указано True для упрощения правки в Glade

        #
        # PAGE_SRCDIRS, список каталогов-источников
        #
        self.srcdirlist = TreeViewShell.new_from_uibuilder(uibldr, 'srcdirlistview')

        self.chkSDirSel = uibldr.get_object('chkSDirSel')

        self.curSrcDir = os.path.expanduser('~') # для dlgSDirChoose
        self.dlgSDirChoose = uibldr.get_object('dlgSDirChoose')

        self.btnScanSrcDirs = uibldr.get_object('btnScanSrcDirs')

        # заполняем список
        self.srcdirlist.nSelected = 0
        self.srcdirlist.nTotal = len(self.env.sourceDirs) # дабы не дёргать лишний раз liststore.iter_n_children()

        for srcdir in self.env.sourceDirs:
            self.srcdirlist.store.append((srcdir.use, srcdir.path))

            if srcdir.use:
                self.srcdirlist.nSelected += 1

        self.srcdirlist_update_sel_all_cbox()

        #
        # PAGE_DESTFNAMES, дерево новых каталогов/файлов
        #
        self.filetree = TreeViewShell.new_from_uibuilder(uibldr, 'filetreeview')

        # костыль для обработки DnD, см. filetree_drag_data_received(), filetree_drag_end()
        self.filetreedroprow = None

        #
        # PAGE_PROGRESS, страница выполнения
        #
        self.txtProgressOperation, self.pbarScanSrcDirs = get_ui_widgets(uibldr,
            ('txtProgressOperation', 'pbarScanSrcDirs'))

        self.jobRunning = False
        self.jobEndPage = 0

        #
        # PAGE_FINAL, страница завершения
        #
        self.txtFinalPageTitle, self.txtFinalPageMsg = get_ui_widgets(uibldr,
            ('txtFinalPageTitle', 'txtFinalPageMsg'))

        #
        # о программе...
        #
        self.dlgAbout = uibldr.get_object('dlgAbout')
        self.dlgAbout.set_program_name(TITLE)
        self.dlgAbout.set_version(VERSION)
        self.dlgAbout.set_copyright(COPYRIGHT)
        self.dlgAbout.set_website(URL)
        self.dlgAbout.set_website_label(URL)
        self.dlgAbout.set_logo(resldr.load_pixbuf('images/logo.svg',
            # размер пока приколотим гвоздями
            128, 128,
            'image-x-generic'))

        #
        self.pages.set_current_page(self.PAGE_START)

        uibldr.connect_signals(self)

        self.wndMain.show_all()

    def mnu_close_if_cuccess_toggled(self, mnuitem):
        self.env.closeIfSuccess = mnuitem.get_active()
        print(self.env.closeIfSuccess)

    def filetree_check_node(self, curitr):
        """Проверка элементов Gtk.TreeStore, находящихся на одном уровне
        с элементом, на который указывает curitr, включая указанный элемент.
        Проверяется повтор поля FTCOL_FNAME, т.к. совпадающие имена файлов
        в одном каталоге недопустимы. Проверка регистро-зависимая.
        Для совпадающих имён значение поля FTCOL_ISBAD устанавливается в True,
        также для них изменяется значок (значение поля FTCOL_ICON)."""

        oldname = None

        # подразумевается, что дерево отсортировано по полю FTCOL_FNAME!
        itr = self.filetree.store.iter_children(self.filetree.store.iter_parent(curitr))

        while itr is not None:
            info, fname = self.filetree.store.get(itr, self.FTCOL_INFO, self.FTCOL_FNAME)

            info.isbad = oldname is not None and oldname == fname

            self.filetree.store.set_value(itr,
                self.FTCOL_ICON,
                self.icons[info.ftype][info.isbad])

            oldname = fname

            itr = self.filetree.store.iter_next(itr)

    def filetree_name_edited(self, crt, path, fname):
        """Имя файла в столбце treeview изменено.
        Проверяем на правильность и кладём в соотв. столбец treemodel."""

        itr = self.filetree.store.get_iter(path)
        info = self.filetree.store.get_value(itr, self.FTCOL_INFO)

        fname = filename_validate(fname, info.fext)

        self.filetree.store.set_value(itr, self.FTCOL_FNAME, fname)

        # а теперь проверяем весь текущий уровень дерева на одинаковые имена
        self.filetree_check_node(itr)

    def filetree_drag_begin(self, tv, ctx):
        """Запрещаем сортировку treestore, т.к. она блокирует drag-n-drop."""

        self.filetree_enable_sorting(False)

    def filetree_drag_drop(self, tv, ctx, x, y, time):
        """Проверяем, куда именно попадает drag-n-drop'нутый элемент.
        Разрешаем перемещение только в каталоги и между файлов, чтобы treeview
        не мог сделать элемент типа "файл" дочерним элементом другого файла."""

        r = self.filetree.view.get_dest_row_at_pos(x, y)
        if r is not None:
            path, pos = r

            if path is not None:
                info = self.filetree.store.get_value(self.filetree.store.get_iter(path), self.FTCOL_INFO)
                if info.ftype != self.FTYPE_DIR and pos in (Gtk.TreeViewDropPosition.INTO_OR_BEFORE, Gtk.TreeViewDropPosition.INTO_OR_AFTER):
                    return True

        return False

    def filetree_drag_data_received(self, tv, ctx, x, y, data, info, time):
        drop = self.filetree.view.get_dest_row_at_pos(x, y)

        if drop is not None and drop[0]:
            self.filetreedroprow = drop[0]
        else:
            self.filetreedroprow = None

    def filetree_drag_end(self, tv, ctx):
        """Завершение операции drag-n-drop.

        Перемещаем selection на дропнутую ветвь (если она известна)
        и проверяем эту ветвь на повторы имён файлов."""

        if self.filetreedroprow:
            try:
                itr = self.filetree.store.get_iter(self.filetreedroprow)
            except ValueError:
                # в некоторых случаях перемещения ветвь self.filetreedroprow
                # уже не существует на момент вызова drag_end,
                # и get_iter падает с исключением, собака такая,
                # хотя мог бы и просто None возвращать...
                return

            self.filetree_select_iter(itr)
            self.filetree_check_node(itr)

        # разрешаем взад сортировку treestore
        self.filetree_enable_sorting(True)

    def filetree_enable_sorting(self, enable):
        """Разрешение/запрет сортировки treestore."""

        self.filetree.store.set_sort_column_id(
            self.FTCOL_FNAME if enable else Gtk.TREE_SORTABLE_UNSORTED_SORT_COLUMN_ID,
            Gtk.SortType.ASCENDING)

    def __scan_dir_to_filetree(self, fromdirname, toiter, progress):
        """Рекурсивный обход каталога с заполнением дерева filetree.store.
        fromdirname - путь к каталогу,
        toiter      - экземпляр Gtk.TreeIter, указывающий на позицию в filetree.store,
        progress    - None или функция с двумя параметрами:
                        text        - сообщение, отображаемое на прогрессбаре,
                        fraction    - -1 или значение от 0.0 до 1.0.
                      Функция должна возвращать булевское значение:
                      True - продолжить, False - прервать работу."""

        if not callable(progress):
            progress = None

        # проверяем, есть ли у нас права на каталог
        # (без этого os.listdir может рухнуть с исключением)
        # заодно проверяется и наличие каталога
        if os.access(fromdirname, os.F_OK | os.R_OK):
            for srcfname in os.listdir(fromdirname):
                #!!!
                if progress is not None:
                    if not progress(fromdirname, -1):
                        return

                if srcfname.startswith('.'):
                    # скрытые файлы - игнорируем
                    continue

                fpath = os.path.join(fromdirname, srcfname)
                if os.path.islink(fpath):
                    if not os.path.exists(os.path.realpath(fpath)):
                        # сломанные линки - пропускаем!
                        continue

                # потом сюда будет всобачиваться результат обработки шаблоном!
                fname, fext = os.path.splitext(srcfname)
                fext = fext.lower()
                fname = '%s%s' % (fname, fext)

                if os.path.isdir(fpath):
                    ftype = self.FTYPE_DIR
                # потом здесь будет определение типа файла по расширению из настроек!
                elif fext in ('.cr2', '.cr3', '.nef', '.arw', '.raw', '.jpg', '.jpeg', '.tiff', '.png'):
                    ftype = self.FTYPE_IMAGE
                elif fext in ('.avi', '.mpg', '.mpeg', '.mkv', '.m4v', '.mov', '.ts'):
                    ftype = self.FTYPE_VIDEO
                else:
                    ftype = self.FTYPE_OTHER

                info = self.FileInfo(fext, ftype, False, srcfname) #!!!!

                tooltip = 'Оригинальное имя файла: <b>%s</b>' % srcfname

                itr = self.filetree.store.append(toiter,
                    # проверяй порядок значений FTCOL_* и столбцов filetree.store в *.ui!
                    (info, self.icons[ftype][False], fname, tooltip))

                if info.ftype == self.FTYPE_DIR:
                    self.__scan_dir_to_filetree(fpath, itr, progress)

    def filetree_refresh(self):
        """Обход каталогов из списка srcdirlist.store с заполнением дерева
        filetree.store."""

        self.job_begin('Поиск файлов...', self.PAGE_DESTFNAMES)

        self.filetree.view.set_model(None)

        self.filetree_enable_sorting(False)
        self.filetree.store.clear()

        itr = self.srcdirlist.store.get_iter_first()

        try:
            while itr is not None:
                #!!!
                if not self.jobRunning:
                    break

                chkd, dirname = self.srcdirlist.store.get(itr, self.SDCOL_SEL, self.SDCOL_DIRNAME)
                if chkd:
                    self.__scan_dir_to_filetree(dirname, None, self.job_progress)

                itr = self.srcdirlist.store.iter_next(itr)
        finally:
            self.filetree_enable_sorting(True)
            self.filetree.view.set_model(self.filetree.store)

            if self.filetree.store.iter_n_children():
                self.jobEndPage = self.PAGE_DESTFNAMES
            else:
                self.jobEndPage = self.PAGE_FINAL
                self.txtFinalPageTitle.set_text('Поиск файлов завершён')
                self.txtFinalPageMsg.set_text('Подходящие файлы не найдены.')

            self.job_end()

    def filetree_expand_all(self, btn):
        self.filetree.view.expand_all()

    def filetree_collapse_all(self, btn):
        self.filetree.view.collapse_all()

    def filetree_get_full_path(self, itr):
        """Возвращает строку с полным путём к элементу дерева,
        указанному itr."""

        path = []
        while itr is not None:
            path.append(self.filetree.store.get_value(itr, self.FTCOL_FNAME))
            itr = self.filetree.store.iter_parent(itr)

        path.reverse()

        return os.path.join(*path)

    def filetree_new_dir(self, wgt):
        """Создаёт каталог в верхнем уровне дерева, если нет выбранных
        элементов, иначе - создаёт дочерний каталог для первого выбранного
        элемента, при условии, что элемент - каталог."""

        itr = self.filetree.get_selected_iter()

        if itr is None:
            parent = None
        else:
            info = self.filetree.store.get_value(itr, self.FTCOL_INFO)
            if info.ftype != self.FTYPE_DIR:
                return

            parent = itr

        newinfo = self.FileInfo('', self.FTYPE_DIR, False, 'new')

        itr = self.filetree.store.append(parent,
            (newinfo, self.icons[newinfo.ftype][False], newinfo.srcfname,
            'Новый каталог. Переименуй его.'))

        self.filetree_select_iter(itr)
        self.filetree_check_node(itr)

    def filetree_revert_srcname(self, wgt):
        """Возвращает исходные имена всем выбранным элементам."""

        sel = self.filetree.selection.get_selected_rows()

        if sel is not None:
            for path in sel[1]:
                itr = self.filetree.store.get_iter(path)

                info = self.filetree.store.get_value(itr, self.FTCOL_INFO)
                self.filetree.store.set_value(itr, self.FTCOL_FNAME, info.srcfname)

    def filetree_remove_item(self, wgt):
        """Удаляет выбранные элементы."""

        # подтверждения пока что спрашивать не будем
        sel = self.filetree.selection.get_selected_rows()

        if sel is not None:
            for path in sel[1]:
                try:
                    itr = self.filetree.store.get_iter(path)
                    self.filetree.store.remove(itr)
                except ValueError:
                    # get_iter() падает с исключением, если path указывает
                    # на уже удалённый элемент!
                    pass

    def srcdirlist_add(self, btn):
        self.dlgSDirChoose.set_current_folder(self.curSrcDir)

        self.dlgSDirChoose.show()
        r = self.dlgSDirChoose.run()
        self.dlgSDirChoose.hide()

        if r != Gtk.ResponseType.OK:
            return

        def __add_srcdir(newdirname):
            """Проверяет, не совпадает ли каталог newdirname с одним из
            хранящихся в srcdirlist.store, и не является ли подкаталогом
            одного из хранящихся.

            При отсутствии совпадений добавляет новый каталог в srcdirlist.store
            и возвращает True, иначе - возвращает False."""

            itr = self.srcdirlist.store.get_iter_first()

            while itr is not None:
                dirname = self.srcdirlist.store.get_value(itr, self.SDCOL_DIRNAME)

                if same_dir(newdirname, dirname):
                    return False

                itr = self.srcdirlist.store.iter_next(itr)

            self.srcdirlist.store.append((True, newdirname))
            self.srcdirlist.nTotal += 1
            self.srcdirlist.nSelected += 1

            return True

        baddirs = []

        for dirname in self.dlgSDirChoose.get_filenames():
            # добавляем поочерёдно каталоги, проверяя каждый на повтор
            # или вложенность с уже добавленными
            # и ругаясь при необходимости

            if not __add_srcdir(dirname):
                baddirs.append(dirname)

        self.srcdirlist_update_sel_all_cbox()

        if baddirs:
            msg_dialog(self.wndMain,
                self.dlgSDirChoose.get_title(),
                'Каталог%s\n%s\nуже есть в списке.' %\
                    ('и' if len(baddirs) > 1 else '',
                     '\n'.join(baddirs)))

    def srcdirlist_remove(self, btn):
        itr = self.srcdirlist.get_selected_iter()
        if itr is not None:
            if msg_dialog(self.wndMain, 'Удаление каталога из списка',
                    'Убрать из списка каталог "%s"?' % self.srcdirlist.store.get_value(itr, self.SDCOL_DIRNAME),
                    Gtk.MessageType.QUESTION,
                    Gtk.ButtonsType.YES_NO) != Gtk.ResponseType.YES:
                return

            if self.srcdirlist.store.get_value(itr, self.SDCOL_SEL):
                self.srcdirlist.nSelected -= 1

            self.srcdirlist.store.remove(itr)
            self.srcdirlist.nTotal -= 1

            self.srcdirlist_update_sel_all_cbox()

    def srcdirlist_item_sel_toggled(self, cr, path):
        # нажат чекбокс в списке каталогов-источников

        itr = self.srcdirlist.store.get_iter(path)
        if itr is not None:
            sel = not self.srcdirlist.store.get_value(itr, self.SDCOL_SEL)
            self.srcdirlist.store.set_value(itr, self.SDCOL_SEL, sel)

            self.srcdirlist.nSelected += -1 if not sel else 1

            self.srcdirlist_update_sel_all_cbox()

    def srcdirlist_update_sel_all_cbox(self):
        """Обновление состояния чекбокса на заголовке столбца."""

        if self.srcdirlist.nTotal == 0 or self.srcdirlist.nSelected == 0:
            sa = False
            si = False
        elif self.srcdirlist.nTotal == self.srcdirlist.nSelected:
            sa = True
            si = False
        else:
            sa = True
            si = True

        self.chkSDirSel.set_active(sa)
        self.chkSDirSel.set_inconsistent(si)

        self.btnScanSrcDirs.set_sensitive(self.srcdirlist.nSelected > 0)

    def __srcdirlist_select_all(self, sel):
        itr = self.srcdirlist.store.get_iter_first()

        while itr is not None:
            self.srcdirlist.store.set_value(itr, self.SDCOL_SEL, sel)
            itr = self.srcdirlist.store.iter_next(itr)

        self.srcdirlist.nSelected = self.srcdirlist.nTotal if sel else 0

        self.srcdirlist_update_sel_all_cbox()

    def srcdirlist_sel_col_clicked(self, cbtn):
        """нажат чекбокс на заголовке столбца каталогов-источников"""

        self.__srcdirlist_select_all(not (self.chkSDirSel.get_active() or self.chkSDirSel.get_inconsistent()))

    def job_begin(self, title, endpage):
        self.txtProgressOperation.set_text(title)
        self.pbarScanSrcDirs.set_fraction(0.0)

        self.pages.set_current_page(self.PAGE_PROGRESS)
        self.jobEndPage = endpage
        self.jobRunning = True

        self.headerBar.set_sensitive(False)

    def job_progress(self, txt, fraction):
        self.pbarScanSrcDirs.set_text(txt)

        if fraction >= 0.0:
            self.pbarScanSrcDirs.set_fraction(fraction)
        else:
            self.pbarScanSrcDirs.pulse()

        flush_gtk_events()

        return self.jobRunning

    def job_end(self):
        self.jobRunning = False
        self.headerBar.set_sensitive(True)
        self.pages.set_current_page(self.jobEndPage)

    def job_stop(self, widget):
        self.jobRunning = False

    def btn_start_clicked(self, btn):
        self.filetree_refresh()

    def btn_restart_clicked(self, wgt):
        self.pages.set_current_page(self.PAGE_START)

    def show_about_box(self, wgt):
        self.dlgAbout.show()
        self.dlgAbout.run()
        self.dlgAbout.hide()

    def main(self):
        Gtk.main()


def main(args):
    env = Environment(sys.argv)

    if env.error:
        msg_dialog(None, TITLE,
            'Ошибка в файле конфигурации:\n%s' % env.error)
        return 1

    try:
        MainWnd(env).main()
    finally:
        pass
        #env.save()

    return 0


if __name__ == '__main__':
    main(sys.argv)
