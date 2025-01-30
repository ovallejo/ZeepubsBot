import os
import re
import secrets
from pathlib import Path
from typing import List, Dict, Any

import ebooklib
import isbnlib
from ebooklib import epub

from ZeepubsBotConnection import ZeepubsBotConnection


class EpubsUtils:
    bot_conn = ZeepubsBotConnection()
    codes = set()

    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def get_cover(cls, epubfile: str) -> bytes:
        book = epub.read_epub(epubfile)
        # Buscar la portada
        cover = None
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_COVER:
                cover = item.get_content()
                if cover:
                    return cover
        # Si no se encuentra ITEM_COVER, buscar imagen con 'cover' en el nombre
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_IMAGE and "cover" in item.file_name.lower():
                return item.get_content()
        return None  # Si no hay portada

    @classmethod
    def get_metadata(cls, epubfile: str) -> Dict[str, Any]:
        # Read the ePUB file
        book = epub.read_epub(epubfile)
        # Crear un conjunto para almacenar los códigos generados
        code = cls.create_book_id()
        creator_metadata = book.get_metadata("DC", "creator")
        creators = creator_metadata[0][0]
        # Obtener la lista de metadatos de título
        type_metadata = book.get_metadata("DC", "type")
        # Verificar si la lista no está vacía
        if type_metadata:
            # Obtener el valor del primer metadato de título
            type_value = type_metadata[0][0]
        else:
            type_value = ""

        title_metadata = book.get_metadata("DC", "title")
        if title_metadata:
            title_metadata = title_metadata[0][0]
        else:
            title_metadata = ""

        description_metadata = book.get_metadata("DC", "description")
        if description_metadata:
            description_metadata = description_metadata[0][0]
        else:
            description_metadata = ""

        language_metadata = book.get_metadata("DC", "language")
        if language_metadata:
            language_metadata = language_metadata[0][0]
        else:
            language_metadata = ""
        alt_title = ""
        for item in book.get_metadata('DC', 'identifier'):
            item_str = str(item[0])
            if item_str.__contains__('isbn'):
                isbn = item_str.replace("isbn:", "").replace("urn:", "").replace("-", "")
                if isbnlib.is_isbn13(isbn):
                    meta_cloud = isbnlib.meta(isbn)
                    alt_title = meta_cloud.get('Title', "")
        title_metadata = re.sub(r"\[.*?\]", "", title_metadata).strip()
        title_metadata = re.sub(r"\(.*?\)", "", title_metadata).strip()
        title_metadata = title_metadata.replace("Volumen", "Vol. ").strip()
        description_metadata = re.sub(r"\<.*?\>", "", description_metadata)

        # Create a dictionary to store the metadata
        metadata_dict = {"id": code, "title": title_metadata, "alt_title": alt_title,
                         "language": language_metadata, "type": type_value, "author": creators,
                         "description": description_metadata}

        # Iterate over the metadata items

        return metadata_dict

    @classmethod
    def processing_ebook(cls, file_downloaded: Path, file_id: str) -> dict:
        file_path = os.path.relpath(file_downloaded)
        dict_medata = cls.get_metadata(file_path)
        cover_data = cls.get_cover(file_path)  # Ahora obtiene bytes

        if dict_medata:
            dict_medata['file_id'] = file_id
            dict_medata['author'] = cls.clean_string(dict_medata['author'])
            dict_medata['title'] = cls.clean_string(dict_medata['title']).lower()
            dict_medata['cover_data'] = cover_data  # Añadir datos binarios
        return dict_medata if dict_medata else {}

    @classmethod
    def clean_string(cls, raw_text: str):
        raw_text = re.sub(r"[^\w\s]", "", raw_text)  # Elimina caracteres especiales
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
    def create_book_id(cls) -> str:
        while True:
            code = secrets.token_hex(5)
            if code not in cls.codes:
                cls.codes.add(code)
                break
        return code
