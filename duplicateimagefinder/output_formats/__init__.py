from duplicateimagefinder.enums import *
import human
import jsono


def outputter_for_format(fmt):
    if fmt is Formats.HUMAN_READABLE:
        return human.HumanFormat()
    if fmt is Formats.JSON:
        return jsono.JsonFormat()
    else: return human.HumanFormat()
