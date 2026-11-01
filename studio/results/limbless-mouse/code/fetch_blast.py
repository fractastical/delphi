import urllib.request, urllib.parse, zipfile, json, io, sys
B="https://blast.ncbi.nlm.nih.gov/Blast.cgi"; UA={"User-Agent":"zrs-comparative-analysis/1.0"}
def fetch_json2(rid, outpath):
    p={"CMD":"Get","RID":rid,"FORMAT_TYPE":"JSON2","FORMAT_OBJECT":"Alignment",
       "ALIGNMENTS":100,"DESCRIPTIONS":100}
    u=B+"?"+urllib.parse.urlencode(p)
    with urllib.request.urlopen(urllib.request.Request(u,headers=UA),timeout=300) as r:
        st,body=r.status,r.read()
    open(outpath,'wb').write(body)
    z=zipfile.ZipFile(io.BytesIO(body))
    inner=[n for n in z.namelist() if n.endswith('_1.json')][0]
    return st,u,len(body),json.loads(z.read(inner))
def hits(d):
    bo=d['BlastOutput2']
    reports=[b['report'] for b in bo] if isinstance(bo,list) else [bo['report']]
    r=reports[0]['results']['search']
    out=[]
    for h in r.get('hits',[]):
        de=h['description'][0]
        for hs in h['hsps']:
            out.append(dict(acc=de.get('accession'),title=de.get('title',''),
                taxid=de.get('taxid'),sciname=de.get('sciname'),
                pid=100*hs['identity']/hs['align_len'],alen=hs['align_len'],
                evalue=hs['evalue'],bit=hs['bit_score'],
                qf=hs['query_from'],qt=hs['query_to'],
                sf=hs['hit_from'],st=hs['hit_to'],strand=hs['hit_strand']))
    return r.get('query_len'), out
if __name__=="__main__":
    rid,out=sys.argv[1],sys.argv[2]
    st,u,n,d=fetch_json2(rid,out)
    ql,hh=hits(d)
    print(f"RID={rid} HTTP={st} bytes={n} query_len={ql} hsps={len(hh)}")
    print(f"url={u}")
    for h in sorted(hh,key=lambda x:-x['bit']):
        print(f"{h['sciname'] or '?':26s} {h['acc']:16s} id%={h['pid']:5.1f} alen={h['alen']:5d} e={h['evalue']:.0e} s={h['sf']}-{h['st']} {h['strand']}")
