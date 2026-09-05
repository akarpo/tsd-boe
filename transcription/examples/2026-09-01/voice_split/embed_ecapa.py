import warnings; warnings.filterwarnings("ignore")
import json, numpy as np, soundfile as sf, torch
from speechbrain.inference.speaker import EncoderClassifier
T="/Users/Alex/Downloads/tsd-boarddocs/scratch/tsd-transcripts/Troy School Board Meeting - 2026-09-01.transcript.json"
utts=json.load(open(T))['utterances']
wav,sr=sf.read("tsd_2026-09-01_16k.wav",dtype='float32')
enc=EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb", savedir="ecapa", run_opts={"device":"cpu"})
rows=[]
for i,u in enumerate(utts):
    if u['speaker'] not in "ABEFG": continue
    s,e=int(u['start']*16),int(u['end']*16)
    if e-s < 16000: continue
    seg=torch.from_numpy(wav[s:e]).unsqueeze(0)
    with torch.no_grad(): emb=enc.encode_batch(seg).squeeze().numpy()
    rows.append({'idx':i,'speaker':u['speaker'],'start':u['start'],'end':u['end'],'emb':emb.tolist(),'text':u['text'][:80]})
    if len(rows)%100==0: print(len(rows),flush=True)
json.dump(rows,open("embs_ecapa.json","w")); print("done",len(rows))
