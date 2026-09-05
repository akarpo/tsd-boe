import warnings; warnings.filterwarnings("ignore")
import json, numpy as np, soundfile as sf, torch, collections
from speechbrain.inference.speaker import EncoderClassifier
T="/Users/Alex/Downloads/tsd-boarddocs/scratch/tsd-transcripts/Troy School Board Meeting - 2026-09-01.transcript.json"
utts=json.load(open(T))['utterances']
rows=json.load(open("embs_ecapa.json"))+json.load(open("embs_ecapa_short.json"))
E=np.array([r['emb'] for r in rows]); E/=np.linalg.norm(E,axis=1,keepdims=True)
byidx={r['idx']:k for k,r in enumerate(rows)}
A=json.load(open("E_ecapa_assign.json"))
names=['STEPH','AUDRA','A','B','F','G']
cent={}
for n in ('STEPH','AUDRA'):
    m=[byidx[int(k)] for k,v in A.items() if v['best']==n and v['dur']>=3 and v['margin']>=0.2]; cent[n]=E[m].mean(0)
for sp in 'ABFG': cent[sp]=E[[k for k,r in enumerate(rows) if r['speaker']==sp]].mean(0)
C=np.array([cent[n]/np.linalg.norm(cent[n]) for n in names])
def hms(ms): s=ms//1000; return f"{s//3600}:{s%3600//60:02d}:{s%60:02d}"
# 1. short E utterances (<1s): assign by STEPH/AUDRA only
short={}
for r in json.load(open("embs_ecapa_short.json")):
    e=np.array(r['emb']); e/=np.linalg.norm(e); s=e@C[:2].T
    short[r['idx']]={'best':names[int(np.argmax(s))],'margin':round(float(abs(s[0]-s[1])),3)}
print("short E (<1s):",collections.Counter(v['best'] for v in short.values()))
json.dump(short,open("E_short_assign.json","w"))
# 2. kNN check for ambiguous utterances: 10 nearest embedded utterances (excluding self), by cluster/assignment
def lab(k):
    r=rows[k]
    if r['speaker']=='E':
        a=A.get(str(r['idx'])); return a['best'] if a and a['dur']>=3 and a['margin']>=0.2 else 'E?'
    return r['speaker']
for i in [688,744,815,1041,473,475,1044,1046,662,164,1070,1083,1087,1094,1104]:
    k=byidx[i]; s=E@E[k]; o=np.argsort(-s)[1:11]
    print(f"kNN {i} {hms(rows[k]['start'])}: {collections.Counter(lab(j) for j in o).most_common()}  {rows[k]['text'][:60]}")
# 3. sliding windows on long E utterances
wav,sr=sf.read("tsd_2026-09-01_16k.wav",dtype='float32')
enc=EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir="ecapa", run_opts={"device":"cpu"})
print("\nsliding 4s windows (hop 2s) on E utterances >= 12s — S=Stephanie A=Audra g=DiPilato b=Nancy .=other")
mixed=[]
for i,u in enumerate(utts):
    if u['speaker']!='E' or u['end']-u['start']<12000: continue
    seq=[]
    for t in range(u['start'], u['end']-4000+1, 2000):
        seg=torch.from_numpy(wav[t*16:(t+4000)*16]).unsqueeze(0)
        with torch.no_grad(): e=enc.encode_batch(seg).squeeze().numpy()
        e/=np.linalg.norm(e); s=e@C.T; b=names[int(np.argmax(s))]
        seq.append({'STEPH':'S','AUDRA':'A','G':'g','B':'b'}.get(b,'.'))
    st="".join(seq); a=A[str(i)]['best']
    flag = "  <-- mixed" if (st.count('S')>=2 and st.count('A')>=2) else ""
    if flag: mixed.append(i)
    print(f"{i:4d} {hms(u['start'])} {a:5s} {st}{flag}")
json.dump(mixed,open("E_mixed.json","w"))
