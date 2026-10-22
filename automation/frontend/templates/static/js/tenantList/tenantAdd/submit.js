// static/js/tenantList/tenantAdd/submit.js

import { showToast, showConfirm } from '../utils.js';
import { collectPayload } from './payload.js';
import {
  markRackInvalid,
  markCustomerInvalid,
  validatePayloadBeforeSubmit,
} from './validation.js';

export function handleSubmitFailure(err, dom, fallbackMsg = 'Terjadi kesalahan.') {
  console.error('[TenantAdd] submit failed:', err);

  const msg = err?.message || fallbackMsg;
  showToast(msg, 'error');

  if (/pilih\s*rack/i.test(msg)) {
    markRackInvalid(dom, msg);
  }

  if (/customer\s*name/i.test(msg)) {
    markCustomerInvalid(dom, msg);
  }
}

export async function submitPayload({
  mode,
  dom,
  api,
  customerId,
  groupId,
  oldRackId,
}) {
  const payload = collectPayload(dom);

  // Centralized validation
  validatePayloadBeforeSubmit(payload, dom);

  if (mode === 'edit' && customerId) {
    const resolvedGroupId =
      groupId ||
      (dom.existingGroupId?.value ? Number(dom.existingGroupId.value) : null);
    const resolvedOldRackId =
      oldRackId ||
      (dom.rackLocation?.dataset?.editRackId
        ? Number(dom.rackLocation.dataset.editRackId)
        : null) ||
      (payload.rack_id ? Number(payload.rack_id) : null);

    if (!resolvedGroupId) {
      throw new Error('Group AR untuk data ini tidak ditemukan. Silakan buka kembali data dari Tenant List dan coba Edit lagi.');
    }

    payload.group_id = resolvedGroupId;
    payload.old_rack_id = resolvedOldRackId;

    await api.saveGroup(customerId, payload);

    try {
      sessionStorage.setItem('tenantToastMessage', 'Data berhasil diubah.');
      sessionStorage.setItem('tenantToastType', 'success');
    } catch (_) {}

    window.location.href = '/';
    return;
  }

  // Default: create
  await api.createGroup(payload);

  try {
    sessionStorage.setItem('tenantToastMessage', 'Tenant berhasil ditambahkan.');
    sessionStorage.setItem('tenantToastType', 'success');
  } catch (_) {}

  window.location.href = '/';
}

export function confirmAndRun({ hasModal, message, yesLabel = 'Ya', run }) {
  if (hasModal) {
    showConfirm(message, run, yesLabel);
    return;
  }

  if (window.confirm(message)) {
    run();
  }
}
