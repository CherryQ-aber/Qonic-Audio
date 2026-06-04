import unittest


class ImportSmokeTests(unittest.TestCase):

    def test_gui_import(self):
        import gui

        self.assertTrue(hasattr(gui, "MainWindow"))


if __name__ == "__main__":
    unittest.main()
