# -*- coding: utf-8 -*-


"""
Программа ищет mp3 файлы в заданном каталоге/подкаталогах и перемещает файлы в каталог назначения в виде:
<каталог назначения>/<исполнитель>/<альбом>/<название трека или имя файла> - <исполнитель> - <альбом>.mp3
Перемещаются только файлы, у которых заполнены теги об исполнителе или альбоме.
В консоль пришет лог перемещений, например:
Du hast.mp3 -> /home/user/some/directory/Rammstein/Sehnsucht/Du hast - Rammstein - Sehnsucht.mp3

"""

import argparse
import errno
import os
import sys

EXT3 = '.mp3'
ERROR_INVALID_NAME = 123  # [WinError 123] Синтаксическая ошибка в имени файла, имени папки или метке тома


class ReadableFolder(argparse.Action):
    """
    Проверяет доступность каталога и права на чтение каталога
    В случае ошибки возбуждает исключение argparse.ArgumentTypeError
    """
    def __call__(self, parser, namespace, values, option_string=None):
        prospective_dir = values
        try:
            os.chdir(prospective_dir)
        except FileNotFoundError:
            raise argparse.ArgumentTypeError(f'Каталог {prospective_dir} не найден!')
        except OSError as exc:
            if hasattr(exc, 'winerror'):
                if exc.winerror == ERROR_INVALID_NAME:
                    raise argparse.ArgumentTypeError(f'Синтаксическая ошибка в имени каталога {prospective_dir}')
            elif exc.errno in {errno.ENAMETOOLONG, errno.ERANGE}:
                raise argparse.ArgumentTypeError(f'Слишком длинный путь к каталогу {prospective_dir}')

        if os.access(prospective_dir, os.R_OK):
            setattr(namespace, self.dest, prospective_dir)
        else:
            raise argparse.ArgumentTypeError(f'У вас нет прав на просмотр каталога {prospective_dir}')


class WritableFolder(argparse.Action):
    """
    Проверяет доступность каталога и права на запись в каталог
    В случае ошибки возбуждает исключение argparse.ArgumentTypeError
    """
    def __call__(self, parser, namespace, values, option_string=None):
        prospective_dir = values
        if not os.path.isdir(prospective_dir):
            try:
                os.makedirs(prospective_dir, mode=0o777, exist_ok=True)
            except NotADirectoryError:
                raise argparse.ArgumentTypeError(f'Неверно задано имя каталога {prospective_dir}')
            except OSError as exc:
                if hasattr(exc, 'winerror'):
                    if exc.winerror == ERROR_INVALID_NAME:
                        raise argparse.ArgumentTypeError(f'Синтаксическая ошибка в имени каталога {prospective_dir}')
                elif exc.errno in {errno.ENAMETOOLONG, errno.ERANGE}:
                    raise argparse.ArgumentTypeError(f'Слишком длинный путь к каталогу {prospective_dir}')

        if os.access(prospective_dir, os.W_OK):
            setattr(namespace, self.dest, prospective_dir)
        else:
            raise argparse.ArgumentTypeError(f'У вас нет прав на запись в каталог {prospective_dir}')


def remove_invalid_chars(string) -> str:
    """
    Примимает строку и возвращает строку, удаляя из нее символы, указанные в invalid_chars
    """
    invalid_chars = '\/:*?"<>|\r\n'
    return string.rstrip().translate(dict.fromkeys(map(ord, invalid_chars)))


def get_mp3_tags(src_path_filename):
    """
    Примимает имя mp3-файла и возвращает в виде строк теги названия, альбома и артиста
    Использует библиотеку eyed3
    """
    import eyed3

    eyed3.log.setLevel("ERROR")

    mp3title = mp3album = mp3artist = None

    mp3tag = eyed3.load(src_path_filename)

    if mp3tag.tag is None or mp3tag.tag.album is None or mp3tag.tag.artist is None:
        return mp3title, mp3album, mp3artist

    mp3title = remove_invalid_chars(mp3tag.tag.title).strip()
    mp3album = remove_invalid_chars(mp3tag.tag.album).strip()
    mp3artist = remove_invalid_chars(mp3tag.tag.artist).strip()

    return mp3title, mp3album, mp3artist


def move_files(source_path, target_path):
    """
    Перемещает файлы mp3 из исходного source_path в целевой каталог target_path
    """
    if not os.path.isabs(source_path):
        source_path = os.path.join(os.getcwd(), source_path)
        print(f'source_path={source_path}')
    if not os.path.isabs(target_path):
        target_path = os.path.join(os.getcwd(), target_path)
        print(f'target_path={target_path}')

    for root, _, files in os.walk(source_path):  # обработка каталога и подкаталогов
        for file in files:
            if file[-4:].lower() in EXT3:  # фильтр - только mp3
                src_path_filename = os.path.join(root, file)  # полный путь к файлу
                # mp3tag = eyed3.load(src_path_filename)
                # if not (mp3tag.tag is None) and not (mp3tag.tag.album is None) and not (mp3tag.tag.artist is None):
                #     if mp3tag.tag.title is None:
                #         mp3title = file
                #     else:
                #         mp3title = remove_invalid_chars(mp3tag.tag.title)
                #     mp3album, mp3artist = remove_invalid_chars(mp3tag.tag.album), remove_invalid_chars(
                #         mp3tag.tag.artist)
                mp3title, mp3album, mp3artist = get_mp3_tags(src_path_filename)

                if mp3artist is None or mp3album is None:   # если тэги артиста и альбома не заданы, файл пропускаем
                    continue

                if mp3title is None:    # если тэг трека не задан, используем имя файла
                    mp3title = file

                mp3_new_file_name = f'{mp3title} - {mp3artist} - {mp3album}.mp3'
                dst_path_filename = os.path.join(target_path, mp3artist, mp3album, mp3_new_file_name)
                print(f'{os.path.join(root, file)} -> {os.path.join(target_path, mp3_new_file_name)}')
                try:
                    os.renames(src_path_filename, dst_path_filename)
                except FileExistsError:  # только для windows: если файл существует
                    os.replace(src_path_filename, dst_path_filename)


if '__main__' in __name__:
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--src-dir', dest='srcdir', default=os.getcwd(), action=ReadableFolder,
                        help='source mp3-files folder')
    parser.add_argument('-d', '--dst-dir', dest='destdir', default=os.getcwd(), action=WritableFolder,
                        help='destination mp3-files folder')

    try:
        args = parser.parse_args()
    except argparse.ArgumentTypeError as err:
        print(err)
        sys.exit(-1)

    move_files(args.srcdir, args.destdir)

    print('Done.')
