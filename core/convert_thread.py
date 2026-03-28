import os
import re
import shutil
import subprocess

from PyQt5.QtCore import QThread, pyqtSignal


class ConvertThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, input_file, output_file):
        super().__init__()
        self.input_file = input_file
        self.output_file = output_file
        self.stop_flag = False

    def log(self, message):
        self.log_signal.emit(str(message))

    def stop(self):
        self.stop_flag = True

    def get_duration_seconds(self, ffprobe_path, input_file):
        cmd = [
            ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            input_file
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )

        if result.returncode != 0:
            return 0.0

        try:
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def time_to_seconds(self, time_str):
        # 例如 00:01:23.45
        try:
            h, m, s = time_str.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
        except Exception:
            return 0.0

    def run(self):
        ffmpeg_path = shutil.which("ffmpeg")
        ffprobe_path = shutil.which("ffprobe")

        if not ffmpeg_path or not ffprobe_path:
            self.finished_signal.emit(False, "未检测到 ffmpeg/ffprobe，请先安装并加入环境变量。")
            return

        if not os.path.exists(self.input_file):
            self.finished_signal.emit(False, f"输入文件不存在：{self.input_file}")
            return

        total_duration = self.get_duration_seconds(ffprobe_path, self.input_file)
        if total_duration <= 0:
            self.log("未能获取总时长，将只显示转码中状态。")

        cmd = [
            ffmpeg_path,
            "-y",
            "-i", self.input_file,
            "-c", "copy",
            self.output_file
        ]

        self.log(f"开始转码：{self.input_file}")
        self.log(f"输出文件：{self.output_file}")
        self.progress_signal.emit(0)

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )

            time_pattern = re.compile(r"time=(\d+:\d+:\d+(?:\.\d+)?)")

            while True:
                if self.stop_flag:
                    process.terminate()
                    self.finished_signal.emit(False, "转码已取消。")
                    return

                line = process.stderr.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    continue

                line = line.strip()
                if line:
                    self.log(line)

                if total_duration > 0:
                    match = time_pattern.search(line)
                    if match:
                        current_time = self.time_to_seconds(match.group(1))
                        progress = int(min(current_time / total_duration * 100, 100))
                        self.progress_signal.emit(progress)

            return_code = process.wait()

            if return_code == 0:
                self.progress_signal.emit(100)
                self.finished_signal.emit(True, self.output_file)
            else:
                self.finished_signal.emit(False, "ffmpeg 转码失败。")

        except Exception as e:
            self.finished_signal.emit(False, f"转码异常：{e}")