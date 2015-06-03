class Formats(object):
    """
    Output format definitions
    """
    HUMAN_READABLE = 1
    JSON = 2
    CSV = 3
    ASCII_TABLE = 4

    @classmethod
    def from_option(cls, opt):
        o = str(opt).lower()
        if o == 'human': return cls.HUMAN_READABLE
        elif o == 'json': return cls.JSON
        elif o == 'csv': return cls.CSV
        elif o == 'table': return cls.ASCII_TABLE
        else: return cls.HUMAN_READABLE
