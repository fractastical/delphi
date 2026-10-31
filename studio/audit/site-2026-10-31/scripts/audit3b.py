import json, re, sys, time
from playwright.sync_api import sync_playwright
BASE="https://frontier.morphoswarm.ai/"; OUT="/data/artifacts/delphi-evolve-rethink/site-audit/r3"
vp=sys.argv[1]; W,H={"desktop":(1440,1000),"mobile":(390,844)}[vp]
steps=[]; console=[]; httpfail=[]; cur=[""]
def step(sid,desc,**kw): steps.append({"id":sid,"vp":vp,"desc":desc,**kw}); print(sid,flush=True); return steps[-1]
def slug(s): return re.sub(r'[^a-zA-Z0-9]+','_',s)[:55].strip('_')
BAD=re.compile(r"\[object |undefined|\bNaN\b|\{\{|\}\}|Infinity|%[0-9A-F]{2}")
def T(pg,n=6000): return re.sub(r'\s+',' ',pg.evaluate("()=>document.getElementById('main').innerText"))[:n]
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox"]); ctx=b.new_context(viewport={"width":W,"height":H},has_touch=(vp=="mobile")); pg=ctx.new_page()
    pg.on("console",lambda m: console.append({"vp":vp,"at":cur[0],"type":m.type,"text":m.text[:200]}) if m.type in("error","warning") else None)
    pg.on("pageerror",lambda e: console.append({"vp":vp,"at":cur[0],"type":"pageerror","text":str(e)[:200]}))
    pg.on("response",lambda r: httpfail.append({"vp":vp,"at":cur[0],"url":r.url[-80:],"status":r.status}) if r.status>=400 else None)
    def go(route,wait=1800):
        cur[0]=route; pg.goto(BASE+route,wait_until="load",timeout=40000); pg.wait_for_timeout(wait)
    def shot(name,full=False):
        f=f"{OUT}/R3_{vp}_{slug(name)}.png"
        try: pg.screenshot(path=f,full_page=full); return f
        except Exception: return None
    def tap(loc,**k): (loc.tap(**k) if vp=="mobile" else loc.click(**k))
    def safe(sid,desc,fn):
        try: return fn()
        except Exception as e: return step(sid,desc,ok=False,error=str(e).split('\n')[0][:160])
    # B1 keyboard order
    FOC="""()=>{const e=document.activeElement;const cs=getComputedStyle(e);const r=e.getBoundingClientRect();return [e.tagName,(e.innerText||e.value||e.getAttribute('aria-label')||e.name||'').slice(0,22),cs.outlineStyle+' '+cs.outlineWidth,cs.boxShadow!=='none',Math.round(r.top),Math.round(r.width)]}"""
    for r in ["#/studio","#/studio/flying-fish","#/knowledge","#/search","#/evidence","#/work","#/engineering","#/belief"]:
        def f(r=r):
            go(r,2500); seq=[]
            for i in range(16): pg.keyboard.press("Tab"); seq.append(pg.evaluate(FOC))
            noind=[s for s in seq if s[2].startswith('none') and not s[3] and s[0] not in('BODY',)]
            offscreen=[s for s in seq if s[4]<-5 or s[4]>H*40]
            step("B1:"+r,"keyboard: 16 Tab stops",ok=not noind,result={"no_focus_indicator":noind[:4],"stops":[(s[0],s[1]) for s in seq][:16],"body_stops":sum(1 for s in seq if s[0]=='BODY')})
        safe("B1:"+r,"kbd",f)
    # skip link
    def f():
        go("#/frontier",1500); pg.keyboard.press("Tab"); first=pg.evaluate(FOC); pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
        step("B1s","skip link works",result={"first_focus":first[:2],"after_enter":pg.evaluate("()=>document.activeElement.id||document.activeElement.tagName")})
    safe("B1s","skip",f)
    # B2 engineering
    def f():
        go("#/engineering",2500); btns=pg.evaluate("()=>[...document.querySelectorAll('main button')].map(b=>b.innerText.trim()).filter(Boolean)"); 
        stl=pg.evaluate("()=>[...document.querySelectorAll('main *')].filter(e=>e.children.length===0&&/\\bSTL\\b/.test(e.innerText||'')).map(e=>[e.tagName,e.innerText.slice(0,80)]).slice(0,8)")
        step("B2a","engineering controls and STL mentions",result={"buttons":btns[:24],"stl":stl})
    safe("B2a","eng",f)
    for label in ['Cypselurus-type, 0.1 kg','Scaled-up Cypselurus, 5 kg','Oxyporhamphus-like (CG aft)','Clear all (unknown)']:
        def f(label=label):
            go("#/engineering",2200); tap(pg.get_by_role("button",name=label).first); pg.wait_for_timeout(900); t=T(pg,30000)
            step("B2p:"+label,"preset",result={"pass":len(re.findall(r'\bpass\b',t)),"fail":len(re.findall(r'\bfail\b',t)),"unknown":len(re.findall(r'\bunknown\b',t)),"unsat":len(re.findall(r'unsat',t)),"bad":sorted(set(m.group(0) for m in BAD.finditer(t))),"h":pg.evaluate("()=>document.documentElement.scrollHeight")},screenshot=shot("eng_"+label))
        safe("B2p:"+label,"preset",f)
    def f():
        go("#/engineering",2500); tap(pg.locator("details:has(input[name=wing_loading_min]) > summary").first); pg.wait_for_timeout(400)
        pg.locator("input[name=wing_loading_min]").fill("300"); pg.locator("input[name=speed_max]").fill("5"); pg.wait_for_timeout(1200); t=T(pg,40000)
        step("B2c","user constraints wing_loading_min=300 speed_max=5",result={"unsat":len(re.findall('unsat',t)),"conflict_ids":re.findall(r'Conflict: [A-Za-z_, ]+',t)[:2],"bad":sorted(set(m.group(0) for m in BAD.finditer(t)))},screenshot=shot("eng_constraints"))
    safe("B2c","eng constraints",f)
    # B3 knowledge
    def f():
        go("#/knowledge",2500); n0=pg.evaluate("()=>document.querySelectorAll('main a[href^=\"#/entity\"],main a[href*=\"#/knowledge/\"]').length")
        for i in range(6): pg.mouse.wheel(0,6000); pg.wait_for_timeout(900)
        n1=pg.evaluate("()=>document.querySelectorAll('main a[href^=\"#/entity\"],main a[href*=\"#/knowledge/\"]').length")
        ox=pg.evaluate("()=>({docOverflow:document.documentElement.scrollWidth>document.documentElement.clientWidth+1,wide:[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth+2&&e.getBoundingClientRect().width>0).slice(0,4).map(e=>[e.tagName,e.className.toString().slice(0,30),Math.round(e.getBoundingClientRect().right),(e.innerText||'').slice(0,30)])})")
        step("B3a","browse claims infinite scroll",result={"cards_before":n0,"cards_after_6_scrolls":n1,"overflow":ox},screenshot=shot("knowledge_scrolled"))
    safe("B3a","knowledge",f)
    def f():
        go("#/knowledge",2500); a=pg.locator("main a[href^='#/entity'],main a[href*='#/knowledge/']").first; href=a.get_attribute("href"); tap(a); pg.wait_for_timeout(2500)
        step("B3b","open first claim card",result={"href":href,"url":pg.url[-70:],"head":T(pg,300)},screenshot=shot("claim_card_open"))
    safe("B3b","claim",f)
    def f():
        go("#/knowledge?tab=graph",3000); st=pg.evaluate("()=>({items:document.querySelectorAll('svg [tabindex]').length,circles:document.querySelectorAll('svg circle').length,lines:document.querySelectorAll('svg line,svg path').length,labels:[...document.querySelectorAll('svg text')].slice(0,3).map(t=>[t.textContent.slice(0,20),getComputedStyle(t).fill])})")
        step("B3g0","claim graph structure",result=st,screenshot=shot("claim_graph"))
        node=pg.locator("svg [tabindex]").first; before=T(pg,3000); tap(node,force=True); pg.wait_for_timeout(600); after=T(pg,3000)
        step("B3g1","graph click",result={"changed":before!=after,"url":pg.url[-60:],"detail":re.sub(r'\s+',' ',pg.evaluate("()=>{const d=document.querySelector('.gdetail,.detail,aside,.panel:last-child');return d?d.innerText.slice(0,260):null}") or '')},screenshot=shot("claim_graph_click"))
        # hover: move the mouse to the midpoint of the first visible line/path
        pos=pg.evaluate("()=>{const e=[...document.querySelectorAll('svg line,svg path')].find(x=>{const r=x.getBoundingClientRect();return r.width>8&&r.height>=0&&r.top>0});if(!e)return null;const r=e.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]}")
        if pos and vp=="desktop":
            pg.mouse.move(pos[0],pos[1]); pg.wait_for_timeout(500); tip=pg.evaluate("()=>[...document.querySelectorAll('[role=tooltip],.tip,.tooltip,svg title')].map(x=>x.textContent.slice(0,80)).slice(0,3)")
            step("B3g2","edge hover tooltip",result={"pos":pos,"tooltips":tip,"hover_style_changed":None},screenshot=shot("claim_graph_hover"))
        else: step("B3g2","edge hover",result={"pos":pos,"skipped":"touch viewport" if vp=="mobile" else "no edge found"})
        pg.keyboard.press("Enter"); pg.wait_for_timeout(300)
    safe("B3g","claim graph",f)
    for tb in ["#/knowledge?tab=claims","#/knowledge?tab=mission","#/knowledge?tab=catalog"]:
        def f(tb=tb):
            go(tb,4000); t=T(pg,20000); step("B3t:"+tb,"knowledge tab",result={"len":len(t),"head":t[:200],"bad":sorted(set(m.group(0) for m in BAD.finditer(t))),"katexErr":pg.evaluate("()=>document.querySelectorAll('.katex-error').length")},screenshot=shot(tb.split('=')[-1]+"_tab"))
        safe("B3t:"+tb,"tab",f)
    # B4 frontier
    def f():
        go("#/frontier",3000); st=pg.evaluate("()=>({svgs:document.querySelectorAll('main svg').length,items:document.querySelectorAll('main svg [tabindex]').length,selects:[...document.querySelectorAll('main select')].map(s=>s.name+':'+s.options.length)})")
        step("B4a","frontier structure",result=st)
        cn=pg.locator("main svg [tabindex]").first; cn.scroll_into_view_if_needed(); tap(cn,force=True); pg.wait_for_timeout(700)
        step("B4b","curated graph click",result={"url":pg.url[-60:],"detail":pg.evaluate("()=>{const d=document.querySelector('.gdetail,.detail-col,aside');return d?d.innerText.slice(0,240):null}")},screenshot=shot("frontier_graph_click"))
    safe("B4","frontier",f)
    def f():
        go("#/frontier",3000); n=pg.locator("main table tbody tr").count(); out=[]
        for i in [0,1,2,5,10,20,30,39]:
            try:
                tap(pg.locator("main table tbody tr").nth(i).locator("td").nth(1),force=True); pg.wait_for_timeout(500)
                pt=pg.evaluate("()=>{const e=[...document.querySelectorAll('main *')].find(x=>/THE QUESTION/.test(x.innerText||'')&&x.children.length>2&&x.getBoundingClientRect().width<700);return e?e.innerText:''}")
                out.append({"i":i,"len":len(pt),"bad":sorted(set(m.group(0) for m in BAD.finditer(pt))),"has_next_action":"NEXT ACTION" in pt,"raw_json":bool(re.search(r'\{"[a-z_]+":',pt))})
            except Exception as e: out.append({"i":i,"err":str(e)[:60]})
        step("B4d","live question details sampled (8 of 40 on screen)",result={"rows":n,"details":out})
    safe("B4d","frontier details",f)
    for q in ["#/frontier?approach=design_goal","#/frontier?scale=organism","#/frontier?state=resolved_in_review","#/frontier?q=zzzzqq","#/frontier?lq=zzzzqq","#/frontier?dir=topdown","#/frontier?lc=actionable"]:
        def f(q=q):
            go(q,3000); t=T(pg,30000); step("B4f:"+q,"frontier filter",result={"len":len(t),"empty_notice":re.findall(r'(?i)no (?:question|record|live)[^.]{0,80}',t)[:1],"shown":re.findall(r'\d+ of \d+ shown[^.]{0,30}',t)[:2]})
        safe("B4f:"+q,"filter",f)
    # B5 belief
    def f():
        go("#/belief",2500); sc=pg.evaluate("()=>[...document.querySelectorAll('main input')].map(i=>[i.name,i.type,i.placeholder])")
        for i,v in enumerate(["0.3","0.6","","0.9"],1):
            if v: pg.locator(f"input[name=v{i}]").fill(v)
        pg.wait_for_timeout(1200); t=T(pg,20000)
        step("B5a","belief scratch with missing v3",result={"inputs":sc,"after":t[t.lower().find('scratch'):][:500] if 'scratch' in t.lower() else t[-500:],"bad":sorted(set(m.group(0) for m in BAD.finditer(t)))},screenshot=shot("belief_partial",True))
        it=pg.locator("main svg [tabindex]"); k=it.count(); before=T(pg,5000); tap(it.nth(min(2,k-1)),force=True) if k else None; pg.wait_for_timeout(500)
        step("B5b","belief graph click",result={"interactive":k,"changed":before!=T(pg,5000),"focus":pg.evaluate("()=>(document.activeElement.getAttribute('aria-label')||document.activeElement.tagName).slice(0,60)")},screenshot=shot("belief_graph_click"))
    safe("B5","belief",f)
    # B6 system tabs
    for tb in ["overview","specs","work","resources","receipts","runtime"]:
        def f(tb=tb):
            t0=time.time(); go(f"#/work?tab={tb}",1500); h=pg.evaluate("()=>({h2:[...document.querySelectorAll('main h2')].map(x=>x.innerText.slice(0,40)).slice(0,8),pre:[...document.querySelectorAll('main pre')].map(x=>x.innerText.length),tables:document.querySelectorAll('main table').length,links:[...document.querySelectorAll('main a[href^=\"http\"],main a[href^=\"/\"]')].length,h:document.documentElement.scrollHeight})")
            step("B6:"+tb,"system tab",result=h|{"render_s":round(time.time()-t0,1)},screenshot=shot("work_"+tb))
        safe("B6:"+tb,"system",f)
    # B7 malformed params
    for r in ["#/knowledge/%","#/knowledge/%E0%A4%A","#/entity/Claim/%","#/entity/Bogus/x","#/search?q=%","#/search?q=%25&tab=bogus","#/studio/unknown-project","#/studio/flying-fish?scale=bogus","#/studio?goal=%00","#/graph/Claim/doesnotexist","#/engineering?scale=bogus","#/work?tab=bogus","#/evidence?src=bogus:xyz","#/evidence?src=doc:","#/frontier?scale=bogus&approach=bogus&state=bogus","#/frontier?n=-1","#/frontier?n=abc","#//","#/%2F%2F"]:
        def f(r=r):
            go(r,2200); t=T(pg,1500); step("B7:"+r,"malformed route",result={"text":t[:200],"bad":sorted(set(m.group(0) for m in BAD.finditer(t))),"blank":len(t)<20,"err_notice":bool(re.search(r'(?i)not found|could not|no such|unknown|invalid|not available',t))},screenshot=None)
        safe("B7:"+r,"malformed",f)
    # B9 touch/scroll behaviours
    if vp=="mobile":
        def f():
            go("#/frontier",2500); tap(pg.locator("header nav a",has_text="Knowledge").first,force=True); pg.wait_for_timeout(800); u1=pg.url
            nav_hidden=pg.evaluate("()=>{const a=[...document.querySelectorAll('header nav a')].find(x=>x.innerText==='System');return a?Math.round(a.getBoundingClientRect().right):null}")
            pg.evaluate("()=>{const u=document.querySelector('header nav ul');u.scrollLeft=u.scrollWidth}"); pg.wait_for_timeout(300)
            step("B9","touch tap nav + nav scroll",result={"url_after_tap":u1[-30:],"system_right_before_scroll":nav_hidden,"system_right_after_scroll":pg.evaluate("()=>{const a=[...document.querySelectorAll('header nav a')].find(x=>x.innerText==='System');return Math.round(a.getBoundingClientRect().right)}"),"vw":390},screenshot=shot("nav_scrolled"))
        safe("B9","touch",f)
    b.close()
json.dump({"steps":steps,"console":console,"httpfail":httpfail,"ts":time.strftime("%F %T %Z")},open(f"{OUT}/audit3b_{vp}.json","w"),indent=1,default=str)
print(vp,"steps",len(steps),"console",len(console),"httpfail",len(httpfail))
