class MetadataExtractor:
    def __init__(self, book):
        self.book = book

    def extract(self):
        metadata = {"creators": self.book.get_metadata("DC", "creator")[0][0] if len(
            self.book.get_metadata("DC", "creator")) > 0 else "",
                    "type": self.book.get_metadata("DC", "type")[0][0] if len(
                        self.book.get_metadata("DC", "type")) > 0 else "",
                    "title": str(self.book.get_metadata("DC", "title")[0][0]).capitalize() if len(
                        self.book.get_metadata("DC", "title")) > 0 else "",
                    "description": self.book.get_metadata("DC", "description")[0][0] if len(
                        self.book.get_metadata("DC", "description")) > 0 else "",
                    "language": self.book.get_metadata("DC", "language")[0][0] if len(
                        self.book.get_metadata("DC", "language")) > 0 else ""}

        return metadata
