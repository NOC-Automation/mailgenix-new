function csrfToken() {
  const input = document.querySelector('#sequenceApp [name="csrfmiddlewaretoken"]');
  if (input?.value) return input.value;
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const fmtDate = (iso) => {
  if (!iso) return '-';
  const [y,m,d] = iso.split('-').map(Number);
  return new Intl.DateTimeFormat('en-GB', {day:'2-digit', month:'short', year:'numeric'}).format(new Date(y,m-1,d));
};

export function initSequenceManagement() {
  const app = document.getElementById('sequenceApp');
  if (!app || app.dataset.initialized === '1') return;
  app.dataset.initialized = '1';

  const $ = (id) => document.getElementById(id);
  const isAdmin = app.dataset.admin === '1';
  const drawer = $('seqDrawer');
  const backdrop = $('seqDrawerBackdrop');
  const form = $('seqForm');
  const tableBody = $('seqTableBody');
  let items = [];
  let filtered = [];
  let currentPage = 1;
  const pageSize = 10;
  let refreshTimer = null;
  let liveSignature = '';
  let searchTimer = null;

  const typeEl = $('seqType'), activityEl = $('seqActivity'), siteEl = $('seqSite');
  const customerSearch = $('seqCustomerSearch'), customerId = $('seqCustomerId');
  const dateEl = $('seqOperationalDate');

  function todayISO() {
    const d = new Date();
    const off = d.getTimezoneOffset();
    return new Date(d.getTime() - off * 60000).toISOString().slice(0,10);
  }

  function setMessage(text, isError=false) {
    const el = $('seqFormMessage');
    if (!text) { el.hidden = true; el.textContent = ''; return; }
    el.hidden = false; el.textContent = text;
    el.classList.toggle('error', isError);
  }

  function updateActivity() {
    const type = typeEl.value;
    const current = activityEl.value;
    activityEl.innerHTML = '';
    if (!type) activityEl.add(new Option('Select Activity',''));
    else if (type === 'EQM') { activityEl.add(new Option('IN','IN')); activityEl.add(new Option('OUT','OUT')); if (['IN','OUT'].includes(current)) activityEl.value=current; }
    else { activityEl.add(new Option(type,type)); activityEl.value=type; }
    $('seqEqmSavedWrap').hidden = type !== 'EQM';
  }

  async function loadCustomers(query='') {
    const siteId = siteEl.value;
    const box = $('seqCustomerResults');
    if (!siteId) { box.hidden = true; box.innerHTML=''; return; }
    const params = new URLSearchParams({site_id: siteId});
    if (query) params.set('q', query);
    try {
      const res = await fetch(`/api/sequences/customers/?${params}`);
      const data = await res.json();
      box.innerHTML = (data.items || []).map(c => `<button type="button" data-id="${c.id}" data-name="${esc(c.name)}">${esc(c.name)}</button>`).join('') || '<div class="seq-combo-empty">No customer found</div>';
      box.hidden = false;
    } catch { box.hidden = true; }
  }

  async function updatePreview() {
    const editId = $('seqEditId').value;
    if (editId) return;
    if (!typeEl.value || !siteEl.value || !dateEl.value) { $('seqPreviewText').textContent='—'; $('seqPreviewNote').textContent='Pilih Type, Site, dan Operational Date.'; return; }
    const params = new URLSearchParams({type:typeEl.value, site_id:siteEl.value, operational_date:dateEl.value, activity:activityEl.value || typeEl.value});
    try {
      const res = await fetch(`/api/sequences/preview/?${params}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Preview gagal');
      $('seqPreviewText').textContent = data.preview;
      $('seqPreviewNote').textContent = data.note || 'Nomor final dikonfirmasi saat disimpan.';
    } catch (err) { $('seqPreviewText').textContent='—'; $('seqPreviewNote').textContent=err.message; }
  }

  function resetForm() {
    form.reset();
    $('seqEditId').value='';
    $('seqDrawerTitle').textContent='Add Sequence';
    $('seqSubmit').textContent='Create Sequence';
    typeEl.disabled=false; siteEl.disabled=false;
    customerId.value=''; customerSearch.value='';
    dateEl.value=todayISO();
    updateActivity();
    setMessage('');
    $('seqPreviewText').textContent='—';
    $('seqPreviewNote').textContent='Pilih Type, Site, dan Operational Date.';
  }

  function openDrawer(record=null) {
    resetForm();
    if (record) {
      $('seqEditId').value=record.id;
      $('seqDrawerTitle').textContent='Edit Sequence';
      $('seqSubmit').textContent='Save Changes';
      typeEl.value=record.sequence_type; updateActivity(); activityEl.value=record.activity;
      siteEl.value=String(record.site_id); typeEl.disabled=true; siteEl.disabled=true;
      customerId.value=record.customer_id; customerSearch.value=record.customer;
      $('seqTicket').value=record.ticket_number || '';
      $('seqDocumentStatus').value=record.document_status;
      dateEl.value=record.operational_date;
      $('seqRemarks').value=record.remarks || '';
      if (record.eqm_saved === true) form.querySelector('input[name="seqEqmSaved"][value="true"]').checked=true;
      if (record.eqm_saved === false) form.querySelector('input[name="seqEqmSaved"][value="false"]').checked=true;
      $('seqPreviewText').textContent=record.sequence_number;
      $('seqPreviewNote').textContent='Sequence Number terkunci dan tidak berubah saat data operasional diedit.';
    }
    drawer.classList.add('open'); drawer.setAttribute('aria-hidden','false'); backdrop.hidden=false;
    document.body.classList.add('seq-drawer-open');
  }

  function closeDrawer() { drawer.classList.remove('open'); drawer.setAttribute('aria-hidden','true'); backdrop.hidden=true; document.body.classList.remove('seq-drawer-open'); }

  function badge(value, kind='') {
    const cls = kind || String(value).toLowerCase().replace(/[^a-z]+/g,'-').replace(/^-|-$/g,'');
    return `<span class="seq-badge ${cls}">${esc(value)}</span>`;
  }

  function renderTable() {
    const start = (currentPage-1)*pageSize;
    const page = filtered.slice(start,start+pageSize);
    tableBody.innerHTML = page.length ? page.map((r,i) => `<tr>
      <td>${start+i+1}</td><td><button class="seq-link" data-copy-sequence="${esc(r.sequence_number)}" title="Click to copy">${esc(r.sequence_number)} ⧉</button></td><td>${esc(r.sequence_type)}</td><td>${esc(r.activity)}</td>
      <td class="seq-customer-cell">${esc(r.customer)}</td><td>${esc(r.site)}</td><td>${esc(r.ticket_number || '-')}</td><td>${badge(r.document_status, r.document_status==='QR Already Sent & Tenant List'?'qr':r.document_status.toLowerCase().replace(' ','-'))}</td>
      <td>${r.sequence_type==='EQM' ? (r.eqm_saved===true?'✓ Yes':r.eqm_saved===false?'No':'-') : '-'}</td><td>${fmtDate(r.operational_date)}</td><td>${esc(r.approved_by)}</td><td>${badge(r.status)}</td>
      <td><div class="seq-actions"><button type="button" title="Edit" data-edit="${r.id}" ${r.status==='Void'?'disabled':''}>Edit</button>${isAdmin?`<button type="button" title="Audit" data-audit="${r.id}">Audit</button><button type="button" class="danger" title="Void" data-void="${r.id}" ${r.status==='Void'?'disabled':''}>Void</button>`:''}</div></td>
    </tr>`).join('') : '<tr><td colspan="13" class="seq-empty">No sequence found.</td></tr>';
    $('seqTableInfo').textContent = filtered.length ? `Showing ${start+1} to ${Math.min(start+pageSize,filtered.length)} of ${filtered.length} entries` : 'Showing 0 entries';
    const pages = Math.max(1, Math.ceil(filtered.length/pageSize));
    if (currentPage>pages) currentPage=pages;
    $('seqPagination').innerHTML = Array.from({length:pages},(_,i)=>i+1).slice(Math.max(0,currentPage-3), Math.min(pages,currentPage+2)).map(p=>`<button type="button" data-page="${p}" class="${p===currentPage?'active':''}">${p}</button>`).join('');
  }

  function applyFilters() {
    const q=$('seqSearch').value.trim().toLowerCase(), type=$('seqFilterType').value, activity=$('seqFilterActivity').value, site=$('seqFilterSite').value, status=$('seqFilterStatus').value, doc=$('seqFilterDocument').value, month=$('seqFilterMonth').value, year=$('seqFilterYear').value;
    filtered=items.filter(r => {
      const hay=`${r.sequence_number} ${r.customer} ${r.ticket_number}`.toLowerCase();
      const [y,m]=r.operational_date.split('-');
      return (!q||hay.includes(q))&&(!type||r.sequence_type===type)&&(!activity||r.activity===activity)&&(!site||r.site===site)&&(!status||r.status===status)&&(!doc||r.document_status===doc)&&(!month||Number(m)===Number(month))&&(!year||y===year);
    });
    currentPage=1; renderTable();
  }

  function updateSummary(summary) { Object.entries(summary||{}).forEach(([k,v]) => { const el=app.querySelector(`[data-kpi="${CSS.escape(k)}"]`); if(el) el.textContent=v; }); }

  async function loadData(silent=false) {
    try {
      const res=await fetch('/api/sequences/'); const data=await res.json(); if(!res.ok) throw new Error(data.error||'Failed to load sequence data');
      items=data.items||[]; updateSummary(data.summary); applyFilters();
    } catch(err) { if(!silent) tableBody.innerHTML=`<tr><td colspan="13" class="seq-empty">${esc(err.message)}</td></tr>`; }
  }

  async function pollLive() {
    if (drawer.classList.contains('open')) return;
    try { const r=await fetch('/api/sequences/live-state/'); const d=await r.json(); const sig=`${d.count}|${d.latest_id}|${d.latest_updated_at}`; if(liveSignature && sig!==liveSignature) await loadData(true); liveSignature=sig; } catch {}
  }

  async function showAudit(id) {
    try {
      const rec=items.find(x=>x.id===id);
      const res=await fetch(`/api/sequences/${id}/audit/`); const data=await res.json(); if(!res.ok) throw new Error(data.detail||data.error||'Gagal mengambil audit log');
      $('seqAuditTitle').textContent=rec?.sequence_number||'Sequence';
      $('seqAuditBody').innerHTML=(data.results||[]).map(a=>`<div class="seq-audit-item"><strong>${esc(String(a.action||'').toUpperCase())}${a.field?' · '+esc(a.field):''}</strong><span>${new Date(a.changed_at).toLocaleString()}</span><p>${a.old?`${esc(a.old)} → `:''}${esc(a.new)}</p><small>by ${esc(a.changed_by)}</small></div>`).join('')||'<p class="seq-empty">No audit history.</p>';
      $('seqAuditModal').hidden=false;
    } catch(err) { alert(err.message); }
  }

  async function voidSequence(id) {
    const rec=items.find(x=>x.id===id); if(!rec) return;
    const reason=window.prompt(`VOID ${rec.sequence_number}\nMasukkan alasan:`); if(reason===null) return; if(!reason.trim()){alert('Alasan VOID wajib diisi.');return;}
    const res=await fetch(`/api/sequences/${id}/void/`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken()},body:JSON.stringify({reason})}); const data=await res.json(); if(!res.ok){alert(data.error||'Void gagal');return;} await loadData();
  }

  form.addEventListener('submit', async e => {
    e.preventDefault(); setMessage('');
    if (!customerId.value) { setMessage('Pilih Customer dari hasil pencarian Tenant List.', true); return; }
    const eqm=form.querySelector('input[name="seqEqmSaved"]:checked');
    const payload={sequence_type:typeEl.value,activity:activityEl.value,site_id:siteEl.value,customer_id:customerId.value,ticket_number:$('seqTicket').value,document_status:$('seqDocumentStatus').value,eqm_saved:eqm?eqm.value==='true':null,operational_date:dateEl.value,remarks:$('seqRemarks').value};
    const editId=$('seqEditId').value;
    const url=editId?`/api/sequences/${editId}/`:'/api/sequences/';
    const method=editId?'PATCH':'POST';
    if(editId){delete payload.sequence_type;delete payload.site_id;}
    $('seqSubmit').disabled=true;
    try { const res=await fetch(url,{method,headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken()},body:JSON.stringify(payload)}); const data=await res.json(); if(!res.ok) throw new Error(data.error||'Gagal menyimpan sequence'); setMessage(editId?'Sequence berhasil diperbarui.':`Sequence ${data.item.sequence_number} berhasil dibuat.`); await loadData(); setTimeout(closeDrawer,650); }
    catch(err){setMessage(err.message,true);} finally{$('seqSubmit').disabled=false;}
  });

  [typeEl,siteEl,dateEl,activityEl].forEach(el=>el.addEventListener('change',()=>{ if(el===typeEl)updateActivity(); if(el===siteEl){customerId.value='';customerSearch.value='';} updatePreview(); }));
  customerSearch.addEventListener('focus',()=>loadCustomers(customerSearch.value));
  customerSearch.addEventListener('input',()=>{customerId.value='';clearTimeout(searchTimer);searchTimer=setTimeout(()=>loadCustomers(customerSearch.value),180);});
  $('seqCustomerResults').addEventListener('click',e=>{const b=e.target.closest('button[data-id]');if(!b)return;customerId.value=b.dataset.id;customerSearch.value=b.dataset.name;$('seqCustomerResults').hidden=true;});
  document.addEventListener('click',e=>{if(!e.target.closest('.seq-combobox'))$('seqCustomerResults').hidden=true;});
  $('seqOpenDrawer').addEventListener('click',()=>openDrawer()); $('seqOpenDrawer2').addEventListener('click',()=>openDrawer()); $('seqCloseDrawer').addEventListener('click',closeDrawer); $('seqCancel').addEventListener('click',closeDrawer); backdrop.addEventListener('click',closeDrawer);
  $('seqAuditClose').addEventListener('click',()=>{$('seqAuditModal').hidden=true;}); $('seqAuditModal').addEventListener('click',e=>{if(e.target===$('seqAuditModal'))$('seqAuditModal').hidden=true;});
  tableBody.addEventListener('click',async e=>{const copy=e.target.closest('[data-copy-sequence]'), edit=e.target.closest('[data-edit]'), audit=e.target.closest('[data-audit]'), v=e.target.closest('[data-void]'); if(copy){try{await navigator.clipboard.writeText(copy.dataset.copySequence);const old=copy.textContent;copy.textContent='Copied!';setTimeout(()=>copy.textContent=old,900);}catch{window.prompt('Copy sequence number:',copy.dataset.copySequence);}return;} if(edit)openDrawer(items.find(x=>x.id===Number(edit.dataset.edit))); else if(audit&&isAdmin)showAudit(Number(audit.dataset.audit)); else if(v&&isAdmin)voidSequence(Number(v.dataset.void));});
  $('seqPagination').addEventListener('click',e=>{const b=e.target.closest('[data-page]');if(!b)return;currentPage=Number(b.dataset.page);renderTable();});
  ['seqSearch','seqFilterType','seqFilterActivity','seqFilterSite','seqFilterStatus','seqFilterDocument','seqFilterMonth','seqFilterYear'].forEach(id=>$(id).addEventListener(id==='seqSearch'?'input':'change',applyFilters));
  $('seqResetFilters').addEventListener('click',()=>{['seqSearch','seqFilterType','seqFilterActivity','seqFilterSite','seqFilterStatus','seqFilterDocument','seqFilterMonth','seqFilterYear'].forEach(id=>$(id).value='');applyFilters();});

  if (isAdmin && $('seqExportBtn')) {
    const reportModal=$('seqReportModal');
    $('seqExportBtn').addEventListener('click',()=>{reportModal.hidden=false;});
    const closeReport=()=>{reportModal.hidden=true;};
    $('seqReportClose')?.addEventListener('click',closeReport);
    $('seqReportCancel')?.addEventListener('click',closeReport);
    $('seqReportForm')?.addEventListener('submit',e=>{e.preventDefault();window.location.href='/reports/sequence.xlsx?'+new URLSearchParams(new FormData(e.target)).toString();closeReport();});
  }

  resetForm(); loadData(); pollLive(); refreshTimer=setInterval(pollLive,15000);
  window.addEventListener('beforeunload',()=>clearInterval(refreshTimer),{once:true});
}
