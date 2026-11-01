"""Browser-to-real-Store annotation round trip; run only via scripts/test_postgres.sh."""
import functools
import http.server
import threading
from pathlib import Path

import pytest

from conftest import TOKENS, claim, source
from frontier.design_review import project_design_context
from frontier.models import ref
from frontier.store import Unauthorized

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


def make_project(store, member_ref=None):
    if member_ref is None:
        target = store.submit(TOKENS["alice"], "composer-claim", claim(store, id="composer-target"))["record"]
        member_ref = ref(target)
    project = {
        "namespace": store.namespace, "kind": "Project", "id": "composer-project", "issuer": "alice",
        "source_uri": "urn:frontier:annotation-browser-test", "visibility": "public", "predecessor": None,
        "payload": {
            "title": "Annotation browser protocol fixture", "mission": "Exercise exact annotation pins in software only.",
            "source": source(), "limitations": ["Software fixture only; no scientific finding."],
            "scale_coverage": [{"scale": "organism", "status": "unimplemented", "note": "No organism result."}],
            "members": [{"ref": member_ref, "role": "subsystem", "subsystem": "fin", "scale": "organism",
                         "relationship": "supports", "applicability": "Fixture pin only.", "rationale": "Protocol test."}],
            "requirements": [], "open_questions": [],
        },
    }
    record = store.submit(TOKENS["alice"], "composer-project", project)["record"]
    return record, member_ref


def mount(browser, base, store, project_record, member_ref, token):
    page = browser.new_page()
    page.goto(base)
    page.add_script_tag(path=str(ROOT / "site/js/annotations.js"))
    calls = []
    page.expose_function("composerIdentity", lambda: {"principal": store.principal(token)})
    page.expose_function("composerReadContext", lambda target: project_design_context(store, target, limit=50))

    def submit(draft, key):
        calls.append((draft, key))
        return store.submit(token, key, draft)

    page.expose_function("composerSubmit", submit)
    page.evaluate("""({projectRecord, memberRef}) => {
      const api = {
        isLive: () => true,
        catalog: async () => ({records:[{ref:{namespace:projectRecord.namespace,kind:projectRecord.kind,id:projectRecord.id,version:projectRecord.version},payload:projectRecord.payload,is_head:true,raw:{record:projectRecord}}]}),
        designContext: async (ref) => window.composerReadContext(ref),
        identity: async () => window.composerIdentity(),
        propose: async (draft,key) => window.composerSubmit(draft,key),
      };
      window.DF.api = api;
      window.DF.annotationComposer.mount(document.querySelector("#main"), {projectId:projectRecord.id,namespace:projectRecord.namespace,anchorRef:memberRef,region:{type:"named_subsystem",name:"fin geometry"},api});
    }""", {"projectRecord": project_record, "memberRef": member_ref})
    return page, calls


def test_browser_emitted_annotation_is_validated_submitted_and_read_back(store, browser, base):
    project_record, member_ref = make_project(store)
    page, calls = mount(browser, base, store, project_record, member_ref, TOKENS["alice"])
    page.get_by_label("Comment, question, or challenge").fill("Store-backed exact-pin annotation")
    page.get_by_role("button", name="Save local draft").click()
    page.get_by_role("button", name="Submit this proposal").click()
    page.wait_for_selector(".local-draft:has-text('submitted as a proposal')")
    page.wait_for_selector(".annotation-saved-list .annotation-card:has-text('Store-backed exact-pin annotation')")
    assert len(calls) == 1
    draft, key = calls[0]
    assert draft["issuer"] == "alice" and draft["kind"] == "Annotation"
    assert draft["payload"]["kind"] == "comment"
    assert draft["payload"]["anchor"]["record"] == member_ref
    assert draft["payload"]["anchor"]["region"] == {"type": "named_subsystem", "name": "fin geometry"}
    from frontier.models import Draft
    Draft.model_validate(draft)
    result = store.submit(TOKENS["alice"], key, draft)
    exact = ref(result["record"])
    readback = store.get(exact)
    assert readback["record"]["payload"]["body"] == "Store-backed exact-pin annotation"
    assert readback["local_review"]["status"] == "proposed"
    assert any(item["ref"] == exact for item in store.annotations_for(member_ref)["annotations"])
    assert "proposed" in page.locator(".annotation-saved-list").inner_text().lower()
    page.close()


def test_wrong_bearer_cannot_submit_annotation_from_composer(store, browser, base):
    project_record, member_ref = make_project(store)
    wrong = "unknown-composer-token-not-provisioned"
    page, calls = mount(browser, base, store, project_record, member_ref, wrong)
    page.get_by_label("Comment, question, or challenge").fill("Must remain local")
    page.get_by_role("button", name="Save local draft").click()
    page.get_by_role("button", name="Submit this proposal").click()
    page.wait_for_selector(".annotation-form-status[role=alert]")
    assert "draft remains in this browser" in page.locator(".annotation-form-status").inner_text().lower()
    assert calls == []
    with pytest.raises(Unauthorized):
        store.principal(wrong)
    assert not store.search(kind="Annotation")["results"]
    page.close()


def test_foreign_imported_member_annotation_is_written_in_project_namespace(stores, browser, base):
    origin, project_store = stores("node-a"), stores("node-b")
    target = origin.submit(TOKENS["alice"], "foreign-target", claim(origin, id="foreign-composer-target"))["record"]
    project_store.import_bundle(TOKENS["alice"], "foreign-import", origin.export_bundle([ref(target)]))
    project_record, member_ref = make_project(project_store, ref(target))
    project_only_token = "project-only-composer-contributor-token"
    project_store.provision(project_only_token, "studio-contributor", "studio-operator", ["contributor"],
                            [project_store.namespace], 20)

    page, calls = mount(browser, base, project_store, project_record, member_ref, project_only_token)
    page.get_by_label("Comment, question, or challenge").fill("Cross-namespace member remains exactly pinned")
    page.get_by_role("button", name="Save local draft").click()
    page.get_by_role("button", name="Submit this proposal").click()
    page.wait_for_selector(".local-draft:has-text('submitted as a proposal')")
    assert len(calls) == 1
    draft, key = calls[0]
    assert draft["namespace"] == project_record["namespace"] == project_store.namespace
    assert draft["namespace"] != member_ref["namespace"]
    assert draft["issuer"] == "studio-contributor"
    assert draft["payload"]["anchor"]["record"] == member_ref
    result = project_store.submit(project_only_token, key, draft)  # same idempotency key returns the real write
    exact = ref(result["record"])
    assert project_store.get(exact)["record"]["payload"]["body"] == "Cross-namespace member remains exactly pinned"
    assert any(item["ref"] == exact for item in project_store.annotations_for(member_ref)["annotations"])
    page.close()
