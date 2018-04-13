import json
import sys
import urllib
import md5
import itertools
import os
import subprocess
import shutil
import threading

def fetch_url(url, tgt):
    urllib.urlretrieve(url, tgt)

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
    print config
    for frag in r['fetch']:
        def fetcher():
            handle_fetch(frag, config)
            sys.stdout.write(".")

        t = threading.Thread(target=fetcher)
        t.start()

def main():
    handle_recipe(sys.argv[1])

if __name__ == "__main__":
    main()


