import re
from unidecode import unidecode

NON_ASCII_REGEX = re.compile(r"[^\x00-\x7F\u2013]")
# Complete punctuation from string.punctuation: !"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~
PUNCTUATIONS = '!"#$%&\'()*+/;<=>@?[\\]^_`{|}~'
PUNCTUATIONS_REGEX = re.compile(r"([%s])" % PUNCTUATIONS)
REAL_SEPARATOR_REGEX = re.compile(r"(([\.,:][^a-zA-Z0-9])|([\.,:]$))")


def unicode_to_ascii(s):
    return unidecode(s)


def normalize_string(s, lower=False):
    s = unicode_to_ascii(s)
    if lower:
        s = s.lower()
    return s


def tokenize(s):
    s = re.sub(PUNCTUATIONS_REGEX, r" \1 ", s)
    s = re.sub(REAL_SEPARATOR_REGEX, r" \1", s)
    words = s.split()
    offsets = []
    offset = 0
    for i, word in enumerate(words):
        start = s.find(word, offset)
        offset = start + len(word)
        offsets.append((word, start))
    return words, offsets

def split_by_last_whitespace(sentence):
    return re.split(r'\s+(?=\S*$)', sentence, 1)