import json
import logging
import os
import random
import threading
import time
import multiprocessing as mp
from multiprocessing.pool import Pool
from urllib import parse
from collections import OrderedDict, namedtuple
import bs4
import requests

from crawl.exam_base import ExamPaperBase, URLs, LogoutError
from crawl.utils import save_cookies, load_cookies, logger
from crawl.project_info import Project


class ScanLogin(ExamPaperBase):
    def __init__(self):
        try:
            self.sess.get(URLs.login)
        except Exception:
            logging.exception("error")

    @staticmethod
    def remove_scan_flag():
        if os.path.exists(Project.scan_flag):
            os.remove(Project.scan_flag)

    @staticmethod
    def generate_scan_flag():
        with open(Project.scan_flag, "wb") as fp:
            fp.write(b"1")

    @staticmethod
    def get_scan_flag():
        return os.path.exists(Project.scan_flag)

    @logger
    def get_qrcode_url(self):
        resp = self.sess.get(URLs.qrcode)
        soup = bs4.BeautifulSoup(resp.text, "html.parser")
        wrp_code = soup.find("div", attrs={"class": "wrp_code"})
        qrcode_url = wrp_code.contents[0].attrs["src"]
        return qrcode_url

    @staticmethod
    @logger
    def get_ticket(qrcode_url):
        query = dict(
            parse.parse_qsl(
                parse.urlsplit(qrcode_url).query
            )
        )
        return query["ticket"]

    @logger
    def save_qrcode_pic(self, qrcode_url):
        resp = self.sess.get(qrcode_url)
        with open(Project.qrcode, "wb") as fp:
            fp.write(resp.content)

    @logger
    def check_scan(self, ticket):
        logging.info("等待扫码: %s", ticket)
        self.remove_scan_flag()
        query = {
            "ticket": ticket,
            "jump_url": URLs.jump_url,
            "r": random.random()
        }
        check_login_url = URLs.issubscribe + "?" + parse.urlencode(query)
        check_cnt = 0
        scan_status = False
        while check_cnt < Project.check_timeout:
            logging.info("扫码...[%s]", threading.current_thread())
            is_login_resp = self.sess.get(check_login_url)
            resp = json.loads(is_login_resp.text)
            # code = 0 等待扫码
            if resp["code"] == 1:
                scan_status = True
                self.generate_scan_flag()
                break
            time.sleep(1)
            check_cnt += 1
        return scan_status

    @logger
    def login_by_scan(self, ticket):
        wx_query = {
            "ticket": ticket,
            "jump_url": URLs.jump_url
        }
        resp = self.sess.get(
            URLs.wxlogin + '?' + parse.urlencode(wx_query),
            verify=False
        )
        if resp.status_code == 200:
            logging.info("登录成功，保存cookies")
            save_cookies(self.sess.cookies)
        else:
            raise requests.HTTPError("wechat login failed")


class CookiesLogin(ExamPaperBase):
    @logger
    def login_by_cookies(self):
        cookies = load_cookies()
        self.sess.cookies = cookies
        if not self.check_login_succ():
            raise LogoutError("pls scan qrcode to login again")


class ZuJuanView(ExamPaperBase):
    def get_username(self):
        resp = self.get(URLs.user)
        soup = bs4.BeautifulSoup(resp.text, "html.parser")
        real_name = soup.find("div", attrs={"id": "J_realname"})
        return real_name.text.replace("\n", "") if real_name else "未知用户名"

    def get_zujuan_view(self):
        ret = OrderedDict()
        resp = self.get(URLs.zujuan)
        soup = bs4.BeautifulSoup(resp.text, "html.parser")
        zujuan = soup.find("ul", attrs={"class": "f-cb"})
        if zujuan:
            for li in zujuan.find_all("p", attrs={"class": "test-txt-p1"}):
                href = li.find("a")
                Record = namedtuple('Record', ['text', 'href'])
                info = Record(href.text, href["href"])
                ret[href["pid"]] = info
        return ret


class ZuJuanTasks(ExamPaperBase):

    def zujuan_task(self, task):
        print(task)
        time.sleep(10)
        print("end===========")
        return task

    def task_run(self, pool, args):
        for task_args in args:
            pool.apply_async(self.zujuan_task, (task_args,))
        pool.close()
        logging.info("等待所有task执行完成...")
        pool.join()
        logging.info("所有task执行完成...")

    @staticmethod
    def task_shutdown(pool):
        if isinstance(pool, Pool):
            logging.info("终止所有任务")
            pool.terminate()


if __name__ == "__main__":
    mp.freeze_support()
    wx_scan = ScanLogin()
    wx_scan.remove_scan_flag()

    pool = mp.Pool(processes=2)
    zujuan = ZuJuanTasks()
    zujuan.task_run(
        pool,
        [
            ["组卷名称", "href====="],
            ["组卷名称2", "href=====2"],
        ]

    )
    zujuan.task_shutdown(pool)
    # qrcode = wx_scan.get_qrcode_url()
    # wx_scan.save_qrcode_pic(qrcode)
    # ticket = wx_scan.get_ticket(qrcode)
    # print(ticket)
    # wx_scan.check_scan(ticket)
    # wx_scan.login_by_scan(ticket)
    # wx_scan.check_login_succ()
    #
    # cookies_login = CookiesLogin()
    # cookies_login.login_by_cookies()
    #
    # print(ZuJuanView().get_username())
    # print(ZuJuanView().get_zujuan_view())
