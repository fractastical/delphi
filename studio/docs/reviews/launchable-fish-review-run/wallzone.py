import struct,sys,numpy as np
p=sys.argv[1]; b=open(p,'rb').read(); n=struct.unpack('<I',b[80:84])[0]
T=np.frombuffer(b[84:84+50*n],dtype=np.dtype([('n','<f4',3),('v','<f4',(3,3)),('a','<u2')]))['v'].astype(float)
a,bb,c=T[:,0],T[:,1],T[:,2]; nr=np.cross(bb-a,c-a); A=np.linalg.norm(nr,axis=1); nr/=A[:,None]; ce=(a+bb+c)/3; e1,e2=bb-a,c-a
sel=np.where((ce[:,0]>12)&(ce[:,0]<28))[0]; print('faces in x 12-28 mm:',len(sel),'of',len(T))
out=[]
for i in sel:
    o=ce[i]-nr[i]*1e-4; d=-nr[i]; h=np.cross(d,e2); det=np.einsum('ij,ij->i',e1,h); ok=np.abs(det)>1e-12; f=np.zeros_like(det); f[ok]=1/det[ok]
    s=o-a; u=f*np.einsum('ij,ij->i',s,h); q=np.cross(s,e1); v=f*(q@d); t=f*np.einsum('ij,ij->i',e2,q)
    hit=ok&(u>=0)&(v>=0)&(u+v<=1)&(t>1e-5); hit[i]=False
    if not hit.any(): continue
    k=np.where(hit)[0][np.argmin(t[hit])]
    if np.dot(nr[k],d)>0.7: out.append((t[k]+1e-4,*ce[i],*ce[k]))
out=np.array(out); th=out[out[:,0]<0.45]
print('wall readings',len(out),'| < 0.45 mm:',len(th),'| < 0.30:',int((out[:,0]<0.30).sum()),'| min',round(out[:,0].min(),3))
if len(th):
    print('thin readings x/y/z range mm: x',th[:,1].min().round(1),th[:,1].max().round(1),'y',th[:,2].min().round(1),th[:,2].max().round(1),'z',th[:,3].min().round(1),th[:,3].max().round(1))
    for r in th[np.argsort(th[:,0])][:8]: print('  t=%.3f  from (%.1f,%.1f,%.1f) to (%.1f,%.1f,%.1f)'%tuple(r))
