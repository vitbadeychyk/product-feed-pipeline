"""Supplier photo URL normalization shared by marketplace feeds."""
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


def marketplace_picture_url(value: str) -> str:
    """Use supplier size 12 images; leave other hosts and unknown paths intact."""
    value = value.strip()
    try:
        url = urlsplit(value)
        if url.scheme not in {"http", "https"} or url.hostname not in {"metr-plus.com.ua", "www.metr-plus.com.ua"}:
            return value
        match = re.fullmatch(r"/img/(\d+)\.(?:jpg|jpeg|png|webp)", url.path, re.IGNORECASE)
        query = parse_qsl(url.query, keep_blank_values=True)
        if match:
            return "https://metr-plus.com.ua/img.php?" + urlencode({"id": match.group(1), "size": "12"})
        if url.path == "/img.php" and any(k == "id" and v.isdigit() for k, v in query):
            query = [(k, v) for k, v in query if k != "size"] + [("size", "12")]
            return urlunsplit(("https", url.netloc, url.path, urlencode(query), url.fragment))
    except ValueError:
        pass
    return value

