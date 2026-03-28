import sys
from PyQt5.QtWidgets import QApplication

from ui.main_window import M3U8Downloader



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = M3U8Downloader()
    window.show()
    sys.exit(app.exec_())


