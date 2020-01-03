# PHOTOMVG

## ВВЕДЕНИЕ

1. Сия программа является свободным ПО под лицензией [GPL v3](https://www.gnu.org/licenses/gpl.html).
2. Программа создана и дорабатывается автором исключительно ради собственных нужд
и в соответствии с его представлениями об эргономике и функциональности.
3. Автор всех видал в гробу и ничего никому не должен, кроме явно прописанного в GPL.
4. Несмотря на вышеуказанное, автор совершенно не против, если программа
подойдёт кому-то еще. А те, под кем прогорит сиденье из-за пунктов
с 1 по 3, могут отправиться туда, куда им фантазия подскажет.

## НАЗНАЧЕНИЕ

Поиск в каталогах-источниках изображений и видеофайлов, их перемещение
(или копирование) в каталог-приемник.


## ЧТО ТРЕБУЕТ ДЛЯ РАБОТЫ

- Linux (или другую ОС, в которой заработает нижеперечисленное)
- Python 3.6 или новее
- GTK 3.20 или новее
- PyGI/PyGObject совместимой со всем этим версии

## КОНФИГУРАЦИЯ

Все параметры хранятся в файле settings.ini (если он существует).

Программа ищет файл настроек в следующих каталогах (в порядке очерёдности):

1. Каталог, где расположена сама программа.
2. $HOME/.config/photomvg/

При отсутствии файла настроек программа использует значения по умолчанию.

## КАК РАБОТАЕТ

### 1. ВЫБОР КАТАЛОГОВ-ИСТОЧНИКОВ И ПОИСК ФАЙЛОВ В НИХ

Программа отображает список каталогов-источников.
В список может быть добавлено произвольное количество каталогов.

При поиске файлов игнорируются физически недоступные каталоги (например,
указывающие на неподключенный внешний диск), и те, у которых не включен
в списке чекбокс.

Каталоги-источники обходятся рекурсивно, из файлов поддерживаемых
(и разрешённых для поиска) форматов извлекаются метаданные (в частности,
поля EXIF).

В случае ошибок чтения файлов или ошибок в формате файлов выводится
предупреждение, и соответствующие файлы не обрабатываются.

Формат файлов определяется тупо и в лоб - по расширению.

После нажатия кнопки "Начать поиск" на основе имён обнаруженных файлов и
метаданных с помощью шаблонов (см. соотв. разделы README) генерируется
задание для перемещения (или копирования) файлов в виде дерева имён.

### 2. ОТОБРАЖЕНИЕ ПОЛУЧЕННОГО ДЕРЕВА В UI

Файлы с одинаковыми именами, если таковые создаст шаблонизатор, будут
помечены в дереве зловещей красной иконкой.

Подобная ситуация может возникнуть при отсутствии
метаданных в файлах (новые имена генерируются по шаблонам на основе
метаданных).

На этой стадии никакого копирования/перемещения файлов ещё
не производится, сгенерированное дерево каталогов и файлов -
фактически является заданием для следующей стадии.

Пользователь может просмотреть дерево файлов на предмет
неправильных имён и т.п., с возможностью переименования
файлов и изменения дерева каталогов вручную.

В случае отсутствия ошибок и/или их успешного устранения пользователь
кнопкой "Выполнить" запускает выполнение следующей стадии, или
возвращается к странице поиска, нажав кнопку "Начать сначала"
или завершает программу.

### 3. КОПИРОВАНИЕ ИЛИ ПЕРЕМЕЩЕНИЕ ФАЙЛОВ

Программа создаёт подкаталоги в каталоге назначения и копирует файлы
под именами, заданными на стадии 2.

Процесс можно прервать соответствующей кнопкой, после чего программа
вернётся на страницу 2.

Если в каталоге-приемнике уже есть файл с таким же именем, как новый,
поведение программы зависит от параметра if-exists файла настроек.

## ФАЙЛ НАСТРОЕК

Файл настроек - текстовый файл в формате INI (имена секций в квадратных
скобках, за ними следуют пары вида "переменная = значение").

#### Секция options

Параметры:

##### if-exists

Задаёт поведение в ситуации, когда файл с таким же именем уже есть.

Значения:

- **s[kip]** - файл не копируется;
- **r[ename]** - к имени нового файла будет добавлен цифровой суффикс
вида "-NN" (режим по умолчанию);
- **o[verwrite]** - имеющийся файл будет перезаписан.

##### known-image-types, known-raw-image-types, known-video-types

Эти необязательные параметры могут содержать списки расширений
файлов изображений и видеофайлов, которые должны обрабатываться
программой, в дополнение к внутренним спискам программы.

Расширения в списках разделяются пробелами. Точки вначале расширений
можно не указывать.

##### search-file-types

Указывает, какие типы файлов следует искать в каталогах-источниках.
Содержит одно или несколько значений, разделяемых пробелами - photo,
raw, video.

##### dest-dir

Каталог назначения. Создаётся программой при необходимости.

Также, если сгенерированныв шаблонами пути содержат подкаталоги, они
создаются внутри каталога назначения во время перемещения (копирования)
файлов.

##### current-template-name

Имя выбранного шаблона для генерации новых имён файлов. Если значение
не указано, используется автовыбор (см. также описание секции "templates").

#### Секция src-dirs

Содержит параметры одного и более исходных каталогов - пары вида
"номер = флаг, путь", где:

Номер - служебный номер параметра, создаваемый программой (или вручную
при редактировании файла настроек);

Флаг - значение вида "true|yes" или "false|no". Каталоги, флаг которых
равен "no", игнорируются при операциях с файлами. Значения флагов изменяются
чекбоксами в списке исходных каталогов в графическом интерфейсе.

    Пример:
```
1 = yes, /media/username/NIKON D7100/DCIM
```

#### Секция dest-dirs

Содержит список ранее использованных каталогов назначения - пары вида
"номер = путь".


#### Секция templates

Необязательная секция; содержит шаблоны для новых имен файлов
и подкаталогов (см. также секцию "ШАБЛОНЫ").

Названия параметров в этой секции:

- \* - в значении этого параметра указывается общий шаблон;
  если общий шаблон не задан, вместо него будет использоваться
  внутренний общий шаблон программы
- _имя модели камеры_ - если название этого параметра соответствует
значению поля Exif.Image.Model из исходного файла, применяется
индивидуальный шаблон камеры; сравнение значения из EXIF с названием
параметра - регистро-независимое

Имя модели камеры может содержать символы подстановки - "?" (любой символ),
"*" (группа любых символов).

Пример:

```
canon eos 5d* = {filename}
```

Т.е. указанный шаблон будет применён к снимкам со всех камер линейки
Canon EOS 5d (mark 2, mark 3, ...).

Если секция __templates__ отсутствует в файле настроек, ко всем файлам
применяется внутренний общий шаблон программы.

Имя подкаталога (подкаталогов) и новое имя файла задаётся в одной строке
шаблона (т.е. она может содержать символы-разделители путей).

#### Секция aliases

Необязательная секция; содержит подстановки имен моделей камер
(для макроса ${alias} шаблонов).

Имена параметров в этой секции - названия моделей камер (как в
поле Exif.Image.Model), а значения - сокращённые имена.

Имена параметров - регистро-независимые.

Пример:

```
NIKON D70 = nd70
Canon EOS 5D Mark III = c5d3
```

## ШАБЛОНЫ

Шаблон представляет собой строку, содержащую макросы подстановки
(текст в фигурных скобках "{}"), разделители путей ("/") и/или
произвольный текст.

Символы, недопустимые в именах файлов, автоматически заменяются
символом подчёркивания "\_", а также при их наличии ругается редактор
шаболнов в окне настроек.

Шаблон не должен содержать расширения - оно __всегда__ берётся из
исходного имени файла и приводится к нижнему регистру.

Символы разделения путей в начале шаблона (до первого макроса или текста)
удаляются.

Внутренний общий шаблон программы, используемый при отсутствии
других шаблонов:

```
{filename}
```

Т.е. сохраняется оригинальное имя файла.

### Макросы подстановки

Формат макроса - {имя}. Имена регистро-независимые, могут быть
указаны в полном или сокращенном виде. Пробелы между скобками и именами
шаблонов игнорируются.

Для вставки в шаблон символов фигурных скобок как есть - их следует
удваивать.

Значения полей берутся из EXIF исходного файла (если есть), из
имён и метаданных файлов в ФС (если есть). Отсутствующие
значения заменяются символом подчёркивания ("_").

#### {y[ear]}, {mon[th]}, {d[ay]}, {h[our]}, {m[inute]}, {s[econd]}

Год (с тысячелетием), месяц, день, час, минута и секунда создания файла
соответственно.

При наличии в файле EXIF - берутся оттуда, иначе - из даты последнего
изменения файла в ФС.

#### {model}

Название модели камеры (из Exif.Image.Model).

#### {a[lias]}

Сокращённое имя модели камеры.

Берётся соотв. значение из секции __aliases__ файла настроек.

#### {p[refix]}

Префикс исходного имени файла (например, для DSCN0666.NEF - "DSCN").

Символы "_" и "-" в начале и в конце префикса удаляются.

#### {n[umber]}

Номер из исходного имени файла (например, для DSCN0666.NEF - "0666").

#### {t[ype]}

Тип исходного файла в сокращённом виде - p (все изображения, в т.ч. RAW) или v (видео).

Определяется по расширению.

#### {l[ongtype]}

Тип исходного файла - raw (фотоснимки в формате RAW), photo (прочие
изображения) или video (видео).

Определяется по расширению.
