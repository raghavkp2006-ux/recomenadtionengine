import os, sys, json, socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
os.chdir(ROOT); sys.path.insert(0,str(ROOT))
os.environ['DATABASE_URL']='sqlite:///'+(OUT/'metric_scratch.db').as_posix()
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
def deny(*args,**kwargs): raise OSError('Offline metrics verification')
socket.socket.connect=deny
import ast, types, csv, pickle, random, math
import numpy as np
import torch
import torch.nn as nn
from typing import Dict, Any
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from models.anime_dnn import AnimeAutoEncoder
from models.spotify_dnn import SpotifySimilarityDNN
# Execute the original evaluation functions without the script's plotting and
# database imports. The dense cache exists, so its unused transformer import
# is removed; model scoring, splits and relevance sampling are unchanged.
tree=ast.parse((ROOT/'scripts/evaluate_models.py').read_text(encoding='utf-8'))
selected=[]
for node in tree.body:
    if isinstance(node,ast.FunctionDef) and node.name in {'evaluate_anime','evaluate_movies','evaluate_spotify'}:
        node.body=[n for n in node.body if not (isinstance(n,ast.ImportFrom) and n.module=='sentence_transformers')]
        selected.append(node)
assert (ROOT/'data/eval/anime_dense_cache.pkl').exists()
ev=types.SimpleNamespace()
namespace=dict(globals())
matrices={}
def save_matrix(cm,labels,path,title):
    matrices[Path(path).stem]={'matrix':cm.tolist(),'labels':labels,'title':title}
namespace['_save_confusion_matrix']=save_matrix
exec(compile(ast.Module(body=selected,type_ignores=[]),'scripts/evaluate_models.py','exec'),namespace)
for name in ['evaluate_anime','evaluate_movies','evaluate_spotify']: setattr(ev,name,namespace[name])
results={}
for name,fn in [('anime',ev.evaluate_anime),('movies',ev.evaluate_movies),('spotify',ev.evaluate_spotify)]:
    try: results[name]=fn()
    except Exception as exc: results[name]={'status':'blocked','reason':str(exc),'exception':type(exc).__name__}
results['confusion_matrices']=matrices
(OUT/'verified_metrics.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
