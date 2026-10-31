import json, re, sys, time
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:18990/"; OUT="/data/artifacts/delphi-evolve-rethink/site-audit/r4"
vp=sys.argv[1]; W,H={"desktop":(1440,1000),"mobile":(390,844)}[vp]
steps=[]; console=[]
def step(sid,desc,**kw): steps.append({"id":sid,"vp":vp,"desc":desc,**kw}); print(sid,flush=True)
def slug(s): return re.sub(r'[^a-zA-Z0-9]+','_',s)[:50].strip('_')
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--use-gl=swiftshader","--enable-unsafe-swiftshader"]); ctx=b.new_context(viewport={"width":W,"height":H},has_touch=(vp=="mobile")); pg=ctx.new_page()
    pg.on("console",lambda m: console.append({"vp":vp,"type":m.type,"text":m.text[:220]}) if m.type in("error","warning") else None)
    pg.on("pageerror",lambda e: console.append({"vp":vp,"type":"pageerror","text":str(e)[:220]}))
    def go(route,wait=2200): pg.goto(BASE+route,wait_until="load",timeout=40000); pg.wait_for_timeout(wait)
    def shot(name,full=False):
        f=f"{OUT}/R4b_{vp}_{slug(name)}.png"
        try: pg.screenshot(path=f,full_page=full); return f
        except Exception: return None
    # docs page: raw markdown + drawer links
    go("#/about/docs",2500)
    h2=pg.evaluate("()=>[...document.querySelectorAll('main h2')].map(h=>h.innerText)")
    raw=[h for h in h2 if re.search(r'\*|`|_{2}|\[.*\]\(',h)]
    links=pg.evaluate("()=>[...new Set([...document.querySelectorAll('main a[href]')].map(a=>a.getAttribute('href')))]")
    step("D1","docs headings with raw markdown",result={"h2_count":len(h2),"raw_markdown_h2":raw,"links":len(links)})
    bad=[]; checked=0
    for h in links:
        if h.startswith("http"): continue
        try:
            go(h,900) if h.startswith("#/") else None
            if "src=" in h:
                t=pg.evaluate("()=>[document.getElementById('drawer').hidden,document.getElementById('dtitle').innerText]")
                if t[0] or 'not available' in t[1]: bad.append((h[:60],t))
            checked+=1
        except Exception as e: bad.append((h[:60],str(e)[:50]))
    step("D2","docs links open (hash/drawer; relative files fetched)",ok=not bad,result={"checked":checked,"bad":bad[:8]})
    go("#/about/docs",1500); rel=[h for h in links if not h.startswith(("#/","http"))]
    rb=[]
    for h in rel[:60]:
        r=pg.request.get(BASE+h.lstrip('/'),timeout=15000); 
        if r.status!=200: rb.append((h[:60],r.status))
    step("D3","docs relative file links",ok=not rb,result={"n":len(rel),"bad":rb[:8]})
    # F1 root-cause injection (DOM only, local)
    go("#/frontier",2500)
    res=pg.evaluate("""()=>{const t=document.querySelector('main table');const w=t.parentElement;const before=[Math.round(t.getBoundingClientRect().width),w.clientWidth];
      const a=t.querySelector('tbody tr td:first-child');const orig=a.innerHTML;a.innerHTML='<a href="#/frontier">problem:ff-aerodynamic-calibration</a>';
      const after=[Math.round(t.getBoundingClientRect().width),w.clientWidth,Math.round(t.querySelector('th').getBoundingClientRect().width),getComputedStyle(a).whiteSpace];return {before,after_with_long_id:after}}""")
    step("F1i","injected 34-char slug into first ID cell (local DOM only)",result=res,screenshot=shot("frontier_injected"))
    # N9 css and mobile knowledge with a long option injected
    go("#/knowledge",3500)
    r=pg.evaluate("""()=>{const s=document.querySelector('main form select');if(!s)return null;const w0=Math.round(s.getBoundingClientRect().width);const o=document.createElement('option');o.textContent='A New Kind of Science, Bioelectricity and other long source names from the live catalog facets';s.appendChild(o);
      const w1=Math.round(s.getBoundingClientRect().width);return {selectW_before:w0,selectW_after_long_option:w1,docW:document.documentElement.scrollWidth,vw:innerWidth,css_maxwidth:getComputedStyle(s).maxWidth}}""")
    step("N9i","injected one long option into the first filter select (local DOM only)",result=r,screenshot=shot("knowledge_injected"))
    # GLB viewer
    go("#/studio/flying-fish?scale=organism",4000)
    v=pg.evaluate("""()=>{const r=document.querySelector('#fish-viewer');if(!r)return {present:false};const c=r.querySelector('canvas');return {present:true,text:r.innerText.replace(/\\s+/g,' ').slice(0,420),canvas:!!c,canvasBox:c?[Math.round(c.getBoundingClientRect().width),Math.round(c.getBoundingClientRect().height)]:null,canvasTab:c?c.tabIndex:null,canvasLabel:c?(c.getAttribute('aria-label')||c.getAttribute('role')):null,buttons:[...r.querySelectorAll('button')].map(b=>b.innerText.slice(0,24)).slice(0,10),details:r.querySelectorAll('table').length}}""")
    step("G1","actual GLB viewer on Studio organism scale",result=v,screenshot=shot("glb_viewer"))
    try:
        c=pg.locator("#fish-viewer canvas").first; c.scroll_into_view_if_needed(); box=c.bounding_box(); pg.mouse.click(box["x"]+box["width"]/2,box["y"]+box["height"]/2) if vp=="desktop" else c.tap(); pg.wait_for_timeout(1200)
        t=pg.evaluate("()=>document.querySelector('#fish-viewer').innerText.replace(/\\s+/g,' ')")
        step("G2","click the GLB canvas centre",result={"detail_after_click":t[:420],"has_provenance_table":bool(re.search(r'(?i)provenance|source|assum',t))},screenshot=shot("glb_click"))
        pg.keyboard.press("Tab"); step("G3","keyboard focus after Tab from canvas",result=pg.evaluate("()=>(document.activeElement.getAttribute('aria-label')||document.activeElement.innerText||document.activeElement.tagName).slice(0,60)"))
    except Exception as e: step("G2","glb interaction",ok=False,error=str(e)[:150])
    b.close()
json.dump({"steps":steps,"console":console},open(f"{OUT}/audit4b_{vp}.json","w"),indent=1,default=str)
print(vp,len(steps))
