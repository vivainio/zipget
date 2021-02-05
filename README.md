# zipget

Problem: you want to download and unzip a bunch of files somewhere, possibly getting them from offline cache if they
were downloaded earlier.

Zipget ingests a json recipe like this:

```json

{
    "config": {
        "archive": ["./t/archive"]
    },
    "fetch": [
        {
            "url": "https://github.com/vivainio/Modulize/releases/download/v2.1/Modulize.zip",
            "unzipTo": "./t"
        },
        {
            "url": "https://github.com/vivainio/hashibuild/archive/v0.1.zip",
            "unzipTo": "./t",
            "saveAs": "./t/zippi.zip"
        }
    ]
}

```

This loads the files to archive:

```
    Directory: C:\p\zipget\t\archive


Mode                LastWriteTime         Length Name
----                -------------         ------ ----
-a----        13.4.2018     19:29         950579 94bff44741872f5164bd2e4221cb89f6_Modulize.zip
-a----        13.4.2018     19:29           3398 f045a290c3022282299bce7d1f04ebce_v0.1.zip
```

The preceding hash is the md5 checkum of the url (so same url is not downloaded twice).

And then it unzips the files to target directory, and/or saves the downloaded file to specified file.

# Installation

```
$ pip install zipget
$ zipget my_recipe.json

# Or: python -m zipget my_recipe.json
```

