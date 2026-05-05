# ui/speed_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt

class SpeedDialog(QDialog):
    def __init__(self, parent=None, max_workers=None, log_update_freq=None):
        super().__init__(parent)
        self.parent = parent
        self.max_workers = max_workers
        self.log_update_freq = log_update_freq
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("调速设置")
        self.resize(350, 220)
        self.setModal(True)  # 模态对话框

        # 主布局
        layout = QVBoxLayout(self)

        # 最大同时下载片量
        label1 = QLabel("最大同时下载片量(下载前更改)", self)
        label1.setAlignment(Qt.AlignLeft)
        self.max_workers_input = QLineEdit(self)
        self.max_workers_input.setText(str(self.max_workers))
        layout.addWidget(label1)
        layout.addWidget(self.max_workers_input)

        # 日志更新频率
        label2 = QLabel("每N次更新一次(可下载中更改)", self)
        label2.setAlignment(Qt.AlignLeft)
        self.update_interval_input = QLineEdit(self)
        self.update_interval_input.setText(str(self.log_update_freq))
        layout.addWidget(label2)
        layout.addWidget(self.update_interval_input)

        # 按钮布局
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("确定", self)
        self.cancel_button = QPushButton("取消", self)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # 绑定信号
        self.ok_button.clicked.connect(self.save_settings)
        self.cancel_button.clicked.connect(self.reject)

    def save_settings(self):
        """保存调速设置"""
        try:
            # 获取并验证输入
            new_max_workers = int(self.max_workers_input.text().strip())
            new_update_interval = int(self.update_interval_input.text().strip())

            if new_max_workers <= 0:
                QMessageBox.critical(self, "错误", "最大同时下载片量必须大于 0")
                return

            if new_update_interval <= 0:
                QMessageBox.critical(self, "错误", "每N次更新一次必须大于 0")
                return

            # 更新父窗口的参数
            self.parent.max_workers = new_max_workers
            self.parent.log_update_freq = new_update_interval

            # 如果下载线程正在运行，更新线程的日志更新频率
            if hasattr(self.parent, 'download_thread'):
                self.parent.download_thread.log_update_freq = new_update_interval

            # 日志提示
            self.parent.log(
                f"调速参数已更新：最大同时下载片量={new_max_workers}，"
                f"每{new_update_interval}次更新一次"
            )
            self.accept()  # 关闭对话框

        except ValueError:
            QMessageBox.critical(self, "错误", "请输入合法的整数")