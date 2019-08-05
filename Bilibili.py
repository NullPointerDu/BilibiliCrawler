import requests
import re, shutil
from moviepy.editor import *


class PathException(Exception):
    def __init__(self, msg):
        self.msg = msg


class ConnectionError(Exception):
    def __init__(self, msg):
        self.msg = msg


class Bilibili:
    def __init__(self, url, ua=None, cookies={}):
        self.url = url
        if ua:
            self.ua = ua
        else:
            self.ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, " \
                      "like Gecko) Chrome/76.0.3809.87 Safari/537.36"
        self.cookies = cookies

    def log(self, msg):
        print(msg)

    def get_page_info(self):
        # html = requests.get(self.url, headers={"User-Agent": self.ua}).text
        # session_pattern = re.compile(r"<script>window\.__playinfo__=.*?\"session\":\"(.*?)\"")
        # session = session_pattern.findall(html)[0]
        aid_pattern = re.compile(r"/av(\d+)")
        aid = aid_pattern.search(self.url).group(1)
        url = "https://api.bilibili.com/x/web-interface/view"
        params = {
            "aid": aid
        }
        json = requests.get(url, params=params, headers={"User-Agent": self.ua}, cookies=self.cookies).json()
        title = re.sub(r"[\/\\\:\*\?\"\<\>\|]", "-", json['data']['title'])
        info = []
        for i in json['data']['pages']:
            info.append({"aid": aid, "cid": i["cid"], "title": title, "part": i["part"]})
        return info

    def get_download_info(self, info, quality_num=112):
        url = "https://api.bilibili.com/x/player/playurl"
        params = {
            "avid": info.get("aid"),
            "cid": info.get("cid"),
            "qn": quality_num,
            "type": "",
            "otype": "json",
            "fnver": 0,
            "fnval": quality_num,
            "session": ""
        }
        headers = {
            "Referer": self.url,
            "Sec-Fetch-Mode": "cors",
            "User-Agent": self.ua
        }
        json = requests.get(url, params=params, headers=headers, cookies=self.cookies).json()
        durl = json['data']['durl']
        quality = json['data']['quality']
        quality_options = json['data']['accept_quality']
        quality_descriptions = json['data']['accept_description']
        quality_dict = {}
        for index in range(len(quality_options)):
            quality_dict[quality_options[index]] = quality_descriptions[index]
        format = json['data']['format']
        urls = []
        for i in durl:
            urls.append({'url': i['url'], 'length': i['size'], 'order': i['order'], 'quality': quality})
        return urls, quality_dict, format

    def download_partial(self, url, range="0-"):
        headers = {
            "range": "bytes=" + range,
            "Referer": self.url,
            "Sec-Fetch-Mode": "cors",
            "User-Agent": self.ua
        }
        req = requests.get(url, headers=headers)
        size_info = req.headers.get("Content-Range")
        return req.content, size_info

    def move_file(self, srcfile, dstfile):
        if os.path.isfile(srcfile):
            if os.path.isfile(dstfile):
                os.remove(dstfile)
            shutil.move(srcfile, dstfile)

    def concatenate_clips(self, base_dir, clips_list, target_dir, filename, ext):
        # target_file_path = os.path.join(target_dir, filename)
        # clips_path_list = []
        # for clip in clips_list:
        #     clip_path = os.path.join(base_dir, clip)
        #     video = VideoFileClip(clip_path)
        #     clips_path_list.append(video)
        # final_clip = concatenate_videoclips(clips_path_list)
        # final_clip.to_videofile(target_file_path, fps=24, remove_temp=False, codec="copy")

        for clip in clips_list:
            clip_path = os.path.join(base_dir, clip)
            order = clip.split(".")[0]
            # filename_list = filename.split(".")
            # name = filename_list[0]
            # ext = "." + filename_list[1]
            self.move_file(clip_path, os.path.join(target_dir, filename + "_" + order + ext))
        shutil.rmtree(base_dir)

    def pack_files_as_directory(self, target_dir, src_name, new_name):
        if os.path.isdir(os.path.join(target_dir, new_name)):
            shutil.rmtree(os.path.join(target_dir, new_name))
        os.rename(os.path.join(target_dir, src_name), os.path.join(target_dir, new_name))

    def get_ext(self, format):
        type = ['mp4', 'flv']
        for i in type:
            if format.find(i) != -1:
                return i
        self.log("Unknown File Type: " + format)
        return "flv"

    def download(self, dirpath=".", filename_in=None, quality_num=112, chuck_size=5000000, concatenate=True):
        if not os.path.isdir(dirpath):
            raise PathException("Save Error: " + dirpath + " is not a Directory.")
        # ext = ".flv"
        for i in self.get_page_info():
            temp_dir = os.path.join(dirpath, ".download")
            if os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            download_info = self.get_download_info(i, quality_num=quality_num)
            download_durl = download_info[0]
            quality_dict = download_info[1]
            ext = "." + self.get_ext(download_info[2])
            if filename_in:
                filename = filename_in + "_" + i['part']
            else:
                filename = i['title'] + "_" + i['part']
            file_list = []
            if chuck_size > 0:
                for url in download_durl:
                    download_file_name = str(url['order']) + ext
                    download_file = os.path.join(temp_dir, download_file_name)
                    download_url = url["url"]
                    current_byte = 0
                    length = url["length"]
                    self.log("Downloading From: " + download_url)
                    self.log("Quality: " + quality_dict[url['quality']])
                    while current_byte < length:
                        range = str(current_byte) + "-" + str(current_byte + chuck_size - 1)
                        error = 0
                        data = None
                        while error < 5 and not data:
                            try:
                                download = self.download_partial(download_url, range=range)
                                data = download[0]
                                size_info = download[1]
                                self.log(size_info)
                            except Exception as e:
                                self.log("ERROR: " + repr(e) + "\n Retry: " + str(error + 1))
                                if error == 4:
                                    shutil.rmtree(temp_dir)
                                    raise e
                                error += 1
                        with open(download_file, "ab+") as f:
                            f.write(data)
                        current_byte += chuck_size
                    file_list.append(download_file_name)
            else:
                for url in download_durl:
                    download_file_name = str(url['order']) + ext
                    download_file = os.path.join(temp_dir, download_file_name)
                    error = 0
                    data = None
                    self.log("Downloading From: " + url["url"])
                    self.log("Quality: " + quality_dict[url['quality']])
                    while error < 5 and not data:
                        try:
                            data = self.download_partial(url["url"])[0]
                        except Exception as e:
                            self.log("ERROR: " + repr(e) + "\n Retry: " + str(error + 1))
                            if error == 4:
                                shutil.rmtree(temp_dir)
                                raise e
                            error += 1
                    with open(download_file, "wb+") as f:
                        f.write(data)
                    file_list.append(download_file_name)
            # concatenate clips
            file_list.sort()
            if concatenate:
                self.concatenate_clips(temp_dir, file_list, dirpath, filename, ext)
            else:
                self.pack_files_as_directory(dirpath, ".download", filename)
        self.log("Done!")


if __name__ == "__main__":
    b = Bilibili(input("Please enter url: "))
    b.download(quality_num=int(input("Please enter quality num: ")))
