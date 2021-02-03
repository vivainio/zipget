from __future__ import print_function

import json
import sys
from urllib.request import urlopen
from urllib.error import HTTPError
from hashlib import md5
from typing import List
import itertools
import os
import subprocess
import shutil
import threading
import time
import tempfile
from argparse import ArgumentParser
import pprint

MAX_RETRIES = 5
BLOCK_SIZE = 10 * 1024 * 1024


def stream_to_file(to_file_name, from_file_obj):
    fd, tmpfile_name = tempfile.mkstemp(dir=os.path.dirname(to_file_name))
    print("to", tmpfile_name)
    try:
        while 1:
            block = from_file_obj.read(BLOCK_SIZE)
            if not block:
                break
            os.write(fd, block)
    finally:
        os.close(fd)
        try:
            os.rename(tmpfile_name, to_file_name)
        except WindowsError as e:
            print(e)


process_exit_code = 0

_report_log = []


def report_ok(s):
    _report_log.append(s)


def report_flush():
    out = "\n".join("zipget: " + l for l in _report_log)
    print(out)


def fetch_url(url, tgt):
    retries = MAX_RETRIES
    global process_exit_code
    while 1:

        try:
            content = urlopen(url)
        except HTTPError as e:
            if e.code >= 500:
                retries -= 1
                print("Fail", url, "retry", retries, e)
                if retries <= 0:
                    raise e
                time.sleep(5)
                continue
            else:
                process_exit_code = 1
                raise
        except Exception as e:
            print("Fail with exception", e)
            process_exit_code = 2
            raise

        stream_to_file(tgt, content)

        break


def file_name_from_url(url):
    hash = md5(url.encode()).hexdigest()
    fpart = "".join(ch for ch in url.rsplit("/")[-1] if ch.isalnum())
    return hash + "_" + fpart


def unzip_to(fname, tgt):
    ensure_dir_for(tgt)

    with open(fname, "rb") as f:
        if f.read(2) != b"PK":
            print("Not zip file, head, deleting:")
            print(f.read(1000))
            f.close()
            os.remove(fname)
            raise Exception("File was not zip file %s (%s), deleted", fname, tgt)

    parms = ["-o", fname, "-d", tgt]
    status = subprocess.call(["unzip", "-q"] + parms)
    if status != 0:
        print("unzip failed, retrying", parms)
        time.sleep(1)
        subprocess.check_call(["unzip"] + parms)

    report_ok("unzipped %s <- %s" % (tgt, fname))


def path_from_config(config, path):
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(config["root"], path))


def run_exe(target_path, args):
    parts = [target_path] + args
    print(">", target_path, args)
    subprocess.check_call(parts)


def run_shell_commands(target_path, args_list):
    for args in args_list:
        print(">", target_path, args)
        subprocess.check_call(args, shell=True, cwd=target_path)


def ensure_dir(dname):
    if not os.path.isdir(dname):
        try:
            os.makedirs(dname)
        except WindowsError as err:
            print("ensure_dir failed because of %s, ignoring" % err)


def ensure_dir_for(pth):
    dname = os.path.dirname(pth)
    if not dname:
        return
    ensure_dir(dname)


def handle_fetch(fetch, config):
    url = fetch["url"]
    fname = file_name_from_url(url)
    archive_dir = path_from_config(config, config["archive"])
    targetpath = os.path.join(archive_dir, fname)
    if not os.path.isfile(targetpath):
        fetch_url(url, targetpath)

    if not os.path.isfile(targetpath):
        raise Exception("File didn't exist: %s (%s)" % targetpath)

    filepath = os.path.abspath(os.path.dirname(__file__))
    saveTarget = fetch.get("saveAs")
    ziptarget = fetch.get("unzipTo")
    runargs = fetch.get("runWithArgs")

    if saveTarget:
        targetdir = os.path.dirname(path_from_config(config, saveTarget))
    elif ziptarget:
        targetdir = path_from_config(config, ziptarget)
    else:
        raise RuntimeError("Either unzipTo or saveAs needs to be defined")

    precommands = fetch.get("preCommands")
    if precommands:
        run_shell_commands(
            path_from_config(config, targetdir),
            [
                [f.replace("[[FILEPATH]]", filepath) for f in command]
                if isinstance(command, ListType)
                else command.replace("[[FILEPATH]]", filepath)
                for command in precommands
            ],
        )

    if ziptarget:
        unzip_to(targetpath, path_from_config(config, ziptarget))

    if saveTarget:
        trg = path_from_config(config, saveTarget)
        ensure_dir_for(trg)
        shutil.copy(targetpath, trg)
        report_ok("saved %s <- %s" % (trg, targetpath))

    if runargs:
        rerouted = [f.replace("[[FILEPATH]]", filepath) for f in runargs]
        run_exe(targetpath, rerouted)

    postcommands = fetch.get("postCommands")
    if postcommands:
        run_shell_commands(
            path_from_config(config, targetdir),
            [
                [f.replace("[[FILEPATH]]", filepath) for f in command]
                if isinstance(command, List)
                else command.replace("[[FILEPATH]]", filepath)
                for command in postcommands
            ],
        )


def created_temp_dir():
    """ creates archive directory in temp (used of none of specified exist) """
    pth = os.path.join(tempfile.gettempdir(), "zipget")
    if not os.path.isdir(pth):
        print("Warning: none of archive dirs existed, creating", pth)
        os.makedirs(pth)
    return pth


def accept_frag(frag, tags):
    # user didn't specify tags -> install everything
    if not tags:
        return True

    if not frag.get("tags"):
        return False
    # user specified tags -> install only if overlapping tags
    return len(set(tags).intersection(set(frag["tags"]))) > 0


def handle_recipe(fname, args):
    r = json.load(open(fname))

    config = {"root": os.path.abspath(os.path.dirname(fname))}
    archive_dirs = r["config"]["archive"]
    archive_tries = [
        f for f in archive_dirs if os.path.isdir(path_from_config(config, f))
    ]
    if len(archive_tries) == 0:
        archive = created_temp_dir()
    else:
        archive = archive_tries[0]

    config["archive"] = path_from_config(config, archive)
    threads = []
    frags = [frag for frag in r["fetch"] if accept_frag(frag, args.tags)]
    if args.v:
        pprint.pprint(config)
        pprint.pprint(frags)
    for frag in frags:
        t = threading.Thread(target=handle_fetch, args=(frag, config))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    report_flush()
    if process_exit_code > 0:
        print("Zipget failed with exit code", process_exit_code)
        sys.exit(process_exit_code)


def run(args):
    """ Handle and dispatch args. Can be used as 'api' """
    p = ArgumentParser()
    p.add_argument("recipe", nargs=1, help="Recipe (json) file to run")
    p.add_argument(
        "tags", nargs="*", metavar="tag", help="Tags for parts of recipe to run"
    )
    p.add_argument("-v", action="store_true", help="Verbose output")
    parsed = p.parse_args(args)
    recipe = parsed.recipe[0]
    handle_recipe(recipe, parsed)


def main():
    run(sys.argv[1:])


if __name__ == "__main__":
    main()
