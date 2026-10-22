// static/js/tenantList/renderers.js
import { escapeHTML, highlightHTML } from './utils.js';

console.log('[TenantList] renderers.js loaded');

// Ditentukan oleh template:
// <script>window.IS_ADMIN = {{ is_admin|yesno:"true,false" }};</script>
const IS_ADMIN =
  typeof window !== 'undefined' && window.IS_ADMIN === true;

/**
 * Tombol aksi per baris (Customer × Rack).
 * - Edit: redirect ke /tenants/add/?mode=edit&customer_id=...
 * - Delete Row: putus relasi Customer ↔ Rack untuk baris ini saja
 */
function groupActionButtons(row) {
  if (!IS_ADMIN) return '';
  const c = escapeHTML(String(row.customer_id ?? ''));
  const r = escapeHTML(String(row.rack_id ?? ''));
  const g = escapeHTML(String(row.group_id ?? ''));
  return `
    <div class="flex items-center gap-3">
      <!-- Edit  -->
      <button class="tenant-group-edit" type="button" aria-label="Edit Group"
              data-action="group-edit" data-id="${c}" data-rack-id="${r}" data-group-id="${g}">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
             class="h-5 w-5 text-indigo-600 group-hover:text-indigo-700 pointer-events-none"
             fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 21l3.75-.75L20 7.06a2.12 2.12 0 10-3-3L3.75 17.25 3 21z"/>
          <path d="M14.5 5.5l4 4"/>
        </svg>
      </button>
      <!-- Delete  -->
      <button class="tenant-group-delete" type="button" aria-label="Delete Group"
              data-action="row-delete" data-id="${c}" data-rack-id="${r}">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
             class="h-5 w-5 text-rose-600 group-hover:text-rose-700 pointer-events-none"
             fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 6h18"/>
          <path d="M8 6V4.8A1.8 1.8 0 019.8 3h4.4A1.8 1.8 0 0116 4.8V6"/>
          <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
          <path d="M10 11v6M14 11v6"/>
        </svg>
      </button>
    </div>
  `;
}

/**
 * Render stack nilai (array atau tunggal) dengan highlight.
 */
function renderStackHL(values, q) {
  if (!Array.isArray(values)) {
    return `<div>${highlightHTML(values ?? '-', q)}</div>`;
  }

  return `
    <div class="flex flex-col gap-1">
      ${values.map((v) => `<div>${highlightHTML(v ?? '-', q)}</div>`).join('')}
    </div>
  `;
}

/**
 * Render tabel desktop
 */
export function renderTable(tableBody, rows, q = '') {
  if (!tableBody) return;

  const totalCols = IS_ADMIN ? 9 : 8;

  if (!rows || rows.length === 0) {
    tableBody.innerHTML = `
      <tr>
        <td class="py-6 text-center text-slate-500" colspan="${totalCols}">
          ${
            q
              ? `Tidak ada hasil untuk "<mark>${escapeHTML(q)}</mark>"`
              : 'Tidak ada data'
          }
        </td>
      </tr>
    `;
    return;
  }

  const html = (rows ?? [])
    .map((row) => {
      const site = highlightHTML(row.site_location ?? '-', q);
      const rack = highlightHTML(row.rack_location ?? '-', q);
      const cust = highlightHTML(row.customer_name ?? '-', q);

      const auth = renderStackHL(
        row.authorized_person_list ?? row.authorized_person,
        q
      );
      const email = renderStackHL(row.email_list ?? row.email, q);
      const phone = renderStackHL(row.phone_list ?? row.phone, q);
      const date = renderStackHL(row.date_list ?? row.date, q);
      const val = renderStackHL(row.validity_list ?? row.validity, q);

      const actionTd = IS_ADMIN
        ? `<td class="align-top">${groupActionButtons(row)}</td>`
        : '';

      return `
        <tr>
          <td class="align-top">${site}</td>
          <td class="align-top">${rack}</td>
          <td class="align-top">${cust}</td>
          <td class="align-top">${auth}</td>
          <td class="align-top">${email}</td>
          <td class="align-top">${phone}</td>
          <td class="align-top">${date}</td>
          <td class="align-top">${val}</td>
          ${actionTd}
        </tr>
      `;
    })
    .join('');

  tableBody.innerHTML = html;
}

/**
 * Render kartu mobile
 */
export function renderCards(cardsContainer, rows, q = '') {
  if (!cardsContainer) return;

  const html = (rows ?? [])
    .map((row) => {
      const site = highlightHTML(row.site_location ?? '-', q);
      const name = highlightHTML(row.customer_name ?? '-', q);
      const rack = highlightHTML(row.rack_location ?? '-', q);

      const auth = row.authorized_person_list ?? [row.authorized_person];
      const email = row.email_list ?? [row.email];
      const phone = row.phone_list ?? [row.phone];
      const date = row.date_list ?? [row.date];
      const val = row.validity_list ?? [row.validity];

      const lineCount = Math.max(
        auth?.length || 0,
        email?.length || 0,
        phone?.length || 0,
        date?.length || 0,
        val?.length || 0
      );

      const lines = Array.from({ length: lineCount }, (_, i) => `
        <div class="text-sm leading-5">
          <div class="font-medium">${highlightHTML(auth?.[i] ?? '-', q)}</div>
          <div class="text-slate-500">
            ${highlightHTML(email?.[i] ?? '-', q)} • ${highlightHTML(phone?.[i] ?? '-', q)}
          </div>
          <div class="text-slate-500">
            ${highlightHTML(date?.[i] ?? '', q)} • ${highlightHTML(val?.[i] ?? '-', q)}
          </div>
        </div>
      `).join('');

      const actions = IS_ADMIN ? `
      <div class="mt-2 flex gap-2">
        <button 
	type="button" 
	data-action="group-edit" 
	data-id="${escapeHTML(String(row.customer_id ?? ''))}"
	data-rack-id="${escapeHTML(String(row.rack_id ?? ''))}"
	data-group-id="${escapeHTML(String(row.group_id ?? ''))}"
	class="px-2 py-1 rounded border text-sm">
		Edit
	</button>
        <button 
	type="button" 
	data-action="row-delete" 
	data-id="${escapeHTML(String(row.customer_id ?? ''))}"
	data-rack-id="${escapeHTML(String(row.rack_id ?? ''))}"
	class="px-2 py-1 rounded border text-sm">
		Delete
	</button>
      </div>
    ` : '';

    return `
      <div class="rounded border p-3 space-y-2">
        <div class="font-semibold">${name}</div>
        <div class="text-sm text-gray-600">${rack}</div>
        <div class="divide-y">${lines}</div>
        ${actions}
      </div>
    `;
  }).join('');

  cardsContainer.innerHTML = html;
}

/**
 * Render pagination
 */
export function renderPagination(paginationEl, current, totalPages) {
  if (!paginationEl) return;

  if (!totalPages || totalPages <= 1) {
    paginationEl.innerHTML = '';
    return;
  }

  const buttons = [];

  const makeButton = (label, page, disabled = false, active = false) => `
    <button
      type="button"
      class="h-8 min-w-[2rem] rounded border px-3 text-sm ${
        active
          ? 'border-sky-600 bg-sky-600 text-white'
          : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}"
      data-page="${page}"
      ${disabled ? 'disabled' : ''}>
      ${label}
    </button>
  `;

  const maxButtons = 5;
  let start = Math.max(1, current - Math.floor(maxButtons / 2));
  let end = start + maxButtons - 1;

  if (end > totalPages) {
    end = totalPages;
    start = Math.max(1, end - maxButtons + 1);
  }

  buttons.push(makeButton('Prev', 'prev', current <= 1));

  for (let p = start; p <= end; p++) {
    buttons.push(makeButton(String(p), String(p), false, p === current));
  }

  buttons.push(makeButton('Next', 'next', current >= totalPages));

  paginationEl.innerHTML = buttons.join('');
}

/**
 * Render info bar
 */
export function renderInfo(infoEl, start, end, total) {
  if (!infoEl) return;

  if (total === 0) {
    infoEl.textContent = 'Showing 0 to 0 of 0 entries';
    return;
  }

  infoEl.textContent = `Showing ${start} to ${end} of ${total} entries`;
}
