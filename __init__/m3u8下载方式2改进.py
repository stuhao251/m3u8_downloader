import m3u8
import requests
import os
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time


def main(m3u8_url, output_dir, output_file):
    # 设置重试机制和禁用 SSL 验证
    session = requests.Session()
    retry = Retry(
        total=5,                              # 最大重试次数
        backoff_factor=1,                     # 重试间隔
        status_forcelist=[500, 502, 503, 504] # 针对服务器错误进行重试
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)

    # 创建保存目录
    os.makedirs(output_dir, exist_ok=True)

    # 下载 m3u8 文件，获取里面ts的url
    response = session.get(m3u8_url, verify=False)  # 禁用 SSL 验证
    response.raise_for_status()
    m3u8_content = response.text
    playlist = m3u8.loads(m3u8_content)

    # 获取 m3u8 的 base URL
    base_url = m3u8_url.rsplit("/", 1)[0] + "/"

    # 下载 TS 文件
    ts_count = 0
    failed_downloads = []  # 记录下载失败的文件
    for idx, segment in enumerate(playlist.segments):
        ts_url = urljoin(base_url, segment.uri)  # 生成完整的 ts 文件 URL
        ts_name = os.path.join(output_dir, f"{idx:05d}.ts")
        print(f"Downloading {ts_url} -> {ts_name}")
        try:
            with open(ts_name, "wb") as f:
                ts_response = session.get(ts_url, verify=False)  # 禁用 SSL 验证
                ts_response.raise_for_status()  # 如果请求失败，抛出异常
                f.write(ts_response.content)
                ts_count += 1
        except requests.exceptions.RequestException as e:
            print(f"Failed to download {ts_url}: {e}")
            failed_downloads.append((ts_url, str(e)))

    # 如果有下载失败的文件，输出错误日志
    if failed_downloads:
        print("\nFailed downloads:")
        for url, error in failed_downloads:
            print(f"URL: {url}, Error: {error}")
    else:
        # 合并所有 TS 文件
        with open(output_file, "wb") as merged_file:
            for idx in range(ts_count):
                part_path = os.path.join(output_dir, f"{idx:05d}.ts")
                with open(part_path, "rb") as part_file:
                    merged_file.write(part_file.read())
                print(f"Merged: {part_path}")

        print(f"Download and merge complete. Saved as {output_file}")


def ts_transfor_mp4(output_file,output_mp4_file):
    # 复制 TS 文件为 MP4 文件（保留 TS 文件）
    with open(output_mp4_file, "wb") as mp4_file:
        with open(output_file, "rb") as ts_file:
            mp4_file.write(ts_file.read())
    print(f"TS file converted to MP4. Saved as {output_mp4_file}")


def delete_ts_partfiles(output_dir):
    if os.path.exists(output_dir):
        for file in os.listdir(output_dir):
            if file.endswith(".ts"):
                os.remove(os.path.join(output_dir, file))
    else:
        print(f"Folder '{output_dir}' does not exist.")


if __name__ == "__main__":
    #不同格式的 m3u8 文件 URL
    m3u8_url = "https://galav-oxwy.mushroomtrack.com/hls/tt6o746k14jMCbxRZyC5xw/1750405190/44000/44515/44515.m3u8"
    m3u8_url = "https://c1.rrcdnbf3.com/video/yanhuangguaxianshengdisanji/%E7%AC%AC10%E9%9B%86/index.m3u8"
    m3u8_url = "https://s8-e1.etcbbh.xyz/ppot/_definst_/mp4:s8/kvod/xj-trjta3-480p-01FE07736.mp4/chunklist.m3u8?vendtime=1735915621&vhash=9jBO-Ag-YIvCc66fAefrJw6_oWlDtdrV4p7Q3pmtjbM=&vCustomParameter=0_58.152.22.120_HK_1_0&lb=22ad18c65ac922a7640f24cabdcc406c&us=1&proxy=SpWjPJ4kPNHZOc9eBdXvUdnpE2rbCIvbT6DYOcakU7bwV7CuBMKnBcLqOs9YQYvuUNfyEPmMifYNEZCnCx2mi9SnjxQz7CuBMKnBdHcOcTYOc8kOsys1&vv=be701e2af67a2b2757de8590fa6b419b&pub=CJSpDJSqCZWoC2uuEJHVI4jVDJWkCJKoBZ8oBZ4oC5yS6Z2Rch4nd32SifcQCHgRiJ2OcHeQiBAR79omc1io6gzEM9ZE6KsDM8nD3GoOsCqDZSrPM4vPc8uE6KnOZ5XDM3"
    m3u8_url = "https://vip.ffzy-play10.com/20230113/9802_00262fc6/2000k/hls/mixed.m3u8"
    m3u8_url = "https://s10-e1.etcbbf.xyz/ppot/_definst_/mp4:s13/lvod/xj-zww-720p-02320D4DF.mp4/chunklist.m3u8?vendtime=1736063118&vhash=wsE1yIGbRYF5hQG8pg56bHWj-1YN6ZPaZiO5vkgbE8A=&vCustomParameter=0_58.152.33.209_HK_0_0&lb=4f44dbec45bc9d49f2e261688a6b8538&proxy=Sp4mBMKnBcLqOs9YPYvuUNfyEPYO5hAObpAwCR4nCvSy7bwV7CnC2rbCIvbT6DYOcWkU7bwV7CnC2rbCIvbT6DYOcakU7bwV7CnC2rbCIvbT6DYOcekU7bw"

    #存放目录
    output_dir = "../downloads"  # 存放单个的 ts 文件的目录
    output_file = "01.ts"       # 合并后的最终 ts 文件名
    output_mp4_file = "01.mp4"  # 最终生成的 MP4 文件名

    start_time = time.time()
    main(m3u8_url,output_dir,output_file)
    end_time = time.time()
    print(f'下载经历时间:{(end_time - start_time):.3f}')

    ts_transfor_mp4(output_file,output_mp4_file)




