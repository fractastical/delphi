import json, re, sys, time, urllib.parse, urllib.request
from playwright.sync_api import sync_playwright
BASE="https://frontier.morphoswarm.ai/"; OUT="/data/artifacts/delphi-evolve-rethink/site-audit/r2"
vp=sys.argv[1]; W,H={"desktop":(1440,1000),"mobile":(390,844)}[vp]
steps=[]; console=[]; httpfail=[]; cur=[""]
def step(sid,desc,**kw): steps.append({"id":sid,"vp":vp,"desc":desc,**kw}); print(sid,flush=True); return steps[-1]
def slug(s): return re.sub(r'[^a-zA-Z0-9]+','_',s)[:60].strip('_')
CONTRAST=open('/tmp/claude-1000/-data-worktrees-delphi-evolve-rethink-critic/45bfe973-0b4e-4c5b-9d70-43d8c4aa8801/scratchpad/audit.py').read().split('CONTRAST="""')[1].split('"""')[0]
def txt(pg,n=300): return re.sub(r'\s+',' ',pg.evaluate("()=>document.getElementById('main').innerText"))[:n]
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--autoplay-policy=no-user-gesture-required"]); ctx=b.new_context(viewport={"width":W,"height":H}); pg=ctx.new_page()
    pg.on("console",lambda m: console.append({"vp":vp,"at":cur[0],"type":m.type,"text":m.text[:220]}) if m.type in("error","warning") else None)
    pg.on("pageerror",lambda e: console.append({"vp":vp,"at":cur[0],"type":"pageerror","text":str(e)[:220]}))
    pg.on("response",lambda r: httpfail.append({"vp":vp,"at":cur[0],"url":r.url[-90:],"status":r.status}) if r.status>=400 else None)
    def go(route,wait=1500):
        cur[0]=route; pg.goto(BASE+route,wait_until="load",timeout=40000); pg.wait_for_timeout(wait)
    def shot(name,full=False):
        f=f"{OUT}/R2_{vp}_{slug(name)}.png"
        try: pg.screenshot(path=f,full_page=full); return f
        except Exception: return None
    # ---- R1 F-1/F-5 frontier table
    go("#/frontier",2500)
    g=pg.evaluate("""()=>{const t=document.querySelector('main table');if(!t)return null;const w=t.parentElement;const a=t.querySelector('tbody tr a');
      return {tableW:Math.round(t.getBoundingClientRect().width),wrapW:w.clientWidth,wrapScrollW:w.scrollWidth,overflowX:getComputedStyle(w).overflowX,
      headers:[...t.querySelectorAll('th')].map(th=>[th.innerText,Math.round(th.getBoundingClientRect().width)]),
      firstId:a?[a.innerText,Math.round(a.getBoundingClientRect().width),Math.round(a.getBoundingClientRect().height)]:null,
      rows:t.querySelectorAll('tbody tr').length,
      clippedCells:[...t.querySelectorAll('tbody tr:first-child td')].map(td=>[Math.round(td.getBoundingClientRect().right),w.getBoundingClientRect().right])}}""")
    emp=lambda: pg.evaluate("()=>/Select a question/.test(document.getElementById('main').innerText)")
    r1={"geometry":g,"panel_empty_on_load":emp()}
    try:
        pg.locator("main table tbody tr").nth(2).locator("td").last.click(timeout=3000); pg.wait_for_timeout(700); r1["row_text_click_selects"]=not emp(); r1["url_after"]=pg.url[-60:]
    except Exception as e: r1["row_click_err"]=str(e)[:100]
    step("R1","F-1/F-5 frontier table geometry, selection",ok=bool(g and g["firstId"] and g["firstId"][2]<40 and g["tableW"]<=g["wrapW"]+1),result=r1,screenshot=shot("frontier_table"))
    for route in ["#/frontier/F001","#/frontier/problem:ff-aerodynamic-calibration","#/frontier/zzz-unknown"]:
        go(route,2000); step("R1:"+route,"frontier path deep link",result={"panel_empty":emp(),"text":txt(pg,200)},screenshot=shot(route))
    pg.keyboard.press("Tab"); 
    # ---- R2 F-2 evidence
    for r in ["#/evidence","#/knowledge","#/simulations","#/engineering","#/studio/flying-fish","#/work","#/search","#/frontier"]:
        go(r,1800); st=pg.evaluate("()=>({h:document.documentElement.scrollHeight,overflowX:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,len:document.getElementById('main').innerText.length,h1:(document.querySelector('h1')||{}).innerText})")
        st["contrast_fail"]=pg.evaluate(CONTRAST); step("R2:"+r,"page height/overflow/contrast",result=st,screenshot=shot(r.replace('#/','')+"_fold"))
    go("#/evidence",1800); step("R2e","evidence structure",result=pg.evaluate("()=>({h2:[...document.querySelectorAll('main h2')].map(h=>[h.innerText.slice(0,40),Math.round((h.closest('section,.card')||h.parentElement).getBoundingClientRect().height)]),tabs:[...document.querySelectorAll('main [role=tab],main .tabs a,main nav a')].map(a=>a.innerText.trim()).slice(0,12),details:document.querySelectorAll('main details').length})"))
    # ---- R3 F-3 system
    go("#/work",1800); t=txt(pg,3000); step("R3","F-3 system labels",result={"runtime_card":re.findall(r'RUNTIME[^A-Z]{0,40}[^.]{0,60}|Runtime\s*[^|]{0,50}',t)[:3],"signed_in_mentions":re.findall(r'.{30}signed in.{30}',t)[:3],"deployed_commit":re.findall(r'.{0,40}[Dd]eployed commit.{0,120}',t)[:3],"session":json.loads(urllib.request.urlopen(BASE+"api/session",timeout=15).read())},screenshot=shot("work_fold"))
    # ---- R4 F-4 documents
    snap=json.loads(urllib.request.urlopen(BASE+"data/snapshot.json",timeout=30).read()); docs=snap.get("documents",[]); res=[]
    for d in docs:
        try: st=urllib.request.urlopen(BASE+d["href"],timeout=20).status
        except Exception as e: st=getattr(e,'code',str(e)[:20])
        res.append((d["id"],st))
    for u in ["data/results/designs.csv"]:
        try: st=urllib.request.urlopen(BASE+u,timeout=20).status
        except Exception as e: st=getattr(e,'code',str(e)[:20])
        res.append((u,st))
    step("R4","F-4 snapshot documents GET",ok=all(s==200 for _,s in res),result={"n":len(res),"non200":[r for r in res if r[1]!=200],"label":snap.get("label")})
    go("#/evidence?src=doc%3A2026-10-31-oca2-exon21-molino-RESULT",2500); step("R4d","oca2 RESULT drawer",result=pg.evaluate("()=>({hidden:document.getElementById('drawer').hidden,title:document.getElementById('dtitle').innerText,body:document.querySelector('#drawer .dbody').innerText.slice(0,200)})"),screenshot=shot("oca2_drawer"))
    # ---- R5 M-1 nav, M-3 search long
    go("#/frontier",1500); step("R5","M-1 header nav fit",result=pg.evaluate("()=>{const n=document.querySelector('header nav');const u=n.querySelector('ul');return {navW:n.clientWidth,ulW:u.scrollWidth,cut:u.scrollWidth>n.clientWidth+1,items:[...u.querySelectorAll('a')].map(a=>[a.innerText,Math.round(a.getBoundingClientRect().right)])}}"),screenshot=shot("nav_top"))
    go("#/search?q="+"a"*300+"&tab=record",3500); step("R5b","M-3 long search",result=txt(pg,500)[-260:])
    # ---- Search workflows
    for q,tab in [("wing","record"),("wing","question"),("wing","artifact"),("wing","action"),("zzzzxxqq","record"),("","record")]:
        go(f"#/search?q={q}&tab={tab}",3500); t=txt(pg,4000)
        step(f"S:{tab}:{q}","search tab",result={"len":len(t),"head":t[:300],"tail":t[-260:],"links":pg.evaluate("()=>[...document.querySelectorAll('main a[href^=\"#/entity\"],main a[href^=\"#/graph\"]')].length")},screenshot=shot(f"search_{tab}_{q}") if q else None)
    # tab buttons
    go("#/search?q=wing&tab=record",3000); step("S:tabs","search tabs present",result=pg.evaluate("()=>[...document.querySelectorAll('main [role=tab],main .tabs a,main nav a,main button')].map(a=>[a.innerText.trim().slice(0,25),a.getAttribute('href')||a.getAttribute('aria-selected')]).slice(0,20)"))
    # first result -> entity -> graph
    try:
        a=pg.locator("main a[href^='#/entity']").first; href=a.get_attribute("href"); a.click(timeout=4000); pg.wait_for_timeout(2500)
        step("E1","open first search result as entity",result={"href":href,"url":pg.url[-90:],"head":txt(pg,400),"graphlinks":pg.evaluate("()=>[...document.querySelectorAll('main a[href^=\"#/graph\"]')].length")},screenshot=shot("entity_from_search",True))
        gl=pg.locator("main a[href^='#/graph']").first
        if gl.count(): gl.click(timeout=4000); pg.wait_for_timeout(3000); step("G1","entity -> neighbourhood graph",result={"url":pg.url[-90:],"head":txt(pg,300),"nodes":pg.evaluate("()=>document.querySelectorAll('svg [tabindex],svg circle,svg g.node').length")},screenshot=shot("graph_from_entity"))
    except Exception as e: step("E1","entity/graph",ok=False,error=str(e)[:150])
    go("#/entity/Claim/doesnotexist",2500); step("E2","unknown entity",result=txt(pg,250)); go("#/graph",2000); step("G0","graph empty state",result=txt(pg,300),screenshot=shot("graph_empty"))
    # ---- Studio
    go("#/studio",2000)
    for q in ["make a fin that can glide","how do fin proportions get set?","zzzz qqq","", "<script>alert(1)</script>"]:
        try:
            go("#/studio",1200); pg.fill("input[type=text],input[type=search],main input",q,timeout=3000) if q else None
            pg.get_by_role("button",name=re.compile("Find where")).click(timeout=3000); pg.wait_for_timeout(1500)
            step("T:"+q[:18],"studio routing",result={"url":pg.url[-80:],"text":txt(pg,700)},screenshot=shot("studio_route_"+(q[:10] or "empty")))
        except Exception as e: step("T:"+q[:18],"studio routing",ok=False,error=str(e)[:120])
    go("#/studio/flying-fish",2500)
    tabs=pg.evaluate("()=>[...document.querySelectorAll('main .tabs a,main nav[aria-label] a,main [role=tab]')].map(a=>[a.innerText.trim(),a.getAttribute('href')]).slice(0,12)")
    step("T1","flying-fish tabs",result=tabs)
    subs=pg.evaluate("()=>[...document.querySelectorAll('main a[href*=\"scale=\"]')].map(a=>a.getAttribute('href')).filter((v,i,a)=>a.indexOf(v)===i)")
    for h in subs[:11]:
        go(h,1500); st=pg.evaluate("()=>({len:document.getElementById('main').innerText.length,videos:document.querySelectorAll('video').length,h:document.documentElement.scrollHeight})"); step("T2:"+h,"scale subsystem",result=st,screenshot=shot("ff_"+h) if h.endswith(("organism","molecular","organ")) else None)
    for t in tabs[1:5]:
        if t[1]:
            go(t[1],2200); step("T3:"+t[0],"flying-fish tab",result={"head":txt(pg,300),"h":pg.evaluate("()=>document.documentElement.scrollHeight")},screenshot=shot("ff_tab_"+t[0]))
    # ---- simulations: video + widget
    go("#/simulations",2500)
    res=pg.evaluate("""async()=>{const out=[];for(const v of document.querySelectorAll('video')){v.muted=true;let r={src:v.currentSrc.split('/').pop(),dur:v.duration,err:v.error&&v.error.code};try{await v.play();await new Promise(r=>setTimeout(r,1200));r.t=v.currentTime}catch(e){r.playErr=String(e).slice(0,60)}v.pause();v.currentTime=Math.min(4,v.duration/2);await new Promise(r=>setTimeout(r,400));r.seek=v.currentTime;out.push(r)}return out}""")
    step("V1","simulation videos play/seek",result=res)
    forms=pg.evaluate("()=>[...document.querySelectorAll('main form')].map(f=>({name:f.dataset.form||f.id,inputs:[...f.querySelectorAll('input')].map(i=>i.name),btns:[...f.querySelectorAll('button')].map(b=>b.innerText.slice(0,30))}))")
    step("V2","simulation forms on page",result=forms)
    b.close()
json.dump({"steps":steps,"console":console,"httpfail":httpfail,"ts":time.strftime("%F %T %Z")},open(f"{OUT}/audit2_{vp}.json","w"),indent=1,default=str)
print(vp,"steps",len(steps),"console",len(console),"httpfail",len(httpfail))
