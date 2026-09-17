"""Deterministic lexical+dense RRF retrieval for FormuLab F1."""
import re
from collections import Counter, defaultdict
import numpy as np

TOKEN=re.compile(r"[\w-]+",re.UNICODE)
def tokens(s): return TOKEN.findall((s or '').lower())
def lexical_rank(rows, query):
 q=set(tokens(query)); scored=[]
 for r in rows:
  score=len(q & set(tokens(r.get('text',''))))
  if score: scored.append((score,r['source_id']))
 return [sid for _,sid in sorted(scored,key=lambda x:(-x[0],x[1]))]
def dense_rank(rows, emb, query_vector):
 if len(rows)!=len(emb): raise ValueError('rows and embeddings must align')
 q=np.asarray(query_vector,dtype=np.float32)
 scores=np.asarray(emb,dtype=np.float32)@q
 return [rows[i]['source_id'] for i in sorted(range(len(rows)),key=lambda i:(-float(scores[i]),rows[i]['source_id']))]
def rrf_fuse(rankings,k=60):
 scores=defaultdict(float)
 for ranking in rankings:
  for rank,sid in enumerate(ranking,1): scores[sid]+=1/(k+rank)
 return [{'source_id':sid,'hybrid_score':score} for sid,score in sorted(scores.items(),key=lambda x:(-x[1],x[0]))]
def search(rows,embeddings,query_vector,query,top_k=5):
 if not query or not query.strip() or not rows:
  return {'evidence_status':'insufficient','related_cases':[],'limitations':['Query atau evidence tidak cukup untuk retrieval.']}
 byid={r['source_id']:r for r in rows}
 fused=rrf_fuse([lexical_rank(rows,query),dense_rank(rows,embeddings,query_vector)])[:top_k]
 cases=[{**byid[x['source_id']],**x} for x in fused]
 return {'evidence_status':'sufficient' if cases else 'insufficient','related_cases':cases,'limitations':['Evidence demo menggunakan data sintetis berbasis skenario.']}
