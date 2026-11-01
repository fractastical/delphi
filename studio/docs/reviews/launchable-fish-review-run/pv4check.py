"""Reviewer check (own code) of print-v4 STLs. usage: pv4check.py <repo> <out.json> [nwall] ; all STLs under artifacts/print-v4/stl"""
import sys,json,struct,hashlib,glob,os,numpy as np
R,OUT=sys.argv[1],sys.argv[2];NW=int(sys.argv[3]) if len(sys.argv)>3 else 12000
RHO=1220.0
def load(p):
    b=open(p,'rb').read();n=struct.unpack('<I',b[80:84])[0]
    ok=(84+50*n==len(b))
    a=np.frombuffer(b[84:84+50*n],dtype=np.dtype([('n','<f4',3),('v','<f4',(3,3)),('a','<u2')]))
    return a['v'].astype(np.float64),a['n'].astype(np.float64),hashlib.sha256(b).hexdigest(),len(b),ok
def topo(T):
    P=T.reshape(-1,3);u,inv=np.unique(P.astype(np.float32),axis=0,return_inverse=True);inv=inv.reshape(-1);F=inv.reshape(-1,3)
    nv=len(u)
    d=np.concatenate([F[:,[0,1]],F[:,[1,2]],F[:,[2,0]]]);k=lambda e:e[:,0].astype(np.int64)*nv+e[:,1]
    fw,bw=k(d),k(d[:,::-1]);uq,c=np.unique(fw,return_counts=True)
    open_e=int((~np.isin(fw,bw)).sum());dup=int((c>1).sum())
    area=0.5*np.linalg.norm(np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]),axis=1)
    degen=int(((F[:,0]==F[:,1])|(F[:,1]==F[:,2])|(F[:,2]==F[:,0])).sum())
    # components (face-connected by shared vertex? use shared edge): union-find over faces via edges
    par=np.arange(len(F))
    def find(x):
        while par[x]!=x: par[x]=par[par[x]];x=par[x]
        return x
    ekey=np.minimum(d[:,0],d[:,1]).astype(np.int64)*nv+np.maximum(d[:,0],d[:,1]);fi=np.tile(np.arange(len(F)),3)
    o=np.argsort(ekey,kind='stable');ek=ekey[o];fo=fi[o]
    for i in np.nonzero(ek[1:]==ek[:-1])[0]:
        a,b=find(fo[i]),find(fo[i+1])
        if a!=b: par[a]=b
    comp=len({find(i) for i in range(len(F))})
    # vertex-manifold: for each vertex, faces around it form one edge-connected fan
    vm_bad=0
    vf={}
    for fidx,f in enumerate(F):
        for v in f: vf.setdefault(int(v),[]).append(fidx)
    # edge->faces
    e2f={}
    for fidx,f in enumerate(F):
        for a,b in((f[0],f[1]),(f[1],f[2]),(f[2],f[0])): e2f.setdefault((min(a,b),max(a,b)),[]).append(fidx)
    for v,fs in vf.items():
        if len(fs)<3: vm_bad+=1;continue
        s=set(fs);seen={fs[0]};st=[fs[0]]
        while st:
            x=st.pop();f=F[x]
            for a,b in((f[0],f[1]),(f[1],f[2]),(f[2],f[0])):
                if v in(a,b):
                    for y in e2f[(min(a,b),max(a,b))]:
                        if y in s and y not in seen: seen.add(y);st.append(y)
        if len(seen)!=len(s): vm_bad+=1
    return dict(verts=nv,tris=len(F),open_edges=open_e,dup_directed=dup,degenerate_repeated_vertex=degen,min_area_mm2=float(area.min()),slivers_lt_1e6=int((area<1e-6).sum()),zero_area_lt_1e10=int((area<1e-10).sum()),edge_components=int(comp),nonmanifold_vertices=int(vm_bad))
def vol(T): return np.einsum('ij,ij->i',T[:,0],np.cross(T[:,1],T[:,2])).sum()/6
def cen(T):
    v=np.einsum('ij,ij->i',T[:,0],np.cross(T[:,1],T[:,2]));return (((T[:,0]+T[:,1]+T[:,2])/4)*v[:,None]).sum(0)/v.sum()
def mt(O,D,T,chunk=192):
    """for each ray, nearest hit t>eps and hit face index (Moller-Trumbore, all tris)"""
    e1=T[:,1]-T[:,0];e2=T[:,2]-T[:,0];best=np.full(len(O),np.inf);bi=np.full(len(O),-1)
    for s in range(0,len(O),chunk):
        o=O[s:s+chunk];d=D[s:s+chunk]
        p=np.cross(d[:,None,:],e2[None]);det=np.einsum('rtk,tk->rt',p,e1)
        with np.errstate(all='ignore'):
            inv=1.0/det;tv=o[:,None,:]-T[None,:,0];u=np.einsum('rtk,rtk->rt',tv,p)*inv
            q=np.cross(tv,e1[None]);v=np.einsum('rk,rtk->rt',d,q)*inv;t=np.einsum('tk,rtk->rt',e2,q)*inv
        m=(np.abs(det)>1e-14)&(u>=0)&(v>=0)&(u+v<=1)&(t>1e-5);t=np.where(m,t,np.inf)
        j=t.argmin(1);best[s:s+chunk]=t[np.arange(len(o)),j];bi[s:s+chunk]=j
    return best,bi
def parity_inside(Pt,T,chunk=192):
    e1=T[:,1]-T[:,0];e2=T[:,2]-T[:,0];d=np.array([0.3713,0.5129,0.7724]);d/=np.linalg.norm(d);out=np.zeros(len(Pt),bool)
    p=np.cross(d,e2);det=p@ e1.T if False else np.einsum('k,tk->t',d*0,e1)
    p=np.cross(np.broadcast_to(d,e2.shape),e2);det=np.einsum('tk,tk->t',p,e1)
    for s in range(0,len(Pt),chunk):
        o=Pt[s:s+chunk]
        with np.errstate(all='ignore'):
            inv=1.0/det;tv=o[:,None,:]-T[None,:,0];u=np.einsum('rtk,tk->rt',tv,p)*inv
            q=np.cross(tv,e1[None]);v=np.einsum('k,rtk->rt',d,q)*inv;t=np.einsum('tk,rtk->rt',e2,q)*inv
        m=(np.abs(det)[None]>1e-14)&(u>=0)&(v>=0)&(u+v<=1)&(t>1e-9);out[s:s+chunk]=(m.sum(1)%2)==1
    return out
def walls(T,N,seed):
    rng=np.random.default_rng(seed);nrm=np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]);a=np.linalg.norm(nrm,axis=1);nrm/=a[:,None]
    idx=rng.choice(len(T),size=N,p=a/a.sum());c=T[idx].mean(1);n=nrm[idx];D=-n;O=c+D*1e-4
    t,bi=mt(O,D,T);hn=nrm[bi];ok=np.isfinite(t)&((hn*D).sum(1)>0.7)
    return t[ok],c[ok],int(ok.sum())
res={}
for p in sorted(glob.glob(f'{R}/artifacts/print-v4/stl/*.stl')):
    T,N,sha,size,ok=load(p);nm=os.path.basename(p);V=vol(T);bb=T.reshape(-1,3);r=dict(sha256=sha,bytes=size,length_ok=bool(ok),finite=bool(np.isfinite(T).all()),volume_mm3=float(V),mass_g=float(V*1e-3*RHO*1e-3*1e3/1e3) if False else float(V*1.22e-3),bbox_mm=[float(x) for x in (bb.max(0)-bb.min(0))],bbox_min=[float(x) for x in bb.min(0)],centroid_mm=[float(x) for x in cen(T)])
    r.update(topo(T));res[nm]=r;print(nm,r['volume_mm3'],r['mass_g'],r['open_edges'],r['edge_components'],r['nonmanifold_vertices'],flush=True)
    if 'scales' not in nm:
        t,c,n=walls(T,NW,101);o=np.argsort(t)[:5]
        r['wall']=dict(samples_used=n,min_mm=float(t.min()),p01=float(np.percentile(t,1)),n_lt_rule=None,worst=[[float(t[i])]+[float(x) for x in c[i]] for i in o])
        # mirror: inside-parity at random points in bbox vs mirror about y=0 (smooth only)
        rng=np.random.default_rng(5);lo,hi=bb.min(0),bb.max(0);Pt=rng.uniform(lo,hi,(6000,3));Pt[:,1]=rng.uniform(0,hi[1],6000)
        a=parity_inside(Pt,T);Pm=Pt.copy();Pm[:,1]*=-1;b=parity_inside(Pm,T)
        r['mirror_parity']=dict(n=6000,inside=int(a.sum()),mismatch=int((a!=b).sum()))
        print(' wall min',r['wall']['min_mm'],'mirror mismatch',r['mirror_parity'],flush=True)
json.dump(res,open(OUT,'w'),indent=1)
