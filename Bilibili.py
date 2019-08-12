import requests
import re
import shutil
import time
import json
from moviepy.editor import *
from selenium import webdriver


class PathException(Exception):
    def __init__(self, msg):
        self.msg = msg


class ConnectionError(Exception):
    def __init__(self, msg):
        self.msg = msg


class Bilibili:
    def __init__(self, url, ua=None, cookies=None):
        self.url = url
        if ua:
            self.ua = ua
        else:
            self.ua = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, " \
                      "like Gecko) Chrome/76.0.3809.87 Safari/537.36"
        self.cookies = cookies

    @staticmethod
    def login():
        browser = webdriver.Chrome(executable_path="./chromedriver")
        browser.get("https://passport.bilibili.com/login")
        while True:
            time.sleep(3)
            for i in browser.get_cookies():
                if i["name"] == "SESSDATA":
                    cookie = {"SESSDATA": i["value"]}
                    browser.close()
                    return cookie

    @staticmethod
    def log(msg):
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

    def get_download_info(self, info, quality_num=112, cookies=None):
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
        if not cookies:
            cookies = self.cookies
        json = requests.get(url, params=params, headers=headers, cookies=cookies).json()
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

    @staticmethod
    def move_file(srcfile, dstfile):
        if os.path.isfile(srcfile):
            if os.path.isfile(dstfile):
                os.remove(dstfile)
            shutil.move(srcfile, dstfile)

    @staticmethod
    def concatenate_clips(base_dir, clips_list, target_dir, filename, ext=".mp4"):
        path_list = []
        video_path = os.path.join(target_dir, filename + ext)
        if os.path.isfile(video_path):
            os.remove(video_path)
        for file in clips_list:
            path = os.path.join(base_dir, file)
            video = VideoFileClip(path)
            path_list.append(video)
        final_clip = concatenate_videoclips(path_list)
        final_clip.to_videofile(video_path, remove_temp=True, codec="h264")
        shutil.rmtree(base_dir)

    @staticmethod
    def pack_files_as_directory(self, target_dir, src_name, new_name):
        if os.path.isdir(os.path.join(target_dir, new_name)):
            shutil.rmtree(os.path.join(target_dir, new_name))
        os.rename(os.path.join(target_dir, src_name), os.path.join(target_dir, new_name))

    def print_quality_options(self):
        self.log("Quality num options:\n"
                "112: '高清 1080P+' (Login Required, Membership Required)\n"
                 "80: '高清 1080P' (Login Required)\n"
                 "64: '高清 720P' (Login Required)\n"
                 "32: '清晰 480P'\n"
                 "16: '流畅 360P'")

    def get_ext(self, format):
        type = ['mp4', 'flv']
        for i in type:
            if format.find(i) != -1:
                return i
        self.log("Unknown File Type: " + format)
        return "flv"

    def get_cookies(self):
        valid_cookies_list = []
        if os.path.isfile("./cookies.json"):
            with open("./cookies.json", "r") as f:
                json_str = f.read()
            json_obj = json.loads(json_str)
            for cookie in json_obj:
                quality = int(self.get_download_info(self.get_page_info()[0],
                                              quality_num=112, cookies=cookie)[0][0]['quality'])
                if quality > 32:
                    valid_cookies_list.append(cookie)
            if not valid_cookies_list:
                valid_cookies_list.append(self.login())
        else:
            valid_cookies_list.append(self.login())
        with open("./cookies.json", "w") as f:
            f.write(json.dumps(valid_cookies_list))
        self.cookies = valid_cookies_list[0]

    def download(self, dirpath=".", filename_in=None, quality_num=112, chuck_size=5000000, concatenate=True):
        if not os.path.isdir(dirpath):
            raise PathException("Save Error: " + dirpath + " is not a Directory.")
        if quality_num >= 64 and not self.cookies:
            self.get_cookies()
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
                self.concatenate_clips(temp_dir, file_list, dirpath, filename, ".mp4")
            else:
                self.pack_files_as_directory(dirpath, ".download", filename)
        self.log("Done!")


if __name__ == "__main__":
    b = Bilibili(input("Please enter URL: "))
    b.print_quality_options()
    b.download(quality_num=int(input("Please enter quality num: ")))
