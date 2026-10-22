// static/js/tenantList/data.js

function normalizeText(value) {
  return (value || '').toString().trim().toLowerCase();
}

function arrayToSearchText(values) {
  if (!Array.isArray(values)) return '';
  return values
    .map((v) => normalizeText(v))
    .filter(Boolean)
    .join(' ');
}

function buildRowSearchText(item) {
  return [
    normalizeText(item.site_location),
    normalizeText(item.rack_location),
    normalizeText(item.customer_name),

    // legacy single-value fields
    normalizeText(item.authorized_person),
    normalizeText(item.email),
    normalizeText(item.phone),
    normalizeText(item.date),
    normalizeText(item.validity),

    // modern grouped fields
    arrayToSearchText(item.authorized_person_list),
    arrayToSearchText(item.email_list),
    arrayToSearchText(item.phone_list),
    arrayToSearchText(item.date_list),
    arrayToSearchText(item.validity_list),
  ]
    .filter(Boolean)
    .join(' ');
}

export function filterData(store) {
  // serverMode=true => data sudah difilter/paginate oleh server
  if (store.state?.serverMode) {
    return Array.isArray(store.state.rows) ? store.state.rows : [];
  }

  const q = normalizeText(store.state.search);
  const src = Array.isArray(store.state.rows) ? store.state.rows : [];

  if (!q) return [...src];

  return src.filter((item) => buildRowSearchText(item).includes(q));
}

export function paginate(
  arr,
  page,
  perPage,
  grandTotal = null,
  { serverMode = false } = {}
) {
  const safeArr = Array.isArray(arr) ? arr : [];
  const per = Math.max(1, Number(perPage) || 10);

  const total =
    typeof grandTotal === 'number' && grandTotal >= 0
      ? grandTotal
      : safeArr.length;

  const totalPages = Math.max(1, Math.ceil(total / per));
  const current = Math.min(Math.max(1, Number(page) || 1), totalPages);

  // serverMode => arr sudah satu halaman dari server
  const slice = serverMode
    ? safeArr
    : safeArr.slice((current - 1) * per, current * per);

  const start = total === 0 ? 0 : (current - 1) * per + 1;
  const end = total === 0 ? 0 : Math.min(start + slice.length - 1, total);

  return { slice, total, current, totalPages, start, end };
}
