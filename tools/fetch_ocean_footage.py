#!/usr/bin/env python3
"""Download a curated set of openly licensed marine videos from Commons."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from urllib.parse import quote
import requests

OUT=Path('ocean-footage'); RAW=OUT/'raw'; CLIPS=OUT/'clips'
HEADERS={'User-Agent':'HyperFramesOceanFootage/1.2 (open-media editing test)'}
MAX_BYTES=450*1024*1024

# Each source page and license was manually checked before adding it here.
SOURCES=[
 {'file':'Sea turtle in North Sulawesi.webm','slug':'sea-turtle','author':'Marwan Mohamad','license':'CC BY-SA 4.0','license_url':'https://creativecommons.org/licenses/by-sa/4.0/'},
 {'file':'Tropical Fish Banner Fish on Coral Reef.webm','slug':'coral-fish','author':'underwatercam','license':'CC BY','license_url':'https://creativecommons.org/licenses/by/4.0/'},
 {'file':'Shark diving.webm','slug':'reef-shark','author':'Pudelek','license':'CC BY-SA','license_url':'https://creativecommons.org/licenses/by-sa/3.0/'},
 {'file':'Wk215-deep-sea-octopuses.webm','slug':'octopus-garden','author':'NOAA ROV','license':'Public domain (NOAA)','license_url':'https://www.noaa.gov/disclaimer'},
 {'file':'Jellyfish- 2016 Deepwater Exploration of the Marianas.webm','slug':'deep-jellyfish','author':'NOAA Ocean Exploration','license':'Public domain (NOAA)','license_url':'https://www.noaa.gov/disclaimer'},
 {'file':'Sea Nettle.webm','slug':'sea-nettle','author':'Sgerbic','license':'CC BY-SA','license_url':'https://creativecommons.org/licenses/by-sa/4.0/'},
 {'file':'Coral Reef Art.webm','slug':'coral-conservation','author':'VOA Africa','license':'Public domain (Voice of America)','license_url':'https://commons.wikimedia.org/wiki/Commons:Copyright_rules_by_territory/United_States#Works_of_the_federal_government'},
 {'file':'Underwater Videos.webm','slug':'underwater-life','author':'See Commons source page','license':'Open license; see source page','license_url':''},
]

def source_page(name): return 'https://commons.wikimedia.org/wiki/File:'+quote(name.replace(' ','_'),safe='()-,_')
def direct_file(name): return 'https://commons.wikimedia.org/wiki/Special:Redirect/file/'+quote(name,safe='()-,_')

def download(url,path):
 with requests.get(url,headers=HEADERS,stream=True,timeout=(30,360),allow_redirects=True) as r:
  r.raise_for_status(); total=0
  with path.open('wb') as f:
   for chunk in r.iter_content(1024*1024):
    if not chunk: continue
    total+=len(chunk)
    if total>MAX_BYTES: raise RuntimeError('source exceeded 450 MB')
    f.write(chunk)
 return total,r.url

def duration(path):
 return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],text=True).strip())

def normalize(src,dst,index):
 dur=duration(src); length=min(8.0,dur); start=min(max(0,dur-length-.25),.5+index*1.15)
 subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','warning','-ss',f'{start:.3f}','-i',str(src),'-t',f'{length:.3f}','-an','-vf','scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,fps=30,format=yuv420p','-c:v','libx264','-preset','medium','-crf','27','-movflags','+faststart',str(dst)],check=True)
 return dur,start,length

def main():
 RAW.mkdir(parents=True,exist_ok=True); CLIPS.mkdir(parents=True,exist_ok=True); done=[]
 for i,item in enumerate(SOURCES,1):
  raw=RAW/f'{i:02d}_{item["slug"]}.webm'; clip=CLIPS/f'{i:02d}_{item["slug"]}.mp4'
  try:
   print('Downloading',item['file'],flush=True)
   n,final_url=download(direct_file(item['file']),raw)
   dur,start,length=normalize(raw,clip,i)
   row={**item,'title':item['file'].rsplit('.',1)[0],'source_page':source_page(item['file']),'download_url':final_url,'original_bytes':n,'source_duration':dur,'clip_start':start,'clip_duration':length,'clip_file':str(clip.relative_to(OUT)),'clip_bytes':clip.stat().st_size}
   done.append(row); print('Completed',item['slug'],flush=True)
  except Exception as exc:
   print(f'Skipping {item["file"]}: {exc}',file=sys.stderr,flush=True)
  finally: raw.unlink(missing_ok=True)
 if len(done)<5: raise RuntimeError(f'Only normalized {len(done)} clips; need at least 5')
 (OUT/'manifest.json').write_text(json.dumps(done,ensure_ascii=False,indent=2),encoding='utf-8')
 lines=['# Open ocean footage attribution','','Retrieved from Wikimedia Commons for a HyperFrames editing test.','Original licenses and attribution requirements remain in force.','']
 for i,x in enumerate(done,1):
  lines += [f'## {i}. {x["title"]}',f'- Local clip: `{x["clip_file"]}`',f'- Author/credit: {x["author"]}',f'- License: {x["license"]}',f'- License URL: {x["license_url"] or "See source page"}',f'- Source page: {x["source_page"]}',f'- Original download: {x["download_url"]}',f'- Extract: {x["clip_start"]:.2f}s–{x["clip_start"]+x["clip_duration"]:.2f}s','']
 (OUT/'ATTRIBUTION.md').write_text('\n'.join(lines),encoding='utf-8'); print(f'Completed {len(done)} clips',flush=True)
if __name__=='__main__': main()
