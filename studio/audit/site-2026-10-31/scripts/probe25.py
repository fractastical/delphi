import json,re,hashlib,urllib.request,sys
from playwright.sync_api import sync_playwright
BASE="https://frontier.morphoswarm.ai/"; OUT="/data/artifacts/delphi-evolve-rethink/site-audit/r6"
snap=json.loads(urllib.request.urlopen(BASE+"data/snapshot.json",timeout=30).read()); cands=snap["fish3d_viewer"]["candidates"]
# independent GLB hash for each candidate (the file the viewer actually loads)
res=[]
for c in cands:
    base=BASE+c["base"]; row={"id":c["id"]}
    try:
        files=[f for f in snap["fish3d_viewer"]["copied"] if f.startswith(c["id"]+"/") and f.endswith(".glb")]
        row["glb_files"]=files
        for f in files:
            data=urllib.request.urlopen(BASE+"artifacts/fish3d/"+f,timeout=60).read(); h=hashlib.sha256(data).hexdigest(); row.setdefault("sha",{})[f.split('/')[-1]]=[len(data),h[:16]]
            # which json records this hash?
            for j in [x for x in snap["fish3d_viewer"]["copied"] if x.startswith(c["id"]+"/") and x.endswith(".json")]:
                try:
                    t=urllib.request.urlopen(BASE+"artifacts/fish3d/"+j,timeout=30).read().decode()
                    if h in t: row.setdefault("recorded_in",[]).append(j.split('/')[-1])
                except Exception: pass
    except Exception as e: row["error"]=str(e)[:100]
    res.append(row)
print(json.dumps(res,indent=0)[:1800])
with sync_playwright() as p:
    b=p.chromium.launch(args=["--no-sandbox"])
    for vp,(w,h) in {"desktop":(1440,1000),"mobile":(390,844)}.items():
        ctx=b.new_context(viewport={"width":w,"height":h},has_touch=(vp=="mobile")); pg=ctx.new_page(); tap=lambda l,**k:(l.tap(**k) if vp=="mobile" else l.click(**k))
        pg.goto(BASE+"#/frontier",wait_until="load"); pg.wait_for_timeout(2500)
        info=pg.evaluate("""()=>{const n=document.querySelector('header nav');const items=[...n.querySelectorAll('a, summary, button')].filter(e=>e.innerText.trim()).map(a=>({t:a.innerText.trim().slice(0,12),l:Math.round(a.getBoundingClientRect().left),r:Math.round(a.getBoundingClientRect().right),vis:a.getBoundingClientRect().width>0}));
          const s=document.querySelector('.aboutmenu summary, .aboutmenu > button');return {vw:innerWidth,items:items.slice(0,9),wrap:getComputedStyle(n.querySelector('ul')).flexWrap,sum:s?{tag:s.tagName,expanded:s.getAttribute('aria-expanded'),controls:s.getAttribute('aria-controls'),h:Math.round(s.getBoundingClientRect().height)}:null}}""")
        pg.screenshot(path=f"{OUT}/R6P_{vp}_nav_top.png")
        s=pg.locator(".aboutmenu summary, .aboutmenu > button").first; tap(s,force=True); pg.wait_for_timeout(500)
        box=pg.evaluate("""()=>{const u=document.querySelector('.aboutmenu ul');const r=u.getBoundingClientRect();return {l:Math.round(r.left),r:Math.round(r.right),vw:innerWidth,clipped:r.right>innerWidth+1||r.left<-1,items:[...u.querySelectorAll('a')].map(a=>[a.innerText.slice(0,24),Math.round(a.getBoundingClientRect().left),Math.round(a.getBoundingClientRect().right)]),open:document.querySelector('.aboutmenu details')?document.querySelector('.aboutmenu details').open:null,expanded:(document.querySelector('.aboutmenu summary, .aboutmenu > button')||{getAttribute:()=>null}).getAttribute('aria-expanded')}}""")
        pg.screenshot(path=f"{OUT}/R6P_{vp}_about_menu_open.png")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(400)
        aft=pg.evaluate("()=>({open:document.querySelector('.aboutmenu details')?document.querySelector('.aboutmenu details').open:null,expanded:(document.querySelector('.aboutmenu summary, .aboutmenu > button')).getAttribute('aria-expanded'),focus:document.activeElement.tagName+':'+(document.activeElement.innerText||'').slice(0,10)})")
        print(vp,'NAV',json.dumps(info)); print(vp,'MENU',json.dumps(box)); print(vp,'AFTER ESC',json.dumps(aft))
        # N2 context
        pg.goto(BASE+"#/studio/flying-fish?scale=organ",wait_until="load"); pg.wait_for_timeout(2800); pg.locator("input[name=sodium_scale]").fill("0.35"); pg.get_by_role("button",name="Run a preview").first.click(); pg.wait_for_timeout(7500)
        w=re.sub(r'\s+',' ',pg.evaluate("()=>document.querySelector('main form input[name=sodium_scale]').closest('section,.card').innerText")); i=w.find('[object')
        print(vp,'N2 [object] context:',w[max(0,i-100):i+80] if i>=0 else 'none', '| code text:',re.findall(r'code [^·]{0,70}',w)[:1])
        pg.locator("input[name=sodium_scale]").scroll_into_view_if_needed(); pg.screenshot(path=f"{OUT}/R6P_{vp}_widget_run.png")
        ctx.close()
    b.close()
