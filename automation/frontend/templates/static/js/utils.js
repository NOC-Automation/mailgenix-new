// static/js/utils.js

export function getCsrfToken() {
  return document.querySelector('[name="csrfmiddlewaretoken"]')?.value || '';
}
