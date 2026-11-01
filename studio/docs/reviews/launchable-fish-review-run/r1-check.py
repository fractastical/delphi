"""Reviewer check of glider r1 revisions: own STL parse, manifold test, tetrahedral volume/centroid/inertia, mass = rho V, assembly sum.
usage: python check.py <repo-root at 19f4546> """
import json, struct, sys, hashlib
import numpy as np
R=sys.argv[1]; RHO=1220.0
def load(path):
    b=open(path,'rb').read(); n=struct.unpack('<I',b[80:84])[0]
    assert 84+50*n==len(b), ('not binary STL of expected length',path)
    return np.frombuffer(b[84:84+50*n],dtype=np.dtype([('n','<f4',3),('v','<f4',(3,3)),('a','<u2')]))['v'].astype(float), hashlib.sha256(b).hexdigest()
def manifold(T):
    q=T.reshape(-1,3); uniq,inv=np.unique(q,axis=0,return_inverse=True); F=inv.reshape(-1,3)
    d=np.concatenate([F[:,[0,1]],F[:,[1,2]],F[:,[2,0]]]); 
    key=lambda e:e[:,0].astype(np.int64)*len(uniq)+e[:,1]
    fw=key(d); bw=key(d[:,::-1]); 
    u,c=np.unique(fw,return_counts=True); dup_dir=int((c>1).sum())          # a directed edge used twice: inconsistent orientation or non-manifold
    miss=int((~np.isin(fw,bw)).sum())                                       # directed edge with no opposite partner: open boundary
    tri_deg=int((np.linalg.norm(np.cross(T[:,1]-T[:,0],T[:,2]-T[:,0]),axis=1)==0).sum())
    return {'verts':len(uniq),'open_edges':miss,'edges_used_twice_same_direction':dup_dir,'zero_area_tris':tri_deg}
def props(T):
    a,b,c=T[:,0],T[:,1],T[:,2]; v6=np.einsum('ij,ij->i',a,np.cross(b,c)); V=v6.sum()/6
    cen=(((a+b+c)/4)*v6[:,None]).sum(0)/v6.sum()
    # inertia about origin by tetra formula (unit density), then shift to CG
    def mom(i,j):
        # integral of x_i x_j over tetra with vertex origin: V/20 * (sum_k p_ik p_jk + (sum p_i)(sum p_j))
        P=np.stack([a,b,c],axis=1)  # tri,3 verts,3 coords
        s=(P[:,:,i]*P[:,:,j]).sum(1)+P[:,:,i].sum(1)*P[:,:,j].sum(1)
        return (v6/6/10*s).sum()   # v6/6 is tetra volume; /10 for (1/20)*... *2: see note
    return V,cen,mom
def inertia(T,rho):
    a,b,c=T[:,0],T[:,1],T[:,2]; v6=np.einsum('ij,ij->i',a,np.cross(b,c)); vol=v6/6
    P=np.stack([a,b,c],axis=1)
    def I2(i,j):
        s=(P[:,:,i]*P[:,:,j]).sum(1)+P[:,:,i].sum(1)*P[:,:,j].sum(1)
        return (vol/20*s).sum()   # exact: int x_i x_j dV over tetra(0,a,b,c) = V/20*(sum_k a_ik a_jk + (sum a_i)(sum a_j))
    S=np.array([[I2(i,j) for j in range(3)] for i in range(3)])
    return S*rho   # second-moment matrix about origin (mass-weighted), units kg*(len^2)
def assembly(parts):
    m=sum(p['m'] for p in parts); cg=sum(p['m']*p['cg'] for p in parts)/m
    S=sum(p['S'] for p in parts)                       # about origin (m^2 kg)
    S_cg=S-m*np.outer(cg,cg)
    I=np.trace(S_cg)*np.eye(3)-S_cg
    return m,cg,I
out={}
for rev in ('r1-strong','r1-light'):
    M=json.load(open(f'{R}/artifacts/glider/{rev}/manifest.json')); rows=[]; use=[]
    for p in M['parts']:
        T0,sha=load(f"{R}/artifacts/glider/{rev}/{p['stl']}")
        mf=manifold(T0); X=np.array(p['print_to_fish_transform'],float); det=float(np.linalg.det(X[:3,:3]))
        T=(T0@X[:3,:3].T+X[:3,3])*1e-3                      # print pose -> fish frame, mm -> m
        if det<0: T=T[:,[0,2,1],:]                          # a reflection reverses winding; restore outward normals
        mf['transform_det']=round(det,6); V,cen,_=props(T); S=inertia(T,RHO); m=RHO*V
        bb=np.array([T.reshape(-1,3).min(0),T.reshape(-1,3).max(0)])*1e3
        mp=p['mass_properties']
        Scg=S-m*np.outer(cen,cen); Icg=np.trace(Scg)*np.eye(3)-Scg
        rows.append({'id':p['id'],'sha_ok':sha==p['stl_file']['sha256'],'mesh':mf,'bbox_mm':np.round(bb,2).tolist(),'size_mm':np.round(bb[1]-bb[0],2).tolist(),
            'vol_mm3':round(V*1e9,3),'vol_rel_diff':abs(V*1e9-mp['volume_mm3'])/mp['volume_mm3'],'mass_g':round(m*1e3,4),'mass_rel_diff':abs(m-mp['mass_kg'])/mp['mass_kg'],
            'cg_mm_diff':float(np.abs(cen*1e3-np.array(mp['cg_mm'])).max()),'Iyy_rel_diff':abs(Icg[1,1]-mp['inertia_cg_kg_m2'][1][1])/mp['inertia_cg_kg_m2'][1][1],
            'Ixx_rel_diff':abs(Icg[0,0]-mp['inertia_cg_kg_m2'][0][0])/mp['inertia_cg_kg_m2'][0][0],'Izz_rel_diff':abs(Icg[2,2]-mp['inertia_cg_kg_m2'][2][2])/mp['inertia_cg_kg_m2'][2][2]})
        if p['id'] in M['nominal_assembly']['parts']: use.append({'m':m,'cg':cen,'S':S})
    am,acg,aI=assembly(use); nd=M['nominal_assembly']['dry']
    out[rev]={'parts':rows,'assembly_dry':{'mass_g':am*1e3,'manifest_mass_g':nd['mass_g'],'cg_mm':(acg*1e3).tolist(),'manifest_cg_mm':nd['cg_mm'],
        'Iyy':aI[1,1],'manifest_Iyy':nd['inertia_cg_kg_m2'][1][1],'Ixx':aI[0,0],'Izz':aI[2,2],'manifest_Ixx':nd['inertia_cg_kg_m2'][0][0],'manifest_Izz':nd['inertia_cg_kg_m2'][2][2],'Ixz':aI[0,2],'manifest_Ixz':nd['inertia_cg_kg_m2'][0][2]}}
json.dump(out,open(sys.argv[2],'w'),indent=1,default=float)
for rev,o in out.items():
    print('==',rev)
    for r in o['parts']:
        print(f"{r['id']:16s} sha_ok={r['sha_ok']} open={r['mesh']['open_edges']} twice={r['mesh']['edges_used_twice_same_direction']} deg={r['mesh']['zero_area_tris']} det={r['mesh']['transform_det']} size={r['size_mm']} V={r['vol_mm3']:.2f} m={r['mass_g']:.3f}g dV={r['vol_rel_diff']:.1e} dCG={r['cg_mm_diff']:.1e}mm dIyy={r['Iyy_rel_diff']:.1e} dIxx={r['Ixx_rel_diff']:.1e} dIzz={r['Izz_rel_diff']:.1e}")
    a=o['assembly_dry']; print('assembly dry: mass',round(a['mass_g'],4),'vs',round(a['manifest_mass_g'],4),'| CG mm',np.round(a['cg_mm'],3).tolist(),'vs',np.round(a['manifest_cg_mm'],3).tolist(),'| Iyy',a['Iyy'],'vs',a['manifest_Iyy'],'| Ixx',a['Ixx'],'vs',a['manifest_Ixx'],'| Izz',a['Izz'],'vs',a['manifest_Izz'],'| Ixz',a['Ixz'],'vs',a['manifest_Ixz'])
