import os
from PyQt5.QtWidgets import ( QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox,QTextEdit, QProgressBar)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QDialog, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt
import subprocess
import sys


from core.convert_thread import ConvertThread
from core.downlod_thread import DownloadThread
from utils.configs import (DEFAULT_MAX_WORKERS,\
                           DEFAULT_LOG_UPDATE_FREQ, DEFAULT_WINDOW_HEIGHT, \
                            DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_Y, DEFAULT_WINDOW_X)
from utils.configs import resource_path
from ui.show_list_dialog import SupportListDialog
from ui.show_convert_dialog import ConvertDialog
from ui.show_speed_dialog import SpeedDialog

class M3U8Downloader(QWidget):  #界面部分
    def __init__(self):
        super().__init__()
        self.max_workers = DEFAULT_MAX_WORKERS                #最大同时下载片量
        self.log_update_freq = DEFAULT_LOG_UPDATE_FREQ        #每n次更新下载log
        self.support_list_file =  resource_path("resources/supported_m3u8_list.txt")          #读取支持的网址列表
        self.download_finished = False  #下载完成flag
        self.current_output_dir = ""    #当前下载的路径
        self.init_ui()                  #初始化UI

    def init_ui(self):
        self.setWindowTitle('M3U8下载器')
        self.setWindowIcon(QIcon(resource_path("resources/logo.png")))   # 将 'logo.png' 替换为你的图标文件路径

        self.setGeometry(DEFAULT_WINDOW_X, DEFAULT_WINDOW_Y, DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)  #窗口的初始大小(x, y, width, height)
        font_label = QFont('Arial', 12)              #label字体设置为 Arial，大小为 12
        font_input = QFont('Arial', 13)              #QLineEdit字体设置为 Arial，大小为 12
        font_button = QFont('Arial', 12)             #button字体设置为 Arial，大小为 12
        font_log = QFont('Arial', 11)                #QTextEdit字体设置为 Arial，大小为 12


        # 0 整体布局（垂直）
        all_layout = QVBoxLayout()

        #1 网格布局
        grid_layout= QGridLayout()

        # 1.1 M3U8 URL 输入框
        self.url_label = QLabel('请输入M3U8 Url地址',self)
        self.url_label.setFont(font_label)
        self.url_label.setAlignment(Qt.AlignCenter)  # 设置水平和垂直居中
        self.url_input = QLineEdit(self)
        self.url_input.setText("")  #默认内容
        grid_layout.addWidget(self.url_label, 1, 0)  # row 1， column 0
        grid_layout.addWidget(self.url_input, 1, 1)  # row 1， column 1
        # 1.2 M3U8 对应的 referer网址 输入框（该输入栏可不用判别是否输入）
        self.refer_label = QLabel('请输入Referer地址', self)
        self.refer_label.setFont(font_label)
        self.refer_label.setAlignment(Qt.AlignCenter)  # 设置水平和垂直居中
        self.referer_url_input = QLineEdit(self)
        self.referer_url_input.setText("")  # 默认内容
        grid_layout.addWidget(self.refer_label, 2, 0)  # row 1， column 0
        grid_layout.addWidget(self.referer_url_input, 2, 1)  # row 1， column 1
        # 1.2 输出目录输入框
        self.dir_input = QLineEdit(self)
        self.dir_input.setText("downloads/电影名/ts")          #默认内容
        self.select_dir_button = QPushButton("选择存放ts分片的路径", self)
        self.select_dir_button.clicked.connect(self.select_ts_dir)
        grid_layout.addWidget(self.select_dir_button, 3, 0)  # row 2， column 0
        grid_layout.addWidget(self.dir_input, 3, 1)          # row 2， column 1
        # 1.3 输出文件输入框
        self.file_input = QLineEdit(self)
        self.file_input.setText("downloads/电影名/movies.ts")    #默认内容
        self.select_file_button = QPushButton("选择ts融合文件的路径", self)
        self.select_file_button.clicked.connect(self.select_output_file)
        grid_layout.addWidget(self.select_file_button, 4 ,0) # row 3， column 0
        grid_layout.addWidget(self.file_input, 4, 1)         # row 3， column 1

        all_layout.addLayout(grid_layout)


        # 2 提示布局
        button_tips_layout = QHBoxLayout()
        # 2.1 提示按钮
        self.download_tips_button = QPushButton('下载url提示', self)
        self.download_tips_button.clicked.connect(self.show_tip_message)
        button_tips_layout.addWidget(self.download_tips_button)
        # 2.2 列表按钮
        self.list_button = QPushButton('示例网址', self)
        self.list_button.clicked.connect(self.show_list_dialog)
        button_tips_layout.addWidget(self.list_button)
        # 2.3 打开下载目录按钮
        self.open_dir_button = QPushButton('打开下载目录', self)
        self.open_dir_button.clicked.connect(self.open_download_dir)
        button_tips_layout.addWidget(self.open_dir_button)
        # 2.4 视频格式转换按钮
        self.convert_button = QPushButton('视频格式转换', self)
        self.convert_button.clicked.connect(self.show_convert_dialog)
        button_tips_layout.addWidget(self.convert_button)

        all_layout.addLayout(button_tips_layout)  # 将提示按钮水平布局添加到主布局中


        # 3 日志log框（QTextEdit）
        self.log_box = QTextEdit(self)
        self.log_box.setReadOnly(True)  # 设置为只读
        self.log_box.setPlaceholderText("下载中的日志将会显示在这里")
        all_layout.addWidget(self.log_box)

        # 4 进度条框
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        all_layout.addWidget(self.progress_bar)

        # 5 水平按钮布局
        button_layout = QHBoxLayout()
        # 5.1 下载按钮
        self.download_button = QPushButton('开始下载', self)
        self.download_button.clicked.connect( self.download )
        button_layout.addWidget(self.download_button)

        # 5.2 暂停按钮
        self.pause_button = QPushButton('暂停下载', self)
        self.pause_button.clicked.connect( self.pause_download )
        button_layout.addWidget(self.pause_button)

        # 5.3 恢复按钮
        self.resume_button = QPushButton('继续下载', self)
        self.resume_button.clicked.connect( self.resume_download )
        button_layout.addWidget(self.resume_button)

        # 5.4 中断按钮
        self.stop_button = QPushButton('中断下载', self)
        self.stop_button.clicked.connect( self.stop_download )
        button_layout.addWidget(self.stop_button)

        # 5.5 清空日志按钮
        self.clear_log_button = QPushButton('清空日志', self)
        self.clear_log_button.clicked.connect(self.clear_log)
        button_layout.addWidget(self.clear_log_button)

        # 5.6 导出日志按钮
        self.export_log_button = QPushButton('导出日志', self)
        self.export_log_button.clicked.connect(self.export_log)
        button_layout.addWidget(self.export_log_button)

        # 5.7 清空单独ts文件按钮
        self.clean_ts_button = QPushButton('清理ts文件', self)
        self.clean_ts_button.clicked.connect(self.clean_ts_files)
        button_layout.addWidget(self.clean_ts_button)

        #5.8 调速按钮
        self.speed_button = QPushButton('调速设置', self)
        self.speed_button.clicked.connect(self.show_speed_dialog)
        button_layout.addWidget(self.speed_button)

        all_layout.addLayout(button_layout)  # 将按钮水平布局添加到主布局中


        #6 设置字体大小
        #给所有按钮统一字体大小
        buttons = [
            self.download_button,
            self.pause_button,
            self.resume_button,
            self.stop_button,
            self.clear_log_button,
            self.select_dir_button,
            self.select_file_button,
            self.list_button,
            self.download_tips_button,
            self.clean_ts_button,
            self.speed_button,
            self.export_log_button,
            self.open_dir_button,
            self.convert_button
        ]
        for btn in buttons:
            btn.setFont(font_button)

        #给所有输入框统一字体大小
        self.url_input.setFont(font_input)
        self.referer_url_input.setFont(font_input)
        self.dir_input.setFont(font_input)
        self.file_input.setFont(font_input)

        #给日志框设置大小
        self.log_box.setFont(font_log)

        self.setLayout(all_layout)
        self.update_button_states("idle")


    # 1.2 选择存放ts分片路径 槽函数
    def select_ts_dir(self):
        current_dir = self.dir_input.text().strip()
        directory = QFileDialog.getExistingDirectory(
            self,  "选择ts存放目录",  current_dir if current_dir else "")

        if directory:
            self.dir_input.setText(directory)

    # 1.3 选择存放输出文件路径 槽函数
    def select_output_file(self):
        current_file = self.file_input.text().strip()
        file_path, _ = QFileDialog.getSaveFileName(
            self,  "选择输出文件",  current_file if current_file else "", "TS文件 (*.ts);;所有文件 (*)" )

        if file_path:
            self.file_input.setText(file_path)


    # 2.1 下载url提示-槽函数
    def show_tip_message(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("下载提示")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setText("")

        label = QLabel(
            "！！！非自动化下载，需要自己找到m3u8的url才可进行下载！！！\n"
            "1 refer是直接复制视频播放的网址url；\n"
            "2 m3u8 url需要定位到正确的m3u8资源url：\n"
            "（1）网页右键->检查->网络中定位到相关url\n"
            "3 部分网址可能没有这种url资源\n"
            "4 可查看右边支持的部分网址列表"
        )
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setFixedWidth(550)  # 这里直接控制文本区域宽度

        layout = msg.layout()
        layout.addWidget(label, 0, 1, 1, layout.columnCount())
        msg.exec_()

    # 2.2 支持列表的示例网址-槽函数
    def show_list_dialog(self):
        dialog = SupportListDialog(self, self.support_list_file)
        dialog.exec_()

    # 2.3 打开下载目录-槽函数
    def open_download_dir(self):
        path = self.file_input.text().strip()
        if not path:
            self.show_message("提示", "当前没有输出文件路径。")
            return

        folder = os.path.dirname(path)
        if not folder:
            self.show_message("提示", "无法确定下载目录。")
            return

        folder = os.path.abspath(folder)
        if not os.path.exists(folder):
            self.show_message("提示", f"目录不存在：\n{folder}")
            return

        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            self.show_message("错误", f"打开目录失败：{e}")

    # 2.4 视频格式转换-槽函数
    def show_convert_dialog(self):
        default_ts_path = self.file_input.text().strip()
        dialog = ConvertDialog(self, default_ts_path)
        dialog.exec_()


    # 3 日志框-槽函数
    def log(self,message):
        self.log_box.append( str(message) )


    # 4 更新进度条-槽函数
    def update_progress(self, value):
        self.progress_bar.setValue(value)


    # 5.1 开始下载-槽函数
    def download(self):
        m3u8_url = self.url_input.text()
        refer_url = self.referer_url_input.text()
        output_dir = self.dir_input.text()
        output_file = self.file_input.text()
        self.log("当前的m3u8 url地址： "+m3u8_url)
        self.log("当前的下载路径： "+ output_dir)
        self.log("当前的输出文件： "+ output_file)

        # 验证输入、输出视频地址是否为空
        if not m3u8_url or not output_dir or not output_file:
            self.show_message("错误", "存在为空的内容，请填写！")
            return
        # 验证是否已经有--下载线程
        if hasattr(self, 'download_thread') and self.download_thread.isRunning():
            self.show_message("提示", "下载任务已在进行中！\n不要重复点击下载！")
            return

        self.progress_bar.setValue(0)
        self.download_finished = False
        self.current_output_dir = output_dir
        self.update_button_states("downloading")

        # 创建并启动下载线程
        self.download_thread = DownloadThread(m3u8_url, output_dir, output_file, self.max_workers, self.log_update_freq, refer_url)
        self.download_thread.logText_signal.connect( self.log )
        self.download_thread.progress_signal.connect( self.update_progress )
        self.download_thread.finished_signal.connect( self.on_download_finished )
        self.download_thread.start()

    # 5.2 暂停下载-槽函数
    def pause_download(self):
        if hasattr(self, 'download_thread') and self.download_thread.isRunning() :
            self.download_thread.pause()
            self.log("下载已暂停...")
            self.update_button_states("paused")
        else:
            self.log("当前没有正在运行的下载任务!")

    # 5.3 继续下载-槽函数
    def resume_download(self):
        if hasattr(self, 'download_thread'):
            self.download_thread.resume()
            self.log("下载已恢复...")
            self.update_button_states("downloading")

    # 5.4 中断下载-槽函数
    def stop_download(self):
        if hasattr(self, 'download_thread'):
            self.download_thread.stop()
            self.log("下载已中断！")
            self.progress_bar.setValue(0)
            self.update_button_states("stopped")

    # 5.5 清理日志-槽函数
    def clear_log(self):
        self.log_box.clear()
        self.progress_bar.setValue(0)

    # 5.6 输出日志 槽函数
    def export_log(self):
        log_text = self.log_box.toPlainText().strip()
        if not log_text:
            self.show_message("提示", "当前没有日志内容可导出！")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出日志",
            "resources/download_log.txt",
            "文本文件 (*.txt);;所有文件 (*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(log_text)
            self.show_message("提示", f"日志已成功导出到：\n{file_path}")
        except Exception as e:
            self.show_message("错误", f"导出日志失败：{e}")

    # 5.7 清理ts文件-槽函数
    def clean_ts_files(self):
        if not hasattr(self, 'download_thread'):
            self.show_message("提示", "没有下载任务！")
            return

        if not self.download_finished:
            self.show_message("提示", "未下载完成，暂不能清理 ts 文件！")
            return

        if not self.current_output_dir or not os.path.isdir(self.current_output_dir):
            self.show_message("提示", "ts 文件目录不存在，无法清理！")
            return

        reply = QMessageBox.question(
            self, "确认清理", "是否清理单独的 ts 文件？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            deleted_count = 0
            failed_files = []

            for name in os.listdir(self.current_output_dir):
                if name.lower().endswith(".ts"):
                    file_path = os.path.join(self.current_output_dir, name)
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                    except Exception as e:
                        failed_files.append((file_path, str(e)))

            if failed_files:
                self.log(f"已删除 {deleted_count} 个 ts 文件，但有 {len(failed_files)} 个删除失败。")
                for file_path, err in failed_files:
                    self.log(f"删除失败: {file_path}, 错误: {err}")
                self.show_message("提示", f"已删除 {deleted_count} 个 ts 文件，但部分文件删除失败。")
            else:
                self.log(f"已成功清理 {deleted_count} 个 ts 文件。")
                self.show_message("提示", f"已成功清理 {deleted_count} 个 ts 文件。")
        else:
            self.log("已取消清理 ts 文件。")

    # 5.8 调速设置对话框槽函数
    def show_speed_dialog(self):
        dialog = SpeedDialog(parent=self, max_workers=self.max_workers, log_update_freq=self.log_update_freq)
        dialog.exec_()

    #下载完成标志
    def on_download_finished(self, success):
        self.download_finished = success
        self.clean_ts_button.setEnabled(success)

        if success:
            self.log("下载任务已完成，可清理 ts 临时文件。")
            self.update_button_states("finished")
        else:
            self.log("下载任务未完整完成，暂不可清理 ts 临时文件。")
            self.update_button_states("stopped")


    def show_message(self, title, message):
        QMessageBox.information(self, title, message)


    #4个下载按钮状态切换函数
    def update_button_states(self, state):
        """
        state:
            idle         初始/可开始下载
            downloading  下载中
            paused       已暂停
            finished     已完成
            stopped      已中断/失败后回到可下载状态
        """

        if state == "idle":
            self.download_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(False)
            self.stop_button.setEnabled(False)
        elif state == "downloading":
            self.download_button.setEnabled(False)
            self.pause_button.setEnabled(True)
            self.resume_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        elif state == "paused":
            self.download_button.setEnabled(False)
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(True)
            self.stop_button.setEnabled(True)
        elif state == "finished":
            self.download_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(False)
            self.stop_button.setEnabled(False)
        elif state == "stopped":
            self.download_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.resume_button.setEnabled(False)
            self.stop_button.setEnabled(False)


# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#     window = M3U8Downloader()
#     window.show()
#     sys.exit(app.exec_())


