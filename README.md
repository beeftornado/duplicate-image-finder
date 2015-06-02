# Duplicate Image Finder
Identifies similar pictures on your local computer

## Usage
This is a python script so requires python 2.7 or higher. While it was tested on OSX 10.10.3, it should work on any system that has Python installed.

```sh
usage: app.py [-h] [-c CONFIDENCE_THRESHOLD] [--cpus CPUS]
              [-d START_DIR | --osxphotos]

Identify duplicate images in large libraries on the hard drive.

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIDENCE_THRESHOLD, --confidence CONFIDENCE_THRESHOLD
                        at what percent (1-100) similarity should photos be
                        flagged (default 90)
  --cpus CPUS           override number of cpu cores to use, default is to
                        utilize all of them (default 8)
  -d START_DIR, --directory START_DIR
                        folder to start looking for photos
  --osxphotos           scan the Photos app library on Mac
```

## Description

This is a free and configurable way of finding duplicate photos on your computer. Often times photo libraries are shared or individual photos are sent back and forth or imported several times for whatever reason and you may begin to accumlate photos that are the same. In an attempt to reclaim precious iCloud space, this small utility can identify all photos that are duplicates. You may be wondering what is so special about finding pictures that are exactly the same? This won't just identify photos that are the same, but also photos that are **almost** the same. If one photo had some minor edits made to it such as auto-enhance, then it is no longer the same. Even if the file format changed from one to another, like jpg to png, it is no longer the same. Maybe one was saved with lower quality, no longer the same.

This utility actually examines the content of the image and comes up with a percentage of similarity to another image. You can configure what threshold you want to use, but I find that if two images are 90% similar then I need to seriously consider purging one.

I saw plenty of solutions online, but they either cost too much money for such a simple task, or it wasn't configurable enough or performant enough. All of these qualities I hope to tackle here. Free, uses all available cpu power, and a confidence threshold option.

## Known Limitations
There is no caching done of the image hashes so re-running it on the same directory several times takes just as long as the first time.

## How It Works
I hope to describe this in further detail soon, but for the sake of time, it computes a hash, which is an almost unique identifier for each image. Then it compares all of the pictures' hashes to each other and produces what is called a "hamming score" for each pair of pictures. This is a description of how similar the content of the photos are. We then convert that number into a percentage so it is easier to comprehend.

## Future Improvements
The first thing I would really like to do is save all the computed hashes so that incremental comparisons won't be an issue when new photos are imported.
