// static/js/tenantList/tenantAdd/autocomplete/customer.js

import { showToast } from '../../utils.js';
import { setArRows } from '../arRows.js';
import {
  debounce,
  fetchJson,
  closeSuggest,
  clearSuggest,
  renderSuggest,
  applyActiveToList,
  bindSuggestHover,
  bindSuggestOutsideClose,
  bindSuggestKeyboard,
  normalizeText,
} from './shared.js';

export function attachCustomerAutocomplete(dom, { prefillMailingList } = {}) {
  if (!dom.customerName || !dom.customerSuggestBox || !dom.customerSuggestList) return;

  if (dom.customerName.dataset.bound === '1') return;
  dom.customerName.dataset.bound = '1';

  let items = [];
  let active = -1;

  const pickCustomer = async (picked) => {
    dom.customerName.value = picked.name;

    if (dom.existingCustomerId) {
      dom.existingCustomerId.value = String(picked.id);
    }

    try {
      const data = await fetchJson(`/api/customers/${picked.id}/prefill/`);

      if (dom.existingGroupId) {
        dom.existingGroupId.value = String(data.group_id || '');
      }

      if (dom.validity) dom.validity.value = data.validity || '';
      if (dom.date) dom.date.value = data.date || '';

      const ars = Array.isArray(data.ars) ? data.ars : [];
      setArRows(dom, ars);

      if (typeof prefillMailingList === 'function') {
        prefillMailingList(dom, data.mailing_list);
      }
    } catch (e) {
      console.warn('[TenantAdd] customer prefill failed:', e);
      showToast('Gagal memuat data customer.', 'error');
    }

    items = [];
    active = -1;
    clearSuggest(dom.customerSuggestList, dom.customerSuggestBox);
  };

  const doSearch = debounce(async () => {
    const qText = normalizeText(dom.customerName.value);

    if (dom.existingCustomerId) dom.existingCustomerId.value = '';
    if (dom.existingGroupId) dom.existingGroupId.value = '';

    if (qText.length < 2) {
      clearSuggest(dom.customerSuggestList, dom.customerSuggestBox);
      return;
    }

    try {
      const res = await fetchJson(`/api/customers/autocomplete/?q=${encodeURIComponent(qText)}`);
      items = Array.isArray(res) ? res : [];
      active = items.length ? 0 : -1;

      renderSuggest(
        dom.customerSuggestList,
        dom.customerSuggestBox,
        items,
        pickCustomer,
        active
      );
      applyActiveToList(dom.customerSuggestList, active);
    } catch (e) {
      clearSuggest(dom.customerSuggestList, dom.customerSuggestBox);
    }
  }, 250);

  dom.customerName.addEventListener('input', doSearch);
  dom.customerName.addEventListener('focus', doSearch);

  dom.customerName.addEventListener('blur', () => {
    setTimeout(() => closeSuggest(dom.customerSuggestBox), 120);
  });

  bindSuggestHover(
    dom.customerSuggestList,
    () => active,
    (idx) => {
      active = idx;
    }
  );

  bindSuggestOutsideClose(dom.customerName, dom.customerSuggestBox);

  bindSuggestKeyboard({
    inputEl: dom.customerName,
    listEl: dom.customerSuggestList,
    box: dom.customerSuggestBox,
    getItems: () => items,
    getActive: () => active,
    setActive: (idx) => {
      active = idx;
    },
    onPick: pickCustomer,
    onClear: () => {
      items = [];
      active = -1;
      clearSuggest(dom.customerSuggestList, dom.customerSuggestBox);
    },
  });
}
