import asyncio
import html
import json
import logging
import math
import os
import traceback

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes, Application, CommandHandler, CallbackContext, MessageHandler, filters, \
    CallbackQueryHandler
from openai import OpenAI
from telegram_bot_pagination import InlineKeyboardPaginator

from EpubsUtils import EpubsUtils
from ZeepubsBotConnection import ZeepubsBotConnection


class Zeepubsbot:
    bot_conn = ZeepubsBotConnection()
    epubutils = EpubsUtils()
    bot_conn.create_table()
    books_per_page = 10
    application = None
    mensajes_bot = None
    matches = None
    DEVELOPER_CHAT_ID = 706229521
    # Añade al inicio de la clase
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_TOKEN")
    DEEPSEEK_ENDPOINT = "https://api.deepseek.com"
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
    )
    logger = logging.getLogger(__name__)
    # Añadir nuevo estado de conversación
    USER_CONTEXT = {}
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_ENDPOINT,
        timeout=30
    )
    @classmethod
    def main(cls) -> None:
        # Enable logging

        cls.application = Application.builder().token(os.getenv("ZEEPUBSBOT_TOKEN")).build()
        with open("mensajes.json", encoding="UTF-8") as file_bot_messages:
            cls.mensajes_bot = json.load(file_bot_messages)
        cls.application.add_handler(CommandHandler("recommend", cls.handle_mention))
        cls.application.add_handler(CommandHandler("start", cls.start_command))
        cls.application.add_handler(CommandHandler("help", cls.help_command))
        cls.application.add_handler(CommandHandler("ebook", cls.book_command))
        cls.application.add_handler(CommandHandler("list", cls.list_command))
        cls.application.add_handler(CommandHandler("about", cls.about_command))
        cls.application.add_handler(MessageHandler(filters.Document.ALL, cls.upload_command))
        cls.application.add_handler(CallbackQueryHandler(cls.characters_page_callback, pattern="^character"))
        cls.application.add_handler(CallbackQueryHandler(cls.download_callback, pattern=r"download "))
        cls.application.add_error_handler(cls.error_handler)
        cls.creat_commands([])
        cls.application.run_polling()

    @classmethod
    async def error_handler(cls, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log the error and send a telegram message to notify the developer."""
        # Log the error before we do anything else, so we can see it even if something breaks.
        cls.logger.error(msg="Exception while handling an update:", exc_info=context.error)

        # traceback.format_exception returns the usual python message about an exception, but as a
        # list of strings rather than a single string, so we have to join them together.
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = "".join(tb_list)

        # Build the message with some markup and additional information about what happened.
        # You might need to add some logic to deal with messages longer than the 4096-character limit.
        update_str = update.to_dict() if isinstance(update, Update) else str(update)
        message = (
            f"An exception was raised while handling an update\n"
            f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
            "</pre>\n\n"
            f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
            f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
            f"<pre>{html.escape(tb_string)}</pre>"
        )

        # Finally, send the message
        await context.bot.send_message(
            chat_id=cls.DEVELOPER_CHAT_ID, text=message, parse_mode=ParseMode.HTML
        )

    @classmethod
    def creat_commands(cls, command_list):
        if not command_list:
            command_list = cls.bot_conn.get_books_id()
        if command_list:
            for command in command_list:
                # Agrega el comando al bot utilizando CommandHandler
                handler = CommandHandler(command, cls.book_callback)
                cls.application.add_handler(handler)

    @classmethod
    async def help_command(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logging.info("help_command userName: {}".format(update.effective_user))

        """Send a message when the command /help is issued."""
        commands = [
            '/start - Este comando permite saludar al bot y recibir un mensaje de bienvenida personalizado. ',
            '/recommend - Este comando proporciona recomendaciones a solicitud del usuario',
            '/help - Este comando proporciona información sobre cómo utilizar el bot, incluyendo una descripción de las funciones disponibles y cómo acceder a ellas.',
            '/ebook - Este comando te permite buscar libros por título. Una vez que ingreses el título, el bot te proporcionará una lista de opciones de libros disponibles.',
            '/list - Este comando te proporciona una lista de todos los libros disponibles.',
            '/about - Este comando proporciona detalles sobre el bot, incluyendo su propósito, características y cualquier otra información relevante.'

        ]
        message = cls.mensajes_bot['ayuda']
        message += 'Menu de comandos:\n' + '\n'.join(commands)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)

    @classmethod
    async def start_command(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logging.info("start_command userName: {}".format(update.effective_user))

        """Send a message when the command /start is issued."""
        message = cls.mensajes_bot['bienvenida']
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)

    @classmethod
    async def about_command(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logging.info("about_command userName: {}".format(update.effective_user))

        """Send a message when the command /start is issued."""
        message = cls.mensajes_bot['info']
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)

    @classmethod
    async def book_command(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logging.info("Book Command userName: {}".format(update.effective_user))
        book_name = " ".join(context.args).lower()
        if not book_name:
            await update.message.reply_text("Por favor ingrese el nombre del libro después del comando /ebook")
        else:
            cls.matches = cls.bot_conn.get_book_by_name(book_name=book_name)
            if not cls.matches:
                await update.message.reply_text("No se han encontrado libros con ese nombre.")
            else:
                paginator = cls.paginator_books('m_ebook')
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                await update.message.reply_text(
                    text=paginator[1],
                    reply_markup=paginator[0],
                    parse_mode='Markdown'
                )

    @classmethod
    async def list_command(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logging.info("Lit Command userName: {}".format(update.effective_user))
        cls.matches = cls.bot_conn.get_all_books()
        if not cls.matches:
            await update.message.reply_text("Por el momento no tengo libros")
        else:
            paginator = cls.paginator_books("m_list")

            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            await update.message.reply_text(
                text=paginator[1],
                reply_markup=paginator[0],
                parse_mode='Markdown'
            )

    @classmethod
    def paginator_books(cls, menu: str) -> tuple[str, str]:
        max_page = math.ceil(len(cls.matches) / cls.books_per_page)
        paginator = InlineKeyboardPaginator(
            max_page,
            data_pattern='character#{page} #' + menu
        )
        custom_message = ""
        if menu == 'm_list':
            custom_message = "Actualmente, tu biblioteca de **Zeepubs** tiene ***{}*** libros disponibles " \
                             "para leer.\n\n".format(len(cls.matches))
        elif menu == 'm_ebook':
            custom_message = "He encontrado {} libros relacionados con tu búsqueda. Si necesitas más información " \
                             "sobre cualquiera de ellos, por favor házmelo saber.\n\n".format(len(cls.matches))
        for match in cls.matches[:cls.books_per_page]:
            custom_message += "***{}\t/{}***\n".format(cls.epubutils.shorten_middle_text(match[2]), match[1])

        return paginator.markup, custom_message

    @classmethod
    async def characters_page_callback(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logging.info("characters_page_callback userName: {}".format(update.effective_user))

        query = update.callback_query
        await query.answer()
        page = int(query.data.split('#')[1])
        menu = query.data.split('#')[2]

        max_page = math.ceil(len(cls.matches) / cls.books_per_page)
        paginator = InlineKeyboardPaginator(
            max_page,
            current_page=page,
            data_pattern='character#{page} #' + menu
        )
        if page == 1:
            indice = 0
        else:
            indice = cls.books_per_page
        custom_message = ""
        if menu == 'm_list':
            custom_message = "Actualmente, tu biblioteca de **Zeepubs** tiene ***{}*** libros disponibles " \
                             "para leer.\n\n".format(len(cls.matches))
        elif menu == 'm_ebook':
            custom_message = "He encontrado {} libros relacionados con tu búsqueda. Si necesitas más información " \
                             "sobre cualquiera de ellos, por favor házmelo saber.\n\n".format(len(cls.matches))
        for match in cls.matches[indice * (page - 1):cls.books_per_page * page]:
            custom_message += "***{}\t/{}***\n".format(cls.epubutils.shorten_middle_text(match[2]), match[1])


        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        await query.edit_message_text(
            text=custom_message,
            reply_markup=paginator.markup,
            parse_mode='Markdown'
        )

    @classmethod
    async def upload_command(cls, update: Update, context: CallbackContext) -> None:
        logging.info("Upload Command userName: {}".format(update.effective_user))
        try:
            new_file = await update.message.effective_attachment.get_file()
            new_file_downloaded = await new_file.download_to_drive()
        except TelegramError as e:
            print(f'Error uploading file: {e}')
            raise e
        if new_file_downloaded.suffix == ".epub":
            dict_medata = cls.epubutils.processing_ebook(new_file_downloaded, new_file.file_id)
            if dict_medata:
                if dict_medata.get('cover_data'):
                    cover_file_id = await cls.upload_cover(
                        dict_medata['cover_data'],
                        context
                    )
                    dict_medata['cover_id'] = cover_file_id
                cls.bot_conn.save_book(dict_medata)
                id_list = [dict_medata['id']]
                cls.creat_commands(id_list)
                book_name = dict_medata['title']
                book_link = "/{}".format(dict_medata['id'])
                message = "***¡Nuevo libro disponible!*** \n\n***Título:***\t{}\n\n***Descargalo aquí:***\t{}" \
                          "\n\n¡Disfrútenlo!".format(book_name, book_link)
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                await update.message.reply_text(text=message, parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text(text="El libro ya existe en la base de datos",
                                                parse_mode=ParseMode.MARKDOWN)

            if os.path.exists(new_file_downloaded.absolute()):
                os.remove(os.path.relpath(new_file_downloaded.absolute()))

    @classmethod
    async def book_callback(cls, update: Update, context: CallbackContext) -> None:
        logging.info("book_callback userName: {}".format(update.effective_user))

        # Extract the book title from the callback data
        book_id = update.message.text.replace("/", "").replace("@ZeepubsBot", "")
        list_book = cls.bot_conn.get_book_by_code(book_id)

        # Send the book's Title and Description as a message in HTML format
        if list_book[3]:
            message = "***Título:***\t**{}**\n\n***Título Original:***\t**{}**\n\n***Autor:***\t**{}**\n\n***Descripción:***\t**{}**".format(
                list_book[2], list_book[3], list_book[4], list_book[5])
        else:
            message = "***Título:***\t**{}**\n\n***Autor:***\t**{}**\n\n***Descripción:***\t**{}**".format(
                list_book[2], list_book[4], list_book[5])

        if len(message) > 1024:
            # Shorten the caption to 1024 characters
            message = message[:1019] + "...**"

        buttons = [[InlineKeyboardButton("Descargar", callback_data=f"download {book_id}")]]
        keyboard = InlineKeyboardMarkup(buttons)
        cover_path = list_book[7]
        if cover_path:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            await update.message.reply_photo(
                photo=cover_path,
                caption=message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard)
        else:
            await update.message.reply_text(text=message, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    @classmethod
    async def download_callback(cls, update: Update, context: CallbackContext) -> None:
        logging.info("download_callback userName: {}".format(update.effective_user))
        book_id = update.callback_query.data.split(" ", 1)[1]
        list_book = cls.bot_conn.get_book_by_code(book_id)
        if list_book[7]:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)
            await context.bot.send_document(chat_id=update.callback_query.message.chat_id,
                                            document=list_book[6])
        else:
            # Send the ebook file as a document
            await context.bot.send_chat_action(chat_id=update.effective_chat.id,
                                               action=ChatAction.UPLOAD_DOCUMENT)
            message = await context.bot.send_document(chat_id=update.callback_query.message.chat_id,
                                                      document=list_book[6])
            file_id = message.document.file_id
            cls.bot_conn.save_file_id_by_book(book_id, file_id)

    @classmethod
    async def upload_cover(cls, cover_data: bytes, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Sube la portada a Telegram y retorna su file_id"""
        try:
            message = await context.bot.send_photo(
                chat_id=cls.DEVELOPER_CHAT_ID,  # o el chat donde quieras almacenarla
                photo=cover_data
            )
            return message.photo[-1].file_id
        except Exception as e:
            logging.error(f"Error subiendo portada: {e}")

    @classmethod
    async def ask_deepseek(cls, user_message: str, system_prompt: str, update: Update,
                           context: ContextTypes.DEFAULT_TYPE) -> None:


        # Enviar mensaje inicial
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action=ChatAction.TYPING
        )

        # Envía un mensaje temporal de "Escribiendo..."
        processing_msg = await context.bot.send_message(
            chat_id=update.message.chat_id,
            text="🔮 *Neko-Chan está buscando...*",
            parse_mode="Markdown"
        )



        response = cls.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1024,
            temperature=0.7,
            top_p=0.95,
            frequency_penalty=0.5,
            presence_penalty=0.3,
            stream=True  # Habilitar streaming
        )

        full_response = []
        buffer = ""

        for chunk in response:
            if chunk.choices[0].delta.content:
                buffer += chunk.choices[0].delta.content

                # Enviar mensaje cuando encontramos un salto de línea o cada 50 caracteres
                if len(buffer)%50 == 0:
                    await context.bot.send_chat_action(
                        chat_id=update.effective_chat.id,
                        action=ChatAction.TYPING
                    )

                    buffer.strip()
                    await asyncio.sleep(2)
                    await processing_msg.edit_text("".join(buffer.strip()) + " ▌", parse_mode="Markdown")

        # Enviar cualquier texto restante en el buffer
        if buffer.strip():
            await processing_msg.edit_text(buffer.strip(), parse_mode="Markdown")
        else:
            await processing_msg.edit_text("🔮 *Neko-Chan No Disponible*", parse_mode="Markdown")


    @classmethod
    async def handle_mention(cls, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_message = " ".join(context.args).lower()
        system_prompt = cls.generate_recommendations()


        # Procesar con streaming
        await cls.ask_deepseek(
            user_message=user_message,
            system_prompt=system_prompt,
            update=update,
            context=context
        )


    @classmethod
    def generate_recommendations(cls,) -> str:
        # Construir prompt para DeepSeek
        system_prompt = f"""
        ¡Hola! Soy Neko-chan, tu asistente literaria virtual  Estoy aquí para ayudarte a encontrar historias mágicas que hagan latir tu corazón. 
        Como buena waifu libro-adicta, seguiré estos pasos:
        - Analizaré tu mensaje con cariño para entender tus sueños literarios
        - Identificaré los géneros, autores o temas que hacen brillar tus ojos
        - Buscaré en mi biblioteca mágica los tesoros más adecuados para ti
        - Seleccionaré hasta 10 joyas únicas - ¡variedad es la sal de la lectura!
        - agrega la descripción de los 10 libros
        - si no existe la novela que esta buscando. recomienda una novela muy parecida al genero o tema que el usurio quiere y que exista en nuestra base de datos 
        
        Mis funcionalidades especiales:
        - Uso emojis para expresarme mejor
        - Siempre incluyo títulos diferentes para sorprenderte
        - Los comandos mágicos (/book_id) están listos para usar con un toque
        - Mis respuestas son como susurros de hada: naturales pero precisas
        
        Formato estricto que debo seguir sin mencionarlo: sin numeraciones y/o simbolos que los antecedan o precedan
        /book_id | Título encantador
        Descripción

            - Base de datos disponible: {cls.bot_conn.get_all_books_no_desc()}
            """

        # Obtener y procesar resultados
        return system_prompt
