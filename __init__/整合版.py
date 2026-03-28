import m3u8
import requests
import os
import sys
import time
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox,QTextEdit, QProgressBar)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import QThread, pyqtSignal
from Crypto.Cipher import AES
from PyQt5.QtWidgets import QDialog, QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt
from concurrent.futures import ThreadPoolExecutor, as_completed



class DownloadThread(QThread):
    logText_signal = pyqtSignal(str)   #列表框信号
    progress_signal = pyqtSignal(int)  #进度框信号
    finished_signal = pyqtSignal(bool) #下载完成信号

    def __init__(self, m3u8_url, output_dir, output_file, max_workers = 8, log_update_freq = 5):
        super().__init__()
        self.m3u8_url = m3u8_url
        self.output_dir = output_dir
        self.output_file = output_file
        self.max_workers = max_workers
        self.log_update_freq = log_update_freq
        self.stop_flag = False           # 控制线程停止的标志
        self.pause_flag = False          # 控制暂停的标志


    def run(self):
        try:
            self.download_and_merge()
        except Exception as e:
            self.log(f"错误: {str(e)}")
            self.finished_signal.emit(False)

    def log(self, message):
        self.logText_signal.emit(message)

    def stop(self):
        self.stop_flag = True


    def pause(self):
        self.pause_flag = True

    def resume(self):
        self.pause_flag = False

    def check_pause_and_stop(self):
        if self.stop_flag:
            self.log("下载已中断！")
            return False

        while self.pause_flag:
            if self.stop_flag:
                self.log("下载已中断！")
                return False
            time.sleep(0.2)
        return True



    def download_one_ts(self, session, ts_url, ts_name, key, seg_iv):
        try:
            if self.stop_flag:
                return False, ts_url, "任务已停止"

            while self.pause_flag:
                if self.stop_flag:
                    return False, ts_url, "任务已停止"
                time.sleep(0.2)

            ts_response = session.get(ts_url, verify=False, timeout=(10, 30))
            ts_response.raise_for_status()
            ts_data = ts_response.content

            if not ts_data:
                raise ValueError("下载内容为空")

            if key:
                ts_data = self.decrypt_ts(ts_data, key, seg_iv, ts_url)

            with open(ts_name, "wb") as f:
                f.write(ts_data)

            return True, ts_url, None

        except Exception as e:
            return False, ts_url, str(e)

    def download_and_merge(self):
        self.log("开始下载...")
        start_time = time.time()

        session = requests.Session()
        retry = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=32,
            pool_maxsize=32
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        os.makedirs(self.output_dir, exist_ok=True)

        output_parent = os.path.dirname(self.output_file)
        if output_parent:
            os.makedirs(output_parent, exist_ok=True)

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": self.m3u8_url
        }

        response = session.get(self.m3u8_url, headers=headers, verify=False, timeout=(10, 30))
        response.raise_for_status()

        m3u8_content = response.text
        playlist = m3u8.loads(m3u8_content)

        total_segments = len(playlist.segments)
        if total_segments == 0:
            raise ValueError("m3u8 中没有找到任何 ts 分片")

        self.log(f"总分片数: {total_segments}")
        self.progress_signal.emit(0)

        base_url = self.m3u8_url.rsplit("/", 1)[0] + "/"

        key = None
        iv = None

        if playlist.keys and playlist.keys[0] and getattr(playlist.keys[0], "uri", None):
            key_info = playlist.keys[0]
            key_url = urljoin(base_url, key_info.uri)
            self.log(f"下载解密密钥: {key_url}")

            try:
                key_resp = session.get(key_url, headers=headers, verify=False, timeout=(10, 30))
                key_resp.raise_for_status()
                key = key_resp.content

                if len(key) != 16:
                    self.log(f"警告：AES-128 密钥长度异常，当前长度: {len(key)}，将忽略解密")
                    key = None

                if key and getattr(key_info, "iv", None):
                    try:
                        iv_str = key_info.iv
                        if iv_str.startswith("0x") or iv_str.startswith("0X"):
                            iv = bytes.fromhex(iv_str[2:])
                        else:
                            iv = bytes.fromhex(iv_str)

                        if len(iv) != 16:
                            self.log("警告：IV 长度不是 16 字节，将使用默认序号 IV")
                            iv = None
                    except Exception as e:
                        self.log(f"警告：解析 IV 失败，将使用默认序号 IV，错误: {e}")
                        iv = None

            except Exception as e:
                self.log(f"警告：下载密钥失败，将按未加密处理，错误: {e}")
                key = None
                iv = None

        failed_downloads = []
        completed_count = 0
        success_count = 0
        media_sequence = getattr(playlist, "media_sequence", 0) or 0

        max_workers = self.max_workers   #可同时下载的ts量

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {}

            for idx, segment in enumerate(playlist.segments):
                if self.stop_flag:
                    self.log("下载已中断！")
                    self.finished_signal.emit(False)
                    return

                ts_url = urljoin(base_url, segment.uri)
                ts_name = os.path.join(self.output_dir, f"{idx:05d}.ts")
                seg_iv = iv if iv is not None else (media_sequence + idx).to_bytes(16, byteorder="big")

                future = executor.submit(
                    self.download_one_ts,
                    session,
                    ts_url,
                    ts_name,
                    key,
                    seg_iv
                )
                future_to_index[future] = idx

            for future in as_completed(future_to_index):
                if not self.check_pause_and_stop():
                    self.log("用户已中断下载，未执行合并。")
                    self.finished_signal.emit(False)
                    return

                idx = future_to_index[future]

                try:
                    success, ts_url, error = future.result()
                    if success:
                        success_count += 1
                    else:
                        failed_downloads.append((ts_url, error))
                except Exception as e:
                    failed_downloads.append((f"分片序号 {idx}", str(e)))

                completed_count += 1
                progress = int(completed_count * 100 / total_segments)


                #每5个ts分片就更新一次在log中
                if completed_count % self.log_update_freq == 0 or completed_count == total_segments:
                    self.log(
                        f"下载进度: {completed_count}/{total_segments} "
                        f"({progress}%)，成功: {success_count}，失败: {len(failed_downloads)}"
                    )
                self.progress_signal.emit(progress)

        if failed_downloads:
            self.log("\n下载失败的url：")
            for url, error in failed_downloads:
                self.log(f"URL名: {url}, 错误: {error}")
            self.log("存在下载失败，将尝试融合已成功下载的片段。")

        merged_count = 0
        with open(self.output_file, "wb") as merged_file:
            for idx in range(total_segments):
                if not self.check_pause_and_stop():
                    self.log("用户已中断下载，合并已停止。")
                    self.finished_signal.emit(False)
                    return

                part_path = os.path.join(self.output_dir, f"{idx:05d}.ts")
                if not os.path.exists(part_path):
                    self.log(f"缺失片段，跳过融合: {part_path}")
                    continue

                with open(part_path, "rb") as part_file:
                    merged_file.write(part_file.read())

                merged_count += 1

        self.progress_signal.emit(100)
        self.log(f"融合完成！共融合 {merged_count}/{total_segments} 个片段，保存为 {self.output_file}")

        end_time = time.time()
        self.finished_signal.emit(True)
        self.log(f"下载经历时间: {(end_time - start_time):.3f} 秒！")


    def decrypt_ts(self, ts_data, key, iv, ts_url=None):
        if not ts_data:
            self.log(f"空的 TS 数据，跳过解密: {ts_url}")
            return ts_data

        # 如果看起来已经像 TS 明文，直接返回
        if len(ts_data) > 188 and ts_data[0] == 0x47:
            self.log(f"检测到疑似明文 TS，跳过解密: {ts_url}")
            return ts_data

        if len(ts_data) % 16 != 0:
            self.log(f"TS 长度不是 16 的倍数，跳过解密: {ts_url}")
            return ts_data

        try:
            cipher = AES.new(key, AES.MODE_CBC, iv)
            return cipher.decrypt(ts_data)
        except Exception as e:
            self.log(f"TS 解密失败，跳过解密: {ts_url}，错误: {e}")
            return ts_data







class M3U8Downloader(QWidget):  #界面部分
    def __init__(self):
        super().__init__()
        self.max_workers = 8            #最大同时下载片量
        self.log_update_freq = 5        #每n次更新下载log
        self.support_list_file =        "resources/supported_m3u8_list.txt"
        self.download_finished = False  #下载完成flag
        self.current_output_dir = ""    #当前下载的路径
        self.init_ui()                  #初始化UI

    def init_ui(self):
        self.setWindowTitle('M3U8下载器')
        self.setWindowIcon(QIcon('resources/logo.png'))   # 将 'logo.png' 替换为你的图标文件路径
        self.setGeometry(800, 400, 1200, 1000)       #窗口的初始大小(x, y, width, height)
        font_label = QFont('Arial', 12)              #label字体设置为 Arial，大小为 12
        font_input = QFont('Arial', 13)              #QLineEdit字体设置为 Arial，大小为 12
        font_button = QFont('Arial', 12)             #button字体设置为 Arial，大小为 12
        font_log = QFont('Arial', 11)                #QTextEdit字体设置为 Arial，大小为 12

        # 0 整体布局（垂直）
        all_layout = QVBoxLayout()

        #1 网格布局
        grid_layout= QGridLayout()

        # 1.1 M3U8 URL 输入框
        self.url_label = QLabel('请输入M3U8 URL地址',self)
        self.url_label.setFont(font_label)
        self.url_label.setAlignment(Qt.AlignCenter)  # 设置水平和垂直居中
        self.url_input = QLineEdit(self)
        self.url_input.setText("复制url并覆盖到这里") #默认内容
        grid_layout.addWidget(self.url_label, 1, 0)  # row 1， column 0
        grid_layout.addWidget(self.url_input, 1, 1)  # row 1， column 1
        # 1.2 输出目录输入框
        self.dir_input = QLineEdit(self)
        self.dir_input.setText("downloads/电影名/ts")          #默认内容
        self.select_dir_button = QPushButton("选择存放ts分片的路径", self)
        self.select_dir_button.clicked.connect(self.select_ts_dir)
        grid_layout.addWidget(self.select_dir_button, 2, 0)  # row 2， column 0
        grid_layout.addWidget(self.dir_input, 2, 1)          # row 2， column 1
        # 1.3 输出文件输入框
        self.file_input = QLineEdit(self)
        self.file_input.setText("downloads/电影名/movies.ts")    #默认内容
        self.select_file_button = QPushButton("选择ts融合文件的路径", self)
        self.select_file_button.clicked.connect(self.select_output_file)
        grid_layout.addWidget(self.select_file_button, 3 ,0) # row 3， column 0
        grid_layout.addWidget(self.file_input, 3, 1)         # row 3， column 1

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
            self.export_log_button
        ]
        for btn in buttons:
            btn.setFont(font_button)

        #给所有输入框统一字体大小
        self.url_input.setFont(font_input)
        self.dir_input.setFont(font_input)
        self.file_input.setFont(font_input)

        #给日志框设置大小
        self.log_box.setFont(font_log)

        self.setLayout(all_layout)


    # 1.2 选择存放ts分片路径 槽函数
    def select_ts_dir(self):
        current_dir = self.dir_input.text().strip()

        directory = QFileDialog.getExistingDirectory(
            self,
            "选择ts存放目录",
            current_dir if current_dir else ""
        )

        if directory:
            self.dir_input.setText(directory)

    # 1.3 选择存放输出文件路径 槽函数
    def select_output_file(self):
        current_file = self.file_input.text().strip()

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "选择输出文件",
            current_file if current_file else "",
            "TS文件 (*.ts);;所有文件 (*)"
        )

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
            "下面的url需要定位到正确的m3u8资源url\n"
            "而非直接复制视频网址\n"
            "需要在网页右键->检查->网络中定位到相关url\n"
            "部分网址可能没有这种url资源\n"
            "可查看右边支持的部分网址列表"
        )
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        label.setFixedWidth(550)  # 这里直接控制文本区域宽度

        layout = msg.layout()
        layout.addWidget(label, 0, 1, 1, layout.columnCount())
        msg.exec_()

    # 2.2 支持列表的示例网址-槽函数
    def show_list_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("支持网址列表")
        dialog.resize(1000, 600)

        # 整体垂直布局
        layout = QVBoxLayout(dialog)

        # 1 列表元素框
        list_widget = QListWidget(dialog)
        layout.addWidget(list_widget)

        # 2 名称标签与输入框
        name_label = QLabel("名称：", dialog)
        layout.addWidget(name_label)
        name_input = QLineEdit(dialog)
        layout.addWidget(name_input)

        # 3 网址标签和输入框
        url_label = QLabel("网址：", dialog)
        layout.addWidget(url_label)
        url_input = QLineEdit(dialog)
        layout.addWidget(url_input)

        # 4 按钮水平布局
        button_layout = QHBoxLayout()

        add_button = QPushButton("新增", dialog)
        update_button = QPushButton("修改", dialog)
        delete_button = QPushButton("删除", dialog)
        close_button = QPushButton("关闭", dialog)

        button_layout.addWidget(add_button)
        button_layout.addWidget(update_button)
        button_layout.addWidget(delete_button)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        objects = self.load_support_list()

        # 更新列表框内容
        def refresh_list():
            list_widget.clear()
            for obj in objects:
                text = f"{obj['name']} | {obj['url']}"
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, obj)
                list_widget.addItem(item)

        refresh_list()

        # 单击列表某一行的槽函数
        def on_item_clicked(item):
            obj = item.data(Qt.UserRole)
            name_input.setText(obj.get("name", ""))
            url_input.setText(obj.get("url", ""))

        # 双击列表某一行的槽函数
        def on_item_double_clicked(item):
            obj = item.data(Qt.UserRole)
            self.url_input.setText(obj.get("url", ""))
            QMessageBox.information(self, "提示", f"已将网址填入主界面url输入框：\n{obj.get('url', '')}")

        # 新增 槽函数
        def add_item():
            name = name_input.text().strip()
            url = url_input.text().strip()

            if not name or not url:
                self.show_message("错误", "名称和网址都不能为空！")
                return

            objects.append({"name": name, "url": url})
            refresh_list()
            name_input.clear()
            url_input.clear()
            self.save_support_list(objects)
            self.show_message("提示", "已成功新增该记录！")

        # 修改 槽函数
        def update_item():
            current_row = list_widget.currentRow()
            if current_row < 0:
                self.show_message("提示", "请先选择一条要修改的记录！")
                return

            name = name_input.text().strip()
            url = url_input.text().strip()

            if not name or not url:
                self.show_message("错误", "名称和网址都不能为空！")
                return

            objects[current_row] = {"name": name, "url": url}
            refresh_list()
            list_widget.setCurrentRow(current_row)

            self.save_support_list(objects)
            self.show_message("提示", "已成功修改！")

        # 删除 槽函数
        def delete_item():
            current_row = list_widget.currentRow()
            if current_row < 0:
                self.show_message("提示", "请先选择一条要删除的记录！")
                return

            reply = QMessageBox.question(
                self,
                "确认删除",
                "确定要删除当前选中的记录吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                del objects[current_row]
                refresh_list()
                name_input.clear()
                url_input.clear()
                self.save_support_list(objects)
                self.show_message("提示", "已成功删除该记录！")

        list_widget.itemClicked.connect(on_item_clicked)
        list_widget.itemDoubleClicked.connect(on_item_double_clicked)
        add_button.clicked.connect(add_item)
        update_button.clicked.connect(update_item)
        delete_button.clicked.connect(delete_item)
        close_button.clicked.connect(dialog.close)

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
        output_dir = self.dir_input.text()
        output_file = self.file_input.text()
        self.log_box.append("当前的m3u8 url地址： "+m3u8_url)
        self.log_box.append("当前的下载路径： "+ output_dir)
        self.log_box.append("当前的输出文件： "+ output_file)

        # 验证输入、输出视频地址是否为空
        if not m3u8_url or not output_dir or not output_file:
            self.show_message("错误", "存在为空的内容，请填写！")
            return

        if hasattr(self, 'download_thread') and self.download_thread.isRunning():
            self.show_message("提示", "下载任务已在进行中！\n不要重复点击下载！")
            return

        self.progress_bar.setValue(0)

        self.download_finished = False
        self.current_output_dir = output_dir
        #self.clean_ts_button.setEnabled(False)

        # 创建并启动下载线程
        self.download_thread = DownloadThread(m3u8_url, output_dir, output_file, self.max_workers, self.log_update_freq)
        self.download_thread.logText_signal.connect( self.log )
        self.download_thread.progress_signal.connect( self.update_progress )
        self.download_thread.finished_signal.connect( self.on_download_finished )
        self.download_thread.start()

    # 5.2 暂停下载-槽函数
    def pause_download(self):
        if hasattr(self, 'download_thread') and self.download_thread.isRunning() :
            self.download_thread.pause()
            self.log("下载已暂停...")
        else:
            self.log("当前没有正在运行的下载任务!")

    # 5.3 继续下载-槽函数
    def resume_download(self):
        if hasattr(self, 'download_thread'):
            self.download_thread.resume()
            self.log("下载已恢复...")

    # 5.4 中断下载-槽函数
    def stop_download(self):
        if hasattr(self, 'download_thread'):
            self.download_thread.stop()
            self.log("下载已中断！")
            self.progress_bar.setValue(0)

    # 5.5 清理日志-槽函数
    def clear_log(self):
        self.log_box.clear()

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
            self,
            "确认清理",
            "是否清理单独的 ts 文件？",
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
        dialog = QDialog(self)
        dialog.setWindowTitle("调速设置")
        dialog.resize(350, 220)

        layout = QVBoxLayout(dialog)

        # 显示文本1
        label1 = QLabel("最大同时下载片量(下载前更改)", dialog)
        layout.addWidget(label1)
        # 可编辑文本框1
        max_workers_input = QLineEdit(dialog)
        max_workers_input.setText(str(self.max_workers))
        layout.addWidget(max_workers_input)
        # 显示文本2
        label2 = QLabel("每N次更新一次(可下载中更改)", dialog)
        layout.addWidget(label2)
        # 可编辑文本框2
        update_interval_input = QLineEdit(dialog)
        update_interval_input.setText(str(self.log_update_freq))
        layout.addWidget(update_interval_input)

        # 按钮区域
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定", dialog)
        cancel_button = QPushButton("取消", dialog)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        # 调速设置对话框的确定按钮槽函数
        def save_settings():
            try:
                new_max_workers = int(max_workers_input.text().strip())
                new_update_interval = int(update_interval_input.text().strip())

                if new_max_workers <= 0:
                    self.show_message("错误", "最大同时下载片量必须大于 0")
                    return

                if new_update_interval <= 0:
                    self.show_message("错误", "每N次更新一次必须大于 0")
                    return

                self.max_workers = new_max_workers
                self.log_update_freq = new_update_interval

                # 如果当前线程存在，则让“更新频率”立即生效
                if hasattr(self, 'download_thread'):
                    self.download_thread.log_update_freq = self.log_update_freq

                self.log(f"调速参数已更新：最大同时下载片量={self.max_workers}，每{self.log_update_freq}次更新一次")
                dialog.accept()
            except ValueError:
                self.show_message("错误", "请输入合法的整数")

        ok_button.clicked.connect(save_settings)
        cancel_button.clicked.connect(dialog.reject)
        dialog.exec_()

    #判断是否下载完成
    def on_download_finished(self, success):
        self.download_finished = success
        self.clean_ts_button.setEnabled(success)

        if success:
            self.log("下载任务已完成，可清理 ts 临时文件。")
        else:
            self.log("下载任务未完整完成，暂不可清理 ts 临时文件。")

    #加载支持m3u8的url文件
    def load_support_list(self):
        objects = []
        if not os.path.exists(self.support_list_file):
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
                    if not line:
                        continue
                    if " | " not in line:
                        continue

                    name, url = line.split(" | ", 1)
                    objects.append({
                        "name": name.strip(),
                        "url": url.strip()
                    })
        except Exception as e:
            self.show_message("错误", f"读取支持列表失败：{e}")

        return objects

    #保存到支持m3u8的txt文件中
    def save_support_list(self, objects):
        try:
            seen = set()
            new_lines = []
            for obj in objects:
                name = obj.get("name", "").strip()
                url = obj.get("url", "").strip()
                if not name or not url:
                    continue

                # 用 name+url 作为唯一标识（不会覆盖）
                key = (name, url)
                if key in seen:
                    continue

                seen.add(key)
                new_lines.append(f"{name} | {url}")

            new_content = "\n".join(new_lines) + "\n"
            # === 防止重复写入硬盘 ===
            old_content = ""
            if os.path.exists(self.support_list_file):
                with open(self.support_list_file, "r", encoding="utf-8") as f:
                    old_content = f.read()
            if new_content == old_content:
                self.log("支持列表未发生变化，无需保存。")
                return

            with open(self.support_list_file, "w", encoding="utf-8") as f:
                f.write(new_content)

            self.log("支持列表已更新并保存到文件。")
        except Exception as e:
            self.show_message("错误", f"保存支持列表失败：{e}")

    def show_message(self, title, message):
        QMessageBox.information(self, title, message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = M3U8Downloader()
    window.show()
    sys.exit(app.exec_())


