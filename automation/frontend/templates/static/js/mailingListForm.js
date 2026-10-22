const REGISTRY={
  'outage':{label:'Outage',subtypes:['Outage Report'],variants:['General','A100','BOND']},
  'preventive-maintenance':{label:'Preventive Maintenance',subtypes:['Preventive Maintenance'],variants:['General','A100','BOND']},
  'response-alarm':{label:'Response Alarm',subtypes:['Response Alarm'],variants:['General','A100']},
  'general-cleaning':{label:'General Cleaning',subtypes:['Schedule General Cleaning'],variants:['General','A100','BOND']},
  'site-access':{label:'Site Access',subtypes:['Site Access Information'],variants:['General','A100','BOND']},
  'sharing-information':{label:'Sharing Information',subtypes:['General','Bomb','Demonstration','Earthquake','Fire','Flooding'],variants:['General','A100','BOND']}
};
const FREQUENCIES=['Monthly','Quarterly','Semi-Annually','Half-Yearly','Annually','Others'];
const q=id=>document.getElementById(id);
const csrf=()=>document.querySelector('[name=csrfmiddlewaretoken]')?.value||document.cookie.match(/csrftoken=([^;]+)/)?.[1]||'';

export function initMailingListForm(){
  const root=q('mg195Mailing'); if(!root)return;
  const st={category:'',to:[],cc:[],bcc:[],req:0,previewTimer:null};
  const categoryButtons=[...root.querySelectorAll('[data-category]')];
  const scopeRadios=[...root.querySelectorAll('input[name="recipient_scope"]')];
  const currentScope=()=>scopeRadios.find(r=>r.checked)?.value||'site-floor';
  const fillSelect=(el,arr)=>{el.innerHTML=arr.map(v=>`<option value="${v}">${v}</option>`).join('');};
  const hide=(id,v=true)=>q(id)?.classList.toggle('hidden',v);

  function chooseCategory(cat){
    st.category=cat;
    categoryButtons.forEach(b=>b.classList.toggle('active',b.dataset.category===cat));
    const cfg=REGISTRY[cat];
    q('selectedTemplateLabel').textContent=cfg.label;
    q('selectedTemplatePill').textContent=cfg.label;
    q('subcategoryWrap').classList.remove('hidden');
    q('variantWrap').classList.remove('hidden');
    fillSelect(q('templateSubcategory'),cfg.subtypes);
    fillSelect(q('templateVariant'),cfg.variants);
    q('outageTypeWrap').classList.toggle('hidden',cat!=='outage');
    q('previewTemplateBtn').disabled=false;
    q('notificationDetailsEmpty').classList.add('hidden');
    q('notificationDetails').classList.remove('hidden');
    renderDynamicFields();
    schedulePreview();
  }

  categoryButtons.forEach(b=>b.addEventListener('click',()=>chooseCategory(b.dataset.category)));
  q('templateSearch')?.addEventListener('input',e=>{
    const t=e.target.value.trim().toLowerCase();
    categoryButtons.forEach(b=>b.classList.toggle('hidden',t&&!b.dataset.search.includes(t)));
  });
  ['templateSubcategory','templateVariant'].forEach(id=>q(id)?.addEventListener('change',()=>schedulePreview()));
  q('outageUpdateType')?.addEventListener('change',()=>{renderDynamicFields();schedulePreview();});

  function pmActivityRow(values={}){
    const freq=values.frequency||'Monthly';
    const mop=(values.mop_attached===false||values.mop_attached==='no')?'no':'yes';
    return `<div class="mg195-pm-row" data-pm-row>
      <div><label class="mg195-label">Item *</label><input class="mg195-field" data-pm="item" placeholder="e.g. CRAC" value="${escapeHtml(values.item||'')}"></div>
      <div><label class="mg195-label">Frequency</label><select class="mg195-field" data-pm="frequency">${FREQUENCIES.map(v=>`<option${v===freq?' selected':''}>${v}</option>`).join('')}</select></div>
      <div><label class="mg195-label">Date & Time *</label><input class="mg195-field" data-pm="date_time" placeholder="e.g. 16 - 19 & 20 - 21 October 2026" value="${escapeHtml(values.date_time||'')}"></div>
      <div><label class="mg195-label">MOP Attached?</label><select class="mg195-field" data-pm="mop_attached"><option value="yes"${mop==='yes'?' selected':''}>Yes</option><option value="no"${mop==='no'?' selected':''}>No</option></select></div>
      <button type="button" class="mg195-pm-remove" data-remove-pm aria-label="Remove maintenance activity">Remove</button>
    </div>`;
  }
  function escapeHtml(value){return String(value).replace(/[&<>'"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));}
  function pmFields(){
    return `<div class="mg195-pm-block">
      <div class="mg195-form-grid">
        <div><label class="mg195-label">Title</label><input id="pmTitle" class="mg195-field mg195-readonly" value="Preventive Maintenance" readonly></div>
        <div><label class="mg195-label">Status</label><input id="maintenance_status" class="mg195-field" value="Assigned"></div>
        <div class="mg195-span-2"><label class="mg195-label">Maintenance Period *</label><input id="maintenance_period" class="mg195-field" placeholder="e.g. 07 October 2026 – 29 October 2026 at 09:00 AM – 05:00 PM (Local Time)"></div>
      </div>
      <div class="mg195-pm-heading"><div><strong>Maintenance Activities</strong><small>Add as many PM activities as required. Final email output is sorted by the earliest date.</small></div><button type="button" id="addPmActivity" class="mg195-secondary">+ Add Maintenance Activity</button></div>
      <div id="pmActivities" class="mg195-pm-rows">${pmActivityRow()}</div>
      <div class="mg195-form-grid mg195-pm-bottom">
        <div class="mg195-span-2"><label class="mg195-label">Service Impact</label><input id="pm_service_impact" class="mg195-field mg195-readonly" value="No Impact to IT Load" readonly></div>
        <div class="mg195-span-2"><label class="mg195-label">Note <span class="mg195-optional">Optional</span></label><textarea id="maintenance_note" class="mg195-field mg195-textarea" rows="2" placeholder="Leave blank to display -"></textarea></div>
      </div>
    </div>`;
  }

  function bindPmEvents(){
    q('addPmActivity')?.addEventListener('click',()=>{
      q('pmActivities').insertAdjacentHTML('beforeend',pmActivityRow());
      schedulePreview(); refreshGenerate();
    });
    q('pmActivities')?.addEventListener('click',e=>{
      const btn=e.target.closest('[data-remove-pm]'); if(!btn)return;
      const rows=[...q('pmActivities').querySelectorAll('[data-pm-row]')];
      if(rows.length===1){rows[0].querySelectorAll('input').forEach(i=>i.value=''); rows[0].querySelector('[data-pm="frequency"]').value='Monthly'; rows[0].querySelector('[data-pm="mop_attached"]').value='yes';}
      else btn.closest('[data-pm-row]').remove();
      schedulePreview(); refreshGenerate();
    });
    q('genericFields')?.addEventListener('input',()=>{schedulePreview();refreshGenerate();});
    q('genericFields')?.addEventListener('change',()=>{schedulePreview();refreshGenerate();});
  }

  function renderDynamicFields(){
    const cat=st.category, update=q('outageUpdateType').value;
    ['monthYearWrap','occurringWrap','recoveringWrap','serviceImpactWrap','currentActionWrap','rootCauseWrap'].forEach(id=>hide(id,true));
    q('genericFields').innerHTML='';
    q('descriptionWrap').classList.remove('hidden');
    q('notificationDateWrap').classList.toggle('hidden',cat==='outage'||cat==='preventive-maintenance');
    if(cat==='outage'){
      hide('occurringWrap',false); hide('serviceImpactWrap',false); hide('currentActionWrap',false); hide('rootCauseWrap',false);
      hide('recoveringWrap',!(update==='Recovery'||update==='Root Cause'));
      q('descriptionWrap').querySelector('label').textContent='Description of Incident';
      q('rootCause').placeholder=update==='Root Cause'?'Enter confirmed root cause':'Under Investigation';
    } else if(cat==='preventive-maintenance'){
      q('descriptionWrap').classList.add('hidden');
      q('genericFields').innerHTML=pmFields();
      bindPmEvents();
    } else if(cat==='response-alarm'){
      q('genericFields').innerHTML=fields([['soc_request_time','SOC Request Time'],['response_time','Response Time'],['data_hall','Data Hall'],['emergency_card','Emergency Card'],['status','Status'],['root_cause_generic','Cause']]);
    } else if(cat==='general-cleaning'){
      q('genericFields').innerHTML=fields([['event_description','Event Description'],['room','Location / Room'],['status','Status']]);
    } else if(cat==='site-access'){
      q('genericFields').innerHTML=fields([['engineer_names','Engineer Name/s',true],['activity_time','Time of Activity'],['room','Room Name'],['reason','Reason of Activity'],['tools','Tools'],['status','Status'],['activity_state','State of the Activity'],['approval_status','Approval Status']]);
    } else if(cat==='sharing-information'){
      hide('serviceImpactWrap',false); hide('currentActionWrap',false);
      q('descriptionWrap').querySelector('label').textContent='Event Description';
    }
    q('genericFields').querySelectorAll('input,textarea,select').forEach(el=>el.addEventListener('input',schedulePreview));
  }
  function fields(items){return `<div class="mg195-form-grid">${items.map(([id,l,multiline=false])=>{const isTime=/time/i.test(l);const isDate=/date/i.test(l)&&!isTime;const type=isTime?'time':(isDate?'date':'text');const step=isTime?' step="1"':'';const control=multiline?`<textarea id="${id}" class="mg195-field mg195-multiline" rows="5" placeholder="One name per line, e.g.&#10;• Wahyu&#10;• Andriawan&#10;• Lalan&#10;• Surya Setiaji"></textarea>`:`<input id="${id}" type="${type}"${step} class="mg195-field">`;return `<div><label class="mg195-label">${l}</label>${control}</div>`}).join('')}</div>`;}
  function fmtDateTime(v){if(!v)return '';const d=new Date(v);if(Number.isNaN(d.getTime()))return v;const months=['January','February','March','April','May','June','July','August','September','October','November','December'];const pad=n=>String(n).padStart(2,'0');return `${pad(d.getDate())} ${months[d.getMonth()]} ${d.getFullYear()}, ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())} (GMT +7)`;}
  function fmtTime(v){if(!v)return '';const p=v.split(':');return `${p[0]||'00'}:${p[1]||'00'}:${p[2]||'00'}`;}

  function maintenanceActivities(){
    return [...root.querySelectorAll('[data-pm-row]')].map(row=>({
      item:row.querySelector('[data-pm="item"]')?.value.trim()||'',
      frequency:row.querySelector('[data-pm="frequency"]')?.value||'',
      date_time:row.querySelector('[data-pm="date_time"]')?.value.trim()||'',
      mop_attached:(row.querySelector('[data-pm="mop_attached"]')?.value||'yes')==='yes'
    })).filter(r=>r.item||r.date_time);
  }

  function formData(){
    const fd=new FormData(); const add=(k,v)=>fd.append(k,v||'');
    add('type_notification',st.category); add('category',st.category); add('subcategory',q('templateSubcategory').value); add('variant',q('templateVariant').value); add('update_type',q('outageUpdateType').value);
    add('ticket_number',q('ticketNumber').value); add('site',q('notificationSite').value); add('customer_site',q('notificationSite').value); add('notification_date',fmtDateTime(q('notificationDate').value)); add('month_year',q('monthYear').value);
    add('description',q('description').value); add('incident_description',q('description').value); add('fault_occurring_time',fmtDateTime(q('faultOccurringTime').value)); add('fault_recovering_time',fmtDateTime(q('faultRecoveringTime').value)); add('service_impact',q('serviceImpact').value); add('current_action',q('currentAction').value); add('root_cause',q('rootCause').value||q('root_cause_generic')?.value||''); add('additional_information',q('additionalInformation').value);
    add('floor_level',q('floorLevel').selectedOptions[0]?.textContent||''); add('customer_name',q('customerName').selectedOptions[0]?.dataset.customerName||'');
    if(st.category==='preventive-maintenance'){
      add('maintenance_period',q('maintenance_period')?.value||''); add('maintenance_status',q('maintenance_status')?.value||'Assigned'); add('maintenance_note',q('maintenance_note')?.value||''); add('maintenance_activities',JSON.stringify(maintenanceActivities())); add('service_impact','No Impact to IT Load');
    } else {
      root.querySelectorAll('#genericFields input,#genericFields textarea,#genericFields select').forEach(el=>add(el.id,el.type==='time'?fmtTime(el.value):el.value));
    }
    return fd;
  }

  async function preview(openModal=false){
    if(!st.category)return;
    const fd=formData();
    const r=await fetch('/render-email-template/',{method:'POST',headers:{'X-CSRFToken':csrf()},body:fd});
    const d=await r.json(); if(!r.ok)throw Error(d.detail||'Preview failed');
    q('subjectPreview').value=d.subject||''; q('finalPreviewFrame').srcdoc=d.html||''; q('previewStatus').textContent='Preview updated';
    if(openModal){q('notificationPreviewTitle').textContent=`${REGISTRY[st.category].label} Preview`;q('notificationPreviewFrame').srcdoc=d.html||'';q('notificationPreviewModal').classList.remove('hidden');q('notificationPreviewModal').classList.add('flex');}
    refreshGenerate();
  }
  function schedulePreview(){clearTimeout(st.previewTimer);st.previewTimer=setTimeout(()=>preview(false).catch(console.error),350);}
  q('previewTemplateBtn')?.addEventListener('click',()=>preview(true).catch(e=>alert(e.message)));
  q('notificationPreviewClose')?.addEventListener('click',()=>{q('notificationPreviewModal').classList.add('hidden');q('notificationPreviewModal').classList.remove('flex');});
  root.querySelectorAll('#notificationDetails input,#notificationDetails textarea,#notificationDetails select').forEach(el=>el.addEventListener('input',schedulePreview));

  function updateFloors(){const sid=q('customerSite').value;[...q('floorLevel').options].forEach(o=>{if(!o.value)return;o.hidden=!!sid&&o.dataset.site!==sid});if(q('floorLevel').selectedOptions[0]?.hidden)q('floorLevel').value='';updateCustomers();}
  function updateCustomers(){const pair=`${q('customerSite').value}:${q('floorLevel').value}`,term=(q('customerSearch').value||'').toLowerCase();[...q('customerName').options].forEach(o=>{if(!o.value)return;const pairs=(o.dataset.locationPairs||'').split(',');o.hidden=!pairs.includes(pair)||(term&&!o.textContent.toLowerCase().includes(term));});if(q('customerName').selectedOptions[0]?.hidden)q('customerName').value='';}
  function applyScope(){const s=currentScope();root.querySelectorAll('[data-scope-card]').forEach(c=>c.classList.toggle('active',c.dataset.scopeCard===s));q('locationScopeFields').classList.toggle('hidden',s==='mailing-group');q('specificCustomerFields').classList.toggle('hidden',s!=='specific');q('mailingGroupFields').classList.toggle('hidden',s!=='mailing-group');resolve();}
  async function resolve(){
    const s=currentScope(),p=new URLSearchParams();
    if(s==='mailing-group'){if(!q('mailingGrouping').value)return clearRecips();p.set('mailing_group',q('mailingGrouping').value)}
    else{if(!q('customerSite').value||!q('floorLevel').value||(s==='specific'&&!q('customerName').value))return clearRecips();p.set('site_id',q('customerSite').value);p.set('floor_id',q('floorLevel').value);if(s==='specific')p.set('customer_id',q('customerName').value)}
    const n=++st.req;q('recipientStatus').textContent='Resolving…';
    try{const r=await fetch(`/api/mailing/recipients/?${p}`),d=await r.json();if(n!==st.req)return;if(!r.ok)throw Error(d.detail||'Resolve failed');st.to=d.to||[];st.cc=d.cc||[];st.bcc=d.bcc||[];q('resolvedTo').value=st.to.join('; ');q('resolvedCc').value=st.cc.join('; ');q('resolvedBcc').value=st.bcc.join('; ');q('toCount').textContent=st.to.length;q('ccCount').textContent=st.cc.length;q('bccCount').textContent=st.bcc.length;q('recipientStatus').textContent='Resolved';if(d.scope_summary){q('mailingGroupSummary').classList.toggle('hidden',s!=='mailing-group');q('groupSummaryName').textContent=d.mailing_group_name||'';q('groupSummaryScope').textContent=[d.site,...(d.floors||[])].join(' · ');q('groupMatchedCustomers').textContent=d.scope_summary.matched_customers;q('groupActiveAr').textContent=d.scope_summary.active_ar;q('groupAdditionalMl').textContent=d.scope_summary.additional_mailing_lists;q('groupUniqueBcc').textContent=d.scope_summary.unique_bcc;}refreshGenerate();schedulePreview();}
    catch(e){clearRecips();q('recipientStatus').textContent='Resolve error';console.error(e)}
  }
  function clearRecips(){st.to=[];st.cc=[];st.bcc=[];['resolvedTo','resolvedCc','resolvedBcc'].forEach(id=>q(id).value='');['toCount','ccCount','bccCount'].forEach(id=>q(id).textContent='0');refreshGenerate();}
  scopeRadios.forEach(r=>r.addEventListener('change',applyScope));
  q('customerSite').addEventListener('change',()=>{updateFloors();resolve()}); q('floorLevel').addEventListener('change',()=>{updateCustomers();resolve()}); q('customerName').addEventListener('change',()=>{resolve();schedulePreview()}); q('customerSearch').addEventListener('input',updateCustomers); q('mailingGrouping').addEventListener('change',resolve);

  function requiredOk(){
    if(!st.category||!q('ticketNumber').value.trim()||!q('notificationSite').value)return false;
    if(st.category==='outage'){
      if(!q('faultOccurringTime').value.trim())return false;
      const u=q('outageUpdateType').value;
      if((u==='Recovery'||u==='Root Cause')&&!q('faultRecoveringTime').value.trim())return false;
      if(u==='Root Cause'&&!q('rootCause').value.trim())return false;
    }
    if(st.category==='preventive-maintenance'){
      if(!q('maintenance_period')?.value.trim())return false;
      const acts=maintenanceActivities();
      if(!acts.length||acts.some(a=>!a.item||!a.date_time))return false;
    }
    return true;
  }
  function refreshGenerate(){q('generateDraftBtn').disabled=!(requiredOk()&&(st.to.length+st.cc.length+st.bcc.length)>0);}
  root.querySelectorAll('input,textarea,select').forEach(el=>el.addEventListener('input',refreshGenerate));
  q('generateDraftBtn').addEventListener('click',async()=>{
    if(q('generateDraftBtn').disabled)return;
    if(!confirm('Generate Outlook .eml draft with the resolved recipients?'))return;
    const fd=formData();fd.append('to',st.to.join(', '));fd.append('cc',st.cc.join(', '));fd.append('bcc',st.bcc.join(', '));q('generateDraftBtn').disabled=true;q('generateDraftBtn').textContent='Preparing draft…';
    try{const r=await fetch('/compose-email-eml/',{method:'POST',headers:{'X-CSRFToken':csrf()},body:fd});if(!r.ok){let d={};try{d=await r.json()}catch{}throw Error(d.detail||'Failed to generate draft')}const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a'),cd=r.headers.get('Content-Disposition')||'',m=cd.match(/filename=\"?([^\";]+)\"?/i);a.href=url;a.download=m?m[1]:'MailGenix-Draft.eml';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),2000)}catch(e){alert(e.message)}finally{q('generateDraftBtn').textContent='Generate Draft';refreshGenerate();}
  });
  updateFloors();applyScope();
}
