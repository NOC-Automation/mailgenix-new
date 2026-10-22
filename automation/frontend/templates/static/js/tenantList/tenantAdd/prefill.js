// static/js/tenantList/tenantAdd/prefill.js

import { showToast } from '../utils.js';
import { ensureSelectValue } from './autocomplete/shared.js';
import { setArRows } from './arRows.js';

export async function prefillTenantEdit({
  dom,
  api,
  customerId,
  groupId,
  oldRackId,
  prefillMailingList,
}) {
  try {
    const data = await api.fetchGroup(customerId, groupId, oldRackId);

    if (dom.customerName) dom.customerName.value = data.customer_name ?? '';
    if (dom.customerSite) dom.customerSite.value = data.customer_site ?? '';
    if (dom.validity) dom.validity.value = data.validity ?? '';
    if (dom.date) dom.date.value = data.date ?? '';

    // Persist the authoritative identifiers returned by the backend.
    // This makes edit safe even when an old/bookmarked URL only contains customer_id.
    if (dom.existingCustomerId) dom.existingCustomerId.value = String(data.customer_id ?? customerId ?? '');
    if (dom.existingGroupId) dom.existingGroupId.value = String(data.group_id ?? groupId ?? '');
    if (dom.rackLocation?.dataset) dom.rackLocation.dataset.editRackId = String(data.rack_id ?? oldRackId ?? '');

    const ars = Array.isArray(data.ars) ? data.ars : [];
    setArRows(dom, ars);

    if (typeof prefillMailingList === 'function') {
      prefillMailingList(dom, data.mailing_list);
    }

    // Prefill Floor & Rack
    if (dom.floorInput) dom.floorInput.value = data.floor_level ?? '';
    ensureSelectValue(dom.floorLevel, data.floor_id, data.floor_level);

    if (dom.rackInput) dom.rackInput.value = data.rack_location ?? '';
    ensureSelectValue(dom.rackLocation, data.rack_id, data.rack_location);

    document.dispatchEvent(new Event('tenantAddPrefilled'));
  } catch (e) {
    console.error('[TenantAdd] Prefill failed:', e);
    showToast('Gagal memuat data edit.', 'error');
  }
}
