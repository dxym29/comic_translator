import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.projects import create_project, get_project, list_projects
from backend.storage import initialize_database


class ProjectTests(unittest.TestCase):
    def test_create_and_list_project(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict("os.environ", {"COMIC_TRANSLATOR_DATA_DIR": temp}):
                initialize_database()
                project = create_project(
                    name="Demo Comic",
                    source_language="English",
                    target_language="Myanmar",
                    typesetting_style="professional",
                    font_family="Noto Sans Myanmar",
                )
                self.assertEqual(project["name"], "Demo Comic")
                self.assertEqual(get_project(project["id"])["id"], project["id"])
                self.assertEqual(len(list_projects()), 1)
                root = Path(project["storage_path"])
                self.assertTrue((root / "project.json").is_file())
                for folder in ("source", "cleaned", "rendered", "exports"):
                    self.assertTrue((root / folder).is_dir())


if __name__ == "__main__":
    unittest.main()
