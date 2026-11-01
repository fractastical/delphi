import json, re, sys, time, urllib.parse
from playwright.sync_api import sync_playwright
BASE="https://frontier.morphoswarm.ai/"; OUT="/data/artifacts/delphi-evolve-rethink/site-audit"
vp=sys.argv[1]; W,H={"desktop":(1440,1000),"mobile":(390,844)}[vp]
steps=[]; console=[]; httpfail=[]; cur=[""]
def step(sid,desc,**kw): steps.append({"id":sid,"vp":vp,"desc":desc,**kw}); return steps[-1]
def slug(s): return re.sub(r'[^a-zA-Z0-9]+','_',s)[:70].strip('_')
CONTRAST="""()=>{function lum(c){const a=c.map(v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)});return 0.2126*a[0]+0.7152*a[1]+0.0722*a[2]}
 function parse(s){const m=s.match(/rgba?\\(([^)]+)\\)/);if(!m)return null;const p=m[1].split(',').map(x=>parseFloat(x));return {c:p.slice(0,3),a:p.length>3?p[3]:1}}
 function bg(e){let x=e;while(x){const p=parse(getComputedStyle(x).backgroundColor);if(p&&p.a>0.9)return p.c;x=x.parentElement}return [255,255,255]}
 const bad=[];const seen=new Set();for(const e of document.querySelectorAll('main *, header *, footer *, aside *')){if(!e.childNodes.length)continue;
  const t=[...e.childNodes].filter(n=>n.nodeType==3&&n.textContent.trim().length>2).map(n=>n.textContent.trim()).join(' ');if(!t)continue;
  const cs=getComputedStyle(e);if(cs.visibility==='hidden'||cs.display==='none'||e.offsetParent===null)continue;const f=parse(cs.color);if(!f)continue;
  const b=bg(e);const L1=lum(f.c),L2=lum(b);const r=(Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);const size=parseFloat(cs.fontSize);const bold=parseInt(cs.fontWeight)>=700;
  const need=(size>=24||(size>=18.66&&bold))?3:4.5;if(r<need){const k=cs.color+'|'+b.join(',')+'|'+size;if(!seen.has(k)){seen.add(k);bad.push({text:t.slice(0,50),ratio:Math.round(r*100)/100,need,size,color:cs.color,bg:b.join(',')})}}}
 return bad.slice(0,12)}"""
STATS="""()=>{const d=document.documentElement;const main=document.getElementById('main');const txt=main.innerText||'';
 return {h1:(document.querySelector('h1')||{}).innerText,scrollH:d.scrollHeight,overflowX:d.scrollWidth>d.clientWidth+1,len:txt.length,
 rawTeX:(txt.match(/\\\\(frac|sqrt|mathrm|rho|alpha|times|left|right|cdot)\\b|\\$[^$\\n]{2,60}\\$/g)||[]).slice(0,5),katex:main.querySelectorAll('.katex').length,katexErr:main.querySelectorAll('.katex-error').length,
 broken:[...document.images].filter(i=>i.complete&&i.naturalWidth===0).map(i=>i.src.split('/').pop()),noAlt:[...document.images].filter(i=>!i.alt).length,
 wide:[...main.querySelectorAll('*')].filter(e=>e.scrollWidth>e.clientWidth+2&&getComputedStyle(e).overflowX==='visible'&&e.clientWidth>0).length,
 smallTargets:[...document.querySelectorAll('a,button,select,input')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&(r.height<24||r.width<24)&&getComputedStyle(e).visibility!=='hidden'}).length}}"""
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox"]); ctx=b.new_context(viewport={"width":W,"height":H}); pg=ctx.new_page()
    pg.on("console",lambda m: console.append({"vp":vp,"at":cur[0],"type":m.type,"text":m.text[:250]}) if m.type in("error","warning") else None)
    pg.on("pageerror",lambda e: console.append({"vp":vp,"at":cur[0],"type":"pageerror","text":str(e)[:250]}))
    pg.on("response",lambda r: httpfail.append({"vp":vp,"at":cur[0],"url":r.url,"status":r.status}) if r.status>=400 else None)
    def go(route,wait=700):
        cur[0]=route; pg.goto(BASE+route,wait_until="networkidle",timeout=30000); pg.wait_for_timeout(wait)
    def shot(name,full=True):
        f=f"{OUT}/{vp}_{slug(name)}.png"
        try: pg.screenshot(path=f,full_page=full); return f
        except Exception: return None
    def stats(): return pg.evaluate(STATS)
    # S01 top-level + tabs
    tops=["#/frontier","#/knowledge","#/knowledge?tab=claims","#/knowledge?tab=graph","#/knowledge?tab=mission","#/knowledge?tab=catalog","#/engineering","#/simulations","#/evidence",
          "#/work","#/work?tab=specs","#/work?tab=work","#/work?tab=resources","#/work?tab=receipts","#/work?tab=runtime","#/belief","#/search","#/nonexistent"]+[f"#/engineering?scale={s}" for s in("molecular","subcellular","tissue","organ","organism","developmental","ecological")]
    for r in tops:
        try:
            go(r); st=stats(); st["contrast_fail"]=pg.evaluate(CONTRAST); step("S01:"+r,"route loads",route=r,ok=True,stats=st,screenshot=shot(r))
        except Exception as e: step("S01:"+r,"route loads",route=r,ok=False,error=str(e)[:200])
    # S02 knowledge claims: every claim route
    go("#/knowledge?tab=claims"); ids=pg.evaluate("()=>[...new Set([...document.querySelectorAll('a[href^=\"#/knowledge/\"]')].map(a=>a.getAttribute('href')))]")
    step("S02a","claim links enumerated",count=len(ids),ids=ids[:40])
    for r in ids[:40]:
        try:
            go(r); st=stats(); step("S02:"+r,"claim detail",route=r,ok=not(st["overflowX"] or st["katexErr"]),stats=st,screenshot=shot(r) if len(steps)%4==0 else None)
        except Exception as e: step("S02:"+r,"claim detail",route=r,ok=False,error=str(e)[:200])
    # claims filters
    for q in ["#/knowledge?tab=claims&group=Pattern+formation","#/knowledge?tab=claims&cat=question","#/knowledge?tab=claims&q=zzzzzz"]:
        go(q); step("S02f:"+q,"claims filter",route=q,text=pg.evaluate("()=>document.getElementById('main').innerText.slice(0,260)"),ok=True)
    # S03 graph interaction
    go("#/knowledge?tab=graph")
    g=pg.evaluate("()=>({nodes:document.querySelectorAll('svg.graph [data-id],svg.graph g.node,svg.graph circle').length,tab:[...document.querySelectorAll('svg.graph [tabindex]')].length,title:document.querySelectorAll('svg.graph title').length,aria:document.querySelectorAll('svg.graph [aria-label]').length})")
    step("S03a","graph structure and keyboard access",stats=g)
    try:
        node=pg.locator("svg.graph circle, svg.graph g.node").first; before=pg.evaluate("()=>document.getElementById('main').innerText.length")
        node.click(timeout=3000); pg.wait_for_timeout(500); after=pg.evaluate("()=>document.getElementById('main').innerText.length")
        step("S03b","click first graph node",ok=True,url=pg.url,changed=before!=after,screenshot=shot("graph_after_node_click",False))
        edge=pg.locator("svg.graph line, svg.graph path").first; edge.hover(timeout=3000,force=True); pg.wait_for_timeout(300)
        step("S03c","hover first graph edge",ok=True,tooltip=pg.evaluate("()=>[...document.querySelectorAll('.tip,[role=tooltip],svg.graph title')].map(e=>e.textContent.slice(0,80)).slice(0,3)"))
    except Exception as e: step("S03b","graph interaction",ok=False,error=str(e)[:200])
    # S04 frontier
    go("#/frontier")
    try:
        rows=pg.locator("main table tbody tr"); n=rows.count(); rows.first.click(timeout=3000); pg.wait_for_timeout(600)
        step("S04a","click first question row",ok=True,rows=n,url=pg.url,panel=pg.evaluate("()=>(document.querySelector('main aside, main .detail, main .panel:last-child')||{}).innerText?.slice(0,300)"),screenshot=shot("frontier_row_click",False))
    except Exception as e: step("S04a","click first question row",ok=False,error=str(e)[:200])
    for r in ["#/frontier/F001","#/frontier/G1","#/frontier/does-not-exist","#/frontier?lc=actionable","#/frontier?lw=leased","#/frontier?lq=zzzzzz","#/frontier?n=100"]:
        try:
            go(r); st=stats(); step("S04:"+r,"frontier deep link / filter",route=r,ok=True,stats=st,text=pg.evaluate("()=>document.getElementById('main').innerText.replace(/\\s+/g,' ').slice(0,220)"),screenshot=shot(r,False))
        except Exception as e: step("S04:"+r,"frontier",route=r,ok=False,error=str(e)[:200])
    # S05 engineering presets + custom conflicts
    go("#/engineering")
    btns=pg.evaluate("()=>[...document.querySelectorAll('form[data-form=candform] button')].map(b=>b.innerText)")
    res_sel="#main"
    for label in btns[:5]:
        try:
            if label.startswith("Download"): continue
            pg.get_by_role("button",name=label).first.click(timeout=3000); pg.wait_for_timeout(500)
            t=pg.evaluate("()=>document.getElementById('main').innerText"); 
            step("S05:preset:"+label,"candidate preset",ok=True,verdict_words={k:len(re.findall(k,t,re.I)) for k in("feasible","unsat","unknown","infeasible","conflict","violat","not checked")},screenshot=shot("eng_"+label,False))
        except Exception as e: step("S05:preset:"+label,"candidate preset",ok=False,error=str(e)[:200])
    try:
        go("#/engineering"); 
        for name,val in [("wing_loading_min","300"),("speed_max","5"),("mass_min","1")]:
            pg.fill(f"input[name={name}]",val)
        pg.evaluate("()=>document.querySelector('form[data-form=candform] input[name=speed_max]').dispatchEvent(new Event('input',{bubbles:true}))"); pg.wait_for_timeout(700)
        t=pg.evaluate("()=>document.getElementById('main').innerText")
        step("S05:conflict","user constraints wing_loading_min=300, speed_max=5, mass_min=1 (should be unsat)",ok=True,verdict_words={k:len(re.findall(k,t,re.I)) for k in("feasible","unsat","unknown","infeasible","conflict")},snippet=re.sub(r'\s+',' ',t[t.lower().find('conflict')-120:t.lower().find('conflict')+260]) if 'conflict' in t.lower() else None,screenshot=shot("eng_conflict",False))
    except Exception as e: step("S05:conflict","unsat",ok=False,error=str(e)[:200])
    # S06 simulations downloads
    go("#/simulations")
    dl=pg.evaluate("()=>[...document.querySelectorAll('main a[download],main a[href*=\"/artifacts/\"]')].map(a=>a.href)")
    stat=[]
    for u in dl[:30]:
        try: r=pg.request.head(u,timeout=15000); stat.append((u.split('/')[-1],r.status))
        except Exception as e: stat.append((u.split('/')[-1],"ERR"))
    step("S06","simulation download links HEAD",count=len(dl),failing=[s for s in stat if s[1]!=200],total=len(stat))
    # S07 evidence: sources + drawers + artifacts downloads
    go("#/evidence"); srcs=pg.evaluate("()=>[...new Set([...document.querySelectorAll('main a[href*=\"src=\"]')].map(a=>a.getAttribute('href')))]")
    step("S07a","evidence source drawer links",count=len(srcs))
    for h in srcs[:12]:
        try:
            go(h,900); d=pg.evaluate("()=>({hidden:document.getElementById('drawer').hidden,title:document.getElementById('dtitle').innerText,len:document.querySelector('#drawer .dbody').innerText.length,txt:document.querySelector('#drawer .dbody').innerText.slice(0,120)})")
            step("S07:"+h,"source drawer",route=h,ok=(not d["hidden"]) and d["len"]>60 and "not available" not in d["title"],drawer=d,screenshot=shot(h,False) if len(steps)%3==0 else None)
        except Exception as e: step("S07:"+h,"source drawer",route=h,ok=False,error=str(e)[:200])
    try:
        go(srcs[0]); pg.keyboard.press("Escape"); pg.wait_for_timeout(500); step("S07b","Escape closes drawer",ok=pg.evaluate("()=>document.getElementById('drawer').hidden"),url=pg.url,focus=pg.evaluate("()=>document.activeElement.tagName+':'+(document.activeElement.innerText||'').slice(0,30)"))
    except Exception as e: step("S07b","Escape closes drawer",ok=False,error=str(e)[:200])
    go("#/evidence"); dl=pg.evaluate("()=>[...document.querySelectorAll('main a[download],main a.btn[href*=\"/artifacts/\"],main a[href*=\"/artifacts/\"]')].map(a=>a.href)"); dl=list(dict.fromkeys(dl)); stat=[]
    for u in dl[:60]:
        try: r=pg.request.head(u,timeout=15000); stat.append((u.split('/artifacts/')[-1][:60],r.status))
        except Exception: stat.append((u[-50:],"ERR"))
    step("S07c","evidence artifact/download links HEAD",count=len(dl),checked=len(stat),failing=[s for s in stat if s[1]!=200])
    # S09 belief
    go("#/belief"); t0=pg.evaluate("()=>document.getElementById('main').innerText.replace(/\\s+/g,' ').slice(0,500)")
    step("S09a","belief empty state",text=t0,screenshot=shot("belief_empty",False))
    try:
        for i,v in enumerate(["0.3","0.6","","0.9"],1):
            if v: pg.fill(f"input[name=v{i}]",v)
        pg.evaluate("()=>document.querySelector('input[name=v1]').dispatchEvent(new Event('input',{bubbles:true}))"); pg.wait_for_timeout(500)
        step("S09b","belief with partial priors (v3 missing)",text=pg.evaluate("()=>document.getElementById('main').innerText.replace(/\\s+/g,' ').slice(0,700)"),screenshot=shot("belief_partial",False))
    except Exception as e: step("S09b","belief",ok=False,error=str(e)[:200])
    # S10 search
    for q in ["","zzzzxxqq","wing","<script>alert(1)</script>","a"*300]:
        try:
            go("#/search?q="+urllib.parse.quote(q)+"&tab=catalog"); step("S10:"+q[:20],"search query",ok=True,text=pg.evaluate("()=>document.getElementById('main').innerText.replace(/\\s+/g,' ').slice(0,260)"),overflow=stats()["overflowX"],screenshot=shot("search_"+q[:10],False) if q in("zzzzxxqq","wing") else None)
        except Exception as e: step("S10:"+q[:20],"search",ok=False,error=str(e)[:200])
    # S11 keyboard
    go("#/frontier"); seq=[]
    for i in range(14):
        pg.keyboard.press("Tab"); seq.append(pg.evaluate("()=>{const e=document.activeElement;const cs=getComputedStyle(e);return [e.tagName,(e.innerText||e.value||e.getAttribute('aria-label')||'').slice(0,24),cs.outlineStyle+' '+cs.outlineWidth,cs.boxShadow!=='none']}"))
    step("S11","first 14 Tab stops on #/frontier (tag,text,outline,boxshadow)",seq=seq,no_focus_indicator=[s for s in seq if s[2].startswith('none') and not s[3]])
    # S12 back/forward
    go("#/frontier"); pg.evaluate("location.hash='#/knowledge'"); pg.wait_for_timeout(500); pg.evaluate("location.hash='#/engineering'"); pg.wait_for_timeout(500)
    pg.go_back(); pg.wait_for_timeout(500); u1=pg.url; t1=pg.title(); pg.go_back(); pg.wait_for_timeout(500); u2=pg.url; t2=pg.title()
    step("S12","back navigation",urls=[u1,u2],titles=[t1,t2],ok=u1.endswith("#/knowledge") and u2.endswith("#/frontier"))
    # S14 nav
    go("#/frontier"); nav=pg.evaluate("()=>{const n=document.querySelector('header nav');const u=n.querySelector('ul');return {navClientW:n.clientWidth,ulScrollW:u.scrollWidth,cut:u.scrollWidth>n.clientWidth+1,items:[...u.querySelectorAll('a')].map(a=>[a.innerText,Math.round(a.getBoundingClientRect().right)])}}")
    step("S14","header nav fits viewport",stats=nav,ok=not nav["cut"])
    b.close()
json.dump({"steps":steps,"console":console,"httpfail":httpfail,"ts":time.strftime("%F %T %Z")},open(f"{OUT}/audit_{vp}.json","w"),indent=1,default=str)
print(vp,"steps",len(steps),"fail",sum(1 for s in steps if s.get("ok") is False),"console",len(console),"httpfail",len(httpfail))
