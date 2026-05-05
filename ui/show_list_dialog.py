
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QListWidget, QListWidgetItem,
                             QLabel, QLineEdit, QHBoxLayout, QPushButton, QMessageBox)
from PyQt5.QtCore import Qt
import os


class SupportListDialog(QDialog):
    def __init__(self, parent=None, support_list_file=None):
        super().__init__(parent)
        self.support_list_file = support_list_file  # 接收支持列表文件路径
        self.objects = self.load_support_list()     # 存储列表数据

        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("支持网址列表")
        self.resize(1000, 600)

        # 整体垂直布局
        layout = QVBoxLayout(self)

        # 1 列表元素框
        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)

        # 2 名称标签与输入框
        name_label = QLabel("名称：", self)
        layout.addWidget(name_label)
        self.name_input = QLineEdit(self)
        layout.addWidget(self.name_input)

        # 3 网址标签和输入框
        url_label = QLabel("网址：", self)
        layout.addWidget(url_label)
        self.url_input = QLineEdit(self)
        layout.addWidget(self.url_input)

        # 4 按钮水平布局
        button_layout = QHBoxLayout()

        add_button = QPushButton("新增", self)
        update_button = QPushButton("修改", self)
        delete_button = QPushButton("删除", self)
        close_button = QPushButton("关闭", self)

        button_layout.addWidget(add_button)
        button_layout.addWidget(update_button)
        button_layout.addWidget(delete_button)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        # 初始化列表
        self.refresh_list()

        # 绑定信号槽
        self.list_widget.itemClicked.connect(self.on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        add_button.clicked.connect(self.add_item)
        update_button.clicked.connect(self.update_item)
        delete_button.clicked.connect(self.delete_item)
        close_button.clicked.connect(self.close)

    def refresh_list(self):
        """刷新列表显示"""
        self.list_widget.clear()
        for obj in self.objects:
            text = f"{obj['name']} | {obj['url']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, obj)
            self.list_widget.addItem(item)

    def on_item_clicked(self, item):
        """单击列表项填充输入框"""
        obj = item.data(Qt.UserRole)
        self.name_input.setText(obj.get("name", ""))
        self.url_input.setText(obj.get("url", ""))

    def on_item_double_clicked(self, item):
        """双击列表项将网址填入主界面"""
        obj = item.data(Qt.UserRole)
        # 向主窗口发送信号--或直接调用主窗口方法
        if self.parent():
            self.parent().url_input.setText(obj.get("url", ""))
            QMessageBox.information(self.parent(), "提示",
                                   f"已将网址填入主界面url输入框：\n{obj.get('url', '')}")

    def add_item(self):
        """新增列表项"""
        name = self.name_input.text().strip()
        url = self.url_input.text().strip()

        if not name or not url:
            QMessageBox.warning(self, "错误", "名称和网址都不能为空！")
            return

        self.objects.append({"name": name, "url": url})
        self.refresh_list()
        self.name_input.clear()
        self.url_input.clear()
        self.save_support_list()
        QMessageBox.information(self, "提示", "已成功新增该记录！")

    def update_item(self):
        """修改列表项"""
        current_row = self.list_widget.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "提示", "请先选择一条要修改的记录！")
            return

        name = self.name_input.text().strip()
        url = self.url_input.text().strip()

        if not name or not url:
            QMessageBox.warning(self, "错误", "名称和网址都不能为空！")
            return

        self.objects[current_row] = {"name": name, "url": url}
        self.refresh_list()
        self.list_widget.setCurrentRow(current_row)

        self.save_support_list()
        QMessageBox.information(self, "提示", "已成功修改！")

    def delete_item(self):
        """删除列表项"""
        current_row = self.list_widget.currentRow()
        if current_row < 0:
            QMessageBox.information(self, "提示", "请先选择一条要删除的记录！")
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除当前选中的记录吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            del self.objects[current_row]
            self.refresh_list()
            self.name_input.clear()
            self.url_input.clear()
            self.save_support_list()
            QMessageBox.information(self, "提示", "已成功删除该记录！")

    def load_support_list(self):
        """加载支持列表文件"""
        objects = []
        if not os.path.exists(self.support_list_file):
            # 默认数据
            default_objects = [
                {"name": "1 小鸭看看", "url": "https://xiaoyakankan.com/"},
                {"name": "小鸭看看m3u8格式", "url": "https://play.subokk.com/play/hls/rb2kDPdW/index.m3u8"},
            ]
            self.save_support_list(default_objects)
            return default_objects

        try:
            with open(self.support_list_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or " | " not in line:
                        continue
                    name, url = line.split(" | ", 1)
                    objects.append({
                        "name": name.strip(),
                        "url": url.strip()
                    })
        except Exception as e:
            QMessageBox.critical(self, "错误", f"读取支持列表失败：{e}")

        return objects

    def save_support_list(self, objects=None):
        """保存支持列表到文件"""
        # 优先使用传入的objects，否则用自身的objects
        save_objects = objects if objects is not None else self.objects
        try:
            seen = set()
            new_lines = []
            for obj in save_objects:
                name = obj.get("name", "").strip()
                url = obj.get("url", "").strip()
                if not name or not url:
                    continue

                key = (name, url)
                if key in seen:
                    continue

                seen.add(key)
                new_lines.append(f"{name} | {url}")

            new_content = "\n".join(new_lines) + "\n"
            # 避免重复写入
            old_content = ""
            if os.path.exists(self.support_list_file):
                with open(self.support_list_file, "r", encoding="utf-8") as f:
                    old_content = f.read()
            if new_content == old_content:
                return

            with open(self.support_list_file, "w", encoding="utf-8") as f:
                f.write(new_content)

            # 如果主窗口存在，调用主窗口的log方法
            if self.parent() and hasattr(self.parent(), "log"):
                self.parent().log("支持列表已更新并保存到文件。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存支持列表失败：{e}")