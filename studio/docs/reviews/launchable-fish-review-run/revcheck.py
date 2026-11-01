"""Reviewer check of a glider revision (own code). usage: python revcheck.py <repo> <rev> <out.json> [wall_samples]
Checks: STL sha, closed+oriented, units mm, volume->mass (rho 1220), per-part CG/inertia vs manifest, assembly vs manifest,
chirality of L/R pairs (printable pair test), independent inward-ray wall sampling of the body."""
import json, struct, sys, hashlib
import numpy as np
R,rev,OUT=sys.argv[1],sys.argv[2],sys.argv[3]; NS=int(sys.argv[4]) if len(sys.argv)>4 else 6000
RHO=1220.0; D=f'{R}/artifacts/glider/{rev}'
M=json.load(open(f'{D}/manifest.json'))
def load(p):
    b=open(p,'rb').read(); n=struct.unpack('<I',b[80:84])[0]; assert 84+50*n==len(b),p
    return np.frombuffer(b[84:84+50*n],dtype=np.dtype([('n','<f4',3),('v','<f4',(3,3)),('a','<u2')]))['v'].astype(float),hashlib.sha256(b).hexdigest()
def closed(T):
    u,inv=np.unique(T.reshape(-1,3),axis=0,return_inverse=True); F=inv.reshape(-1,3)
    d=np.concatenate([F[:,[0,1]],F[:,[1,2]],F[:,[2,0]]]); k=lambda e:e[:,0].astype(np.int64)*len(u)+e[:,1]
    fw,bw=k(d),k(d[:,::-1]); uq,c=np.unique(fw,return_counts=True)
    return {'open_edges':int((~np.isin(fw,bw)).sum()),'dup_directed_edges':int((c>1).sum()),'zero_area':int((np.linalg.norm(np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]),axis=1)==0).sum())}
def vol(T): return np.einsum('ij,ij->i',T[:,0],np.cross(T[:,1],T[:,2])).sum()/6
def second(T,rho):
    a,b,c=T[:,0],T[:,1],T[:,2]; v=np.einsum('ij,ij->i',a,np.cross(b,c))/6; P=np.stack([a,b,c],1)
    I2=lambda i,j:(v/20*((P[:,:,i]*P[:,:,j]).sum(1)+P[:,:,i].sum(1)*P[:,:,j].sum(1))).sum()
    return np.array([[I2(i,j) for j in range(3)] for i in range(3)])*rho
def cen(T):
    v=np.einsum('ij,ij->i',T[:,0],np.cross(T[:,1],T[:,2])); return (((T[:,0]+T[:,1]+T[:,2])/4)*v[:,None]).sum(0)/v.sum()
res={'revision':rev,'parts':[],'pairs':[]}; use=[]; raw={}; fishm={}
for p in M['parts']:
    T0,sha=load(f"{D}/{p['stl']}"); X=np.array(p['print_to_fish_transform'],float); det=float(np.linalg.det(X[:3,:3]))
    Tf=(T0@X[:3,:3].T+X[:3,3]); 
    if det<0: Tf=Tf[:,[0,2,1],:]
    raw[p['id']]=T0; fishm[p['id']]=Tf; T=Tf*1e-3; V=vol(T); m=RHO*V; c=cen(T); S=second(T,RHO); Scg=S-m*np.outer(c,c); Icg=np.trace(Scg)*np.eye(3)-Scg
    mp=p['mass_properties']; bb=(T0.reshape(-1,3).min(0),T0.reshape(-1,3).max(0))
    res['parts'].append({'id':p['id'],'sha_ok':sha==p['stl_file']['sha256'],'mesh':closed(T0),'print_stl_signed_volume_positive':bool(vol(T0)>0),'transform_det':round(det,6),
        'size_mm':np.round(np.array(bb[1])-np.array(bb[0]),2).tolist(),'vol_mm3':V*1e9,'mass_g':m*1e3,'vol_rel':abs(V*1e9-mp['volume_mm3'])/mp['volume_mm3'],
        'cg_diff_mm':float(np.abs(c*1e3-np.array(mp['cg_mm'])).max()),'Iyy_rel':abs(Icg[1,1]-mp['inertia_cg_kg_m2'][1][1])/mp['inertia_cg_kg_m2'][1][1]})
    if p['id'] in M['nominal_assembly']['parts']: use.append((m,c,S))
mt=sum(u[0] for u in use); cg=sum(u[0]*u[1] for u in use)/mt; S=sum(u[2] for u in use); Scg=S-mt*np.outer(cg,cg); I=np.trace(Scg)*np.eye(3)-Scg; nd=M['nominal_assembly']['dry']
res['assembly']={'mass_g':mt*1e3,'manifest_mass_g':nd['mass_g'],'cg_mm':(cg*1e3).tolist(),'manifest_cg_mm':nd['cg_mm'],'Iyy':I[1,1],'manifest_Iyy':nd['inertia_cg_kg_m2'][1][1]}
# chirality: for each L/R pair
ids=[p['id'] for p in M['parts']]
def vs(T): u=np.unique(T.reshape(-1,3),axis=0); return u[np.lexsort(u.T[::-1])]
for i in ids:
    if '_L' in i:
        j=i.replace('_L','_R')
        if j not in ids: continue
        a,b=vs(raw[i]),vs(raw[j]); same=len(a)==len(b) and np.array_equal(a,b)
        fa,fb=vs(fishm[i]),vs(fishm[j]); fb2=fb.copy(); fb2[:,1]*=-1; fb2=fb2[np.lexsort(fb2.T[::-1])]
        mirror_fish=len(fa)==len(fb2) and np.allclose(fa,fb2,atol=1e-4)
        dl=float(np.linalg.det(np.array(M['parts'][ids.index(i)]['print_to_fish_transform'])[:3,:3])); dr=float(np.linalg.det(np.array(M['parts'][ids.index(j)]['print_to_fish_transform'])[:3,:3]))
        res['pairs'].append({'L':i,'R':j,'print_vertex_sets_identical':bool(same),'fish_frame_R_is_mirror_y_of_L':bool(mirror_fish),'det_L':dl,'det_R':dr,
            'printable_pair': (not same) and mirror_fish and dl>0 and dr>0})
# independent wall sampling of the body (inward ray from face centroids; exit face must oppose)
T=raw['body']; a,b,c=T[:,0],T[:,1],T[:,2]; nrm=np.cross(b-a,c-a); A=np.linalg.norm(nrm,axis=1); nrm/=A[:,None]; cen_=(a+b+c)/3
rng=np.random.default_rng(20261031); pick=rng.choice(len(T),size=min(NS,len(T)),replace=False,p=A/A.sum())
lc=M['launch_catch']; catch_x=lc['seat_mm'][0] if 'seat_mm' in lc else lc['nominal']['slot_x_mm']; near=np.where(np.abs(cen_[:,0]-catch_x)<10)[0]; pick=np.unique(np.concatenate([pick,rng.choice(near,size=min(1500,len(near)),replace=False)]))
e1,e2=b-a,c-a; ds=[];info=[]
for i in pick:
    o=cen_[i]-nrm[i]*1e-4; d=-nrm[i]
    h=np.cross(d,e2); det=np.einsum('ij,ij->i',e1,h); ok=np.abs(det)>1e-12
    f=np.zeros_like(det); f[ok]=1/det[ok]; s=o-a; u=f*np.einsum('ij,ij->i',s,h); q=np.cross(s,e1); v=f*(q@d); t=f*np.einsum('ij,ij->i',e2,q)
    hit=ok&(u>=0)&(v>=0)&(u+v<=1)&(t>1e-5); hit[i]=False
    if not hit.any(): ds.append(np.nan); info.append((0,0,0,0)); continue
    k=np.where(hit)[0][np.argmin(t[hit])]; opp=float(np.dot(nrm[k],d))     # the cavity-side face's outward normal points along the ray: wall if dot > 0.7
    ds.append(t[k]+1e-4 if opp>0.7 else np.nan); info.append((opp,)+tuple(cen_[i]))
ds=np.array(ds); good=ds[~np.isnan(ds)]; cen_p=cen_[pick]
res['wall']={'samples':int(len(pick)),'wall_readings':int(len(good)),'not_a_wall_readings':int(np.isnan(ds).sum()),'min_mm':float(good.min()),'p01_mm':float(np.percentile(good,1)),'median_mm':float(np.median(good)),
   'below_0.45':int((good<0.45).sum()),'below_0.40':int((good<0.40).sum()),
   'thin_locations_mm':[np.round(cen_p[~np.isnan(ds)][k],1).tolist()+[round(float(good[k]),3)] for k in np.argsort(good)[:12]]}
json.dump(res,open(OUT,'w'),indent=1,default=float)
print(rev,'assembly',round(res['assembly']['mass_g'],4),'vs',round(res['assembly']['manifest_mass_g'],4),'CG',np.round(res['assembly']['cg_mm'],3).tolist(),'vs',np.round(res['assembly']['manifest_cg_mm'],3).tolist())
bad=[p['id'] for p in res['parts'] if not p['sha_ok'] or p['mesh']['open_edges'] or p['mesh']['dup_directed_edges'] or p['vol_rel']>1e-5 or p['cg_diff_mm']>1e-3]; print('parts failing sha/closure/volume/CG:',bad,'| parts with det<0:',[p['id'] for p in res['parts'] if p['transform_det']<0])
for q in res['pairs']: print('pair',q['L'],q['R'],'identical_print_verts',q['print_vertex_sets_identical'],'fish_mirror',q['fish_frame_R_is_mirror_y_of_L'],'dets',q['det_L'],q['det_R'],'PRINTABLE_PAIR',q['printable_pair'])
w=res['wall']; print('wall (mine, ray from sampled faces + 1500 near the catch):',{k:w[k] for k in w if k!='thin_locations_mm'}); print(' thinnest:',w['thin_locations_mm'][:6])
