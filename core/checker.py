import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from database import get_all_active_proxies, update_ping, increment_fail_count, deactivate_proxy

MAX_FAIL_COUNT = 3


def check_proxy_ping(server, port, timeout=3.0):
    start = time.perf_counter()
    try:
        with socket.create_connection((server, port), timeout=timeout):
            return int((time.perf_counter() - start) * 1000)
    except (socket.timeout, OSError):
        return None


def check_one_proxy(proxy):
    ping = check_proxy_ping(proxy["server"], proxy["port"])

    if ping is not None:
        update_ping(proxy["proxy_url"], ping)
        return proxy["proxy_url"], ping

    increment_fail_count(proxy["proxy_url"])
    if proxy["fail_count"] + 1 >= MAX_FAIL_COUNT:
        deactivate_proxy(proxy["proxy_url"])

    return proxy["proxy_url"], None


def check_all_active_proxies(limit=100, max_workers=20):
    proxies = [dict(p) for p in get_all_active_proxies(limit=limit)]

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(check_one_proxy, p) for p in proxies]
        for future in as_completed(futures):
            results.append(future.result())

    success_count = sum(1 for _, ping in results if ping is not None)
    print(f"{success_count}/{len(results)} active proxies")
    return results