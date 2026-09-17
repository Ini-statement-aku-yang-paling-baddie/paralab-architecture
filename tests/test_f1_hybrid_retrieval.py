"""Tests for deterministic F1 lexical+dense RRF retrieval."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'scripts'/'f1_hybrid_retrieval.py'
def api():
 s=importlib.util.spec_from_file_location('f1_hybrid',P); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
class TestHybrid(unittest.TestCase):
 def test_rrf_promotes_document_found_by_both_rankers(self):
  m=api(); fused=m.rrf_fuse([['A','B'],['B','C']],k=60)
  self.assertEqual(fused[0]['source_id'],'B')
 def test_search_returns_stable_top_k_and_evidence_status(self):
  m=api(); rows=[{'source_id':'A','text':'viskositas turun elektrolit','outcome':'failed','failure_mode':'viscosity_collapse'},{'source_id':'B','text':'stabil homogen','outcome':'passed','failure_mode':None}]
  e=np.array([[1.,0.],[0.,1.]],dtype=np.float32)
  out=m.search(rows,e,np.array([1.,0.],dtype=np.float32),'viskositas turun',top_k=1)
  self.assertEqual(out['evidence_status'],'sufficient'); self.assertEqual(out['related_cases'][0]['source_id'],'A')
 def test_empty_query_abstains(self):
  m=api(); self.assertEqual(m.search([],np.empty((0,2),dtype=np.float32),np.array([1.,0.],dtype=np.float32),'')['evidence_status'],'insufficient')
if __name__=='__main__': unittest.main()
