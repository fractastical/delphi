import json, re, sys, time, urllib.request
from playwright.sync_api import sync_playwright
BASE="https://frontier.morphoswarm.ai/"; OUT="/data/artifacts/delphi-evolve-rethink/site-audit/r5"
vp=sys.argv[1]; W,H={"desktop":(1440,1000),"mobile":(390,844)}[vp]
steps=[]; console=[]; httpfail=[]; posts=[]; cur=[""]
def step(sid,desc,**kw): steps.append({"id":sid,"vp":vp,"desc":desc,**kw}); print(sid,flush=True)
def slug(s): return re.sub(r'[^a-zA-Z0-9]+','_',s)[:55].strip('_')
CONTRAST=open('/tmp/claude-1000/-data-worktrees-delphi-evolve-rethink-critic/45bfe973-0b4e-4c5b-9d70-43d8c4aa8801/scratchpad/audit.py').read().split('CONTRAST="""')[1].split('"""')[0]
BAD=re.compile(r"\[object |undefined|\bNaN\b|\{\{|\}\}|Infinity")
def jserr(f): return str(f).split('\n')[0][:150]
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--autoplay-policy=no-user-gesture-required","--use-gl=swiftshader","--enable-unsafe-swiftshader"]); ctx=b.new_context(viewport={"width":W,"height":H},has_touch=(vp=="mobile")); pg=ctx.new_page()
    pg.on("console",lambda m: console.append({"vp":vp,"at":cur[0],"type":m.type,"text":m.text[:200]}) if m.type=="error" else None)
    pg.on("pageerror",lambda e: console.append({"vp":vp,"at":cur[0],"type":"pageerror","text":str(e)[:200]}))
    pg.on("response",lambda r: httpfail.append({"vp":vp,"at":cur[0],"url":r.url[-80:],"status":r.status}) if r.status>=400 else None)
    pg.on("request",lambda r: posts.append((cur[0],r.method,r.url[-40:])) if r.method!="GET" else None)
    def go(route,wait=2200): cur[0]=route; pg.goto(BASE+route,wait_until="load",timeout=45000); pg.wait_for_timeout(wait)
    def shot(name,full=False):
        f=f"{OUT}/R5_{vp}_{slug(name)}.png"
        try: pg.screenshot(path=f,full_page=full); return f
        except Exception: return None
    def T(n=100000): return re.sub(r'\s+',' ',pg.evaluate("()=>document.getElementById('main').innerText"))[:n]
    def safe(sid,fn):
        try: fn()
        except Exception as e: step(sid,"error",ok=False,error=jserr(e))
    tap=lambda l,**k: (l.tap(**k) if vp=="mobile" else l.click(**k))
    # ---- CRITICAL: F1 table
    def f():
        go("#/frontier",3500)
        g=pg.evaluate("""()=>{const t=document.querySelector('main table');if(!t)return null;const w=t.parentElement;const wr=w.getBoundingClientRect();const tr=t.querySelector('tbody tr');
          const cells=[...tr.querySelectorAll('td')].map(td=>({txt:td.innerText.slice(0,26),w:Math.round(td.getBoundingClientRect().width),vis:td.getBoundingClientRect().right<=wr.right+1&&td.getBoundingClientRect().left>=wr.left-1}));
          return {tableW:Math.round(t.getBoundingClientRect().width),wrapW:w.clientWidth,idW:Math.round(t.querySelector('th').getBoundingClientRect().width),rowH:Math.round(tr.getBoundingClientRect().height),cells,rows:t.querySelectorAll('tbody tr').length,
          ws:getComputedStyle(tr.querySelector('td')).whiteSpace,cards:getComputedStyle(t).display}}""")
        step("C1","F-1 frontier table",ok=bool(g and sum(1 for c in g["cells"] if c["vis"])>=3),result=g,screenshot=shot("frontier_table"))
        try:
            tap(pg.locator("main table tbody tr").nth(2).locator("td").nth(1),force=True); pg.wait_for_timeout(800)
            d=pg.evaluate("()=>{const e=[...document.querySelectorAll('main *')].find(x=>/THE QUESTION/.test(x.innerText||'')&&x.children.length>2&&x.getBoundingClientRect().width<700);return e?e.innerText:''}")
            step("C6","N-8 raw JSON in live question detail",ok=not re.search(r'\{"[a-z_]+":',d),result={"len":len(d),"raw_json":bool(re.search(r'\{"[a-z_]+":',d)),"sample":re.findall(r'\{"[a-z_]+":.{0,80}',d)[:1],"url":pg.url[-60:]},screenshot=shot("frontier_detail"))
        except Exception as e: step("C6","detail",ok=False,error=jserr(e))
        for r in ["#/frontier?live=zzz-unknown"]:
            go(r,2500); t=T(); step("C8","F-5 unknown id notice",ok=bool(re.search(r'(?i)not found|no such|no live|unknown (id|question)|could not find|not visible',t)),result={"notice":re.findall(r'(?i)[^.]{0,60}(?:not found|no such|not visible|could not find)[^.]{0,60}',t)[:1]})
    safe("C1",f)
    # N9 + knowledge load
    def f():
        t0=time.time(); go("#/knowledge",100); first=None
        for i in range(120):
            n=pg.evaluate("()=>document.querySelectorAll('main a[href^=\"#/entity\"],main a[href*=\"#/knowledge/\"]').length")
            if n>0: first=round(time.time()-t0,1); break
            pg.wait_for_timeout(250)
        pg.wait_for_timeout(2500); ov=pg.evaluate("()=>({docW:document.documentElement.scrollWidth,vw:innerWidth,wide:[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth+2&&e.getBoundingClientRect().width>0).slice(0,3).map(e=>[e.tagName,Math.round(e.getBoundingClientRect().right),(e.innerText||'').slice(0,24)])})")
        step("C2","N-9 knowledge overflow + load",ok=ov["docW"]<=ov["vw"]+1 and (first or 99)<5,result=ov|{"first_cards_s":first},screenshot=shot("knowledge"))
    safe("C2",f)
    # N11 work tab
    def f():
        go("#/work?tab=work",3500); r=pg.evaluate("()=>({pre:[...document.querySelectorAll('main pre')].map(p=>[p.innerText.length,!!p.closest('details'),p.closest('details')?p.closest('details').open:null]),h:document.documentElement.scrollHeight,h2:[...document.querySelectorAll('main h2')].map(h=>h.innerText.slice(0,40))})")
        step("C3","N-11 work tab raw JSON",ok=all(x[0]<20000 or (x[1] and not x[2]) for x in r["pre"]),result=r,screenshot=shot("work_work"))
    safe("C3",f)
    # nav + About menu
    def f():
        go("#/frontier",2000); nav=pg.evaluate("()=>{const n=document.querySelector('header nav');const items=[...n.querySelectorAll(':scope > ul > li > a, :scope > ul > li > details > summary')].map(a=>({t:a.innerText.trim(),l:Math.round(a.getBoundingClientRect().left),r:Math.round(a.getBoundingClientRect().right)}));return {vw:innerWidth,items,ox:getComputedStyle(n).overflowX,wrap:getComputedStyle(n.querySelector('ul')).flexWrap}}")
        cut=[i for i in nav["items"] if i["r"]>nav["vw"] or i["l"]<0]
        step("C4a","header nav items inside viewport",ok=not cut,result=nav|{"cut":cut},screenshot=shot("nav_top"))
        s=pg.locator(".aboutmenu summary"); tap(s,force=True); pg.wait_for_timeout(400)
        box=pg.evaluate("()=>{const u=document.querySelector('.aboutmenu ul');const r=u.getBoundingClientRect();return {open:document.querySelector('.aboutmenu details').open,l:Math.round(r.left),r:Math.round(r.right),vw:innerWidth,clipped:r.right>innerWidth||r.left<0,items:[...u.querySelectorAll('a')].map(a=>a.innerText.slice(0,26))}}")
        shot("about_menu_open"); pg.keyboard.press("Escape"); pg.wait_for_timeout(300); esc=pg.evaluate("()=>!document.querySelector('.aboutmenu details').open")
        step("C4b","About menu open geometry + Esc",ok=(not box["clipped"]) and esc,result=box|{"closes_on_escape":esc},screenshot=shot("about_menu_state"))
    safe("C4",f)
    # N2 widget
    def f():
        go("#/studio/flying-fish?scale=organ",2800); pg.locator("input[name=sodium_scale]").fill("-5"); pg.get_by_role("button",name="Run a preview").first.click(); pg.wait_for_timeout(2500)
        w=re.sub(r'\s+',' ',pg.evaluate("()=>document.querySelector('main form input[name=sodium_scale]').closest('section,.card').innerText")); err=w[w.find('nothing is stored'):][:200]
        pg.locator("input[name=sodium_scale]").fill("0.35"); pg.get_by_role("button",name="Run a preview").first.click(); pg.wait_for_timeout(7500)
        w2=re.sub(r'\s+',' ',pg.evaluate("()=>document.querySelector('main form input[name=sodium_scale]').closest('section,.card').innerText"))
        step("C5","N-2 [object Object] in preview",ok=("[object" not in err and "[object" not in w2),result={"error":err,"success_footer_has_object":"[object" in w2,"code":re.findall(r'code [^·]{0,50}',w2)[:1]},screenshot=shot("widget"))
    safe("C5",f)
    # N3 search, N4 graph
    def f():
        go("#/search?q=zzzzxxqq&tab=record",4500); t=T(6000)
        step("C9","N-3 gibberish search",ok=bool(re.search(r'(?i)no (literal|lexical|exact) match|weak|low similarity|nothing matches|no record matches',t)) and not re.search(r'\{"dimensions"',t),result={"note":bool(re.search(r'(?i)no (literal|lexical|exact) match|weak|low similarity|nothing matches|no record matches',t)),"raw_json":bool(re.search(r'\{"dimensions"',t))},screenshot=shot("search_gibberish"))
        go("#/search?q=wing&tab=record",4000); tap(pg.locator("main a[href^='#/entity']").first); pg.wait_for_timeout(2500); tap(pg.locator("main a[href^='#/graph']").first); pg.wait_for_timeout(3000)
        gr=pg.evaluate("()=>{const svg=document.querySelector('main svg');if(!svg)return null;return {bg:getComputedStyle(svg.parentElement).backgroundColor,labels:[...svg.querySelectorAll('text')].slice(0,3).map(t=>[t.textContent.slice(0,22),getComputedStyle(t).fill]),nodes:svg.querySelectorAll('circle').length,edges:svg.querySelectorAll('line,path').length}}")
        step("C10","N-4 graph label readability",result=gr,screenshot=shot("graph"))
    safe("C9",f)
    # docs/csv
    snap=json.loads(urllib.request.urlopen(BASE+"data/snapshot.json",timeout=30).read()); res=[]
    for u in [d["href"] for d in snap.get("documents",[])]+["data/results/designs.csv"]:
        try: st=urllib.request.urlopen(BASE+u,timeout=20).status
        except Exception as e: st=getattr(e,'code',str(e)[:20])
        res.append((u[-50:],st))
    step("C7","documents + designs.csv",ok=all(s==200 for _,s in res),result={"n":len(res),"non200":[r for r in res if r[1]!=200]})
    # ---- NEW surfaces
    for r in ["#/about","#/about/team","#/about/docs","#/about/inspirations","#/generative"]:
        def f(r=r):
            go(r,2800); t=T(); st=pg.evaluate("()=>({h:document.documentElement.scrollHeight,ox:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,h1:document.querySelectorAll('main h1').length,broken:[...document.images].filter(i=>i.complete&&i.naturalWidth===0).length,katex:document.querySelectorAll('main .katex').length,katexErr:document.querySelectorAll('main .katex-error').length,vids:document.querySelectorAll('video').length})")
            step("N:"+r,"new route",ok=not st["ox"] and not st["katexErr"],result=st|{"len":len(t),"bad":sorted(set(m.group(0) for m in BAD.finditer(t))),"rawTeX":re.findall(r'\\\\(?:frac|sqrt|mathrm|partial|nabla)\b|\$[^$]{3,40}\$',t)[:3],"contrast_n":len(pg.evaluate(CONTRAST)),"head":t[:120]},screenshot=shot(r.replace('#/','')+"_full",True))
        safe("N:"+r,f)
    # generative equations
    def f():
        go("#/generative",3500); eq=pg.evaluate("()=>{const k=[...document.querySelectorAll('main .katex-display, main .eqn, main .equation')];const all=[...document.querySelectorAll('main .katex')];return {display:document.querySelectorAll('main .katex-display').length,inline:all.length,clipped:[...document.querySelectorAll('main .katex-display')].filter(e=>e.scrollWidth>e.clientWidth+2).length,widest:Math.max(0,...[...document.querySelectorAll('main .katex-display')].map(e=>e.scrollWidth)),vw:innerWidth,sources:[...document.querySelectorAll('main .katex-html')].length}}")
        step("N:gen_eq","generative equations render",ok=eq["clipped"]==0,result=eq,screenshot=shot("generative_eq",False))
    safe("N:gen_eq",f)
    # Home GLB
    def f():
        go("#/home",2500); pg.locator("#fish-viewer").scroll_into_view_if_needed(); pg.wait_for_timeout(7000)
        v=pg.evaluate("()=>{const r=document.querySelector('#fish-viewer');const c=r.querySelector('canvas');return {canvas:!!c,box:c?[Math.round(c.getBoundingClientRect().width),Math.round(c.getBoundingClientRect().height)]:null,label:c?c.getAttribute('aria-label'):null,state:r.innerText.replace(/\\s+/g,' ').slice(0,240),shaOk:/sha256 matches/.test(r.innerText),ox:document.documentElement.scrollWidth>innerWidth+1}}")
        step("N:glb","Home actual GLB viewer",ok=v["canvas"] and v["shaOk"],result=v,screenshot=shot("home_glb"))
    safe("N:glb",f)
    # sim gallery
    def f():
        go("#/simulations",3500)
        n=pg.evaluate("()=>document.querySelectorAll('main video').length"); cards=pg.evaluate("()=>[...document.querySelectorAll('main article,main .simcard,main .card')].length")
        res=pg.evaluate("""async()=>{const out=[];for(const v of document.querySelectorAll('main video')){v.muted=true;const r={src:(v.currentSrc||v.src||'').split('/').pop().slice(0,36),dur:v.duration,ready:v.readyState,err:v.error&&v.error.code,poster:!!v.poster};
          try{v.scrollIntoView({block:'center'});await new Promise(a=>setTimeout(a,600));await v.play();await new Promise(a=>setTimeout(a,900));r.t=Math.round(v.currentTime*100)/100;v.pause();v.currentTime=Math.min(3,(v.duration||6)/2);await new Promise(a=>setTimeout(a,350));r.seek=Math.round(v.currentTime*100)/100}catch(e){r.playErr=String(e).slice(0,50)}out.push(r)}return out}""")
        bad=[r for r in res if r.get("err") or r.get("playErr") or not r.get("t") or r.get("t")<0.3 or (r.get("seek") or 0)<1]
        step("N:sim","simulation gallery players",ok=(n>=14 and not bad),result={"videos":n,"cards":cards,"bad":bad[:8],"sample":res[:3],"height":pg.evaluate("()=>document.documentElement.scrollHeight")},screenshot=shot("sim_gallery",False))
    safe("N:sim",f)
    # system build usage
    for tb in ["overview","runtime","resources","receipts","work","specs"]:
        def f(tb=tb):
            go(f"#/work?tab={tb}",3000); t=T(60000); st=pg.evaluate("()=>({h:document.documentElement.scrollHeight,ox:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,h2:[...document.querySelectorAll('main h2')].map(h=>h.innerText.slice(0,36)),pre:[...document.querySelectorAll('main pre')].map(p=>p.innerText.length)})")
            step("N:sys:"+tb,"system tab",result=st|{"bad":sorted(set(m.group(0) for m in BAD.finditer(t))),"usage_words":re.findall(r'(?i)(?:usage|tokens?|cost|spend|metered|subscription)[^.]{0,70}',t)[:2]},screenshot=shot("sys_"+tb) if tb in("overview","runtime","resources") else None)
        safe("N:sys:"+tb,f)
    # design review
    def f():
        go("#/studio/flying-fish",3500)
        dr=pg.evaluate("""()=>{const s=document.querySelector('#designreview');if(!s)return {present:false};const det=[...s.querySelectorAll('details')].map(d=>[d.querySelector('summary').innerText.slice(0,70),d.open]);return {present:true,text:s.innerText.replace(/\\s+/g,' ').slice(0,420),details:det,textareas:s.querySelectorAll('textarea').length,buttons:[...s.querySelectorAll('button')].map(b=>b.innerText.slice(0,26)).slice(0,8),h:Math.round(s.getBoundingClientRect().height)}}""")
        step("N:design","design review panel",result=dr,screenshot=shot("design_review",False))
        before=len(posts)
        ta=pg.locator("#designreview textarea").first
        if ta.count(): 
            ta.scroll_into_view_if_needed(); ta.fill("critic local draft, not submitted"); pg.wait_for_timeout(600)
            b=[x for x in pg.locator("#designreview button").all() if re.search(r'(?i)save|draft|add',x.inner_text())]
            if b: tap(b[0]); pg.wait_for_timeout(800)
            step("N:design_draft","local draft stays local (no non-GET request)",ok=(len(posts)==before),result={"new_non_get":posts[before:],"after":pg.evaluate("()=>document.querySelector('#designreview').innerText.replace(/\\s+/g,' ').slice(-240)")},screenshot=shot("design_review_draft",False))
    safe("N:design",f)
    try:
        r=json.loads(urllib.request.urlopen(BASE+"api/design/context",timeout=20).read()); step("N:api","GET /api/design/context",result={"keys":list(r)[:10],"snippet":json.dumps(r)[:300]})
    except Exception as e: step("N:api","GET /api/design/context",ok=False,error=str(e)[:120])
    b.close()
json.dump({"steps":steps,"console":console,"httpfail":httpfail,"non_get":posts,"ts":time.strftime("%F %T %Z")},open(f"{OUT}/audit5_{vp}.json","w"),indent=1,default=str)
print(vp,"steps",len(steps),"console",len(console),"httpfail",len(httpfail))
