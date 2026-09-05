import os, json, numpy as np, collections
from PIL import Image
T="/Users/Alex/Downloads/tsd-boarddocs/scratch/tsd-transcripts/Troy School Board Meeting - 2026-09-01.transcript.json"
utts=json.load(open(T))['utterances']
def thumb(p): return (np.asarray(Image.open(p).convert('RGB').resize((32,18)),dtype=np.float32)/255).ravel()
files=sorted(os.listdir("uframes")); X=np.array([thumb(f"uframes/{f}") for f in files]); ids=[int(f[1:5]) for f in files]
rng=np.random.default_rng(0); k=12
C=X[rng.choice(len(X),k,replace=False)]
for it in range(30):
    lab=np.argmin(((X[:,None,:]-C[None])**2).sum(-1),1)
    for j in range(k):
        if (lab==j).any(): C[j]=X[lab==j].mean(0)
# label presets with the full-size frames already inspected by eye
refs={'AUDRA':['f_2-59-20','f_3-30-30','f_2-48-10'],
      'STEPH':['f_2-51-22','f_3-11-45','f_3-13-50','f_3-08-30','f_2-45-51','f_3-39-45','f_2-52-16'],
      'EMINA':['f_1-07-40','f_1-50-40','f_2-49-40','f_3-05-00','f_2-46-44'],
      'VITAL':['f_2-28-25','f_0-00-30']}
votes=collections.defaultdict(collections.Counter)
for L,fs in refs.items():
    for f in fs:
        x=thumb(f"frames/{f}.jpg"); j=int(np.argmin(((C-x)**2).sum(1))); votes[j][L]+=1; print(f"{f} -> preset {j}")
plabel={}
for j in range(k):
    v=votes.get(j); plabel[j]=v.most_common(1)[0][0] if v else 'other'
print("preset labels:",plabel, "sizes:",np.bincount(lab,minlength=k).tolist())
fl={i:plabel[int(l)] for i,l in zip(ids,lab)}
json.dump({'frame_label':fl,'preset':{i:int(l) for i,l in zip(ids,lab)},'plabel':plabel},open("frame_labels2.json","w"))
for sp in "ABEFG":
    c=collections.Counter(fl[i] for i in fl if utts[i]['speaker']==sp)
    print(f"cluster {sp}: {dict(c)}")
