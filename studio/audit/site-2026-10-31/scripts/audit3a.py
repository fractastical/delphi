import json, re, sys, time, urllib.request
from playwright.sync_api import sync_playwright
BASE="https://frontier.morphoswarm.ai/"; OUT="/data/artifacts/delphi-evolve-rethink/site-audit/r3"
vp=sys.argv[1]; W,H={"desktop":(1440,1000),"mobile":(390,844)}[vp]
steps=[]; console=[]; httpfail=[]; cur=[""]
def step(sid,desc,**kw): steps.append({"id":sid,"vp":vp,"desc":desc,**kw}); print(sid,flush=True); return steps[-1]
def slug(s): return re.sub(r'[^a-zA-Z0-9]+','_',s)[:55].strip('_')
CONTRAST=open('/tmp/claude-1000/-data-worktrees-delphi-evolve-rethink-critic/45bfe973-0b4e-4c5b-9d70-43d8c4aa8801/scratchpad/audit.py').read().split('CONTRAST="""')[1].split('"""')[0]
BAD=re.compile(r"\[object |undefined|\bNaN\b|\bnull\b|\{\{|\}\}|Infinity|\bTODO\b|%[0-9A-F]{2}")
def T(pg,n=100000): return pg.evaluate("()=>document.getElementById('main').innerText")[:n]
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--autoplay-policy=no-user-gesture-required"]); ctx=b.new_context(viewport={"width":W,"height":H}); pg=ctx.new_page()
    pg.on("console",lambda m: console.append({"vp":vp,"at":cur[0],"type":m.type,"text":m.text[:200]}) if m.type in("error","warning") else None)
    pg.on("pageerror",lambda e: console.append({"vp":vp,"at":cur[0],"type":"pageerror","text":str(e)[:200]}))
    pg.on("response",lambda r: httpfail.append({"vp":vp,"at":cur[0],"url":r.url[-80:],"status":r.status}) if r.status>=400 else None)
    def go(route,wait=1800):
        cur[0]=route; pg.goto(BASE+route,wait_until="load",timeout=40000); pg.wait_for_timeout(wait)
    def shot(name,full=False):
        f=f"{OUT}/R3_{vp}_{slug(name)}.png"
        try: pg.screenshot(path=f,full_page=full); return f
        except Exception: return None
    # A1 frontier table
    go("#/frontier",3000)
    g=pg.evaluate("""()=>{const t=document.querySelector('main table');const w=t.parentElement;const wr=w.getBoundingClientRect();
      const ths=[...t.querySelectorAll('th')].map(th=>[th.innerText,Math.round(th.getBoundingClientRect().width),th.getBoundingClientRect().right<=wr.right+1]);
      const tr=t.querySelector('tbody tr');const cells=[...tr.querySelectorAll('td')].map(td=>({txt:td.innerText.slice(0,30),w:Math.round(td.getBoundingClientRect().width),visible:td.getBoundingClientRect().right<=wr.right+1&&td.getBoundingClientRect().left>=wr.left-1}));
      return {tableW:Math.round(t.getBoundingClientRect().width),wrapW:w.clientWidth,scrollW:w.scrollWidth,ths,cells,rowH:Math.round(tr.getBoundingClientRect().height),rows:t.querySelectorAll('tbody tr').length,
        layout:getComputedStyle(t).tableLayout,panel:(()=>{const e=[...document.querySelectorAll('main *')].find(x=>/LIVE LEASE HOLDER/.test(x.innerText||'')&&x.children.length>2&&x.getBoundingClientRect().width<700);return e?{w:Math.round(e.getBoundingClientRect().width),pos:getComputedStyle(e).position}:null})()}}""")
    colsvis=sum(1 for c in g["cells"] if c["visible"]); 
    step("A1","F-1 frontier table geometry",ok=g["tableW"]<=g["wrapW"]+2 or colsvis>=3,result=g|{"visible_cell_count":colsvis},screenshot=shot("frontier_table"))
    # row select
    try:
        pg.locator("main table tbody tr").nth(3).locator("td").nth(1).click(timeout=3000,force=True); pg.wait_for_timeout(800); sel=pg.url[-70:]
    except Exception as e: sel="ERR "+str(e)[:80]
    step("A1b","row click selects",result=sel,screenshot=shot("frontier_row_selected"))
    for r in ["#/frontier?live=zzz-unknown","#/frontier/zzz-unknown"]:
        go(r,2500); t=T(pg); step("A1c:"+r,"unknown id notice",result={"notice":re.findall(r'(?i)[^.]{0,80}(?:not found|no such|not visible|unknown (?:id|question)|could not find)[^.]{0,80}',t)[:2]},screenshot=shot("frontier_unknown"))
    # A2 nav
    go("#/frontier",1500); nav=pg.evaluate("()=>{const n=document.querySelector('header nav');const u=n.querySelector('ul');const links=[...u.querySelectorAll('a')].map(a=>({t:a.innerText,r:Math.round(a.getBoundingClientRect().right),l:Math.round(a.getBoundingClientRect().left)}));return {navW:n.clientWidth,navRight:Math.round(n.getBoundingClientRect().right),ulW:u.scrollWidth,links,vw:innerWidth,wrap:getComputedStyle(u).flexWrap,ox:getComputedStyle(n).overflowX}}")
    cut=[l for l in nav["links"] if l["r"]>nav["navRight"]+1 or l["r"]>nav["vw"]]
    step("A2","M-1 header nav",ok=not cut,result=nav|{"cut_items":cut},screenshot=shot("nav_top"))
    # A3 knowledge timing
    t0=time.time(); go("#/knowledge",100); first=None
    for i in range(80):
        n=pg.evaluate("()=>document.querySelectorAll('main a[href^=\"#/entity\"],main a[href*=\"#/knowledge/\"]').length")
        if n>0: first=round(time.time()-t0,1); break
        pg.wait_for_timeout(250)
    step("A3","N-1 knowledge first cards",ok=first is not None and first<5,result={"seconds_to_first_link":first,"text_head":re.sub(r'\s+',' ',T(pg,300))},screenshot=shot("knowledge_loaded"))
    # A7 downloads
    snap=json.loads(urllib.request.urlopen(BASE+"data/snapshot.json",timeout=30).read()); res=[]
    for u in [d["href"] for d in snap.get("documents",[])]+["data/results/designs.csv"]:
        try: st=urllib.request.urlopen(BASE+u,timeout=20).status
        except Exception as e: st=getattr(e,'code',str(e)[:20])
        res.append((u[-50:],st))
    step("A7","documents + designs.csv GET",ok=all(s==200 for _,s in res),result={"n":len(res),"non200":[r for r in res if r[1]!=200]})
    # A6 sim widget
    go("#/studio/flying-fish?scale=organ",2500)
    pg.locator("input[name=sodium_scale]").fill("-5"); pg.get_by_role("button",name="Run a preview").first.click(); pg.wait_for_timeout(2500)
    w=re.sub(r'\s+',' ',pg.evaluate("()=>document.querySelector('main form input[name=sodium_scale]').closest('section,.card').innerText"))
    err_ctx=w[w.find('nothing is stored'):][:220]
    pg.locator("input[name=sodium_scale]").fill("0.35"); pg.get_by_role("button",name="Run a preview").first.click(); pg.wait_for_timeout(7000)
    w2=re.sub(r'\s+',' ',pg.evaluate("()=>document.querySelector('main form input[name=sodium_scale]').closest('section,.card').innerText"))
    step("A4","N-2 [object Object] in preview",ok=("[object" not in err_ctx and "[object" not in w2),result={"error_text":err_ctx,"success_has_object":"[object" in w2,"code_text":re.findall(r'code [^·]{0,60}',w2)[:2]},screenshot=shot("widget_error"))
    # A5 search
    go("#/search?q=zzzzxxqq&tab=record",4000); t=T(pg,5000)
    step("A5","N-3 gibberish search",result={"has_no_match_note":bool(re.search(r'(?i)no (literal|lexical|exact) match|weak|low similarity|nothing matches|no record matches',t)),"raw_json_banner":bool(re.search(r'\{"dimensions"',t)),"first_result":re.sub(r'\s+',' ',t[t.find('Ranked'):][:260])},screenshot=shot("search_gibberish"))
    # A6 graph readability
    go("#/search?q=wing&tab=record",3500)
    try:
        pg.locator("main a[href^='#/entity']").first.click(timeout=4000); pg.wait_for_timeout(2500); pg.locator("main a[href^='#/graph']").first.click(timeout=4000); pg.wait_for_timeout(3000)
        gr=pg.evaluate("""()=>{const svg=document.querySelector('main svg');if(!svg)return null;const bg=getComputedStyle(svg.parentElement).backgroundColor;const labels=[...svg.querySelectorAll('text')].map(t=>({txt:(t.textContent||'').slice(0,28),fill:getComputedStyle(t).fill,op:getComputedStyle(t).opacity,size:getComputedStyle(t).fontSize}));
          const cav=[...document.querySelectorAll('main .note,main .banner,main p')].map(e=>e.innerText.length).sort((a,b)=>b-a)[0];return {bg,labels:labels.slice(0,6),nodes:svg.querySelectorAll('circle').length,edges:svg.querySelectorAll('line,path').length,longestParagraph:cav}}""")
        step("A6","N-4 graph readability (search->entity->graph)",result=gr,screenshot=shot("graph_from_entity"))
    except Exception as e: step("A6","graph",ok=False,error=str(e)[:150])
    # A8 page heights/contrast + malformed text scan over all primary routes
    routes=["#/studio","#/studio/flying-fish","#/frontier","#/knowledge","#/knowledge?tab=graph","#/knowledge?tab=mission","#/knowledge?tab=catalog","#/evidence","#/work","#/work?tab=specs","#/work?tab=work","#/work?tab=resources","#/work?tab=receipts","#/work?tab=runtime","#/engineering","#/simulations","#/belief","#/search","#/home","#/graph"]
    for r in routes:
        try:
            go(r,2500 if "knowledge" not in r else 6000); t=T(pg); st=pg.evaluate("()=>({h:document.documentElement.scrollHeight,ox:document.documentElement.scrollWidth>document.documentElement.clientWidth+1})")
            step("A8:"+r,"height/contrast/malformed",result=st|{"len":len(t),"contrast_n":len(pg.evaluate(CONTRAST)),"bad_strings":sorted(set(m.group(0) for m in BAD.finditer(t)))[:6],"bad_ctx":[t[max(0,m.start()-40):m.end()+30].replace('\n',' ') for m in list(BAD.finditer(t))[:2]]},screenshot=shot(r.replace('#/','')+"_fold"))
        except Exception as e: step("A8:"+r,"route",ok=False,error=str(e)[:120])
    b.close()
json.dump({"steps":steps,"console":console,"httpfail":httpfail,"ts":time.strftime("%F %T %Z")},open(f"{OUT}/audit3a_{vp}.json","w"),indent=1,default=str)
print(vp,"steps",len(steps),"console",len(console),"httpfail",len(httpfail))
