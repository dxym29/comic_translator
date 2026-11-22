import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import storage


class StorageTests(unittest.TestCase):
    def test_database_initializes_tables(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict("os.environ", {"COMIC_TRANSLATOR_DATA_DIR": temp}):
                storage.initialize_database()
                with storage.connect() as db:
                    names = {
                        row["name"]
                        for row in db.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        ).fetchall()
                    }
                self.assertTrue({"projects", "chapters", "pages", "text_regions", "jobs"} <= names)

    def test_data_directories_are_created(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "app-data"
            with patch.dict("os.environ", {"COMIC_TRANSLATOR_DATA_DIR": str(root)}):
                result = storage.get_data_dir()
                self.assertTrue((result / "projects").is_dir())
                self.assertTrue((result / "cache").is_dir())


if __name__ == "__main__":
    unittest.main()
