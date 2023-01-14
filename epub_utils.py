import json
import os
import re
import secrets
from typing import List, Dict, Any
from tqdm import tqdm
import ebooklib
import isbnlib
from ebooklib import epub


def get_cover(epubfile: str):
    book = epub.read_epub(epubfile)
    root = os.path.dirname(epubfile)
    # Buscar la portada del libro (si existe)
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_COVER:
            cover = item.get_content()
            with open(os.path.join(root, 'cover.jpg'), 'wb') as f:
                f.write(cover)
            break


def get_metadata(epubfile: str) -> Dict[str, Any]:
    # Read the ePUB file
    book = epub.read_epub(epubfile)
    # Crear un conjunto para almacenar los códigos generados
    codes = set()
    while True:
        code = secrets.token_hex(5)
        if code not in codes:
            codes.add(code)
            break
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
    title_metadata = re.sub(r"\[.*?\]", "", title_metadata)
    title_metadata = re.sub(r"\(.*?\)", "", title_metadata)
    title_metadata = title_metadata.replace("Volumen", "Vol. ")
    description_metadata = re.sub(r"\<.*?\>", "", description_metadata)

    # Create a dictionary to store the metadata
    metadata_dict = {"id": code, "title": title_metadata, "alt_title": alt_title,
                     "language": language_metadata, "type": type_value, "author": creators,
                     "description": description_metadata, "path": os.path.relpath(epubfile)}

    # Iterate over the metadata items

    return metadata_dict


def get_epub_files(directory: str) -> List[str]:
    epub_files = []  # List to store the paths of the ePUB files
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".epub"):
                epub_files.append(os.path.join(root, file))
    return epub_files


def main():
    metadata_aux = []
    epub_lis = get_epub_files("ebooks")
    for i, epub_file in enumerate(tqdm(epub_lis, desc="Procesando Libros", ascii="|/-\\", ncols=100,
                                       bar_format='{l_bar}{bar} {n}/{total}')):
        metadata_aux.append(get_metadata(epub_file))
        get_cover(epub_file)
    with open("ebooks/metadata.json", "w", encoding='UTF-8') as f:
        json.dump(metadata_aux, f)


if __name__ == "__main__":
    main()
