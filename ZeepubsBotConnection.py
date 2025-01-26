import sqlite3
from typing import Any


class ZeepubsBotConnection:

    def __init__(self) -> None:
        self.conn = sqlite3.connect('books.db')
        self.cursor = self.conn.cursor()

    def create_table(self):
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY,
                    book_id TEXT,
                    title TEXT,
                    alt_title TEXT,
                    author TEXT,
                    description TEXT,
                    file_id TEXT,
                    cover_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
        except sqlite3.Error as e:
            print(f'Error creating table: {e}')
            raise e

    def close_connection(self):
        try:
            self.conn.close()
        except sqlite3.Error as e:
            print(f'Error closing connection: {e}')
            raise e

    def save_book(self, bdict_medata: dict):
        try:
            if not bdict_medata:
                raise ValueError("Invalid input data")

            self.cursor.execute('''
                INSERT INTO books (book_id, title, alt_title, author, description, file_id, cover_id)
                SELECT ?, ?, ?, ?, ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM books WHERE title = ?)
                ''', (bdict_medata['id'], bdict_medata['title'], bdict_medata['alt_title'], bdict_medata['author'],
                      bdict_medata['description'], bdict_medata['file_id'], bdict_medata['cover_id'],
                      bdict_medata['title']))
            self.conn.commit()

            self.cursor.execute('''
                    UPDATE books
                    SET book_id = ?, alt_title = ?, author = ?, description = ?, file_id = ?, cover_id = ?
                    WHERE title = ?
                    ''', (bdict_medata['id'], bdict_medata['alt_title'], bdict_medata['author'],
                          bdict_medata['description'], bdict_medata['file_id'], bdict_medata['cover_id'],
                          bdict_medata['title']))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f'Error saving file id: {e}')
            raise e
        except ValueError as e:
            print(f'Error: {e}')
            raise e

    def save_file_id_by_book(self, book_id: str, file_id: str):
        try:
            if not book_id or not file_id:
                raise ValueError("Invalid input data")

            self.cursor.execute('''
                UPDATE SET file_id = ?
                WHERE book_id = ?
            ''', (book_id, file_id))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f'Error saving file id: {e}')
            raise e
        except ValueError as e:
            print(f'Error: {e}')
            raise e

    def get_book_by_name(self, book_name: str) -> list[Any] | None:
        try:
            if not book_name:
                raise ValueError("Invalid input data")
            self.cursor.execute('''
                SELECT * FROM books WHERE title LIKE ? ORDER BY title
            ''', ('%' + book_name + '%',))
            result = self.cursor.fetchall()
            if result:
                return result
            else:
                return None
        except sqlite3.Error as e:
            print(f'Error getting file id: {e}')
            raise e
        except ValueError as e:
            print(f'Error: {e}')
            raise e

    def get_all_books(self) -> list[Any] | None:
        try:
            self.cursor.execute('''
                SELECT * FROM books ORDER BY title
            ''')
            result = self.cursor.fetchall()
            if result:
                return result
            else:
                return None
        except sqlite3.Error as e:
            print(f'Error getting file id: {e}')
            raise e
        except ValueError as e:
            print(f'Error: {e}')
            raise e

    def get_book_by_code(self, book_id: str) -> list[Any] | None:
        try:
            if not book_id:
                raise ValueError("Invalid input data")
            self.cursor.execute('''
                SELECT * FROM books WHERE book_id = ?
            ''', (book_id,))
            result = self.cursor.fetchone()
            if result:
                return result
            else:
                return None
        except sqlite3.Error as e:
            print(f'Error getting file id: {e}')
            raise e
        except ValueError as e:
            print(f'Error: {e}')
            raise e

    def get_books_id(self):
        try:
            self.cursor.execute('''
                SELECT book_id FROM books
            ''')
            result = self.cursor.fetchall()
            if result:
                return result
            else:
                return None
        except sqlite3.Error as e:
            print(f'Error getting file id: {e}')
            raise e
        except ValueError as e:
            print(f'Error: {e}')
            raise e

    def get_message_by_title(self, title: str) -> str | None:
        try:
            if not title:
                raise ValueError("Invalid input data")
            self.cursor.execute('''
                SELECT message FROM bot_messages WHERE title = ?
            ''', (title,))
            result = self.cursor.fetchone()
            if result:
                return result[0]
            else:
                return "None"
        except sqlite3.Error as e:
            print(f'Error getting bot message: {e}')
            raise e
        except ValueError as e:
            print(f'Error: {e}')
            raise e

    def get_all_books_no_desc(self) -> list[Any] | None:
        try:
            self.cursor.execute('''
                SELECT book_id, title FROM books ORDER BY title
            ''')
            result = self.cursor.fetchall()
            if result:
                return result
            else:
                return None
        except sqlite3.Error as e:
            print(f'Error getting file id: {e}')
            raise e
        except ValueError as e:
            print(f'Error: {e}')
            raise e