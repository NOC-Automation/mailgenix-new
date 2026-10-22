// static/js/tenantList/tenantAdd/init.js

console.log('[TenantAdd] tenantAdd/init.js loaded');

import * as api from '../api.js';

import { findDom } from './dom.js';
import {
  handleSubmitFailure,
  submitPayload,
  confirmAndRun,
} from './submit.js';
import { prefillTenantEdit } from './prefill.js';
import { attachDynamicAr } from './arRows.js';
import { attachMailingListToggle, prefillMailingList } from './mailingList.js';

import { attachFloorAutocomplete } from './autocomplete/floor.js';
import { attachRackAutocomplete } from './autocomplete/rack.js';
import { attachCustomerAutocomplete } from './autocomplete/customer.js';

export async function initTenantAdd() {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get('mode') ?? 'create';
  const customerId = parseInt(params.get('customer_id') ?? '0', 10) || null;
  const groupId = parseInt(params.get('group_id') ?? '0', 10) || null;
  const oldRackId = parseInt(params.get('rack_id') ?? '0', 10) || null;

  const dom = findDom();
  if (!dom.form) {
    console.error('[TenantAdd] form not found');
    return;
  }

  attachDynamicAr(dom);
  attachMailingListToggle(dom);
  attachFloorAutocomplete(dom);
  attachRackAutocomplete(dom);
  attachCustomerAutocomplete(dom);

  if (mode === 'edit' && customerId) {
    await prefillTenantEdit({
      dom,
      api,
      customerId,
      groupId,
      oldRackId,
      prefillMailingList,
    });
  }

  const hasModal =
    !!document.getElementById('tenantConfirmModal') &&
    !!document.getElementById('tenantConfirmMessage') &&
    !!document.getElementById('tenantConfirmYes');

  dom.form.addEventListener('submit', (e) => {
    e.preventDefault();

    if (dom.form.checkValidity && !dom.form.checkValidity()) {
      dom.form.reportValidity && dom.form.reportValidity();
      return;
    }

    const isEdit = mode === 'edit' && !!customerId;
    const confirmMsg = isEdit
      ? 'Apakah Anda yakin ingin mengedit data ini?'
      : 'Apakah Anda yakin ingin menambahkan customer ini?';

    confirmAndRun({
      hasModal,
      message: confirmMsg,
      yesLabel: 'Ya',
      run: async () => {
        try {
          await submitPayload({
            mode,
            dom,
            api,
            customerId,
            groupId,
            oldRackId,
          });
        } catch (err) {
          handleSubmitFailure(
            err,
            dom,
            isEdit ? 'Gagal menyimpan perubahan.' : 'Gagal menambah data.'
          );
        }
      },
    });
  });

  // fallback: tombol submit UI -> submit form
  if (dom.submitBtn && !dom.submitBtn.dataset.bound) {
    dom.submitBtn.dataset.bound = '1';
    dom.submitBtn.addEventListener('click', () => {
      if (typeof dom.form.requestSubmit === 'function') {
        dom.form.requestSubmit();
      } else {
        dom.form.dispatchEvent(
          new Event('submit', { cancelable: true, bubbles: true })
        );
      }
    });
  }
}

// Auto-run
if (typeof window !== 'undefined' && !window.__TENANT_ADD_INIT__) {
  window.__TENANT_ADD_INIT__ = true;
  try {
    initTenantAdd();
  } catch (e) {
    console.error('[TenantAdd] auto init error:', e);
  }
}
