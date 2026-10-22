// static/js/tenantList/tenantAdd/autocomplete/rack.js

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
  ensureSelectValue,
} from './shared.js';

export function attachRackAutocomplete(dom) {
  if (!dom.rackInput || !dom.rackSuggestBox || !dom.rackSuggestList) return;

  if (dom.rackInput.dataset.bound === '1') return;
  dom.rackInput.dataset.bound = '1';

  let rackItems = [];
  let rackActive = -1;

  const rackPick = (picked) => {
    dom.rackInput.value = picked.name;
    ensureSelectValue(dom.rackLocation, picked.id, picked.name);

    rackItems = [];
    rackActive = -1;
    clearSuggest(dom.rackSuggestList, dom.rackSuggestBox);
  };

  const doSearch = debounce(async () => {
    const qText = normalizeText(dom.rackInput.value);
    const floorId = dom.floorLevel?.value ? Number(dom.floorLevel.value) : null;

    if (!floorId) {
      const help = document.getElementById('addRackHelp');
      if (help) {
        help.textContent = 'Silakan pilih Floor Level terlebih dahulu.';
        help.classList.remove('hidden');
      }

      rackItems = [];
      rackActive = -1;
      clearSuggest(dom.rackSuggestList, dom.rackSuggestBox);
      return;
    } else {
      const help = document.getElementById('addRackHelp');
      if (help) help.classList.add('hidden');
    }

    if (qText.length === 0) {
      rackItems = [];
      rackActive = -1;
      clearSuggest(dom.rackSuggestList, dom.rackSuggestBox);
      if (dom.rackLocation) dom.rackLocation.value = '';
      return;
    }

    const url = `/api/racks/autocomplete/?floor_id=${encodeURIComponent(String(floorId))}&q=${encodeURIComponent(qText)}`;

    try {
      const items = await fetchJson(url);
      rackItems = items || [];
      rackActive = rackItems.length ? 0 : -1;

      renderSuggest(
        dom.rackSuggestList,
        dom.rackSuggestBox,
        rackItems,
        rackPick,
        rackActive
      );
      applyActiveToList(dom.rackSuggestList, rackActive);
    } catch (e) {
      rackItems = [];
      rackActive = -1;
      clearSuggest(dom.rackSuggestList, dom.rackSuggestBox);
      console.warn('[TenantAdd] rack autocomplete error:', e);
    }
  }, 250);

  dom.rackInput.addEventListener('input', doSearch);
  dom.rackInput.addEventListener('focus', doSearch);

  dom.rackInput.addEventListener('blur', () => {
    setTimeout(() => closeSuggest(dom.rackSuggestBox), 120);
  });

  bindSuggestHover(
    dom.rackSuggestList,
    () => rackActive,
    (idx) => {
      rackActive = idx;
    }
  );

  bindSuggestOutsideClose(dom.rackInput, dom.rackSuggestBox);

  bindSuggestKeyboard({
    inputEl: dom.rackInput,
    listEl: dom.rackSuggestList,
    box: dom.rackSuggestBox,
    getItems: () => rackItems,
    getActive: () => rackActive,
    setActive: (idx) => {
      rackActive = idx;
    },
    onPick: rackPick,
    onClear: () => {
      rackItems = [];
      rackActive = -1;
      clearSuggest(dom.rackSuggestList, dom.rackSuggestBox);
    },
  });
}
