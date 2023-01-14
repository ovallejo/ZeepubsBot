import json
import logging
import math
import os
import re

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction
from telegram.ext import ContextTypes, Application, CommandHandler, CallbackContext, MessageHandler, filters, \
    CallbackQueryHandler
from telegram_bot_pagination import InlineKeyboardPaginator

import epub_utils
from ZeepubsBotConnection import ZeepubsBotConnection


class Zeepubsbot:
    bot_conn = ZeepubsBotConnection()
    bot_conn.create_table()
    books_per_page = 5
    application = None
    mensajes_bot = None
    matches = None

    @classmethod
    def main(cls) -> None:
        # Enable logging
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
        )
        logger = logging.getLogger(__name__)
        cls.application = Application.builder().token(os.getenv("ZEEPUBSBOT_TOKEN")).build()
        with open("mensajes.json", encoding="UTF-8") as file_bot_messages:
            cls.mensajes_bot = json.load(file_bot_messages)
        cls.application.add_handler(CommandHandler("start", cls.start_command))
        cls.application.add_handler(CommandHandler("help", cls.help_command))
        cls.application.add_handler(CommandHandler("book", cls.book_command))
        cls.application.add_handler(CommandHandler("list", cls.list_command))
        handler_upload = MessageHandler(filters.Document.ALL, cls.upload_command)
        cls.application.add_handler(handler_upload)
        cls.application.add_handler(CallbackQueryHandler(cls.characters_page_callback, pattern="^character"))
        cls.application.add_handler(CallbackQueryHandler(cls.download_callback, pattern=r"download "))
        command_list = cls.bot_conn.get_books_id()
        if command_list:
            for command in command_list:
                # Agrega el comando al bot utilizando CommandHandler
                handler = CommandHandler(command, cls.book_callback)
                cls.application.add_handler(handler)
        else:
            logger.info("NO SE CARGARON LOS COMANDOS")
        cls.application.run_polling()



    @classmethod
    async def help_command(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /help is issued."""
        commands = [
            '/start - Saluda al bot y muestra un mensaje de bienvenida',
            '/help - Muestra un mensaje de ayuda',
            '/ebook - Busca libros por título y muestra una lista de opciones'
        ]
        message = cls.mensajes_bot['ayuda']
        message += 'Menu de comandos:\n' + '\n'.join(commands)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await update.message.reply_text(message, parse_mode="HTML")

    @classmethod
    async def start_command(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /start is issued."""
        message = cls.mensajes_bot['bienvenida']
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await update.message.reply_text(message, parse_mode="HTML")

    @classmethod
    async def book_command(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        book_name = " ".join(context.args).lower()
        if not book_name:
            await update.message.reply_text("Ingresa el nombre del libro.")
        else:
            cls.matches = cls.bot_conn.get_book_by_name(book_name=book_name)
            if not cls.matches:
                await update.message.reply_text("No se han encontrado libros con ese nombre.")
            else:
                max_page = math.ceil(len(cls.matches) / cls.books_per_page)
                paginator = InlineKeyboardPaginator(
                    max_page,
                    data_pattern='character#{page}'
                )
                custom_message = ""
                for match in cls.matches[:cls.books_per_page]:
                    custom_message += "{}\t/{}\n\n".format(match[2], match[1])

                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                await update.message.reply_text(
                    text=custom_message,
                    reply_markup=paginator.markup,
                    parse_mode='Markdown'
                )

    @classmethod
    async def list_command(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        cls.matches = cls.bot_conn.get_all_books()
        if not cls.matches:
            await update.message.reply_text("Por el momento no tengo libros")
        else:
            max_page = math.ceil(len(cls.matches) / cls.books_per_page)
            paginator = InlineKeyboardPaginator(
                max_page,
                data_pattern='character#{page}'
            )
            custom_message = ""
            for match in cls.matches[:cls.books_per_page]:
                custom_message += "{}\t/{}\n\n".format(match[2], match[1])

            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            await update.message.reply_text(
                text=custom_message,
                reply_markup=paginator.markup,
                parse_mode='Markdown'
            )

    @classmethod
    async def characters_page_callback(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        page = int(query.data.split('#')[1])

        max_page = math.ceil(len(cls.matches) / cls.books_per_page)
        paginator = InlineKeyboardPaginator(
            max_page,
            current_page=page,
            data_pattern='character#{page}'
        )
        custom_message = ""
        if page == 1:
            indice = 0
        else:
            indice = cls.books_per_page
        for match in cls.matches[indice * (page - 1):cls.books_per_page * page]:
            custom_message += "{}\t/{}\n\n".format(match[2], match[1])

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await query.edit_message_text(
            text=custom_message,
            reply_markup=paginator.markup,
            parse_mode='Markdown'
        )

    @classmethod
    async def upload_command(cls, update: Update, context: CallbackContext) -> None:
        new_file = await update.message.effective_attachment.get_file()
        new_file_downloaded = await new_file.download_to_drive()

        if new_file_downloaded.suffix == ".epub":
            file_path = os.path.relpath(new_file_downloaded)
            dict_medata = epub_utils.get_metadata(file_path)
            dict_medata['file_id'] = new_file.file_id
            if dict_medata:
                author_dir = re.sub(r'[^a-zA-Z0-9\s]', '', str(dict_medata['author']).lower())
                author_dir = re.sub('\\s', '_', author_dir)
                title = re.sub(r'[^a-zA-Z0-9\s]', '', str(dict_medata['title']).lower())
                title = re.sub('\\s', '_', title)
                ebook_path = "ebooks/{}/{}/{}.epub".format(author_dir, title, title)
                dict_medata['path'] = ebook_path
                cls.bot_conn.save_book(dict_medata)
                if not os.path.exists(ebook_path):
                    os.makedirs(os.path.dirname(ebook_path), exist_ok=True)
                    os.rename(new_file_downloaded.absolute(), os.path.relpath(ebook_path))
                    epub_utils.get_cover(ebook_path)
                    #             new_file_medata = epub_utils.get_metadata(ebook_path)
                    #             # books += [new_file_medata]
                    handler = CommandHandler(dict_medata['id'], cls.book_callback)
                    cls.application.add_handler(handler)

                    book_name = dict_medata['title']
                    book_author = dict_medata['author']
                    book_link = "/{}".format(dict_medata['id'])
                    message = "<b>¡Nuevo libro disponible!</b> \n\n<b>Título:</b>\t{}\n\n<b>Descargalo aquí:</b>\t{}\n\n¡Disfrútenlo!".format(
                        book_name, book_link)
                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                    await update.message.reply_text(text=message, parse_mode="HTML")

                else:
                    os.remove(os.path.relpath(new_file_downloaded.absolute()))
                    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                    await update.message.reply_text("Libro ya existe")
        else:
            if os.path.exists(new_file_downloaded.absolute()):
                os.remove(os.path.relpath(new_file_downloaded.absolute()))
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                await update.message.reply_text("El archivo no esta en formato EPUB")

    @classmethod
    async def book_callback(cls, update: Update, context: CallbackContext) -> None:
        # Extract the book title from the callback data
        book_id = update.message.text.replace("/", "").replace("@ZeepubsBot", "")
        list_book = cls.bot_conn.get_book_by_code(book_id)

        # Send the book's Title and Description as a message in HTML format
        if list_book:
            message = "<b>Título:</b>\t{}\n\n<b>Título Original:</b>\t{}\n\n<b>Autor:</b>\t{}\n\n<b>Descripción:</b>\t{}".format(
                list_book[2], list_book[3], list_book[4], list_book[5])
        else:
            message = "<b>Título:</b>\t{}\n\n<b>Autor:</b>\t{}\n\n<b>Descripción:</b>\t{}".format(
                list_book[2], list_book[4], list_book[5])

        if len(message) > 1024:
            # Shorten the caption to 1024 characters
            message = message[:1021] + "..."

        buttons = [[InlineKeyboardButton("Descargar", callback_data=f"download {book_id}")]]
        keyboard = InlineKeyboardMarkup(buttons)
        cover_path = f"{os.path.dirname(list_book[6])}/cover.jpg"
        if os.path.exists(cover_path):
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            await update.message.reply_photo(
                photo=f"{os.path.dirname(list_book[6])}/cover.jpg",
                caption=message,
                parse_mode="HTML",
                reply_markup=keyboard)
        else:
            await update.message.reply_text(text=message, parse_mode="HTML", reply_markup=keyboard)

    @classmethod
    async def download_callback(cls, update: Update, context: CallbackContext) -> None:
        book_id = update.callback_query.data.split(" ", 1)[1]
        list_book = cls.bot_conn.get_book_by_code(book_id)
        if list_book[7]:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)
            await context.bot.send_document(chat_id=update.callback_query.message.chat_id,
                                            document=list_book[7])
        else:
            # Send the ebook file as a document
            await context.bot.send_chat_action(chat_id=update.effective_chat.id,
                                               action=ChatAction.UPLOAD_DOCUMENT)
            message = await context.bot.send_document(chat_id=update.callback_query.message.chat_id,
                                                      document=list_book[6])
            file_id = message.document.file_id
            cls.bot_conn.save_file_id_by_book(book_id, file_id)
