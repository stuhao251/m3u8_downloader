import os
import requests
'''下载看美剧的m3u8视频：http://www.kanmjw.com/dongman/30421-0-6.html'''


#1 添加所有 .ts 文件的URL列表
base_url = "https://c1.rrcdnbf3.com/video/yanhuangguaxianshengdisanji/%E7%AC%AC06%E9%9B%86/"  #ts的baseurl
ts_count = 164   # 手动设置 TS 文件总数
ts_urls = []
for i in range(ts_count):
    ts_url = f"{base_url}{i:07d}.ts"   #从 0000000.ts 拼接base_url，拼接自定义个
    ts_urls.append(f"{ts_url}")
print("共有ts文件url如下：")
for ts_url in ts_urls:
    print(ts_url)

#2 下载所有的 .ts 文件
output_dir = "downloaded_ts"
os.makedirs(output_dir, exist_ok=True)
for idx, url in enumerate(ts_urls):
    response = requests.get(url, stream=True)
    file_path = os.path.join(output_dir, f"part{idx:04d}.ts")
    with open(file_path, "wb") as f:
        f.write(response.content)
    print(f"Downloaded: {file_path}")

#3 合并ts文件
with open("output.ts", "wb") as merged_file:
    for idx in range(len(ts_urls)):
        part_path = os.path.join(output_dir, f"part{idx:04d}.ts")
        with open(part_path, "rb") as part_file:
            merged_file.write(part_file.read())
        print(f"Merged: {part_path}")

print("All files merged into output.ts")
