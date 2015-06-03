from duplicateimagefinder.enums import *
import human


def outputter_for_format(fmt):
    if fmt is Formats.HUMAN_READABLE:
        return human.HumanFormat()
    else: return human.HumanFormat()
