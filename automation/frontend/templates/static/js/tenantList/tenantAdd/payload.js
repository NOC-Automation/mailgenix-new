// static/js/tenantList/tenantAdd/payload.js

import { pickAll } from './dom.js';

export function collectPayload(dom) {
  const rackSel = dom.rackLocation;
  const rackId = rackSel?.value ? Number(rackSel.value) : null;

  const rackNameFromInput = dom.rackInput?.value?.trim() ?? '';
  const rackTextFromSelect =
    rackSel?.options?.[rackSel.selectedIndex]?.textContent?.trim() ?? '';
  const rackName = rackNameFromInput || rackTextFromSelect;

  const floorId = dom.floorLevel?.value ? Number(dom.floorLevel.value) : null;
  const floorName = dom.floorInput?.value?.trim() ?? '';



  const base = {
    customer_name: dom.customerName?.value?.trim() ?? '',
    customer_site: dom.customerSite?.value?.trim() ?? '',

    // tampilan / display
    rack_location: rackName,

    // hidden/select compatibility
    rack_id: rackId,
    floor_level: floorId,

    validity: dom.validity?.value ?? null,
    date: dom.date?.value ?? null,

    // create-if-not-exists support
    floor_name: floorName,
    rack_name: rackName,

    // Optional mailing-list membership for the ARs in this AR Group/location.
    // Multiple values are separated with semicolon, e.g. "Customer Escalation; Facility Contact".
    mailing_list: dom.mailingListInput?.value?.trim() ?? '',
  };

  const rows = pickAll('.ar-row');
  const ars = rows.map((row) => ({
    id: row.querySelector('.ar-id')?.value ?? undefined,
    authorized_name: row.querySelector('.ar-name')?.value ?? '',
    email: row.querySelector('.ar-email')?.value ?? '',
    phone: row.querySelector('.ar-phone')?.value ?? '',
  }));

  return { ...base, ars };
}
