"""Stage the verified local JHZA6 reference into a patched t2s source checkout."""
from pathlib import Path
import hashlib, sys, struct
reference, device = map(Path, sys.argv[1:])
data = reference.read_bytes()
if hashlib.sha256(data).hexdigest() != '31d3fd5882b57a3fb772991e56ce24c9df51fceb25240237844616b194d1faa7':
    raise ValueError('Unexpected reference image digest')
page = struct.unpack_from('<I', data, 36)[0]
kernel, ramdisk = [struct.unpack_from('<I', data, i)[0] for i in (8,16)]
dto, offset = struct.unpack_from('<IQ',data,1632)
dtb = struct.unpack_from('<I',data,1648)[0]
sections = {'Image':data[page:page+kernel], 'dtbo.img':data[offset:offset+dto]}
start = (offset+dto+page-1)//page*page
sections['dtb'] = data[start:start+dtb]
for name, content in sections.items():
    (device/'t2s/prebuilt'/name).write_bytes(content)
import gzip, re, stat
begin=(page+kernel+page-1)//page*page
archive=gzip.decompress(data[begin:begin+ramdisk])
pos=0
while archive[pos:pos+6] == b'070701':
    f=[int(archive[i:i+8],16) for i in range(pos+6,pos+110,8)]
    name=archive[pos+110:pos+109+f[11]].decode()
    start=(pos+110+f[11]+3)&~3
    pos=(start+f[6]+3)&~3
    if name=='TRAILER!!!':
        break
    if stat.S_ISREG(f[1]) and re.fullmatch(r'lib/modules/[\w.\-]+|vendor/firmware/y792_t2\.bin',name):
        dest=device/'t2s/jhza6-root'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(archive[start:start+f[6]])
