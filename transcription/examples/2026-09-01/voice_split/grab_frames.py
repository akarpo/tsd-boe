import json, subprocess, os
T="/Users/Alex/Downloads/tsd-boarddocs/scratch/tsd-transcripts/Troy School Board Meeting - 2026-09-01.transcript.json"
V="/Users/Alex/Downloads/tsd-boarddocs/scratch/tsd-transcripts/tsd_2026-09-01.mp4"
utts=json.load(open(T))['utterances']
jobs=[]
for i,u in enumerate(utts):
    if u['speaker'] not in "ABEFG": continue
    dur=(u['end']-u['start'])/1000
    if dur<2.5: continue
    t=u['start']/1000 + (2.0 if dur>=4 else dur/2)
    out=f"uframes/u{i:04d}.jpg"
    if os.path.exists(out): continue
    jobs.append((i,t,out))
print(len(jobs),"frames to grab",flush=True)
for n,(i,t,out) in enumerate(jobs):
    subprocess.run(["ffmpeg","-loglevel","error","-y","-ss",f"{t:.2f}","-i",V,"-frames:v","1","-vf","scale=320:-1","-q:v","4",out])
    if n%50==0: print(n,flush=True)
print("done")
