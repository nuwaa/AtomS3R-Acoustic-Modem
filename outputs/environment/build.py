from pathlib import Path
import subprocess
import os
import json
import hashlib
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor

base = Path(__file__).resolve().parent
config = json.loads((base/'settings.json').read_text(encoding='utf-8'))
root = base.parent
core = Path(config['core'])
sdk = Path(config['sdk'])
bin = Path(config['compiler_bin'])
os.environ['XTENSA_GNU_CONFIG'] = str(bin.parent/'lib/xtensa_esp32s3.so')
out = Path(config['build_directory'])
out.mkdir(parents=True,exist_ok=True)
sketch = root/'AtomS3R_AfskRx'
library = Path(config['echo_library'])
gfx = Path(config['gfx_library'])
includes = [sketch,core/'cores/esp32',core/'variants/esp32s3',library]
for lib in ['Wire','ESP_I2S','FS','SPI','Preferences']:
    includes.append(core/'libraries'/lib/'src')
includes.append(gfx)
common = ['-MMD','-mdynconfig=xtensa_esp32s3.so','-c','-Os','-Werror=return-type','-DF_CPU=240000000L','-DARDUINO=10607',
          '-DARDUINO_ESP32S3_DEV','-DARDUINO_ARCH_ESP32','-DESP32=ESP32',
          '-DARDUINO_BOARD="ESP32S3_DEV"','-DARDUINO_VARIANT="esp32s3"',
          '-DARDUINO_PARTITION_default_8MB','-DCORE_DEBUG_LEVEL=0',
          '-DARDUINO_RUNNING_CORE=1','-DARDUINO_EVENT_RUNNING_CORE=1',
          '-DBOARD_HAS_PSRAM','-DARDUINO_USB_MODE=1','-DARDUINO_USB_CDC_ON_BOOT=1',
          '-DARDUINO_USB_MSC_ON_BOOT=0','-DARDUINO_USB_DFU_ON_BOOT=0',
          '@'+str(sdk/'flags/defines'),'-iprefix',sdk.as_posix()+'/include/',
          '@'+str(sdk/'flags/includes'),'-I'+str(sdk/'qio_opi/include')]
common += ['-I'+str(p) for p in includes]
sources = [sketch/'AtomS3R_AfskRx.ino']
sources += sorted(sketch.glob('*.cpp'))
for folder in [core/'cores/esp32',library]+includes[4:]:
    sources += [p for p in folder.rglob('*') if p.suffix in ('.cpp','.c','.S')]

# Header edits must invalidate object files as well as .ino edits.
headers = sorted(set(p for folder in includes for p in folder.rglob('*.h')))
dependency_hash = hashlib.sha256()
dependency_hash.update(json.dumps(common).encode())
for p in headers:
    dependency_hash.update(str(p).encode())
    dependency_hash.update(p.read_bytes())
header_key = dependency_hash.hexdigest()
cache_file = out/'cache.json'
cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
if '--clean' in sys.argv: cache = {}
new_cache = {}

def compile_one(item):
    i, source = item
    obj = out/f'{i}_{source.name}.o'
    key = hashlib.sha256(header_key.encode()+str(source).encode()+source.read_bytes()).hexdigest()
    new_cache[str(source)] = key
    if obj.exists() and cache.get(str(source)) == key:
        return obj
    cpp = source.suffix in ('.cpp','.ino')
    language = ['-x','c++'] if source.suffix=='.ino' else []
    flag = 'cpp_flags' if cpp else 'S_flags' if source.suffix=='.S' else 'c_flags'
    compiler = bin/('xtensa-esp-elf-g++.exe' if cpp else 'xtensa-esp-elf-gcc.exe')
    command = [str(compiler),'@'+str(sdk/'flags'/flag)]+common+language+[str(source),'-o',str(obj)]
    result = subprocess.run(command,capture_output=True,text=True)
    if result.returncode:
        print(result.stdout+result.stderr,flush=True)
        raise RuntimeError(str(source))
    if result.stderr:
        print(result.stderr,flush=True)
    print('Compiled',source.name,flush=True)
    return obj

workers = max(1, int(os.environ.get('ATOM_BUILD_WORKERS', '3')))
with ThreadPoolExecutor(max_workers=workers) as pool:
    objects = list(pool.map(compile_one,enumerate(sources)))
cache_file.write_text(json.dumps(new_cache,indent=2))
elf=out/'AtomS3R_AfskRx.elf'
command = [str(bin/'xtensa-esp-elf-g++.exe'),'-mdynconfig=xtensa_esp32s3.so',
    '-Wl,--Map='+str(out/'AtomS3R_AfskRx.map'),
    '-L'+str(sdk/'lib'),'-L'+str(sdk/'ld'),'-L'+str(sdk/'qio_opi'),
    '-Wl,--wrap=esp_panic_handler','@'+str(sdk/'flags/ld_flags'),
    '@'+str(sdk/'flags/ld_scripts'),'-Wl,--start-group']
command += [str(p) for p in objects]+['@'+str(sdk/'flags/ld_libs'),'-Wl,--end-group','-Wl,-EL','-o',str(elf)]
subprocess.run(command,check=True)
subprocess.run([str(bin/'xtensa-esp-elf-size.exe'),str(elf)],check=True)
print('PASS: ESP32-S3 full ELF compile/link using Arduino-ESP32 3.3.2 and M5Atomic-EchoBase 1.0.2',flush=True)
firmware=root/'firmware'
firmware.mkdir(exist_ok=True)
for src,name in [(elf,'application.bin'),(sdk/'bin/bootloader_qio_80m.elf','bootloader.bin')]:
    subprocess.run([config['esptool'],'--chip','esp32s3','elf2image','--flash-mode','dio',
                    '--flash-freq','80m','--flash-size','8MB','-o',str(firmware/name),str(src)],check=True)
subprocess.run([sys.executable,str(core/'tools/gen_esp32part.py'),
                str(core/'tools/partitions/default_8MB.csv'),str(firmware/'partitions.bin')],check=True)
shutil.copyfile(core/'tools/partitions/boot_app0.bin',firmware/'boot_app0.bin')
print('Firmware ready:',firmware,flush=True)
