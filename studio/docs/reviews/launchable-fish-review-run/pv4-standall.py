import sys,numpy as np
sys.argv=['x','.','/dev/null','1']
src=open('/tmp/claude-1000/dc/pv4check.py').read().split("res={}")[0]
exec(src)
for f in ['prop-stand','prop-reinforced-stand']:
    T,_,_,_,_=load('/data/worktrees/delphi-frontier/pv4-8a3e7a3/artifacts/print-v4/stl/fish3d-v3c-daane-length-%s.stl'%f)
    nrm=np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]);nrm/=np.linalg.norm(nrm,axis=1)[:,None];c=T.mean(1);D=-nrm;t,bi=mt(c+D*1e-4,D,T);ok=np.isfinite(t)&((nrm[bi]*D).sum(1)>0.7)
    print(f,len(T),int(ok.sum()),'min',t[ok].min(),'n<1.5',int((t[ok]<1.5).sum()))
