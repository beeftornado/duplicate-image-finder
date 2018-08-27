# Duplicate Image Finder
Identifies similar pictures on your local computer

## Installation

```sh
git clone https://github.com/beeftornado/duplicate-image-finder.git
cd duplicate-image-finder
pip install -r requirements.txt  # or pip install -e .
duplicateimagefinder/app.py --help
```

## Usage
This is a python script so requires python 2.7 or higher. While it was tested on OSX 10.10.3, it should work on any system that has Python installed.

```sh
usage: app.py [-h] [-c CONFIDENCE_THRESHOLD] [--cpus CPUS]
              [-d DIR | --osxphotos] [-d2 COMPARE_DIR] [-f OUTPUT_FORMAT]
              [--index] [--inverse]

Identify duplicate or very similar images in large libraries on the hard
drive.

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIDENCE_THRESHOLD, --confidence CONFIDENCE_THRESHOLD
                        at what percent (1-100) similarity should photos be
                        flagged (default: 90)
  --cpus CPUS           override number of cpu cores to use, default is to
                        utilize all of them (default: 8)
  -d DIR, --directory DIR
                        folder to start looking for photos
  --osxphotos           scan the Photos app library on Mac
  -d2 COMPARE_DIR, --compare_to COMPARE_DIR
                        By default, images in the directory (-d) are compared
                        to each other, but if you intend on merging two
                        folders, you can instead compare the images in one
                        directory (-d) to those in another (-d2)
  -f OUTPUT_FORMAT, --format OUTPUT_FORMAT
                        how do you want the list of photos presented to you
                        (choices: human, json)
  --index               only index the photos and skip comparison and output
                        steps
  --inverse             instead of picking out duplicates, identify photos
                        that are different
```

## Description

This is a free and configurable way of finding duplicate photos on your computer. Often times photo libraries are shared or individual photos are sent back and forth or imported several times for whatever reason and you may begin to accumlate photos that are the same. In an attempt to reclaim precious iCloud space, this small utility can identify all photos that are duplicates. You may be wondering what is so special about finding pictures that are exactly the same? This won't just identify photos that are the same, but also photos that are **almost** the same. If one photo had some minor edits made to it such as auto-enhance, then it is no longer the same. Even if the file format changed from one to another, like jpg to png, it is no longer the same. Maybe one was saved with lower quality, no longer the same.

This utility actually examines the content of the image and comes up with a percentage of similarity to another image. You can configure what threshold you want to use, but I find that if two images are 90% similar then I need to seriously consider purging one.

I saw plenty of solutions online, but they either cost too much money for such a simple task, or it wasn't configurable enough or performant enough. All of these qualities I hope to tackle here. Free, uses all available cpu power, and a confidence threshold option.

## Examples

### Most Basic: Searching for duplicates in a folder

You want to find duplicate photos in `~/Pictures`

```
./app.py -d ~/Pictures
```

Too much noise, you only want photos that are almost identical

```
./app.py -d ~/Pictures -c 98
```

### OSX Specific: Specifically searching Photos.app library

```
./app.py --osxphotos
```

### Using reduced cpu power
If you want to keep your computer responsive during the scan then you should specify a reduced cpu load. If you print out the usage information via `./app.py -h` then take note of the default cpu value. It will be specific to your computer and then set the value to anything less. In the example I am specifying 4, which is less then my default of 8 (4 cores, 2 threads per core).

```
./app.py -d ~/Pictures --cpus 4
```

### Only comparing two folders
You can pick out the duplicates between folders instead of within itself if you intend to combine folders but would like to pick out the duplicates ahead of time. This could be useful if you favor one folder over another and want to remove duplicates before merging.

```
./app.py -d ~/Pictures/pics\ i\ took -d2 ~/Pictures/pics\ my\ friend\ took -c 98
```

## How It Works
There is absolutely nothing fancy going on here. I just combined some fancy tricks I found in blog posts. I hope to describe this in further detail soon, but for the sake of time, it computes a hash, which is an almost unique identifier for each image. Then it compares all of the pictures' hashes to each other and produces what is called a "hamming score" for each pair of pictures. This is a description of how similar the content of the photos are. We then convert that number into a percentage so it is easier to comprehend.

## Future Improvements
* Option to change output format
* Offer some statistics from the photos like how much space could be saved, how many dupes there are, identify clusters of dupes to surface any events that may have caused them.
