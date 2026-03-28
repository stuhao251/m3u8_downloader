import m3u8
import requests
import os
from urllib.parse import urljoin

#m3u8 文件 URL
m3u8_url = "https://c1.rrcdnbf3.com/video/yanhuangguaxianshengdisanji/%E7%AC%AC08%E9%9B%86/index.m3u8"
output_dir = "../downloads"  # 存放 ts 文件的目录


# 下载 m3u8 文件
response = requests.get(m3u8_url)
response.raise_for_status()
m3u8_content = response.text
playlist = m3u8.loads(m3u8_content)

# 获取 m3u8 的 base URL
base_url = m3u8_url.rsplit("/", 1)[0] + "/"

# 创建保存目录
os.makedirs(output_dir, exist_ok=True)

# 下载所有 TS 文件
ts_count = 0
for idx, segment in enumerate(playlist.segments):
    ts_url = urljoin(base_url, segment.uri)  # 生成完整的 ts 文件 URL
    ts_name = os.path.join(output_dir, f"{idx:05d}.ts")
    print(f"Downloading {ts_url} -> {ts_name}")
    with open(ts_name, "wb") as f:
        f.write(requests.get(ts_url).content)
        ts_count += 1




with open("08.ts", "wb") as merged_file:
    for idx in range(ts_count):
        part_path = os.path.join(output_dir, f"{idx:05d}.ts")
        with open(part_path, "rb") as part_file:
            merged_file.write(part_file.read())
        print(f"Merged: {part_path}")


