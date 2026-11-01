import json, re, sys, time, hashlib, urllib.request
from playwright.sync_api import sync_playwright
BASE="https://frontier.morphoswarm.ai/"; OUT="/data/artifacts/delphi-evolve-rethink/site-audit/r6"
vp=sys.argv[1]; W,H={"desktop":(1440,1000),"mobile":(390,844)}[vp]
steps=[]; console=[]; httpfail=[]; posts=[]; cur=[""]
def step(sid,desc,**kw): steps.append({"id":sid,"vp":vp,"desc":desc,**kw}); print(sid,flush=True)
def slug(s): return re.sub(r'[^a-zA-Z0-9]+','_',s)[:55].strip('_')
def jserr(e): return str(e).split('\n')[0][:150]
BAD=re.compile(r"\[object |undefined|\bNaN\b|\{\{|\}\}|Infinity")
snap=json.loads(urllib.request.urlopen(BASE+"data/snapshot.json",timeout=30).read()); cands=snap["fish3d_viewer"]["candidates"]
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--autoplay-policy=no-user-gesture-required","--use-gl=swiftshader","--enable-unsafe-swiftshader"]); ctx=b.new_context(viewport={"width":W,"height":H},has_touch=(vp=="mobile")); pg=ctx.new_page()
    pg.on("console",lambda m: console.append({"vp":vp,"at":cur[0],"type":m.type,"text":m.text[:200]}) if m.type=="error" else None)
    pg.on("pageerror",lambda e: console.append({"vp":vp,"at":cur[0],"type":"pageerror","text":str(e)[:200]}))
    pg.on("response",lambda r: httpfail.append({"vp":vp,"at":cur[0],"url":r.url[-80:],"status":r.status}) if r.status>=400 else None)
    pg.on("request",lambda r: posts.append((cur[0],r.method,r.url[-40:])) if r.method!="GET" else None)
    def go(route,wait=2200): cur[0]=route; pg.goto(BASE+route,wait_until="load",timeout=45000); pg.wait_for_timeout(wait)
    def shot(name,full=False):
        f=f"{OUT}/R6_{vp}_{slug(name)}.png"
        try: pg.screenshot(path=f,full_page=full); return f
        except Exception: return None
    def T(n=100000): return re.sub(r'\s+',' ',pg.evaluate("()=>document.getElementById('main').innerText"))[:n]
    tap=lambda l,**k: (l.tap(**k) if vp=="mobile" else l.click(**k))
    def safe(sid,fn):
        try: fn()
        except Exception as e: step(sid,"error",ok=False,error=jserr(e))
    # ---------------- Home v3 candidates
    def home():
        go("#/home",2500); pg.locator("#fish-viewer").scroll_into_view_if_needed(); pg.wait_for_timeout(6000)
        opts=pg.evaluate("()=>[...document.querySelectorAll('#fishcand option')].map(o=>[o.value,o.text,o.selected])")
        step("H0","Home candidate selector",ok=len(opts)==len(cands),result={"options":opts,"snapshot_candidates":len(cands),"select_label":pg.evaluate("()=>{const s=document.querySelector('#fishcand');return [s.labels&&s.labels[0]&&s.labels[0].innerText,s.tabIndex]}")})
        for c in cands:
            def f(c=c):
                pg.select_option("#fishcand",c["id"]); pg.wait_for_timeout(7000)
                v=pg.evaluate("""()=>{const r=document.querySelector('#fish-viewer');const cv=r.querySelector('canvas');return {canvas:!!cv,box:cv?[Math.round(cv.getBoundingClientRect().width),Math.round(cv.getBoundingClientRect().height)]:null,state:r.innerText.replace(/\\s+/g,' ').slice(0,300),shaOk:/sha256 matches/.test(r.innerText),shaBad:/mismatch|does not match|not verified/i.test(r.innerText),variants:[...r.querySelectorAll('[aria-label="Appearance variant"] button')].map(b=>[b.innerText.slice(0,24),b.getAttribute('aria-pressed')]),note:(document.querySelector('#fishnote')||{innerText:''}).innerText.slice(0,220),stmt:(document.querySelector('.grounding .note.warn')||{innerText:''}).innerText.slice(0,160)}}""")
                # blank check of the canvas area
                sh=shot("home_"+c["id"],False)
                try:
                    from PIL import Image, ImageStat
                    cv=pg.locator("#fish-viewer canvas").first; fn=f"{OUT}/_cv_{vp}_{slug(c['id'])}.png"; cv.screenshot(path=fn); im=Image.open(fn).convert("L"); st=ImageStat.Stat(im); v["canvas_stddev"]=round(st.stddev[0],1)
                except Exception as e: v["canvas_stddev"]=None
                # independent glb hash
                g=None
                try:
                    glb=urllib.request.urlopen(BASE+c["base"]+"fish.glb",timeout=60).read(); g=hashlib.sha256(glb).hexdigest()
                    rj=json.loads(urllib.request.urlopen(BASE+c["base"]+"render/render.json",timeout=30).read()); rec=[x for x in re.findall(r'[0-9a-f]{64}',json.dumps(rj))]
                    v["glb_bytes"]=len(glb); v["glb_sha256"]=g[:16]; v["glb_sha_in_render_json"]=g in rec
                except Exception as e: v["glb_fetch_error"]=jserr(e)
                step("H1:"+c["id"],"candidate loads real GLB",ok=bool(v["canvas"] and v["shaOk"] and not v["shaBad"] and (v.get("canvas_stddev") or 0)>5 and v.get("glb_sha_in_render_json")),result=v,screenshot=sh)
            safe("H1:"+c["id"],f)
        # knobs shown for a v3 candidate
        def f():
            pg.select_option("#fishcand",cands[1]["id"]); pg.wait_for_timeout(4000); t=T(40000)
            step("H2","v3 knobs/statement reflect selection",result={"mentions_knob_values":[k for k in ("7","8","22","0.55") if k in t][:4],"has_ray_statement":bool(re.search(r'(?i)ray-supported|individual rays',t)),"stmt":re.findall(r'Ray-supported fins[^.]{0,120}',t)[:1],"bad":sorted(set(m.group(0) for m in BAD.finditer(t)))},screenshot=shot("home_v3_text",False))
        safe("H2",f)
        # appearance buttons
        def f():
            btn=pg.locator('#fish-viewer [aria-label="Appearance variant"] button'); n=btn.count()
            res=[]
            for i in range(min(n,4)):
                tap(btn.nth(i)); pg.wait_for_timeout(2500); res.append(pg.evaluate("()=>[document.querySelector('#fish-viewer').innerText.replace(/\\s+/g,' ').match(/Appearance[^.]{0,140}/)?.[0]||null,[...document.querySelectorAll('#fish-viewer [aria-label=\"Appearance variant\"] button')].map(b=>b.getAttribute('aria-pressed')).join(',')]"))
            step("H3","appearance variant buttons",result={"n":n,"states":res},screenshot=shot("home_appearance",False))
        safe("H3",f)
    safe("H",home)
    # ---------------- mobile/filter/table/raw fixes
    def f():
        go("#/frontier",3500)
        g=pg.evaluate("""()=>{const t=document.querySelector('main table');if(!t)return {table:false,cards:document.querySelectorAll('main .qcard,main li.q').length};const w=t.parentElement;const wr=w.getBoundingClientRect();const tr=t.querySelector('tbody tr');
          const cells=[...tr.querySelectorAll('td')].map(td=>({t:td.innerText.slice(0,24),vis:td.getBoundingClientRect().right<=wr.right+1&&td.getBoundingClientRect().left>=wr.left-1}));return {table:true,tableW:Math.round(t.getBoundingClientRect().width),wrapW:w.clientWidth,rowH:Math.round(tr.getBoundingClientRect().height),cells,ws:getComputedStyle(tr.querySelector('td')).whiteSpace}}""")
        step("F1","Frontier table",ok=bool(g.get("table")==False or sum(1 for c in g.get("cells",[]) if c["vis"])>=3),result=g,screenshot=shot("frontier_table"))
        tap(pg.locator("main table tbody tr").nth(2).locator("td").nth(1),force=True); pg.wait_for_timeout(800)
        d=pg.evaluate("()=>{const e=[...document.querySelectorAll('main *')].find(x=>/THE QUESTION/.test(x.innerText||'')&&x.children.length>2&&x.getBoundingClientRect().width<700);return e?e.innerText:''}")
        step("F2","N8 raw JSON in question detail",ok=not re.search(r'\{"[a-z_]+":',d),result={"raw_json":bool(re.search(r'\{"[a-z_]+":',d)),"sample":re.findall(r'(?i)assessment.{0,160}',d)[:1]},screenshot=shot("frontier_detail"))
        go("#/frontier?live=zzz-unknown",2500); t=T(); step("F3","unknown id notice",ok=bool(re.search(r'(?i)not found|no such|no live|could not find|not visible',t)),result={"notice":re.findall(r'(?i)[^.]{0,60}(?:not found|no such|not visible|could not find)[^.]{0,60}',t)[:1]})
    safe("F",f)
    def f():
        go("#/knowledge",4000); ov=pg.evaluate("()=>({docW:document.documentElement.scrollWidth,vw:innerWidth,wide:[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth+2&&e.getBoundingClientRect().width>0).slice(0,3).map(e=>[e.tagName,Math.round(e.getBoundingClientRect().right)])})")
        n0=pg.evaluate("()=>document.querySelectorAll('main a[href^=\"#/entity\"],main a[href*=\"#/knowledge/\"]').length")
        sel=pg.locator("main form select").first; opts=sel.evaluate("s=>[...s.options].map(o=>o.value).slice(0,4)"); 
        if len(opts)>1:
            sel.select_option(opts[1]); tap(pg.get_by_role("button",name="Apply").first); pg.wait_for_timeout(2500); n1=pg.evaluate("()=>document.querySelectorAll('main a[href^=\"#/entity\"],main a[href*=\"#/knowledge/\"]').length"); sh=T(400)
        else: n1=None; sh=''
        step("N9","Knowledge page width + filter works",ok=ov["docW"]<=ov["vw"]+1 and (n1 is not None and n1!=n0),result=ov|{"cards_before":n0,"cards_after_filter":n1,"filter_text":sh[:140]},screenshot=shot("knowledge_filter"))
    safe("N9",f)
    def f():
        go("#/work?tab=work",3500); r=pg.evaluate("()=>({pre:[...document.querySelectorAll('main pre')].map(p=>[p.innerText.length,!!p.closest('details'),p.closest('details')?p.closest('details').open:null]),h:document.documentElement.scrollHeight})")
        step("N11","Work tab raw JSON",ok=all(x[0]<20000 or (x[1] and not x[2]) for x in r["pre"]),result=r,screenshot=shot("work_work"))
        go("#/studio/flying-fish?scale=organ",2800); pg.locator("input[name=sodium_scale]").fill("-5"); pg.get_by_role("button",name="Run a preview").first.click(); pg.wait_for_timeout(2500)
        w=re.sub(r'\s+',' ',pg.evaluate("()=>document.querySelector('main form input[name=sodium_scale]').closest('section,.card').innerText")); err=w[w.find('nothing is stored'):][:200]
        pg.locator("input[name=sodium_scale]").fill("0.35"); pg.get_by_role("button",name="Run a preview").first.click(); pg.wait_for_timeout(7500)
        w2=re.sub(r'\s+',' ',pg.evaluate("()=>document.querySelector('main form input[name=sodium_scale]').closest('section,.card').innerText"))
        step("N2","[object Object] in preview",ok=("[object" not in err and "[object" not in w2),result={"error":err,"footer_object":"[object" in w2,"code":re.findall(r'code [^·]{0,50}',w2)[:1]},screenshot=shot("widget"))
    safe("N11",f)
    # ---------------- public source label
    def f():
        go("#/work?tab=built",3500); t=T(30000); m=re.findall(r'Source repository:.{0,260}',t)
        step("L1","public source label",result={"text":m[:1],"pill_public":"public source" in t,"links":pg.evaluate("()=>[...document.querySelectorAll('main a[href*=\"github.com\"]')].map(a=>[a.href,a.rel,a.target])")},screenshot=shot("work_built_source",False))
        for u in ["https://github.com/kganjam/delphi-frontier","https://github.com/kganjam/delphi-frontier/tree/codex/frontier-demo-20261031"]:
            try: st=urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"critic-audit"}),timeout=20).status
            except Exception as e: st=getattr(e,'code',str(e)[:30])
            step("L2:"+u[-30:],"source URL reachable unauthenticated",ok=(st==200),result={"url":u,"status":st})
        go("#/about",2500); t2=T(); step("L3","About / footer mention of source",result={"repo_mentions":re.findall(r'(?i).{0,50}(?:github|source repository|public source|private).{0,60}',t2)[:3],"footer":re.sub(r'\s+',' ',pg.evaluate("()=>document.getElementById('foot').innerText"))[:260]})
    safe("L",f)
    # ---------------- About menu + nav
    def f():
        go("#/frontier",2200); nav=pg.evaluate("()=>{const n=document.querySelector('header nav');const items=[...n.querySelectorAll(':scope > ul > li > a, :scope > ul > li > details > summary, :scope a, :scope summary')].filter((e,i,a)=>a.indexOf(e)===i).slice(0,8).map(a=>({t:a.innerText.trim().slice(0,14),l:Math.round(a.getBoundingClientRect().left),r:Math.round(a.getBoundingClientRect().right)}));return {vw:innerWidth,items,wrap:getComputedStyle(n.querySelector('ul')).flexWrap,nav_w:Math.round(n.getBoundingClientRect().width)}}")
        cut=[i for i in nav["items"] if i["t"] and (i["r"]>nav["vw"]+0 or i["l"]<0)]
        step("A1","header nav inside viewport",ok=not cut,result=nav|{"cut":cut},screenshot=shot("nav_top"))
        s=pg.locator(".aboutmenu summary,.aboutmenu > button").first; sinfo=pg.evaluate("()=>{const s=document.querySelector('.aboutmenu summary,.aboutmenu > button');return {tag:s.tagName,expanded:s.getAttribute('aria-expanded'),controls:s.getAttribute('aria-controls'),h:Math.round(s.getBoundingClientRect().height),w:Math.round(s.getBoundingClientRect().width)}}")
        tap(s,force=True); pg.wait_for_timeout(500)
        box=pg.evaluate("()=>{const u=document.querySelector('.aboutmenu ul');const r=u.getBoundingClientRect();return {l:Math.round(r.left),r:Math.round(r.right),vw:innerWidth,clipped:r.right>innerWidth+1||r.left<-1,items:[...u.querySelectorAll('a')].map(a=>({t:a.innerText.slice(0,26),l:Math.round(a.getBoundingClientRect().left),r:Math.round(a.getBoundingClientRect().right),h:Math.round(a.getBoundingClientRect().height)})),expanded:document.querySelector('.aboutmenu summary,.aboutmenu > button').getAttribute('aria-expanded'),open:document.querySelector('.aboutmenu details')?document.querySelector('.aboutmenu details').open:null}")
        shot("about_menu_open",False)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
        after=pg.evaluate("()=>({open:document.querySelector('.aboutmenu details')?document.querySelector('.aboutmenu details').open:null,expanded:document.querySelector('.aboutmenu summary,.aboutmenu > button').getAttribute('aria-expanded'),focus:document.activeElement.tagName+':'+(document.activeElement.innerText||'').slice(0,12)})")
        step("A2","About menu geometry, aria, Escape",ok=(not box["clipped"]) and sinfo["expanded"] is not None and (after["open"] in (False,None)) ,result={"summary":sinfo,"open_box":box,"after_escape":after},screenshot=shot("about_menu_state",False))
    safe("A",f)
    # ---------------- gallery navigation
    def f():
        go("#/simulations",3500)
        g=pg.evaluate("""()=>{const cards=[...document.querySelectorAll('main article')].filter(a=>a.querySelector('video'));return {cards:cards.length,h:document.documentElement.scrollHeight,filters:[...document.querySelectorAll('main select,main input[type=search],main [role=group] button,main .chip')].length,jump:[...document.querySelectorAll('main a[href^="#"]')].filter(a=>!a.getAttribute('href').startsWith('#/')).length,jumpHash:[...document.querySelectorAll('main a')].filter(a=>/simulations\\?.*(card|sim)=|#sim-/.test(a.getAttribute('href')||'')).length,preload:[...new Set(cards.map(c=>c.querySelector('video').preload))],counter:(document.getElementById('main').innerText.match(/\\d+ of \\d+[^.]{0,30}/)||[null])[0],collapsed:document.querySelectorAll('main details:not([open]) video, main details:not([open])').length}}""")
        step("G1","gallery navigation present + height",ok=(g["h"]<15000 if vp=="mobile" else g["h"]<20000) and (g["filters"]>0 or g["jump"]>0 or g["jumpHash"]>0),result=g,screenshot=shot("sim_gallery",False))
        ctrl=pg.evaluate("()=>[...document.querySelectorAll('main button, main select, main input')].slice(0,14).map(e=>[e.tagName,(e.innerText||e.name||e.getAttribute('aria-label')||'').slice(0,24)])")
        step("G2","gallery controls found (first 14)",result=ctrl)
    safe("G",f)
    # filter works if a Molecular control exists
    def f():
        go("#/simulations",3500); c=pg.get_by_role("button",name=re.compile("^Molecular",re.I))
        if c.count():
            tap(c.first); pg.wait_for_timeout(1200); n=pg.evaluate("()=>[...document.querySelectorAll('main article')].filter(a=>a.querySelector('video')&&a.getBoundingClientRect().height>0&&getComputedStyle(a).display!=='none').length")
            step("G3","filter Molecular shows 2 cards",ok=(n==2),result={"visible_cards":n,"counter":(T(3000).match(r'\d+ of \d+[^.]{0,30}') or [None])[0]},screenshot=shot("sim_filter_molecular",False))
        else: step("G3","filter Molecular",ok=False,result={"found":False})
    safe("G3",f)
    b.close()
json.dump({"steps":steps,"console":console,"httpfail":httpfail,"non_get":posts,"ts":time.strftime("%F %T %Z")},open(f"{OUT}/audit6_{vp}.json","w"),indent=1,default=str)
print(vp,"steps",len(steps),"console",len(console),"httpfail",len(httpfail))
