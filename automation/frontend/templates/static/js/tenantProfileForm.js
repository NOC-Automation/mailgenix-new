const q = (s, root=document) => root.querySelector(s);
const qa = (s, root=document) => Array.from(root.querySelectorAll(s));

function csrf() {
  return document.cookie.split('; ').find(x => x.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
}
function statusFromDate(value) {
  if (!value) return {key:'active', label:'Active'};
  const today = new Date(); today.setHours(0,0,0,0);
  const due = new Date(`${value}T00:00:00`);
  const days = Math.floor((due - today) / 86400000);
  if (days < 0) return {key:'expired', label:'Expired'};
  if (days <= 30) return {key:'expiring', label:'Expiring Soon'};
  return {key:'active', label:'Active'};
}
function updateStatus(row) {
  const state = statusFromDate(q('.profile-ar-date', row)?.value || '');
  const badge = q('.profile-ar-status', row);
  if (!badge) return;
  badge.className = `profile-ar-status customer-status-badge status-${state.key}`;
  badge.textContent = state.label;
}
function renumber() {
  qa('.location-row').forEach((r,i)=>q('.row-number',r).textContent=i+1);
  qa('.ar-profile-row').forEach((r,i)=>q('.row-number',r).textContent=i+1);
  qa('.additional-mailing-row').forEach((r,i)=>q('.row-number',r).textContent=i+1);
}
function filterFloors(row, siteName, selectedFloorId='') {
  const select = q('.location-floor', row);
  qa('option', select).forEach(opt => {
    if (!opt.value) { opt.hidden = false; return; }
    opt.hidden = opt.dataset.siteName !== siteName;
  });
  if (selectedFloorId) select.value = String(selectedFloorId);
  else if (select.selectedOptions[0]?.hidden) select.value = '';
}
function addLocation(data={}) {
  const tpl = document.getElementById('locationRowTemplate');
  const row = tpl.content.firstElementChild.cloneNode(true);
  const site = q('.location-site', row), floor = q('.location-floor', row), rack = q('.location-rack', row);
  site.value = data.customer_site || data.site || '';
  filterFloors(row, site.value, data.floor_id || '');
  rack.value = data.rack_name || data.rack || '';
  site.addEventListener('change', ()=>filterFloors(row, site.value));
  q('.remove-location', row).addEventListener('click', ()=>{ row.remove(); renumber(); });
  document.getElementById('locationsList').appendChild(row); renumber();
}
function addAr(data={}) {
  const tpl = document.getElementById('authorizedRowTemplate');
  const row = tpl.content.firstElementChild.cloneNode(true);
  q('.profile-ar-name', row).value = data.authorized_name || data.name || '';
  q('.profile-ar-email', row).value = data.email || '';
  q('.profile-ar-phone', row).value = data.phone || '';
  q('.profile-ar-date', row).value = data.due_date || '';
  q('.profile-ar-date', row).addEventListener('change', ()=>updateStatus(row));
  q('.remove-ar', row).addEventListener('click', ()=>{ row.remove(); renumber(); });
  updateStatus(row);
  document.getElementById('authorizedList').appendChild(row); renumber();
}
function addAdditionalMailing(data='') {
  const tpl = document.getElementById('additionalMailingRowTemplate');
  const row = tpl.content.firstElementChild.cloneNode(true);
  q('.additional-mailing-email', row).value = typeof data === 'string' ? data : (data.email_address || data.email || '');
  q('.remove-additional-mailing', row).addEventListener('click', ()=>{ row.remove(); renumber(); });
  document.getElementById('additionalMailingList').appendChild(row); renumber();
}

function collect() {
  const locations = qa('.location-row').map(row => ({
    customer_site: q('.location-site', row).value,
    floor_level: Number(q('.location-floor', row).value) || null,
    rack_name: q('.location-rack', row).value.trim(),
  }));
  const ars = qa('.ar-profile-row').map(row => ({
    authorized_name: q('.profile-ar-name', row).value.trim(),
    email: q('.profile-ar-email', row).value.trim(),
    phone: q('.profile-ar-phone', row).value.trim(),
    due_date: q('.profile-ar-date', row).value,
  }));
  const additional_mailing_lists = qa('.additional-mailing-row').map(row => q('.additional-mailing-email', row).value.trim()).filter(Boolean);
  return {customer_name:q('#profileCustomerName').value.trim(), office_phone:q('#profileOfficePhone').value.trim(), locations, ars, additional_mailing_lists};
}
function validate(payload) {
  if (!payload.customer_name) throw new Error('Customer Name wajib diisi.');
  if (!payload.locations.length) throw new Error('Minimal 1 Location / Rack wajib ditambahkan.');
  for (const [i,loc] of payload.locations.entries()) if (!loc.customer_site || !loc.floor_level || !loc.rack_name) throw new Error(`Location #${i+1} belum lengkap.`);
  if (!payload.ars.length) throw new Error('Minimal 1 Authorized Person wajib ditambahkan.');
  const emails = new Set();
  for (const [i,ar] of payload.ars.entries()) {
    if (!ar.email) throw new Error(`Email Authorized Person #${i+1} wajib diisi.`);
    const k=ar.email.toLowerCase(); if (emails.has(k)) throw new Error('Email Authorized Person tidak boleh duplikat.'); emails.add(k);
  }
  const mlSeen = new Set();
  for (const [i,email] of (payload.additional_mailing_lists || []).entries()) {
    const k=email.toLowerCase();
    if (mlSeen.has(k)) throw new Error(`Additional Mailing List #${i+1} duplikat.`);
    mlSeen.add(k);
  }
}
async function request(url, options={}) {
  const res = await fetch(url, options); const data = await res.json().catch(()=>({}));
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`); return data;
}
async function boot() {
  const form = document.getElementById('tenantProfileForm'); if (!form) return;
  const params = new URLSearchParams(location.search), mode=params.get('mode') || 'create', customerId=Number(params.get('customer_id')||0)||null;
  q('#tenantProfileTitle').textContent = mode==='edit' ? 'Edit Tenant' : 'Add Tenant';
  q('#addLocationBtn').addEventListener('click', ()=>addLocation()); q('#addAuthorizedBtn').addEventListener('click', ()=>addAr()); q('#addAdditionalMailingBtn').addEventListener('click', ()=>addAdditionalMailing());
  qa('[data-cancel-profile]').forEach(b=>b.addEventListener('click', ()=>location.href='/?tab=tenant'));
  if (mode==='edit' && customerId) {
    const data = await request(`/api/customers/${customerId}/profile/`);
    q('#profileCustomerName').value=data.customer_name||''; q('#profileOfficePhone').value=data.office_phone||'';
    (data.locations||[]).forEach(addLocation); (data.ars||[]).forEach(addAr); (data.additional_mailing_lists||[]).forEach(addAdditionalMailing);
  } else { addLocation(); addAr(); }
  form.addEventListener('submit', async e => {
    e.preventDefault();
    try {
      const payload=collect(); validate(payload);
      const url = mode==='edit' && customerId ? `/api/customers/${customerId}/profile/` : '/api/customers/profile/';
      const method = mode==='edit' && customerId ? 'PUT' : 'POST';
      const btn=q('#saveTenantProfileBtn'); const old=btn.textContent; btn.disabled=true; btn.textContent='Saving...';
      try { await request(url,{method,headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(payload)}); sessionStorage.setItem('tenantToastMessage', mode==='edit'?'Customer berhasil diperbarui.':'Customer berhasil ditambahkan.'); location.href='/?tab=tenant'; }
      finally { btn.disabled=false; btn.textContent=old; }
    } catch(err) { alert(err.message || 'Gagal menyimpan customer.'); }
  });
}
boot().catch(err=>{ console.error(err); alert('Gagal memuat form tenant: '+err.message); });
