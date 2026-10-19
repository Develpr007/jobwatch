import time
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

DEFAULT_HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def get(s: requests.Session, url: str, retries: int = 2, timeout: int = 30, **kw):
    last = None
    for i in range(retries + 1):
        try:
            r = s.get(url, timeout=timeout, **kw)
            if r.status_code in (429, 500, 502, 503, 504) and i < retries:
                time.sleep((15 if r.status_code == 429 else 2) * (i + 1))
                continue
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last


def post(s: requests.Session, url: str, retries: int = 3, timeout: int = 30, **kw):
    last = None
    for i in range(retries + 1):
        try:
            r = s.post(url, timeout=timeout, **kw)
            if r.status_code in (429, 500, 502, 503, 504) and i < retries:
                time.sleep((15 if r.status_code == 429 else 2) * (i + 1))
                continue
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last
