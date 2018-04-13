import json
import sys
from urllib2 import urlopen, HTTPError
import md5
import itertools
import os
import subprocess
import shutil
import threading
import time

MAX_RETRIES = 5
BLOCK_SIZE = 10 * 1024 * 1024

def stream_to_file(to_file_name, from_file_obj):
    with open(to_file_name, "wb") as f:
        while 1:
            block = from_file_obj.read(BLOCK_SIZE)
            if not block:
                break
            f.write(block)

process_exit_code = 0


def fetch_url(url, tgt):
    retries = MAX_RETRIES
    global process_exit_code

    while 1:

        try:
            content = urlopen(url)
        except HTTPError,e:
            if e.code >= 500:
                retries -= 1
                print "Fail", url, "retry", retries, e
                if retries <= 0:
                    raise e
                time.sleep(5)
                continue
            else:
                process_exit_code = 1
                raise
        stream_to_file(tgt, content)
        break


def file_name_from_url(url):
    hash = md5.md5(url).hexdigest()

    return hash + "_" + url.rsplit("/")[-1]

def unzip_to(fname, tgt):
    subprocess.check_call(["unzip",  "-o", "-q", fname, "-d", tgt])

def path_from_config(config,path):
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(config['root'], path))


def handle_fetch(fetch, config):
    url = fetch['url']
    fname = file_name_from_url(url)
    archive_dir = path_from_config(config, config['archive'])
    targetpath = os.path.join(archive_dir, fname)
    if not os.path.isfile(targetpath):
        fetch_url(url, targetpath)
    ziptarget = fetch.get('unzipTo')
    if ziptarget:
        unzip_to(targetpath, path_from_config(config, ziptarget))
    saveTarget = fetch.get("saveAs")
    if saveTarget:
        shutil.copy(targetpath, path_from_config(config, saveTarget))


def handle_recipe(fname):
    r = json.load(open(fname))

    config = {
        "root": os.path.abspath(os.path.dirname(fname))
    }
    archive_dirs = r['config']['archive']
    archive = [f for f in archive_dirs if os.path.isdir(path_from_config(config, f) )][0]
    config['archive'] = path_from_config(config, archive)
    threads = []
    for frag in r['fetch']:
        t = threading.Thread(target=handle_fetch, args=(frag, config))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    if process_exit_code > 0:
        print "Zipget failed with exit code", process_exit_code
        sys.exit(process_exit_code)

def main():
    handle_recipe(sys.argv[1])

if __name__ == "__main__":
    main()


