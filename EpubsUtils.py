import json
import os
import re
import secrets
from pathlib import Path
from typing import List, Dict, Any
from jsonpath_rw import jsonpath, parse

import requests
from tqdm import tqdm
import ebooklib
import isbnlib
from ebooklib import epub

from MetadataExtractor import MetadataExtractor
from ZeepubsBotConnection import ZeepubsBotConnection


class EpubsUtils:
    bot_conn = ZeepubsBotConnection()
    codes = set()

    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def get_cover(cls, epubfile: str) -> str:
        book = epub.read_epub(epubfile)
        root = os.path.dirname(epubfile)
        # Buscar la portada del libro (si existe)
        cover = None
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_COVER:
                cover = item.get_content()
                if cover:
                    with open(os.path.join(root, 'cover.jpg'), 'wb') as f:
                        f.write(cover)
        if not cover:
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_IMAGE and str(item.file_name).__contains__('cover'):
                    cover = item.get_content()
                    with open(os.path.join(root, 'cover.jpg'), 'wb') as f:
                        f.write(cover)
        return os.path.join(root, 'cover.jpg').replace("\\", "/")

    @classmethod
    def get_metadata(cls, epubfile: str) -> Dict[str, Any]:
        # Read the ePUB file
        book = epub.read_epub(epubfile)
        # Crear un conjunto para almacenar los códigos generados
        code = cls.create_book_id()
        extractor = MetadataExtractor(book)
        metadata = extractor.extract()
        alt_title = ""
        identifier_ebook = isbnlib.get_isbnlike(str(book.get_metadata('DC', 'identifier')))
        if identifier_ebook:
            list_isbn = isbnlib.editions(identifier_ebook[0], service='merge')
            for isbn in list_isbn:
                if isbnlib.is_isbn13(isbn):
                    meta_cloud = isbnlib.meta(isbn)
                    if str(isbn).startswith('9784') and meta_cloud and len(list_isbn) > 1:
                        alt_title = meta_cloud['Title']
                        break
                    else:
                        alt_title = meta_cloud['Title']

        else:
            vol_re = ""
            title_re = re.search(r'^(.*?)(?i)(?:vol(?:umen)?[\s.]*)', metadata['title']).group(1).strip()[:40]
            vol_re = re.search(r'(?i)(?:vol(?:umen)?[\s.]*)(\d+)', metadata['title'])
            isbn_cloud = isbnlib.isbn_from_words(title_re)

            if isbn_cloud:
                meta_cloud = isbnlib.meta(isbn_cloud)
                if meta_cloud:
                    title_cloud = re.sub(r'[0-9]', '', meta_cloud['Title'])
                    if vol_re:
                        alt_title = cls.find_google_books(title_cloud, vol_re.group(0))
                else:
                    alt_title = cls.find_google_books(metadata['title'], 0)

        metadata_dict = {"id": code, "title": metadata['title'], "alt_title": alt_title,
                         "language": metadata['language'], "type": metadata['type'], "author": metadata['creators'],
                         "description": metadata['description'], "path": os.path.relpath(epubfile)}

        # Iterate over the metadata items
        print(metadata_dict)
        return metadata_dict

    @classmethod
    def find_google_books(cls, title_cloud: str, vol_re: int):
        alt_title = ""
        api_key = 'AIzaSyC7ZzkkzEg9p8UXWY2u1LtMxfQ5qUDvkhQ'
        url = f'https://www.googleapis.com/books/v1/volumes?q=intitle:{title_cloud}&key={api_key}'
        response = requests.get(url)
        data = json.loads(response.text)
        jsonpath_expr = parse('$.items[*].volumeInfo.title')
        # Buscar el valor del títul
        result = jsonpath_expr.find(data)
        if vol_re > 0:
            for match in result:
                if re.search(rf'{vol_re}', match.value):
                    alt_title = match.value
        else:
            for match in result:
                if re.search(rf'{vol_re}', match.value):
                    alt_title = match.value
        return alt_title

    @classmethod
    def create_book_structure(cls, file_downloaded: Path, file_id: str) -> dict:
        file_path = os.path.relpath(file_downloaded)
        dict_medata = cls.get_metadata(file_path)
        if dict_medata:
            dict_medata['file_id'] = file_id
            dict_medata['author'] = cls.clean_string(dict_medata['author'])
            author = cls.path_format_string(dict_medata['author']).lower()
            dict_medata['title'] = cls.clean_string(dict_medata['title']).lower()
            title = cls.path_format_string(dict_medata['title'])

            ebook_path = "ebooks/{}/{}/{}.epub".format(author[:20], title, title)
            dict_medata['ebook_path'] = ebook_path
            if not os.path.exists(ebook_path):
                os.makedirs(os.path.dirname(ebook_path), exist_ok=True)
                os.rename(file_downloaded.absolute(), os.path.relpath(ebook_path))
                cover_path = cls.get_cover(ebook_path)
                dict_medata['cover_path'] = cover_path
            else:
                return {}
        return dict_medata

    @classmethod
    def clean_string(cls, raw_text: str):
        raw_text = re.sub(r"[^\w\s]", "", re.sub(r'[\(\[\{].*?[\)\]\}]', '', raw_text)) \
            .replace("  ", " ") \
            .replace("Volumen", "Vol.") \
            .strip()

        return raw_text

    @classmethod
    def path_format_string(cls, raw_text: str):
        raw_text = raw_text.replace(" ", "_").strip()  # Reemplaza espacios con "_"
        return raw_text

    @classmethod
    def get_epub_files(cls, directory: str) -> List[str]:
        epub_files = []  # List to store the paths of the ePUB files
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(".epub"):
                    epub_files.append(os.path.join(root, file))
        return epub_files

    @classmethod
    def shorten_middle_text(cls, raw_text: str) -> str:
        if len(raw_text) > 40:
            return raw_text[:20] + "..." + raw_text[-20:]
        else:
            return raw_text

    @classmethod
    def main(cls) -> None:
        metadata_aux = []
        epub_lis = cls.get_epub_files("ebooks")
        for i, epub_file in enumerate(tqdm(epub_lis, desc="Procesando Libros", ascii="|/-\\", ncols=100,
                                           bar_format='{l_bar}{bar} {n}/{total}')):
            metadata_aux.append(cls.get_metadata(epub_file))
            cls.get_cover(epub_file)
        with open("ebooks/metadata.json", "w", encoding='UTF-8') as f:
            json.dump(metadata_aux, f)

    @classmethod
    def create_book_id(cls) -> str:
        while True:
            code = secrets.token_hex(5)
            if code not in cls.codes:
                cls.codes.add(code)
                break
        return code
