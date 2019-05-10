# a MD5 GIF collider

# Ange Albertini 2018-2019

# takes a GIF of 2 frames (so that both frames already share headers, dimensions...)
# and generates 2 GIFs with the same MD5 showing either image.

# only a basic configuration is supported:
#  2 frames, no comments, no color profile, no local palette

# 'gifsicle --colors 256 --delay 100' is a good way to get such an image

import sys
import hashlib
import os
import glob
import shutil


TYPE_EXTENSION  = "!"
TYPE_IMAGE      = ","
TYPE_TERMINATOR = ";"

TYPE = {
  "!":TYPE_EXTENSION ,
  ",":TYPE_IMAGE     ,
  ";":TYPE_TERMINATOR
}

# the only supported ones
FUNCTION_COMMENT = "\xFE"
FUNCTION_GCE     = "\xF9"

FUNCTION = {
  "\xFE":FUNCTION_COMMENT,
  "\xF9":FUNCTION_GCE    ,
}


class Chunk():
  def __init__(self, d, start, end):
    self.start = start
    self.end = end
    self.type = TYPE[d[start]]
    self.function = None
    if self.type == TYPE_EXTENSION:
      self.function = FUNCTION[d[start + 1]]


def readFlags(ll, f):
  flags = {}
  for l in ll:
    flags[l[0]] = f & (2**(l[1]+1)-1)
    f >>= l[1]
  return flags


def skipSubBlocks(offset):
  l = ord(d[offset])
  while (l > 0):
    offset += 1 + l
    l = ord(d[offset])

  offset += 1
  return offset



fn = sys.argv[1]
with open(fn, "rb") as f:
  d = f.read()

assert d.startswith("GIF")      # magic
assert d[3:6] in ["87a", "89a"] # version

flags = readFlags([
  ["GlobalColorTable",1],
  ["ColorResolution", 3],
  ["Sort", 1],
  ["GCTSize", 3],
][::-1],
  ord(d[0xA])
)


if (flags["GlobalColorTable"] == 1):
  gplSize = 3*(2<<(flags["GCTSize"]))
else:
  print "Error: only global palettes are supported"
  assert False

hdrSize = 6 + 7 + gplSize

offset = hdrSize
# print "header size %x"  % hdrSize



chunks = []
while (True):
  chunkStart = offset
  separator = d[offset]

  if (separator == "!"): # Extension
    offset += 2 # skip function code
    offset = skipSubBlocks(offset)
    chunkEnd = offset

  elif (separator == ","): # image descriptor
    flags = d[offset + 9]
    offset += 10 #TODO: handle local palette
    offset += 1 # LZWSize
    offset = skipSubBlocks(offset)
    chunkEnd = offset

  elif (separator == ";"): # terminator
    break

  # discard comments
  if separator == "!":
    if d[chunkStart + 1] == "\xfe":
      continue
  chunks.append(Chunk(d, chunkStart, chunkEnd))


#for c in chunks:
#  print "%08X %08X %s %s" % (c.start, c.end, c.type, c.function if c.function is not None else "" )


assert chunks[0].type == TYPE_EXTENSION
assert chunks[0].function == FUNCTION_GCE

assert chunks[1].type == TYPE_IMAGE

print "File layout: OK"


# set version to 89 as it's the one supporting comment extensions
d = "".join([
  d[:4],
  "9",
  d[5:]])

# set delay of frame 1 to 0xFFFF (10m55s)
offDelay = chunks[0].start + 4
d = "".join([
  d[:offDelay],
  "\xff\xff",
  d[offDelay + 2:]
  ])


# preparing prefix...
prefix = d[:chunks[0].start] + "\x21\xfe" # comment extension

# padding to collision blocks
prefixLen = len(prefix)
if (prefixLen % 64) != 63:
  delta = 62 - (prefixLen % 64)
  prefix = prefix + chr(delta) + " " * delta

  prefix += chr(0x7B) # relative offset of the last difference of a fastcoll
  assert len(prefix) % 64 == 0

prefixHash = hashlib.sha256(prefix).hexdigest()[:8]

print "Prefix hash: %s" % prefixHash


if not glob.glob("gif1-%s.bin" % prefixHash):
  print " Not found! Launching computation..."

  with open("prefix", "wb") as f:
    f.write(prefix)

  os.system("fastcoll -p prefix")
  shutil.copyfile("msg1.bin", "gif1-%s.bin" % prefixHash)
  shutil.copyfile("msg2.bin", "gif2-%s.bin" % prefixHash)
else:
  print " already present."



with open("gif1-%s.bin" % prefixHash, "rb") as f:
  block1 = f.read()
with open("gif2-%s.bin" % prefixHash, "rb") as f:
  block2 = f.read()



assert prefix == block1[:len(prefix)]
assert prefix == block2[:len(prefix)]
assert len(block1) == len(block2)
assert hashlib.md5(block1).digest() == hashlib.md5(block2).digest()

off1 = ord(block1[-5])
off2 = ord(block2[-5])
# relation between these difference
assert off1 == off2 ^ 0x80

print "Prefix pair: OK"


offMin = min(off1, off2)

suffix = (offMin - 4) * " "      # finishing the first comment subblock

suffix += chr(0x80) + 0x7f * " " # trampoline between subblocks

suffix += chr(0x14) + chr(0)     # 14 = extend the comment subblock to the image data subblock
                                 #      (local palette is not supported)
                                 # 00 = close the comment extension before the GCE

suffix += d[chunks[0].start:]    # append the rest of the data



with open("collide1.gif", "wb") as f:
  f.write(block1 + suffix)
with open("collide2.gif", "wb") as f:
  f.write(block2 + suffix)


print "Files written OK:"
print " %s %s" % (hashlib.md5(block1 + suffix).hexdigest(), hashlib.sha256(block1 + suffix).hexdigest())
print " %s %s" % (hashlib.md5(block2 + suffix).hexdigest(), hashlib.sha256(block2 + suffix).hexdigest())
