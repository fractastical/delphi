"""Focused browser checks for the real Studio Annotation module.

Run capped: systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G \
  -p MemorySwapMax=0 -p RuntimeMaxSec=600 python3 -m pytest tests/test_site_annotations.py -q
"""
import functools
import http.server
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture(scope="module")
def base():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "site"))
    handler.log_message = lambda *_: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()


def mounted_page(browser, base, *, authorized=False):
    page = browser.new_page()
    page.goto(base)
    page.add_script_tag(path=str(ROOT / "site/js/annotations.js"))
    page.evaluate("""({ authorized }) => {
      const project = {namespace:"frontier",kind:"Project",id:"fish",version:"a".repeat(64)};
      const member = {namespace:"frontier",kind:"Claim",id:"geometry",version:"b".repeat(64)};
      const oldProject = {namespace:"frontier",kind:"Project",id:"fish",version:"c".repeat(64)};
      const savedRef = {namespace:"frontier",kind:"Annotation",id:"saved-1",version:"d".repeat(64)};
      const priorRef = {namespace:"frontier",kind:"Annotation",id:"prior-1",version:"e".repeat(64)};
      const projectRecord = {namespace:"frontier",kind:"Project",id:"fish",version:project.version,predecessor:oldProject.version,payload:{members:[{ref:member}]}};
      const priorRecord = {namespace:"frontier",kind:"Project",id:"fish",version:oldProject.version,predecessor:null,payload:{members:[]}};
      const memberAnnotation = {kind:"Annotation",id:"saved-1",version:savedRef.version,issuer:"curator",payload:{kind:"comment",body:"<img src=x onerror=alert(1)>",anchor:{record:member}}};
      const priorAnnotation = {kind:"Annotation",id:"prior-1",version:priorRef.version,issuer:"historical-author",payload:{kind:"challenge",body:"Old version challenge",anchor:{record:oldProject}}};
      window.annotationTest = {project,member,oldProject,savedRef,priorRef,proposalCalls:[],identityCalls:0};
      const api = {
        isLive: () => true,
        catalog: async () => ({records:[{ref:project,payload:projectRecord.payload,is_head:true,raw:{record:projectRecord}}]}),
        designContext: async (ref) => ref.version === project.version
          ? {project:{record:projectRecord},members:[{pin:member}],annotations:[{ref:savedRef,record:memberAnnotation,local_status:"proposed"}],pagination:{truncated:false}}
          : {project:{record:priorRecord},members:[],annotations:[{ref:priorRef,record:priorAnnotation,local_status:"imported_unreviewed"}],pagination:{truncated:false}},
        record: async (ref) => ({raw:{record:priorRecord}}),
      };
      if (authorized) {
        api.identity = async () => { window.annotationTest.identityCalls++; return {principal:{actor:"authenticated-actor",operator:"op",roles:["contributor"],namespaces:["frontier"],daily_write_limit:10}}; };
        // A refusal proves the real module sends a proposal only on explicit click; this test adapter never persists.
        api.propose = async (draft,key) => { window.annotationTest.proposalCalls.push({draft,key}); throw new Error("test adapter refused without persistence"); };
      }
      window.DF.api = api;
      window.DF.annotationComposer.mount(document.querySelector("#main"), {
        projectId:"fish",namespace:"frontier",anchorRef:member,
        region:{type:"named_subsystem",name:"fin geometry"},api
      });
    }""", {"authorized": authorized})
    return page


def test_exact_context_prior_versions_and_local_draft_are_separate(browser, base):
    page = mounted_page(browser, base)
    page.wait_for_selector(".annotation-saved-list .annotation-card")
    assert "saved annotations on the current exact version" in page.locator(".annotation-saved").inner_text().lower()
    page.locator(".annotation-prior-version summary").click()
    assert "old version challenge" in page.locator(".annotation-prior-version-list").inner_text().lower()
    assert "not been moved" in page.locator(".annotation-prior-version").inner_text().lower()
    assert page.locator(".annotation-saved-list img").count() == 0
    assert page.locator(".annotation-saved-list").inner_text().find("<img src=x onerror=alert(1)>") >= 0

    page.get_by_label("Comment, question, or challenge").fill("Check exact member anchor")
    page.get_by_role("button", name="Save local draft").click()
    page.wait_for_selector(".local-draft")
    draft = page.evaluate("JSON.parse(Object.entries(localStorage).find(([k]) => k.startsWith('frontier-annotation-composer:'))[1])[0]")
    assert draft["payload"]["anchor"]["record"] == page.evaluate("annotationTest.member")
    assert draft["payload"]["anchor"]["region"] == {"type": "named_subsystem", "name": "fin geometry"}
    assert "local draft, not submitted" in page.locator(".local-draft").inner_text()
    assert page.get_by_role("button", name="Submit this proposal").is_disabled()
    assert page.evaluate("annotationTest.proposalCalls.length") == 0
    page.close()


def test_explicit_submit_derives_issuer_and_retains_failed_local_draft(browser, base):
    page = mounted_page(browser, base, authorized=True)
    page.get_by_label("Comment, question, or challenge").fill("A bounded challenge")
    page.get_by_role("button", name="Save local draft").click()
    page.get_by_role("button", name="Submit this proposal").click()
    page.wait_for_selector("text=test adapter refused without persistence")
    submitted = page.evaluate("annotationTest.proposalCalls[0]")
    assert submitted["draft"]["issuer"] == "authenticated-actor"
    assert submitted["draft"]["namespace"] == "frontier"
    assert submitted["draft"]["payload"]["anchor"]["record"] == page.evaluate("annotationTest.member")
    assert submitted["draft"]["payload"]["anchor"]["region"] == {"type": "named_subsystem", "name": "fin geometry"}
    assert submitted["key"].startswith("annotation-studio-annotation-")
    assert page.evaluate("annotationTest.identityCalls") == 1
    assert page.locator(".local-draft").count() == 1
    assert "local draft, not submitted" in page.locator(".local-draft").inner_text()
    assert "no accepted state is inferred" in page.locator(".annotation-form-status").inner_text().lower()
    page.close()
