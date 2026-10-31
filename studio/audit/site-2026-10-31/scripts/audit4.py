import json, re, sys, time
from playwright.sync_api import sync_playwright
BASE="http://127.0.0.1:18990/"; OUT="/data/artifacts/delphi-evolve-rethink/site-audit/r4"
vp=sys.argv[1]; W,H={"desktop":(1440,1000),"mobile":(390,844)}[vp]
steps=[]; console=[]; httpfail=[]; cur=[""]
def step(sid,desc,**kw): steps.append({"id":sid,"vp":vp,"desc":desc,**kw}); print(sid,flush=True)
def slug(s): return re.sub(r'[^a-zA-Z0-9]+','_',s)[:55].strip('_')
CONTRAST=open('/tmp/claude-1000/-data-worktrees-delphi-evolve-rethink-critic/45bfe973-0b4e-4c5b-9d70-43d8c4aa8801/scratchpad/audit.py').read().split('CONTRAST="""')[1].split('"""')[0]
BAD=re.compile(r"\[object |undefined|\bNaN\b|\{\{|\}\}|Infinity")
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox","--use-gl=swiftshader","--enable-unsafe-swiftshader"]); ctx=b.new_context(viewport={"width":W,"height":H},has_touch=(vp=="mobile")); pg=ctx.new_page()
    pg.on("console",lambda m: console.append({"vp":vp,"at":cur[0],"type":m.type,"text":m.text[:220]}) if m.type in("error","warning") else None)
    pg.on("pageerror",lambda e: console.append({"vp":vp,"at":cur[0],"type":"pageerror","text":str(e)[:220]}))
    pg.on("response",lambda r: httpfail.append({"vp":vp,"at":cur[0],"url":r.url[-80:],"status":r.status}) if r.status>=400 else None)
    def go(route,wait=2200):
        cur[0]=route; pg.goto(BASE+route,wait_until="load",timeout=40000); pg.wait_for_timeout(wait)
    def shot(name,full=True):
        f=f"{OUT}/R4_{vp}_{slug(name)}.png"
        try: pg.screenshot(path=f,full_page=full); return f
        except Exception: return None
    def T(n=100000): return re.sub(r'\s+',' ',pg.evaluate("()=>document.getElementById('main').innerText"))[:n]
    # About 5 routes
    for r in ["#/about","#/about/team","#/about/docs","#/about/inspirations","#/generative"]:
        try:
            go(r); t=T(); st=pg.evaluate("""()=>{const d=document.documentElement;const main=document.getElementById('main');const hs=[...main.querySelectorAll('h1,h2,h3')].map(h=>[h.tagName,h.innerText.slice(0,40)]);
              const imgs=[...document.images];const links=[...main.querySelectorAll('a[href]')].map(a=>a.getAttribute('href'));
              return {h:d.scrollHeight,ox:d.scrollWidth>d.clientWidth+1,h1:main.querySelectorAll('h1').length,hs:hs.slice(0,10),brokenImgs:imgs.filter(i=>i.complete&&i.naturalWidth===0).map(i=>i.src.slice(-40)),noAlt:imgs.filter(i=>!i.alt).length,nLinks:links.length,ext:links.filter(h=>/^https?:/.test(h)).length,
              extNoRel:[...main.querySelectorAll('a[target=_blank]')].filter(a=>!/noopener/.test(a.rel)).length,title:document.title,lang:d.lang,landmarks:[...document.querySelectorAll('header,nav,main,footer,aside')].map(e=>e.tagName).join(','),
              wide:[...main.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>innerWidth+2&&e.getBoundingClientRect().width>0).slice(0,4).map(e=>[e.tagName,e.className.toString().slice(0,25),Math.round(e.getBoundingClientRect().right)])}}""")
            step("AB:"+r,"about route",result=st|{"len":len(t),"head":t[:220],"bad":sorted(set(m.group(0) for m in BAD.finditer(t))),"notfound":bool(re.search(r'Not found|delivered by a module',t)),"contrast_n":len(pg.evaluate(CONTRAST)),"contrast":pg.evaluate(CONTRAST)[:3]},screenshot=shot(r.replace('#/','')))
        except Exception as e: step("AB:"+r,"about route",ok=False,error=str(e)[:150])
    # internal link check on about pages: collect hash links and fetch local targets
    go("#/about"); links=pg.evaluate("()=>[...new Set([...document.querySelectorAll('main a[href]')].map(a=>a.getAttribute('href')))]")
    bad=[]
    for h in links:
        if h.startswith("#/"):
            try:
                go(h,1200); t=T(300); 
                if re.search(r'Not found|could not be drawn|delivered by a module',t): bad.append((h,t[:80]))
            except Exception as e: bad.append((h,str(e)[:60]))
        elif h.startswith(("http","mailto")): pass
        else:
            try:
                r=pg.request.get(BASE+h.lstrip('/'),timeout=15000); 
                if r.status!=200: bad.append((h,r.status))
            except Exception as e: bad.append((h,'ERR'))
    step("AB:links","about links resolve (hash + relative; external not fetched)",ok=not bad,result={"n":len(links),"external":sum(1 for h in links if h.startswith('http')),"bad":bad[:10]})
    # global About menu accessibility
    go("#/frontier",1500)
    menu=pg.evaluate("""()=>{const d=document.querySelector('.aboutmenu details');const s=d.querySelector('summary');const r=s.getBoundingClientRect();const u=d.querySelector('ul');
      return {role:s.getAttribute('role'),aria:s.getAttribute('aria-expanded'),ariaCtl:s.getAttribute('aria-controls'),summaryBox:[Math.round(r.left),Math.round(r.right),Math.round(r.width),Math.round(r.height)],tabindex:s.tabIndex,ulLabel:u.getAttribute('aria-label'),
      nav:(()=>{const n=document.querySelector('header nav');const links=[...n.querySelectorAll('a,summary')].map(a=>({t:a.innerText,r:Math.round(a.getBoundingClientRect().right),w:Math.round(a.getBoundingClientRect().width),h:Math.round(a.getBoundingClientRect().height)}));return {navRight:Math.round(n.getBoundingClientRect().right),vw:innerWidth,items:links}})()}}""")
    step("AM0","About menu structure",result=menu,screenshot=shot("nav_closed",False))
    def f():
        s=pg.locator(".aboutmenu summary"); s.focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(300); open1=pg.evaluate("()=>document.querySelector('.aboutmenu details').open")
        box=pg.evaluate("()=>{const u=document.querySelector('.aboutmenu ul');const r=u.getBoundingClientRect();return [Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom),innerWidth,getComputedStyle(u).position]}")
        shot("about_menu_open",False)
        pg.keyboard.press("Tab"); foc=pg.evaluate("()=>(document.activeElement.innerText||'').slice(0,30)+'|'+document.activeElement.tagName")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300); open2=pg.evaluate("()=>document.querySelector('.aboutmenu details').open")
        pg.locator(".aboutmenu summary").click(); pg.wait_for_timeout(200); pg.mouse.click(5,H-5); pg.wait_for_timeout(300); open3=pg.evaluate("()=>document.querySelector('.aboutmenu details').open")
        pg.locator(".aboutmenu summary").click(); pg.wait_for_timeout(200); pg.locator(".aboutmenu a").first.click(); pg.wait_for_timeout(1200); open4=pg.evaluate("()=>document.querySelector('.aboutmenu details').open")
        step("AM1","About menu keyboard/pointer behaviour",result={"opens_on_Enter":open1,"menu_box_l_t_r_b_vw_pos":box,"focus_after_Tab":foc,"closes_on_Escape":not open2,"closes_on_outside_click":not open3,"closes_after_choosing_link":not open4,"url_after_choice":pg.url[-30:]})
    try: f()
    except Exception as e: step("AM1","About menu behaviour",ok=False,error=str(e)[:160])
    # System link reachable + hit area
    go("#/frontier",1500)
    sysl=pg.evaluate("()=>{const a=[...document.querySelectorAll('header nav a')].find(x=>x.innerText==='System');const r=a.getBoundingClientRect();return {right:Math.round(r.right),w:Math.round(r.width),h:Math.round(r.height),vw:innerWidth,visibleWithoutScroll:r.right<=innerWidth}}")
    step("AM2","System link position/target size",ok=sysl["visibleWithoutScroll"],result=sysl,screenshot=shot("nav_system",False))
    if vp=="mobile":
        go("#/about",1500); pg.locator("header nav > ul").first.evaluate("u=>u.scrollLeft=u.scrollWidth"); pg.wait_for_timeout(300)
        step("AM3","nav scrolled fully right on phone",result=pg.evaluate("()=>[...document.querySelectorAll('header nav a,header nav summary')].map(a=>[a.innerText,Math.round(a.getBoundingClientRect().left),Math.round(a.getBoundingClientRect().right)])"),screenshot=shot("nav_scrolled_right",False))
        try:
            pg.locator(".aboutmenu summary").tap(); pg.wait_for_timeout(400)
            step("AM4","tap About on phone",result=pg.evaluate("()=>{const u=document.querySelector('.aboutmenu ul');const r=u.getBoundingClientRect();return {open:document.querySelector('.aboutmenu details').open,box:[Math.round(r.left),Math.round(r.top),Math.round(r.right),Math.round(r.bottom)],vw:innerWidth,clippedRight:r.right>innerWidth,clippedLeft:r.left<0,items:[...u.querySelectorAll('a')].map(a=>[a.innerText.slice(0,28),Math.round(a.getBoundingClientRect().height)])}}"),screenshot=shot("about_menu_open_phone",False))
        except Exception as e: step("AM4","tap About",ok=False,error=str(e)[:150])
    # Frontier table / Knowledge overflow / Work raw JSON in local (snapshot) mode
    go("#/frontier",2500); step("F1","frontier table (local snapshot mode)",result=pg.evaluate("()=>{const t=document.querySelector('main table');if(!t)return {table:false,mode:(document.querySelector('.mode')||{}).innerText};const w=t.parentElement;return {table:true,tableW:Math.round(t.getBoundingClientRect().width),wrapW:w.clientWidth,idW:Math.round(t.querySelector('th').getBoundingClientRect().width),mode:(document.querySelector('.mode')||{}).innerText,rows:t.querySelectorAll('tbody tr').length}}"),screenshot=shot("frontier_local",False))
    go("#/knowledge",3500); step("N9","knowledge page width",result=pg.evaluate("()=>({docW:document.documentElement.scrollWidth,vw:innerWidth,over:[...document.querySelectorAll('main form *')].filter(e=>e.getBoundingClientRect().right>innerWidth+2).slice(0,3).map(e=>[e.tagName,Math.round(e.getBoundingClientRect().right)])})"),screenshot=shot("knowledge_local",False))
    go("#/work?tab=work",3000); step("N11","work tab raw json",result=pg.evaluate("()=>({pre:[...document.querySelectorAll('main pre')].map(p=>p.innerText.length),mode:(document.querySelector('.mode')||{}).innerText,h:document.documentElement.scrollHeight})"))
    b.close()
json.dump({"steps":steps,"console":console,"httpfail":httpfail,"ts":time.strftime("%F %T %Z")},open(f"{OUT}/audit4_{vp}.json","w"),indent=1,default=str)
print(vp,"steps",len(steps),"console",len(console),"httpfail",len(httpfail))
