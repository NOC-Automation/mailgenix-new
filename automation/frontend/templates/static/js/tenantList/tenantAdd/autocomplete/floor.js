// static/js/tenantList/tenantAdd/autocomplete/floor.js

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

export function attachFloorAutocomplete(dom) {
  if (!dom.floorInput || !dom.floorSuggestBox || !dom.floorSuggestList) return;

  if (dom.floorInput.dataset.bound === '1') return;
  dom.floorInput.dataset.bound = '1';

  let floorItems = [];
  let floorActive = -1;

  const floorPick = (picked) => {
    dom.floorInput.value = picked.name;
    ensureSelectValue(dom.floorLevel, picked.id, picked.name);

    // reset rack setiap kali floor berubah
    if (dom.rackInput) dom.rackInput.value = '';
    if (dom.rackLocation) dom.rackLocation.value = '';

    floorItems = [];
    floorActive = -1;
    clearSuggest(dom.floorSuggestList, dom.floorSuggestBox);
  };

  const doSearch = debounce(async () => {
    const qText = normalizeText(dom.floorInput.value);

    // ambil siteId dari selected option dataset
    const opt = dom.customerSite?.selectedOptions?.[0];
    const siteId = opt?.dataset?.siteId;

    if (!siteId) {
      clearSuggest(dom.floorSuggestList, dom.floorSuggestBox);
      return;
    }

    if (qText.length === 0) {
      clearSuggest(dom.floorSuggestList, dom.floorSuggestBox);

      if (dom.floorLevel) dom.floorLevel.value = '';
      if (dom.rackInput) dom.rackInput.value = '';
      if (dom.rackLocation) dom.rackLocation.value = '';
      return;
    }

    const url = `/api/floors/autocomplete/?site_id=${encodeURIComponent(siteId)}&q=${encodeURIComponent(qText)}`;

    try {
      const items = await fetchJson(url);
      floorItems = items || [];
      floorActive = floorItems.length ? 0 : -1;

      renderSuggest(
        dom.floorSuggestList,
        dom.floorSuggestBox,
        floorItems,
        floorPick,
        floorActive
      );
      applyActiveToList(dom.floorSuggestList, floorActive);
    } catch (e) {
      clearSuggest(dom.floorSuggestList, dom.floorSuggestBox);
      console.warn('[TenantAdd] floor autocomplete error:', e);
    }
  }, 250);

  dom.floorInput.addEventListener('input', doSearch);
  dom.floorInput.addEventListener('focus', doSearch);

  dom.floorInput.addEventListener('blur', () => {
    setTimeout(() => closeSuggest(dom.floorSuggestBox), 120);
  });

  // Jika site berubah, reset floor & rack
  if (dom.customerSite && !dom.customerSite.dataset._floorResetBound) {
    dom.customerSite.dataset._floorResetBound = '1';

    dom.customerSite.addEventListener('change', () => {
      if (dom.floorInput) dom.floorInput.value = '';
      if (dom.floorLevel) dom.floorLevel.value = '';
      if (dom.rackInput) dom.rackInput.value = '';
      if (dom.rackLocation) dom.rackLocation.value = '';
      clearSuggest(dom.floorSuggestList, dom.floorSuggestBox);
    });
  }

  bindSuggestHover(
    dom.floorSuggestList,
    () => floorActive,
    (idx) => {
      floorActive = idx;
    }
  );

  bindSuggestOutsideClose(dom.floorInput, dom.floorSuggestBox);

  bindSuggestKeyboard({
    inputEl: dom.floorInput,
    listEl: dom.floorSuggestList,
    box: dom.floorSuggestBox,
    getItems: () => floorItems,
    getActive: () => floorActive,
    setActive: (idx) => {
      floorActive = idx;
    },
    onPick: floorPick,
    onClear: () => {
      floorItems = [];
      floorActive = -1;
      clearSuggest(dom.floorSuggestList, dom.floorSuggestBox);
    },
  });
}
