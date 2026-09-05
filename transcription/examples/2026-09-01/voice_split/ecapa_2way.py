import json, numpy as np, collections
rows=json.load(open("embs_ecapa.json"))
E=np.array([r['emb'] for r in rows]); E/=np.linalg.norm(E,axis=1,keepdims=True)
def ms(h,m,s): return ((h*60+m)*60+s)*1000
def near(t,spk,tol=1500): return [i for i,r in enumerate(rows) if r['speaker']==spk and abs(r['start']-t)<=tol]
seeds={'STEPH':[ms(3,8,18),ms(3,13,32),ms(3,39,36),ms(3,8,53),ms(3,10,19)], 'AUDRA':[ms(2,48,4),ms(2,59,0),ms(3,30,19),ms(2,59,45),ms(3,1,27)]}
cent={k:E[[j for t in ts for j in near(t,'E')]].mean(0) for k,ts in seeds.items()}
for sp in 'ABFG': cent[sp]=E[[i for i,r in enumerate(rows) if r['speaker']==sp]].mean(0)
names=list(cent)
eidx=[i for i,r in enumerate(rows) if r['speaker']=='E']
# iterate 2-way k-means on the long E utterances, seeded, keeping other centroids fixed as "sinks"
long=[i for i in eidx if rows[i]['end']-rows[i]['start']>=3000]
for it in range(10):
    Cm=np.array([cent[n]/np.linalg.norm(cent[n]) for n in names]); s=E[long]@Cm.T; a=np.argmax(s,1)
    for g,n in enumerate(names[:2]):
        m=[long[j] for j in range(len(long)) if a[j]==g]
        if m: cent[n]=E[m].mean(0)
Cm=np.array([cent[n]/np.linalg.norm(cent[n]) for n in names]); S=E[eidx]@Cm.T
out={}
for j,i in enumerate(eidx):
    r=rows[i]; srt=np.argsort(-S[j]); best,second=names[srt[0]],names[srt[1]]
    out[r['idx']]={'start':r['start'],'dur':(r['end']-r['start'])/1000,'best':best,'margin':round(float(S[j,srt[0]]-S[j,srt[1]]),3),'sims':{n:round(float(S[j,k]),3) for k,n in enumerate(names)},'text':r['text']}
json.dump(out,open("E_ecapa_assign.json","w"),indent=0)
print("E assignment (all):",collections.Counter(v['best'] for v in out.values()))
print("E assignment (>=3s):",collections.Counter(v['best'] for v in out.values() if v['dur']>=3))
print("centroid cos:", {f"{a}-{b}":round(float(Cm[i]@Cm[j]),3) for i,a in enumerate(names) for j,b in enumerate(names) if i<j})
