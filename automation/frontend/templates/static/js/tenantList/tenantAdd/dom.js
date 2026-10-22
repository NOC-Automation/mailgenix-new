// static/js/tenantList/tenantAdd/dom.js

const q = (sel) => document.querySelector(sel);
const qa = (sel) => Array.from(document.querySelectorAll(sel));

export function pick(...candidates) {
  for (const c of candidates) {
    if (!c) continue;
    const el = typeof c === 'string' ? q(c) : c;
    if (el) return el;
  }
  return null;
}

export function pickAll(...candidates) {
  for (const c of candidates) {
    if (!c) continue;
    const els = typeof c === 'string' ? qa(c) : Array.isArray(c) ? c : [];
    if (els && els.length) return els;
  }
  return [];
}

export function findDom() {
  const form = pick('[data-hook="form"]', '#tenantAddForm', 'form');

  return {
    // ---------- Root ----------
    form,
    submitBtn: pick('[data-hook="submit"]', '#tenantAddSubmit', 'button[type="submit"]'),

    // ---------- Primary fields ----------
    customerName: pick('[data-hook="customer_name"]', '[name="customer_name"]', '#addCustomerName'),
    customerSite: pick('[data-hook="customer_site"]', '[name="customer_site"]', '#addCustomerSite'),
    validity: pick('[data-hook="validity"]', '[name="validity"]', '#addValidity'),
    date: pick('[data-hook="date"]', '[name="date"]', '#addDate'),

    // ---------- Hidden / compatibility selects ----------
    floorLevel: pick('#addFloorLevel'),
    rackLocation: pick('[name="rack_location"]', '#addRackLocation'),

    // ---------- Visible autocomplete inputs ----------
    floorInput: pick('#floorLevelInput'),
    rackInput: pick('#rackLocationInput'),

    // ---------- Customer existing state ----------
    existingCustomerId: pick('#existingCustomerId'),
    existingGroupId: pick('#existingGroupId'),

    // ---------- Suggestion UI ----------
    customerSuggestBox: pick('#customerSuggest'),
    customerSuggestList: pick('#customerSuggestList'),

    floorSuggestBox: pick('#floorLevelSuggest'),
    floorSuggestList: pick('#floorLevelSuggestList'),

    rackSuggestBox: pick('#rackLocationSuggest'),
    rackSuggestList: pick('#rackLocationSuggestList'),

    // ---------- Mailing list ----------
    mailingListContainer: pick('#mailingListContainer'),
    mailingListInput: pick('#mailingListInput'),
    btnAddMailingList: pick('#btnAddMailingList'),

    // ---------- Optional dynamic AR fallback ----------
    arList: pick('#arList', '[data-ar-list]', '[data-hook="ar_list"]'),
    addArBtn: pick('#addArBtn', '[data-add-ar]', '[data-hook="add_ar"]'),
    arTemplateSel: '#arRowTemplate',
  };
}

