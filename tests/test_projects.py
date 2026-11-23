import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.projects import create_project, get_project, list_projects
from backend.main import projects_delete
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


    def test_delete_project_removes_its_folder_and_database_row(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict("os.environ", {"COMIC_TRANSLATOR_DATA_DIR": temp}):
                initialize_database()
                project = create_project(name="Delete Me")
                project_dir = Path(project["storage_path"])
                self.assertTrue(project_dir.exists())
                result = projects_delete(project["id"])
                self.assertTrue(result["deleted"])
                self.assertIsNone(get_project(project["id"]))
                self.assertFalse(project_dir.exists())


if __name__ == "__main__":
    unittest.main()
