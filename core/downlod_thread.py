import m3u8
import requests
import os
import sys
import time
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from PyQt5.QtCore import QThread, pyqtSignal
from Crypto.Cipher import AES
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QCoreApplication

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



#测试-日志框输出信号是否正常
def on_log(msg):
    print("[LOG]", msg)

#测试-进度条输出信号是否正常
def on_progress(val):
    pass
    #print("[PROGRESS]", val)

#测试-完成flag输出信号是否正常
def on_finished(ok):
    print("[FINISHED]", ok)
    QCoreApplication.quit()



if __name__ == "__main__":
    app = QCoreApplication(sys.argv)


    m3u8_url = "https://hls.iiswca.cn/videos5/528ae3c0a0f0987013b6f896d9458d7f/528ae3c0a0f0987013b6f896d9458d7f.m3u8?auth_key=1774690150-69c79f66af6fb-0-96128d8df6815923b7c6eebb7177c9b7&v=3&time=0"
    output_dir = r'download/movie/ts'
    output_file = r'download/movie/file.ts'

    # 创建并启动下载线程
    download_thread = DownloadThread(m3u8_url,
                                     output_dir,
                                     output_file,
                                     8,
                                     10)
    download_thread.logText_signal.connect(on_log)
    download_thread.progress_signal.connect(on_progress)
    download_thread.finished_signal.connect(on_finished)

    download_thread.start()

    sys.exit(app.exec_())








