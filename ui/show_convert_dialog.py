import os
import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QProgressBar, QTextEdit, QApplication
)
from core.convert_thread import ConvertThread

class ConvertDialog(QDialog):
    def __init__(self, parent=None, default_ts_path=""):
        super().__init__(parent)
        self.default_ts_path = default_ts_path
        self.convert_thread = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("转换为其他格式")
        self.resize(750, 320)

        # 整体垂直布局
        layout = QVBoxLayout(self)

        # 选择文件标签和输入框
        label = QLabel("请选择要转换的 TS 文件：", self)
        layout.addWidget(label)

        self.file_input = QLineEdit(self)
        self.file_input.setText(self.default_ts_path)
        layout.addWidget(self.file_input)

        # 进度条
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # 日志框
        self.log_box = QTextEdit(self)
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)

        # 按钮水平布局
        button_layout = QHBoxLayout()

        self.select_button = QPushButton("选择其他文件", self)
        self.to_mp4_button = QPushButton("转换为mp4", self)
        self.to_mkv_button = QPushButton("转换为mkv", self)  # 原代码笔误写的rmvb，实际是mkv
        self.cancel_button = QPushButton("取消转码", self)
        self.close_button = QPushButton("关闭", self)

        button_layout.addWidget(self.select_button)
        button_layout.addWidget(self.to_mp4_button)
        button_layout.addWidget(self.to_mkv_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

        # 绑定按钮事件
        self.select_button.clicked.connect(self.select_other_file)
        self.to_mp4_button.clicked.connect(lambda: self.start_convert("mp4"))
        self.to_mkv_button.clicked.connect(lambda: self.start_convert("mkv"))
        self.cancel_button.clicked.connect(self.cancel_convert)
        self.close_button.clicked.connect(self.close_dialog)

        # 初始化按钮状态
        self.set_convert_buttons_running(False)

    def append_log(self, message):
        """追加日志到日志框"""
        self.log_box.append(str(message))

    def set_convert_buttons_running(self, running):
        """设置转换相关按钮状态"""
        self.select_button.setEnabled(not running)
        self.to_mp4_button.setEnabled(not running)
        self.to_mkv_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)

    def select_other_file(self):
        """选择要转换的TS文件"""
        current_file = self.file_input.text().strip()
        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "选择TS文件",
            current_file if current_file else "",
            "TS文件 (*.ts);;所有文件 (*)"
        )
        if selected_file:
            self.file_input.setText(selected_file)

    def start_convert(self, target_ext):
        """开始格式转换"""
        input_file = self.file_input.text().strip()

        if not input_file:
            QMessageBox.information(self, "提示", "请先选择一个 TS 文件。")
            return

        if not os.path.exists(input_file):
            QMessageBox.information(self, "提示", f"文件不存在：\n{input_file}")
            return

        # 生成输出文件路径
        base_name = os.path.splitext(input_file)[0]
        output_file = f"{base_name}.{target_ext}"

        # 重置进度条和日志
        self.progress_bar.setValue(0)
        self.log_box.clear()

        # 创建并启动转换线程
        self.convert_thread = ConvertThread(input_file, output_file)
        self.convert_thread.log_signal.connect(self.append_log)
        self.convert_thread.progress_signal.connect(self.progress_bar.setValue)
        self.convert_thread.finished_signal.connect(self.on_convert_finished)

        self.set_convert_buttons_running(True)
        self.convert_thread.start()

    def cancel_convert(self):
        """取消转换"""
        if self.convert_thread and self.convert_thread.isRunning():
            self.convert_thread.stop()

    def close_dialog(self):
        """关闭对话框"""
        if self.convert_thread and self.convert_thread.isRunning():
            QMessageBox.information(self, "提示", "当前正在转码，请先取消转码。")
            return
        self.accept()

    def on_convert_finished(self, success, message):
        """转换完成回调"""
        self.set_convert_buttons_running(False)
        if success:
            QMessageBox.information(self, "提示", f"转换成功！\n输出文件：\n{message}")
        else:
            QMessageBox.critical(self, "错误", message)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    ll = "downloads\电影名"

    dialog = ConvertDialog(default_ts_path=ll)
    dialog.show()
    sys.exit(app.exec_())