import json, re, sys, time, hashlib
from playwright.sync_api import sync_playwright
BASE="https://frontier.morphoswarm.ai/"
VP={"desktop":(1440,1000),"mobile":(390,844)}
OUT="/data/artifacts/delphi-evolve-rethink/site-audit"
vpname=sys.argv[1]; limit=int(sys.argv[2]) if len(sys.argv)>2 else 120
w,h=VP[vpname]
seeds=["#/frontier","#/knowledge","#/engineering","#/simulations","#/evidence","#/work","#/belief","#/search","#/search?q=wing&tab=catalog","#/nonexistent"]
seen=set(); queue=list(seeds); manifest=[]; console=[]; httpfail=[]
def slug(r): return re.sub(r'[^a-zA-Z0-9]+','_',r)[:90].strip('_') or 'root'
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox"]); ctx=b.new_context(viewport={"width":w,"height":h}); page=ctx.new_page()
    page.on("console",lambda m: console.append({"vp":vpname,"route":cur[0] if cur else None,"type":m.type,"text":m.text[:300]}) if m.type in("error","warning") else None)
    page.on("pageerror",lambda e: console.append({"vp":vpname,"route":cur[0] if cur else None,"type":"pageerror","text":str(e)[:300]}))
    page.on("response",lambda r: httpfail.append({"vp":vpname,"route":cur[0] if cur else None,"url":r.url,"status":r.status}) if r.status>=400 else None)
    page.on("requestfailed",lambda r: httpfail.append({"vp":vpname,"route":cur[0] if cur else None,"url":r.url,"status":"FAILED "+str(r.failure)[:80]}))
    cur=[None]
    while queue and len(manifest)<limit:
        r=queue.pop(0)
        if r in seen: continue
        seen.add(r); cur[0]=r
        try:
            page.goto(BASE+r,wait_until="networkidle",timeout=30000); page.wait_for_timeout(700)
        except Exception as e:
            manifest.append({"route":r,"error":str(e)[:200]}); continue
        info=page.evaluate("""()=>{const d=document.documentElement;const main=document.getElementById('main');
          const txt=main.innerText||'';
          const imgs=[...document.images].filter(i=>i.complete&&i.naturalWidth===0).map(i=>i.src);
          const vids=[...document.querySelectorAll('video')].map(v=>({src:v.currentSrc||v.src,ready:v.readyState,err:v.error&&v.error.code,dur:v.duration}));
          const canv=document.querySelectorAll('canvas,svg').length;
          const links=[...document.querySelectorAll('a[href^="#/"]')].map(a=>a.getAttribute('href'));
          const tabs=[...document.querySelectorAll('[role=tab],.tabs a,.tabs button')].map(a=>a.getAttribute('href')||a.textContent.trim());
          return {h1:(document.querySelector('h1')||{}).innerText,title:document.title,scrollW:d.scrollWidth,clientW:d.clientWidth,
            overflowX:d.scrollWidth>d.clientWidth+1,len:txt.length,brokenImgs:imgs,videos:vids,graphics:canv,
            rawTeX:(txt.match(/\\\\(frac|sqrt|mathrm|rho|alpha|times)\\b|\\$[^$\\n]{2,40}\\$/g)||[]).slice(0,5),
            loading:/Loading/.test(txt)&&txt.length<300,notFound:/Not found|could not be drawn/.test(txt),
            drawer:!document.getElementById('drawer').hidden,links,tabs,
            banner:(document.querySelector('.banner')||{}).innerText||null,mode:(document.querySelector('.mode')||{}).innerText||null,
            sample:txt.slice(0,400)}}""")
        shot=f"{OUT}/{vpname}_{slug(r)}.png"
        try: page.screenshot(path=shot,full_page=True)
        except Exception as e: shot=None
        info.update(route=r,viewport=vpname,screenshot=shot); manifest.append(info)
        for l in info["links"]:
            if l not in seen and l not in queue and not l.startswith("#/search?q") : queue.append(l)
    b.close()
json.dump({"manifest":manifest,"console":console,"httpfail":httpfail,"queue_remaining":queue,"ts":time.strftime("%F %T %Z")},open(f"{OUT}/crawl_{vpname}.json","w"),indent=1)
print(vpname,"routes",len(manifest),"remaining",len(queue),"console",len(console),"httpfail",len(httpfail))
