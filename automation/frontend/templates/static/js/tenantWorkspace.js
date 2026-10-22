const esc = (value) => String(value ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

function getCookie(name) {
  const row = document.cookie.split('; ').find(x => x.startsWith(`${name}=`));
  return row ? decodeURIComponent(row.split('=').slice(1).join('=')) : '';
}

function statusBadge(status) {
  const key = status?.key || 'active';
  const label = status?.label || 'Active';
  return `<span class="customer-status-badge status-${esc(key)}">${esc(label)}</span>`;
}

function setModalOpen(modal, open) {
  if (!modal) return;
  modal.classList.toggle('hidden', !open);
  modal.classList.toggle('open', open);
  document.body.classList.toggle('mg-modal-open', open);
}

export function initTenantWorkspace() {
  const root = document.getElementById('tenantWorkspace');
  if (!root || root.dataset.initialized === '1') return;
  root.dataset.initialized = '1';

  const el = {
    search: document.getElementById('customerExplorerSearch'),
    sites: document.getElementById('customerExplorerSites'),
    empty: document.getElementById('customerWorkspaceEmpty'),
    content: document.getElementById('customerWorkspaceContent'),
    name: document.getElementById('customerWorkspaceName'),
    status: document.getElementById('customerWorkspaceStatus'),
    context: document.getElementById('customerWorkspaceSiteContext'),
    edit: document.getElementById('customerWorkspaceEdit'),
    locations: document.getElementById('customerLocationsBody'),
    authorized: document.getElementById('customerAuthorizedBody'),
    additionalMailing: document.getElementById('customerAdditionalMailingBody'),
    support: document.getElementById('customerSupportBody'),
    contractor: document.getElementById('customerContractorBody'),
    visitor: document.getElementById('customerVisitorBody'),
    associationForm: document.getElementById('associationForm'),
    associationRack: document.getElementById('associationRack'),
    metricLocations: document.getElementById('metricLocations'),
    metricAuthorized: document.getElementById('metricAuthorized'),
    metricSupport: document.getElementById('metricSupport'),
    metricValidity: document.getElementById('metricValidity'),
    add: document.getElementById('tenantWorkspaceAddBtn'),
    importBtn: document.getElementById('tenantWorkspaceImportBtn'),
    csvModal: document.getElementById('customerCsvModal'),
    csvClose: document.getElementById('customerCsvClose'),
    csvCancel: document.getElementById('customerCsvCancel'),
    csvFile: document.getElementById('customerCsvFile'),
    csvUpload: document.getElementById('customerCsvUpload'),
    csvResult: document.getElementById('customerCsvResult'),
    addSupport: document.getElementById('supportGroupAddBtn'),
    supportImportBtn: document.getElementById('supportGroupImportBtn'),
    supportCsvModal: document.getElementById('supportCsvModal'),
    supportCsvClose: document.getElementById('supportCsvClose'),
    supportCsvCancel: document.getElementById('supportCsvCancel'),
    supportCsvFile: document.getElementById('supportCsvFile'),
    supportCsvUpload: document.getElementById('supportCsvUpload'),
    supportCsvResult: document.getElementById('supportCsvResult'),
    form: document.getElementById('supportGroupForm'),
    supportRack: document.getElementById('supportRack'),
  };

  const ACCORDION_KEY = 'mailgenixTenantSiteAccordionV194';
  const savedAccordion = (() => { try { return JSON.parse(localStorage.getItem(ACCORDION_KEY) || '{}'); } catch (_) { return {}; } })();
  const state = { explorer: null, detail: null, customerId: null, site: '', query: '', collapsedSites: savedAccordion };

  function persistAccordion() {
    try { localStorage.setItem(ACCORDION_KEY, JSON.stringify(state.collapsedSites)); } catch (_) {}
  }

  async function loadExplorer() {
    const res = await fetch('/api/customers/explorer/', {headers:{Accept:'application/json'}});
    if (!res.ok) throw new Error('Failed to load customers');
    state.explorer = await res.json();
    renderExplorer();
  }

  function renderExplorer() {
    const q = state.query.trim().toLowerCase();
    const html = (state.explorer?.sites || []).map(site => {
      const customers = site.customers.filter(c => !q || c.name.toLowerCase().includes(q));
      if (!customers.length) return '';
      const collapsed = q ? false : !!state.collapsedSites[site.name];
      const rows = customers.map(c => {
        const active = state.customerId === c.id && state.site === site.name;
        return `<button type="button" class="customer-list-item ${active?'active':''}" data-customer-id="${c.id}" data-site="${esc(site.name)}">
          <span class="status-dot status-${esc(c.status?.key || 'active')}"></span>
          <span class="customer-list-copy"><strong>${esc(c.name)}</strong><small>${c.authorized_count || 0} AR · ${c.support_count || 0} SG</small></span>
          ${c.status?.key !== 'active' ? `<span class="customer-list-status-text status-text-${esc(c.status?.key)}">${esc(c.status.label)}</span>` : ''}
        </button>`;
      }).join('');
      return `<div class="customer-site-group ${collapsed?'collapsed':''}">
        <button type="button" class="customer-site-heading customer-site-toggle" data-site-toggle="${esc(site.name)}" aria-expanded="${collapsed?'false':'true'}">
          <span class="customer-site-heading-main"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="m6.5 8 3.5 3.5L13.5 8" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg><strong>${esc(site.name)}</strong></span>
          <small>${customers.length} Customers</small>
        </button>
        <div class="customer-site-items" ${collapsed?'hidden':''}>${rows}</div>
      </div>`;
    }).join('');
    el.sites.innerHTML = html || '<div class="customer-explorer-loading">No customer found.</div>';
  }

  async function loadDetail() {
    if (!state.customerId) return;
    const url = `/api/customers/${state.customerId}/workspace/?site=${encodeURIComponent(state.site)}`;
    const res = await fetch(url, {headers:{Accept:'application/json'}});
    if (!res.ok) throw new Error('Failed to load customer detail');
    state.detail = await res.json();
    renderDetail();
  }

  function renderDetail() {
    const d = state.detail;
    if (!d) return;
    el.empty.classList.add('hidden');
    el.content.classList.remove('hidden');
    el.name.textContent = d.customer.name;
    if (el.status) {
      el.status.outerHTML = statusBadge(d.customer.status).replace('<span ', '<span id="customerWorkspaceStatus" ');
      el.status = document.getElementById('customerWorkspaceStatus');
    }
    el.context.textContent = state.site ? `${state.site} · Site view` : 'All registered locations';
    el.metricLocations.textContent = d.locations.length;
    el.metricAuthorized.textContent = d.authorized_persons.length;
    el.metricSupport.textContent = d.support_groups.length;
    el.metricValidity.textContent = d.customer.status?.next_date || '-';
    if (el.edit) el.edit.href = `/tenants/add/?mode=edit&customer_id=${d.customer.id}`;

    el.locations.innerHTML = d.locations.map(r => `<tr><td><strong>${esc(r.site)}</strong></td><td>${esc(r.floor)}</td><td>${esc(r.rack)}</td><td>${esc(r.description || '-')}</td></tr>`).join('') || '<tr><td colspan="4" class="empty-table-cell">No location registered.</td></tr>';

    el.authorized.innerHTML = d.authorized_persons.map(a =>
      `<tr><td><strong>${esc(a.name || '-')}</strong></td><td>${esc(a.email || '-')}</td><td>${esc(a.phone || '-')}</td><td>${esc(a.due_date || '-')}</td><td>${statusBadge(a.status)}</td></tr>`
    ).join('') || '<tr><td colspan="5" class="empty-table-cell">No authorized person registered.</td></tr>';

    renderAdditionalMailing();
    renderSupport();
    renderAssociations();
    fillRackOptions();
  }

  function renderAdditionalMailing() {
    if (!el.additionalMailing) return;
    const items = state.detail?.additional_mailing_lists || [];
    el.additionalMailing.innerHTML = items.map((email, idx) => `<tr><td>${idx+1}</td><td><strong>${esc(email)}</strong></td><td><span class="mailing-list-chip">Specific: CC</span> <span class="mailing-list-chip">Bulk: BCC</span></td></tr>`).join('') || `<tr><td colspan="3" class="empty-table-cell">No additional mailing list registered.</td></tr>`;
  }

  function renderSupport() {
    const canManage = window.CUSTOMER_WORKSPACE_CAN_MANAGE_SUPPORT !== false;
    const rows = state.detail?.support_groups || [];
    el.support.innerHTML = rows.map(s => `<tr>
      <td><strong>${esc(s.name)}</strong>${s.notes?`<small class="support-note">${esc(s.notes)}</small>`:''}</td>
      <td>${esc(s.identity_number||'-')}</td><td>${esc(s.access_level||'-')}</td><td>${esc(s.email_phone||'-')}</td><td>${esc(s.reference_info||'-')}</td><td>${esc(s.validity_date||'-')}</td>
      <td>${statusBadge({key:s.status==='Expired'?'expired':(s.status==='Expiring Soon'?'expiring':'active'),label:s.status})}</td>
      ${canManage?`<td><div class="support-actions"><button type="button" data-support-edit="${s.id}">Edit</button><button type="button" class="danger" data-support-delete="${s.id}">Delete</button></div></td>`:''}
    </tr>`).join('') || `<tr><td colspan="${canManage?8:7}" class="empty-table-cell">No support group registered.</td></tr>`;
  }

  function renderAssociations() {
    const rows = state.detail?.associations || [];
    const renderRows = (type) => rows.filter(x=>x.type===type).map(a=>`<tr><td><strong>${esc(a.name)}</strong></td><td>${esc(a.access_level||'-')}</td><td>${esc(a.validity_date||'-')}</td><td>${statusBadge({key:a.status==='Expired'?'expired':(a.status==='Expiring Soon'?'expiring':'active'),label:a.status})}</td><td><div class="support-actions"><button type="button" data-association-edit="${a.id}">Edit</button><button type="button" class="danger" data-association-delete="${a.id}">Delete</button></div></td></tr>`).join('') || '<tr><td colspan="5" class="empty-table-cell">No data.</td></tr>';
    if(el.contractor) el.contractor.innerHTML=renderRows('contractor_waf');
    if(el.visitor) el.visitor.innerHTML=renderRows('visitor_ave');
  }

  function fillRackOptions() {
    const options = '<option value="">All / Not specified</option>' + (state.detail?.locations || []).map(r => `<option value="${r.rack_id}">${esc(r.site)} / ${esc(r.floor)} / ${esc(r.rack)}</option>`).join('');
    if (el.supportRack) el.supportRack.innerHTML = options;
    if (el.associationRack) el.associationRack.innerHTML = options;
  }

  el.search?.addEventListener('input', () => { state.query = el.search.value; renderExplorer(); });
  el.sites?.addEventListener('click', (e) => {
    const toggle = e.target.closest('[data-site-toggle]');
    if (toggle) {
      const siteName = toggle.dataset.siteToggle || '';
      state.collapsedSites[siteName] = !state.collapsedSites[siteName];
      persistAccordion();
      renderExplorer();
      return;
    }
    const btn = e.target.closest('[data-customer-id]');
    if (!btn) return;
    state.customerId = Number(btn.dataset.customerId);
    state.site = btn.dataset.site || '';
    renderExplorer();
    loadDetail().catch(console.error);
  });
  el.add?.addEventListener('click', () => { window.location.href = '/tenants/add/?mode=create'; });

  document.querySelectorAll('[data-customer-section]').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('[data-customer-section]').forEach(x => x.classList.toggle('active', x === btn));
    document.querySelectorAll('[data-customer-panel]').forEach(panel => panel.classList.toggle('hidden', panel.dataset.customerPanel !== btn.dataset.customerSection));
  }));

  // CSV import is owned by Customer Workspace in v1.8 (Table View was removed).
  el.importBtn?.addEventListener('click', () => {
    if (el.csvResult) { el.csvResult.classList.add('hidden'); el.csvResult.innerHTML = ''; }
    setModalOpen(el.csvModal, true);
  });
  const closeCsv = () => setModalOpen(el.csvModal, false);
  el.csvClose?.addEventListener('click', closeCsv);
  el.csvCancel?.addEventListener('click', closeCsv);
  el.csvModal?.addEventListener('click', e => { if (e.target === el.csvModal) closeCsv(); });
  el.csvUpload?.addEventListener('click', async () => {
    const file = el.csvFile?.files?.[0];
    if (!file) { alert('Pilih file CSV terlebih dahulu.'); return; }
    const form = new FormData(); form.append('file', file);
    const old = el.csvUpload.textContent; el.csvUpload.disabled = true; el.csvUpload.textContent = 'Importing...';
    try {
      const res = await fetch('/api/customers/import-csv/', {method:'POST',headers:{'X-CSRFToken':getCookie('csrftoken')},body:form});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) throw new Error(data.detail || 'Import failed');
      const errors = Array.isArray(data.errors) ? data.errors : [];
      el.csvResult.classList.remove('hidden');
      el.csvResult.innerHTML = `<strong>Import completed.</strong><div>${data.success_count || 0} row success · ${data.error_count || 0} failed</div>${errors.length ? `<ul>${errors.slice(0,20).map(x=>`<li>Line ${x.line}: ${esc(x.error)}</li>`).join('')}</ul>` : ''}`;
      await loadExplorer();
    } catch (err) {
      el.csvResult.classList.remove('hidden'); el.csvResult.innerHTML = `<strong>Import failed:</strong> ${esc(err.message)}`;
    } finally { el.csvUpload.disabled = false; el.csvUpload.textContent = old; }
  });

  el.supportImportBtn?.addEventListener('click', () => {
    if (!state.customerId) { alert('Pilih customer terlebih dahulu.'); return; }
    if (el.supportCsvResult) { el.supportCsvResult.classList.add('hidden'); el.supportCsvResult.innerHTML = ''; }
    if (el.supportCsvFile) el.supportCsvFile.value = '';
    setModalOpen(el.supportCsvModal, true);
  });
  const closeSupportCsv = () => setModalOpen(el.supportCsvModal, false);
  el.supportCsvClose?.addEventListener('click', closeSupportCsv);
  el.supportCsvCancel?.addEventListener('click', closeSupportCsv);
  el.supportCsvModal?.addEventListener('click', e => { if (e.target === el.supportCsvModal) closeSupportCsv(); });
  el.supportCsvUpload?.addEventListener('click', async () => {
    if (!state.customerId) { alert('Pilih customer terlebih dahulu.'); return; }
    const file = el.supportCsvFile?.files?.[0];
    if (!file) { alert('Pilih file CSV Support Group terlebih dahulu.'); return; }
    const form = new FormData(); form.append('file', file);
    const old = el.supportCsvUpload.textContent; el.supportCsvUpload.disabled = true; el.supportCsvUpload.textContent = 'Importing...';
    try {
      const res = await fetch(`/api/customers/${state.customerId}/support-groups/import-csv/`, {method:'POST', headers:{'X-CSRFToken':getCookie('csrftoken')}, body:form});
      const data = await res.json().catch(()=>({}));
      if (!res.ok) throw new Error(data.detail || 'Import Support Group failed');
      const errors = Array.isArray(data.errors) ? data.errors : [];
      el.supportCsvResult.classList.remove('hidden');
      el.supportCsvResult.innerHTML = `<strong>Import completed.</strong><div>${data.created_count || 0} created · ${data.updated_count || 0} updated · ${data.error_count || 0} failed</div>${errors.length ? `<ul>${errors.slice(0,20).map(x=>`<li>Line ${x.line}: ${esc(x.error)}</li>`).join('')}</ul>` : ''}`;
      await loadDetail(); await loadExplorer();
    } catch (err) {
      el.supportCsvResult.classList.remove('hidden'); el.supportCsvResult.innerHTML = `<strong>Import failed:</strong> ${esc(err.message)}`;
    } finally { el.supportCsvUpload.disabled = false; el.supportCsvUpload.textContent = old; }
  });

  const formFields = {
    id: document.getElementById('supportGroupId'), name: document.getElementById('supportName'), identity_number: document.getElementById('supportIdentity'), access_level: document.getElementById('supportAccess'), email_phone: document.getElementById('supportEmailPhone'), reference_info: document.getElementById('supportReference'), notes: document.getElementById('supportNotes'), validity_date: document.getElementById('supportValidity'), rack_id: document.getElementById('supportRack')
  };
  function openSupportForm(item = null) {
    if (!el.form) return;
    el.form.classList.remove('hidden');
    document.getElementById('supportFormTitle').textContent = item ? 'Edit Support Group' : 'Add Support Group';
    Object.entries(formFields).forEach(([key, field]) => { if (!field) return; field.value = item ? (item[key] ?? '') : (key === 'status' ? 'Active' : ''); });
    el.form.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
  function closeSupportForm(){ el.form?.classList.add('hidden'); }
  el.addSupport?.addEventListener('click', () => openSupportForm());
  document.getElementById('supportFormClose')?.addEventListener('click', closeSupportForm);
  document.getElementById('supportCancelBtn')?.addEventListener('click', closeSupportForm);
  el.support?.addEventListener('click', async e => {
    const edit = e.target.closest('[data-support-edit]'); const del = e.target.closest('[data-support-delete]');
    if (edit) { const item = state.detail.support_groups.find(x => x.id === Number(edit.dataset.supportEdit)); openSupportForm(item); }
    if (del && confirm('Delete support group ini?')) { const r = await fetch(`/api/support-groups/${del.dataset.supportDelete}/`, {method:'DELETE',headers:{'X-CSRFToken':getCookie('csrftoken')}}); if(!r.ok) alert('Delete failed'); else { await loadDetail(); await loadExplorer(); } }
  });
  el.form?.addEventListener('submit', async e => {
    e.preventDefault();
    const payload = {}; Object.entries(formFields).forEach(([k,f]) => payload[k] = f?.value || '');
    const id = payload.id; delete payload.id;
    const url = id ? `/api/support-groups/${id}/` : `/api/customers/${state.customerId}/support-groups/`;
    const res = await fetch(url,{method:id?'PUT':'POST',headers:{'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')},body:JSON.stringify(payload)});
    const data = await res.json().catch(()=>({})); if(!res.ok){ alert(data.detail || 'Save failed'); return; }
    closeSupportForm(); await loadDetail(); await loadExplorer();
  });

  const associationFields = {
    id: document.getElementById('associationId'), type: document.getElementById('associationType'), name: document.getElementById('associationName'), identity_number: document.getElementById('associationIdentity'), access_level: document.getElementById('associationAccess'), email_phone: document.getElementById('associationEmailPhone'), reference_info: document.getElementById('associationReference'), notes: document.getElementById('associationNotes'), rack_id: document.getElementById('associationRack'), validity_date: document.getElementById('associationValidity')
  };
  function openAssociationForm(type, item=null){
    if(!el.associationForm)return;
    el.associationForm.classList.remove('hidden');
    document.getElementById('associationFormTitle').textContent=item?`Edit ${item.type_label}`:(type==='contractor_waf'?'Add Contractor / WAF':'Add Visitor / AVE');
    Object.entries(associationFields).forEach(([key,field])=>{if(!field)return;field.value=item?(item[key]??''):(key==='type'?type:'');});
    el.associationForm.scrollIntoView({behavior:'smooth',block:'nearest'});
  }
  function closeAssociationForm(){el.associationForm?.classList.add('hidden');}
  root.querySelectorAll('[data-association-add]').forEach(btn=>btn.addEventListener('click',()=>openAssociationForm(btn.dataset.associationAdd)));
  document.getElementById('associationFormClose')?.addEventListener('click',closeAssociationForm);
  document.getElementById('associationCancelBtn')?.addEventListener('click',closeAssociationForm);
  [el.contractor,el.visitor].forEach(body=>body?.addEventListener('click',async e=>{
    const edit=e.target.closest('[data-association-edit]'),del=e.target.closest('[data-association-delete]');
    if(edit){const item=(state.detail?.associations||[]).find(x=>x.id===Number(edit.dataset.associationEdit));if(item)openAssociationForm(item.type,item);}
    if(del&&confirm('Delete association ini?')){const r=await fetch(`/api/customer-associations/${del.dataset.associationDelete}/`,{method:'DELETE',headers:{'X-CSRFToken':getCookie('csrftoken')}});if(!r.ok)alert('Delete failed');else await loadDetail();}
  }));
  el.associationForm?.addEventListener('submit',async e=>{
    e.preventDefault();const payload={};Object.entries(associationFields).forEach(([k,f])=>payload[k]=f?.value||'');const id=payload.id;delete payload.id;
    const url=id?`/api/customer-associations/${id}/`:`/api/customers/${state.customerId}/associations/`;const res=await fetch(url,{method:id?'PUT':'POST',headers:{'Content-Type':'application/json','X-CSRFToken':getCookie('csrftoken')},body:JSON.stringify(payload)});const data=await res.json().catch(()=>({}));if(!res.ok){alert(data.detail||'Save failed');return;}closeAssociationForm();await loadDetail();await loadExplorer();
  });

  window.addEventListener('mailgenix:data-changed', async () => {
    // Do not disturb an open edit form; refresh the background workspace only.
    if (el.form && !el.form.classList.contains('hidden')) return;
    try { await loadExplorer(); if (state.customerId) await loadDetail(); } catch (err) { console.warn('[LiveSync] tenant refresh failed', err); }
  });

  loadExplorer().catch(err => { console.error(err); el.sites.innerHTML = '<div class="customer-explorer-loading">Failed to load customer workspace.</div>'; });
}
