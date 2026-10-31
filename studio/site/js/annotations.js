/* Reusable exact-pin Annotation composer for Studio.
 * Local drafts are not records. Submission is an explicit, bearer-authorized proposal and stays proposed. */
(function () {
  const DF = window.DF = window.DF || {};
  const REF_KINDS = new Set(["Project", "Problem", "Claim", "Evidence", "Assessment", "Action", "Actor", "ResourceOffer", "Interest", "Annotation"]);
  const KINDS = ["comment", "question", "challenge", "proposed_edit"];
  const sameRef = (a, b) => !!a && !!b && ["namespace", "kind", "id", "version"].every((k) => a[k] === b[k]);
  const validRef = (r) => !!r && REF_KINDS.has(r.kind) && typeof r.namespace === "string" && typeof r.id === "string" && /^[0-9a-f]{64}$/.test(r.version || "");
  const refKey = (r) => [r.namespace, r.kind, r.id, r.version].join("\u001f");
  const escRef = (r) => `${r.namespace}/${r.kind}/${r.id}@${r.version}`;
  const makeId = () => `studio-annotation-${crypto.randomUUID()}`;
  const sourceUri = "urn:frontier:studio:annotation-composer";

  function el(name, text, cls) {
    const n = document.createElement(name);
    if (text !== undefined && text !== null) n.textContent = String(text);
    if (cls) n.className = cls;
    return n;
  }
  function label(text, control) {
    const l = el("label", text, "annotation-field"); l.appendChild(control); return l;
  }
  function readDrafts(key) {
    try {
      const rows = JSON.parse(localStorage.getItem(key) || "[]");
      return Array.isArray(rows) ? rows.filter((x) => x && KINDS.includes(x.kind) && x.payload && x.payload.anchor && validRef(x.payload.anchor.record)) : [];
    } catch (_) { return []; }
  }
  function writeDrafts(key, rows) {
    try { localStorage.setItem(key, JSON.stringify(rows)); return true; } catch (_) { return false; }
  }

  function mount(container, options = {}) {
    if (!container || !container.ownerDocument) throw new TypeError("A Studio container element is required");
    const api = options.api || (DF.api || {});
    const projectId = String(options.projectId || "");
    const namespace = String(options.namespace || "");
    let projectRef = null, context = null, anchors = [], selectedAnchor = null, cursor = null, loading = false, destroyed = false;
    let drafts = [], activeDraft = null;
    let key = `frontier-annotation-composer:${namespace}:${projectId}:${options.projectVersion || "head"}`;
    const root = el("section", null, "annotation-composer panel");
    root.setAttribute("aria-labelledby", "annotation-composer-title");
    const title = el("h3", "Annotations and local drafts"); title.id = "annotation-composer-title"; root.appendChild(title);
    const notice = el("p", "Loading exact Project context…", "annotation-notice small"); notice.setAttribute("role", "status"); root.appendChild(notice);
    const saved = el("section", null, "annotation-saved");
    const savedTitle = el("h4", "Saved annotations on the current exact version"); saved.appendChild(savedTitle);
    const savedList = el("div", null, "annotation-saved-list"); saved.appendChild(savedList);
    const more = el("button", "Load more saved annotations", "btn small ghost"); more.type = "button"; more.hidden = true;
    saved.append(savedList, more); root.appendChild(saved);
    const priorVersions = el("section", null, "annotation-prior-versions");
    priorVersions.appendChild(el("h4", "Discussion on earlier Project versions"));
    const priorList = el("div", null, "annotation-prior-list"); priorVersions.appendChild(priorList); root.appendChild(priorVersions);
    const local = el("section", null, "annotation-local");
    const localTitle = el("h4", "Drafts in this browser"); local.appendChild(localTitle);
    const localList = el("div", null, "annotation-local-list"); local.appendChild(localList); root.appendChild(local);

    const form = document.createElement("form"); form.className = "annotation-form"; form.setAttribute("aria-label", "Draft an annotation");
    const formTitle = el("h4", "Draft an annotation"); form.appendChild(formTitle);
    const kind = document.createElement("select"); kind.name = "kind";
    KINDS.forEach((v) => { const o = el("option", v.replaceAll("_", " ")); o.value = v; kind.appendChild(o); });
    form.appendChild(label("Type", kind));
    const anchor = document.createElement("select"); anchor.name = "anchor";
    form.appendChild(label("Exact record version", anchor));
    const region = document.createElement("textarea"); region.name = "region"; region.rows = 2; region.maxLength = 1500;
    region.setAttribute("aria-label", "Typed region anchor JSON; blank means no region");
    form.appendChild(label("Region anchor JSON (optional)", region));
    const reply = document.createElement("select"); reply.name = "reply";
    const noReply = el("option", "New annotation"); noReply.value = ""; reply.appendChild(noReply);
    form.appendChild(label("Reply to an exact saved Annotation (optional)", reply));
    const body = document.createElement("textarea"); body.name = "body"; body.rows = 3; body.required = true; body.maxLength = 12000;
    form.appendChild(label("Comment, question, or challenge", body));
    const editFields = el("fieldset", null, "annotation-edit-fields"); editFields.hidden = true;
    editFields.appendChild(el("legend", "Proposed edit data (proposal only)"));
    const path = document.createElement("input"); path.name = "target_path"; path.maxLength = 200; path.placeholder = "payload.field";
    editFields.appendChild(label("Target path", path));
    const value = document.createElement("textarea"); value.name = "proposed_value"; value.rows = 3; value.maxLength = 8000; value.placeholder = "JSON value";
    editFields.appendChild(label("Proposed JSON value", value));
    const rationale = document.createElement("textarea"); rationale.name = "rationale"; rationale.rows = 2; rationale.maxLength = 12000;
    editFields.appendChild(label("Rationale", rationale)); form.appendChild(editFields);
    const actions = el("div", null, "annotation-actions");
    const save = el("button", "Save local draft", "btn"); save.type = "submit"; actions.appendChild(save);
    const clear = el("button", "Clear form", "btn small ghost"); clear.type = "button"; actions.appendChild(clear); form.appendChild(actions);
    const formStatus = el("p", "", "annotation-form-status small"); formStatus.setAttribute("role", "status"); form.appendChild(formStatus);
    root.appendChild(form);
    container.replaceChildren(root);

    const setNotice = (s, alert = false) => { notice.textContent = s; notice.setAttribute("role", alert ? "alert" : "status"); };
    const setFormStatus = (s, alert = false) => { formStatus.textContent = s; formStatus.setAttribute("role", alert ? "alert" : "status"); };
    const annotationItems = () => context && Array.isArray(context.annotations) ? context.annotations : [];
    const appendAnnotations = (host, items, emptyText) => {
      if (!items.length) host.appendChild(el("p", emptyText, "empty small"));
      for (const item of items) {
        const rec = item.record || {}, payload = rec.payload || {};
        const card = el("article", null, "annotation-card");
        const meta = el("p", `${payload.kind || "annotation"} · ${item.local_status || "status unavailable"} · ${rec.issuer || "issuer unavailable"}`, "small"); card.appendChild(meta);
        const anchorRef = payload.anchor && payload.anchor.record;
        if (validRef(anchorRef)) card.appendChild(el("p", `Anchor: ${escRef(anchorRef)}${payload.anchor.region ? ` · region ${JSON.stringify(payload.anchor.region)}` : ""}`, "small faint"));
        if (item.ref) card.appendChild(el("p", `Annotation ref: ${escRef(item.ref)}`, "small faint"));
        card.appendChild(el("p", payload.body || "(empty body)", "annotation-body"));
        if (payload.reply_to) card.appendChild(el("p", `Reply to: ${escRef(payload.reply_to)}`, "small faint"));
        const disclaimer = el("p", "A proposal or annotation is not acceptance, a vote, an answer, or biological validation.", "small warn"); card.appendChild(disclaimer);
        host.appendChild(card);
      }
    };
    const drawSaved = () => {
      savedList.replaceChildren();
      appendAnnotations(savedList, annotationItems(), "No saved annotations are visible on the Project/member pins read so far.");
      more.hidden = !cursor || loading;
      more.disabled = loading;
    };
    const drawDrafts = () => {
      localList.replaceChildren(); drafts = readDrafts(key);
      if (!drafts.length) { localList.appendChild(el("p", "No local drafts.", "empty small")); return; }
      drafts.forEach((draft, i) => {
        const card = el("article", null, "annotation-card local-draft");
        card.appendChild(el("p", `${draft.kind.replaceAll("_", " ")} · ${draft.submitted ? "submitted as a proposal" : "local draft, not submitted"}`, "small"));
        card.appendChild(el("p", `Anchor: ${escRef(draft.payload.anchor.record)}${draft.payload.anchor.region ? ` · region ${JSON.stringify(draft.payload.anchor.region)}` : ""}`, "small faint"));
        card.appendChild(el("p", draft.payload.body, "annotation-body"));
        if (draft.proposal_ref) card.appendChild(el("p", `Proposal ref: ${escRef(draft.proposal_ref)} · proposed; review state is separate.`, "small"));
        const row = el("div", null, "annotation-actions");
        const edit = el("button", "Edit draft", "btn small ghost"); edit.type = "button"; edit.dataset.edit = String(i); row.appendChild(edit);
        const remove = el("button", draft.submitted ? "Hide local proposal receipt" : "Delete local draft", "btn small ghost"); remove.type = "button"; remove.dataset.delete = String(i); row.appendChild(remove);
        const submit = el("button", draft.submitted ? "Already submitted" : "Submit this proposal", "btn small"); submit.type = "button"; submit.dataset.submit = String(i); submit.disabled = !!draft.submitted || !projectRef || typeof api.identity !== "function" || typeof api.propose !== "function"; row.appendChild(submit);
        card.appendChild(row); localList.appendChild(card);
      });
      if (typeof api.identity !== "function" || typeof api.propose !== "function") {
        localList.appendChild(el("p", "Proposal submission is unavailable until the site connects its bearer-only identity and proposal adapters. Drafts remain local.", "note small"));
      }
    };
    const populateAnchors = () => {
      anchor.replaceChildren(); anchors.forEach((r) => { const o = el("option", `${r.kind} ${r.id} · ${r.version.slice(0, 12)}…`); o.value = refKey(r); anchor.appendChild(o); });
      if (selectedAnchor) anchor.value = refKey(selectedAnchor);
      populateReplies();
    };
    const populateReplies = () => {
      const keep = reply.value; reply.replaceChildren(); const opt = el("option", "New annotation"); opt.value = ""; reply.appendChild(opt);
      for (const item of annotationItems()) {
        const payload = (item.record || {}).payload || {}, ref = item.ref;
        if (!validRef(ref) || ref.kind !== "Annotation" || !sameRef(payload.anchor && payload.anchor.record, selectedAnchor)) continue;
        const o = el("option", `${payload.kind || "annotation"}: ${(payload.body || "").slice(0, 90)} · ${ref.version.slice(0, 12)}…`); o.value = refKey(ref); reply.appendChild(o);
      }
      if ([...reply.options].some((o) => o.value === keep)) reply.value = keep;
    };
    kind.addEventListener("change", () => { editFields.hidden = kind.value !== "proposed_edit"; });
    anchor.addEventListener("change", () => { selectedAnchor = anchors.find((r) => refKey(r) === anchor.value) || null; populateReplies(); });
    clear.addEventListener("click", () => { form.reset(); editFields.hidden = true; activeDraft = null; selectedAnchor = anchors[0] || null; populateAnchors(); region.value = options.region ? JSON.stringify(options.region) : ""; setFormStatus("Form cleared. Nothing was submitted."); });
    form.addEventListener("submit", (event) => {
      event.preventDefault(); setFormStatus("");
      if (!selectedAnchor || !validRef(selectedAnchor)) return setFormStatus("An exact record version is required before saving an Annotation draft.", true);
      const text = body.value.trim(); if (!text) return setFormStatus("Enter annotation text before saving.", true);
      let parsedRegion = null;
      if (region.value.trim()) { try { parsedRegion = JSON.parse(region.value); } catch (_) { return setFormStatus("Region must be valid JSON matching an Anchor region type.", true); }
        if (!parsedRegion || !["named_subsystem", "mesh_part", "image_rect", "equation_symbol", "parameter_path"].includes(parsedRegion.type)) return setFormStatus("Region needs a supported Anchor region type.", true);
      }
      const payload = { kind: kind.value, body: text, anchor: { record: selectedAnchor, ...(parsedRegion ? { region: parsedRegion } : {}) } };
      const replyRef = annotationItems().find((it) => refKey(it.ref) === reply.value && sameRef((it.record || {}).payload?.anchor?.record, selectedAnchor));
      if (reply.value && !replyRef) return setFormStatus("That reply target is not a saved Annotation on this exact record version.", true);
      if (replyRef) payload.reply_to = replyRef.ref;
      if (kind.value === "proposed_edit") {
        let proposed; try { proposed = JSON.parse(value.value); } catch (_) { return setFormStatus("Proposed value must be valid JSON.", true); }
        if (!/^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z0-9_-]+|\[[0-9]{1,4}\]){0,12}$/.test(path.value.trim()) || !rationale.value.trim()) return setFormStatus("A proposed edit needs a valid target path and rationale.", true);
        payload.proposed_edit = { target_path: path.value.trim(), proposed, rationale: rationale.value.trim() };
      }
      const row = { local_id: activeDraft ? activeDraft.local_id : makeId(), kind: kind.value, payload, submitted: false, created_at: new Date().toISOString() };
      if (activeDraft) drafts = drafts.map((d) => d.local_id === activeDraft.local_id ? row : d); else drafts.push(row);
      if (!writeDrafts(key, drafts)) return setFormStatus("Browser storage is unavailable; draft was not saved.", true);
      activeDraft = null; drawDrafts(); setFormStatus("Saved in this browser only. Nothing was submitted; use the separate proposal button when ready.");
      form.reset(); editFields.hidden = true; selectedAnchor = anchors[0] || null; populateAnchors(); region.value = options.region ? JSON.stringify(options.region) : "";
    });
    root.addEventListener("click", async (event) => {
      const editButton = event.target.closest("[data-edit]");
      if (editButton) {
        const d = drafts[Number(editButton.dataset.edit)]; if (!d || d.submitted) return;
        activeDraft = d; selectedAnchor = d.payload.anchor.record; kind.value = d.kind; body.value = d.payload.body;
        region.value = d.payload.anchor.region ? JSON.stringify(d.payload.anchor.region) : "";
        editFields.hidden = d.kind !== "proposed_edit";
        if (d.payload.proposed_edit) { path.value = d.payload.proposed_edit.target_path; value.value = JSON.stringify(d.payload.proposed_edit.proposed, null, 2); rationale.value = d.payload.proposed_edit.rationale; }
        populateAnchors(); if (d.payload.reply_to) reply.value = refKey(d.payload.reply_to); form.scrollIntoView({ block: "nearest" }); return;
      }
      const del = event.target.closest("[data-delete]");
      if (del) { drafts.splice(Number(del.dataset.delete), 1); writeDrafts(key, drafts); drawDrafts(); setFormStatus("Local draft deleted. No server record changed."); return; }
      const submit = event.target.closest("[data-submit]"); if (!submit || submit.disabled) return;
      const draft = drafts[Number(submit.dataset.submit)]; if (!draft || draft.submitted) return;
      submit.disabled = true; submit.textContent = "Checking authorization…"; setFormStatus("");
      try {
        if (typeof api.identity !== "function" || typeof api.propose !== "function") throw new Error("Site proposal adapters are not connected.");
        const identity = await api.identity(); const principal = identity && identity.principal;
        if (!principal || typeof principal.actor !== "string" || !Array.isArray(principal.roles) || !principal.roles.includes("contributor")) throw new Error("A contributor bearer credential is required; no proposal was sent.");
        // Discussion belongs to the selected Project's Store; the exact anchor may be a public imported member from another namespace.
        const targetNamespace = projectRef.namespace;
        if (!Array.isArray(principal.namespaces) || !principal.namespaces.includes(targetNamespace)) throw new Error("The authenticated contributor is not authorized for this namespace; no proposal was sent.");
        const envelope = { namespace: targetNamespace, kind: "Annotation", id: draft.local_id, issuer: principal.actor, source_uri: sourceUri,
          visibility: "public", predecessor: null, payload: draft.payload };
        const result = await api.propose(envelope, `annotation-${draft.local_id}`);
        const record = result && result.record;
        if (!record || record.kind !== "Annotation" || record.issuer !== principal.actor || record.namespace !== targetNamespace || !validRef({ namespace: record.namespace, kind: record.kind, id: record.id, version: record.version })) {
          throw new Error("Proposal response did not contain the expected pinned Annotation record; local draft retained.");
        }
        draft.submitted = true; draft.proposal_ref = { namespace: record.namespace, kind: record.kind, id: record.id, version: record.version };
        writeDrafts(key, drafts); drawDrafts(); setFormStatus("Submitted as a proposal. The record remains proposed until independent review; refreshing saved context…");
        await readContext(false);
      } catch (error) {
        drawDrafts(); setFormStatus(`${error && error.message ? error.message : "Proposal failed."} Draft remains in this browser; no accepted state is inferred.`, true);
      }
    });
    more.addEventListener("click", () => readContext(true));

    async function readContext(nextPage) {
      if (loading || destroyed || typeof api.designContext !== "function" || !projectRef) return;
      loading = true; more.disabled = true;
      try {
        const page = await api.designContext(projectRef, { cursor: nextPage ? cursor : "", limit: 50 });
        context = nextPage && context ? { ...page, annotations: [...(context.annotations || []), ...(page.annotations || [])] } : page;
        cursor = page.pagination && page.pagination.next_cursor || null;
        drawSaved(); populateReplies(); setNotice(`Reading exact Project ${projectRef.id}@${projectRef.version.slice(0, 12)}… and pinned member annotations. ${context.pagination?.truncated ? "More pages are available." : "Current page set is complete."}`);
      } catch (_) {
        if (!context) setNotice("Saved context is unavailable from this node. Exact refs and local drafts are retained; nothing is shown as saved.", true);
        else setNotice("Could not load another page. Previously read saved annotations remain visible.", true);
      } finally { loading = false; drawSaved(); }
    }
    async function readPreviousVersions(currentRecord) {
      priorList.replaceChildren();
      const seen = new Set([projectRef.version]); let record = currentRecord, count = 0;
      for (let depth = 0; depth < 5; depth++) {
        const previous = record && record.predecessor;
        if (!previous) break;
        if (!/^[0-9a-f]{64}$/.test(previous) || seen.has(previous)) {
          priorList.appendChild(el("p", "Earlier Project history stopped at an invalid or repeated predecessor pin.", "small warn")); return;
        }
        seen.add(previous);
        const ref = { namespace: projectRef.namespace, kind: "Project", id: projectRef.id, version: previous };
        try {
          const loaded = await api.record(ref);
          const exactRecord = (loaded.raw && loaded.raw.record) || loaded.record;
          if (!exactRecord || !sameRef({ namespace: exactRecord.namespace, kind: exactRecord.kind, id: exactRecord.id, version: exactRecord.version }, ref)) throw new Error("exact predecessor mismatch");
          const oldContext = await api.designContext(ref, { limit: 50 });
          const details = el("details", null, "annotation-prior-version");
          const summary = el("summary", `Earlier exact Project version ${ref.version.slice(0, 16)}… · ${oldContext.annotations?.length || 0} annotations on pinned Project/member records`);
          details.appendChild(summary);
          details.appendChild(el("p", "These annotations remain attached to this earlier Project version and its exact member pins. They have not been moved to the current version.", "small warn"));
          const list = el("div", null, "annotation-prior-version-list");
          appendAnnotations(list, oldContext.annotations || [], "No saved annotations were returned for this earlier exact version.");
          if (oldContext.pagination?.truncated) list.appendChild(el("p", "This earlier-version context is paginated; only its first bounded page is shown here.", "small faint"));
          details.appendChild(list); priorList.appendChild(details); count++; record = exactRecord;
        } catch (_) {
          priorList.appendChild(el("p", `Could not read prior Project version ${previous.slice(0, 16)}… by exact pin. The current version remains separate.`, "small warn")); return;
        }
      }
      if (!count && !priorList.children.length) priorList.appendChild(el("p", "No earlier Project version is recorded.", "empty small"));
      if (record && record.predecessor && count === 5) priorList.appendChild(el("p", "History display is bounded to five predecessor versions.", "small faint"));
    }
    async function init() {
      drafts = readDrafts(key); drawDrafts();
      if (!projectId || !namespace || typeof api.catalog !== "function" || typeof api.designContext !== "function") {
        setNotice("Exact Project lookup is unavailable. No unpinned Annotation is created; connect the live catalog and design-context adapters.", true); return;
      }
      try {
        if (typeof api.isLive === "function" && !api.isLive()) throw new Error("Live Frontier node unavailable.");
        const result = await api.catalog({ kind: "Project", query: projectId, limit: 50 });
        const candidates = (result.records || []).filter((r) => r.ref && r.ref.kind === "Project" && r.ref.id === projectId && r.ref.namespace === namespace && validRef(r.ref));
        const chosen = candidates.find((r) => r.is_head) || candidates[0];
        if (!chosen) throw new Error("No exact Project record is available.");
        let selectedProject = chosen;
        if (options.projectVersion) {
          const selected = candidates.find((r) => r.ref.version === options.projectVersion);
          if (!selected) throw new Error("Requested Project version is not available in the exact catalog response.");
          selectedProject = selected;
        }
        projectRef = selectedProject.ref;
        key = `frontier-annotation-composer:${namespace}:${projectId}:${projectRef.version}`;
        drafts = readDrafts(key); drawDrafts();
        const initial = options.anchorRef;
        const payload = selectedProject.payload || {};
        const memberRefs = (payload.members || []).map((m) => m.ref).filter(validRef);
        anchors = [projectRef, ...memberRefs];
        if (initial && !anchors.some((r) => sameRef(r, initial))) throw new Error("Requested anchor is not the exact Project pin or an exact member ref.");
        selectedAnchor = initial || projectRef;
        populateAnchors(); region.value = options.region ? JSON.stringify(options.region) : "";
        const pinned = el("p", `${memberRefs.length} exact member pin${memberRefs.length === 1 ? "" : "s"} available. New annotations preserve the selected record version and typed region.`, "small faint");
        form.insertBefore(pinned, formTitle.nextSibling);
        await readContext(false);
        try {
          let record = (selectedProject.raw && selectedProject.raw.record) || selectedProject.record;
          if (!record || record.version !== projectRef.version) {
            const loaded = await api.record(projectRef); record = (loaded.raw && loaded.raw.record) || loaded.record;
          }
          await readPreviousVersions(record);
        } catch (_) { priorList.appendChild(el("p", "Earlier Project version history is unavailable. Current exact-version discussion remains separate.", "small faint")); }
      } catch (_) { setNotice("Could not resolve the exact Project and member context. No anchor was guessed; drafts are not submitted.", true); form.querySelectorAll("input,select,textarea,button[type=submit]").forEach((x) => { x.disabled = true; }); }
    }
    init();
    return { destroy() { destroyed = true; container.replaceChildren(); }, refresh() { return readContext(false); }, element: root };
  }

  DF.annotationComposer = { mount, sameRef, validRef };
})();
