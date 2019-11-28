#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" gtktools.py

    Набор обвязок и костылей к GTK, общий для типовых гуёв.

    Copyright 2018 mc6312

    This module is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This module is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this module.  If not, see <http://www.gnu.org/licenses/>."""


# для обвязок GTK
from gi import require_version as gi_require_version
gi_require_version('Gtk', '3.0')
# если сей модуль, gtktools, указать первым перед прочими связанными
# с GTK модулями - не придётся из оттудова дёргать gi_require_version()
from gi.repository import Gtk, Gdk, GObject, GLib, Pango, Gio
from gi.repository.GdkPixbuf import Pixbuf


# для *ResourceLoader
import zipfile
from sys import stderr, argv
import os.path


def get_widget_base_unit():
    """Возвращает базовое значение, которое можно использовать для расчета
    отступов между виджетами и т.п., дабы несчастного пользователя
    не вывернуло от пионерского вида гуя.
    Значение считаем на основе размера шрифта по умолчанию, так как
    прицепиться больше не к чему."""

    pangoContext = Gdk.pango_context_get()
    return int(pangoContext.get_metrics(pangoContext.get_font_description(),
        None).get_approximate_char_width() / Pango.SCALE)


WIDGET_BASE_UNIT = get_widget_base_unit()

# обычный интервал между виджетами (напр. внутри Gtk.Box)
WIDGET_SPACING = WIDGET_BASE_UNIT // 2
if WIDGET_SPACING < 4:
    WIDGET_SPACING = 4

# расширенный интервал - для разделения групп виджетов там,
# где Gtk.Separator не смотрится
WIDE_WIDGET_SPACING = WIDGET_SPACING * 3


def load_system_icon(name, size, pixelsize=False):
    """Возвращает Pixbuf для "системной" (из установленной темы)
    иконки с именем name и размером size.

    size    - стандартный размер Gtk.IconSize.* если pixelsize==False,
              иначе считаем, что size - размер в пикселях."""

    if not pixelsize:
        size = Gtk.IconSize.lookup(size)[1]

    return Gtk.IconTheme.get_default().load_icon(name,
        size,
        Gtk.IconLookupFlags.FORCE_SIZE)


#
# "общие" иконки
#
MENU_ICON_SIZE_PIXELS =  Gtk.IconSize.lookup(Gtk.IconSize.MENU)[1]


def get_ui_widgets(builder, names):
    """Получение списка указанных виджетов.
    builder     - экземпляр класса Gtk.Builder,
    names       - список или кортеж имён виджетов.
    Возвращает список экземпляров Gtk.Widget и т.п."""

    widgets = []

    for wname in names:
        wgt = builder.get_object(wname)
        if wgt is None:
            raise KeyError('get_ui_widgets(): экземпляр Gtk.Builder не содержит виджет с именем "%s"' % wname)

        widgets.append(wgt)

    return widgets


def set_widgets_sensitive(widgets, bsensitive):
    """Устанавливает значения свойства "sensitive" равным значению
    bsensitive для виджетов из списка widgets."""

    for widget in widgets:
        widget.set_sensitive(bsensitive)


def get_child_with_class(container, wantclass):
    """Ищет первый попавшийся виджет класса wantclass
    в виджете-контейнере container.

    Может пригодиться, когда нужно принудительно дёрнуть grab_focus()
    для какого-то составного виджета вроде Gtk.FileChooser, "внешний"
    контейнер которого не умеет принимать фокус ввода.

    Если чего найдет - возвращает ссылку на экземпляр, иначе возвращает
    None."""

    if not isinstance(container, Gtk.Container):
        return None

    children = container.get_children()

    if not children:
        return None

    for child in children:
        if isinstance(child, wantclass):
            return child

    # страдаем рекурсией только в том случае, если на текущем уровне
    # не нашлось ни одного подходящего виджета
    for child in children:
        r = get_child_with_class(child, wantclass)
        if r is not None:
            return r


def create_aligned_label(title, halign=0.0, valign=0.0):
    label = Gtk.Label(title)
    label.set_alignment(halign, valign)
    #label.set_justify(Gtk.Justification.LEFT)
    return label


def set_widget_style(widget, css):
    """Задание стиля для виджета widget в формате CSS"""

    dbsp = Gtk.CssProvider()
    dbsp.load_from_data(css) # убейте гномосексуалистов кто-нибудь!
    dbsc = widget.get_style_context()
    dbsc.add_provider(dbsp, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def msg_dialog(parent, title, msg, msgtype=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.OK, widgets=None):
    dlg = Gtk.MessageDialog(parent, 0, msgtype, buttons, msg,
        flags=Gtk.DialogFlags.MODAL|Gtk.DialogFlags.DESTROY_WITH_PARENT)

    dlg.set_title(title)

    if widgets is not None:
        ca = dlg.get_message_area()

        for widget in widgets:
            ca.pack_start(widget, False, False, 0)

        ca.show_all()

    r = dlg.run()
    dlg.destroy()

    return r


def create_file_filter(name, patterns):
    """Создаёт экземпляр Gtk.FileFilter для Gtk.FileChooser*.

    name     - строка для отображения в комбобоксе выбора типа файлов,
    patterns - маски типов файлов, в виде строки, разделённой запятыми,
               или кортежа/списка строк (которые могут содержать
               несколько масок, разделённых запятыми)."""

    ffl = Gtk.FileFilter()
    ffl.set_name('Изображения')

    def add_pattern_str(s):
        for pat in map(lambda v: v.strip(), s.split(',')):
            if pat:
                ffl.add_pattern(pat)

    if isinstance(patterns, str):
        add_pattern_str(patterns)
    elif isinstance(patterns, list) or isinstance(patterns, tuple):
        for pv in patterns:
            add_pattern_str(pv)

    return ffl


def get_gtk_builder(resldr, filename):
    """Возвращает экземпляр класса Gtk.Builder.
    resldr - экземпляр класса *ResourceLoader,
    filename - имя файла .ui."""

    uistr = resldr.load(filename)
    return Gtk.Builder.new_from_string(str(uistr, 'utf-8'), -1)


def flush_gtk_events():
    """Даём GTK переварить все накопившиеся события"""

    while Gtk.events_pending():
        Gtk.main_iteration()


def get_resource_loader():
    """Возвращает экземпляр класса FileResourceLoader
    или ZipFileResourceLoader, в зависимости от того, как запущена
    программа - из обычного файла, или из архива ZIP."""

    # получаем путь к главному модулю (приложению)
    appFilePath = os.path.abspath(argv[0])

    # мы в жо... в зипе?
    appIsZIP = zipfile.is_zipfile(appFilePath)

    return ZipFileResourceLoader(appFilePath) if appIsZIP else FileResourceLoader(appFilePath);


class FileResourceLoader():
    """Загрузчик файлов ресурсов.
    Mожет использоваться при загрузке файлов иконок, .ui и т.п.

    Внимание! Методы этого класса в случае ошибок генерируют исключения."""

    def __init__(self, appFilePath):
        """Инициализация.

        appFilePath - путь к основному файлу (модулю) приложения."""

        self.appFilePath = appFilePath
        self.appDir = os.path.split(appFilePath)[0]

    def load(self, filename):
        """Загружает файл filename в память и возвращает в виде
        bytestring.

        filename - относительный путь к файлу."""

        filename = os.path.join(self.appDir, filename)

        if not os.path.exists(filename):
            raise ValueError('Файл "%s" не найден' % filename)

        try:
            self.error = None
            with open(filename, 'rb') as f:
                return f.read()
        except Exception as ex:
            # для более внятных сообщений
            self.error = 'Не удалось загрузить файл "%s" - %s' % (filename, str(ex))

    def load_bytes(self, filename):
        """Загружает файл filename в память и возвращает в виде
        экземпляра GLib.Bytes.

        filename - относительный путь к файлу."""

        return GLib.Bytes.new(self.load(filename))

    def load_memory_stream(self, filename):
        """Загружает файл в память и возвращает в виде экземпляра Gio.MemoryInputStream."""

        return Gio.MemoryInputStream.new_from_bytes(self.load_bytes(filename))

    @staticmethod
    def pixbuf_from_bytes(b, width, height):
        """Создаёт и возвращает Gdk.Pixbuf из b - экземпляра GLib.Bytes.

        width, height - размеры создаваемого изображения в пикселах."""

        return Pixbuf.new_from_stream_at_scale(Gio.MemoryInputStream.new_from_bytes(b),
            width, height, True)

    def load_pixbuf(self, filename, width, height, fallback=None):
        """Загружает файл в память и возвращает экземпляр Gdk.Pixbuf.

        filename        - имя файла (см. load_bytes),
        width, height   - размеры создаваемого изображения в пикселах,
        fallback        - имя стандартной иконки, которая будет загружена,
                          если не удалось загрузить файл filename;
                          если fallback=None - генерируется исключение."""

        try:
            return self.pixbuf_from_bytes(self.load_bytes(filename),
                width, height)
        except Exception as ex:
            print('Can not load image "%s" - %s' % (filename, str(ex)), file=stderr)
            if fallback is None:
                raise ex
            else:
                print('Loading fallback image "%s"' % fallback, file=stderr)
                return Gtk.IconTheme.get_default().load_icon(fallback, height, Gtk.IconLookupFlags.FORCE_SIZE)


class ZipFileResourceLoader(FileResourceLoader):
    """Загрузчик файлов ресурсов из архива ZIP.
    Архив - сам файл flibrowser2 в случае, когда он
    представляет собой python zip application."""

    def load(self, filename):
        """Аналогично FileResourceLoader.load(), загружает файл
        filename в память и возвращает в виде экземпляра bytestring.

        filename - путь к файлу внутри архива."""

        if not zipfile.is_zipfile(self.appFilePath):
            raise TypeError('Файл "%s" не является архивом ZIP' % self.appFilePath)

        with zipfile.ZipFile(self.appFilePath, allowZip64=True) as zfile:
            try:
                with zfile.open(filename, 'r') as f:
                    return f.read()
            except Exception as ex:
                raise Exception('Не удалось загрузить файл "%s" - %s' % (filename, str(ex)))


class TreeViewShell():
    """Обёртка для упрощения дёргания Gtk.TreeView"""

    def __init__(self, tv):
        """tv   - экземпляр Gtk.TreeView."""

        self.view = tv
        self.store = tv.get_model()
        self.selection = tv.get_selection()

        # см. метод select_iter
        self.expandSelectedRow = False
        self.expandSelectedAll = False

    @classmethod
    def new(cls, tv):
        # сей метод - для единообразия
        return cls(tv)

    @classmethod
    def new_from_uibuilder(cls, builder, widgetname):
        """Создаёт экземпляр TreeViewShell, запрашивая
        экземпляр Gtk.TreeView у builder (экземпляра класса Gtk.Builder)
        по имени виджета widgetname."""

        return cls(builder.get_object(widgetname))

    def get_selected_iter(self):
        """Возвращает Gtk.TreeIter первого выбранного элемента (если
        что-то выбрано) или None."""

        sel = self.selection.get_selected_rows()

        if sel is not None:
            rows = sel[1]
            if rows:
                return self.store.get_iter(rows[0])

    def filetree_select_iter(self, itr):
        """Выбирает элемент в дереве, указанный itr (экземпляром
        Gtk.TreeIter), при необходимости заставляет TreeView развернуть
        соответствующий уровень дерева."""

        path = self.store.get_path(itr)

        if self.expandSelectedRow:
            self.view.expand_row(path, self.expandSelectedAll)

        self.selection.select_path(path)
        self.view.set_cursor(path, None, False)


if __name__ == '__main__':
    print('[test of %s]' % __file__)

    rl = get_resource_loader()

    b = rl.load('btfm-ui.xml')
    s = str(b, 'utf-8')
    print(s)
