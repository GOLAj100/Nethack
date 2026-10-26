"""Extract MP4 audio once with ffmpeg; originals are never modified."""
import os
import shutil
import subprocess
import sys
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(errors='replace')
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg=get_ffmpeg_exe()
        except (ImportError,RuntimeError): pass
    if not ffmpeg:
        print('Install ffmpeg and add it to PATH, then run this script again.')
        return 1
    errors=0
    for folder,_,files in os.walk(os.path.join(ROOT,'Sound trak')):
        for filename in files:
            if not filename.lower().endswith('.mp4'): continue
            source=os.path.join(folder,filename)
            dest=os.path.join(ROOT,'sound_cache',os.path.relpath(folder,os.path.join(ROOT,'Sound trak')),filename+'.ogg')
            if os.path.isfile(dest): continue
            os.makedirs(os.path.dirname(dest),exist_ok=True)
            temp=dest+'.tmp.ogg'
            result=subprocess.run([ffmpeg,'-nostdin','-v','error','-y','-i',source,'-vn','-c:a','libvorbis','-q:a','4',temp])
            if result.returncode:
                errors+=1
                if os.path.exists(temp): os.remove(temp)
            else:
                os.replace(temp,dest)
                print(os.path.relpath(dest,ROOT))
    return bool(errors)

if __name__=='__main__': sys.exit(main())
