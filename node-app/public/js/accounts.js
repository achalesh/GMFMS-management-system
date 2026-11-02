const search = document.querySelector('#account-search');
const accounts = [...document.querySelectorAll('[data-account]')];
function filterAccounts() {
  const term = search.value.trim().toLocaleLowerCase();
  let count = 0;
  for (const account of accounts) {
    account.hidden = !account.querySelector('summary').textContent.toLocaleLowerCase().includes(term);
    if (!account.hidden) count++;
  }
  document.querySelector('#account-count').textContent = `${count} accounts shown`;
}
search?.addEventListener('input', filterAccounts);
if (search) filterAccounts();
for (const form of document.querySelectorAll('[data-role-assignment]')) {
  const role = form.elements.role, scope = form.elements.scope;
  const district = form.elements.district, block = form.elements.block;
  function update() {
    const fixed = {ADMIN: 'STATE', SUPER_ADMIN: 'STATE', STATE_ADMIN: 'STATE', DISTRICT_ADMIN: 'DISTRICT', DISTRICT_COORDINATOR: 'DISTRICT', BLOCK_COORDINATOR: 'BLOCK'}[role.value];
    for (const option of scope.options) option.disabled = Boolean(fixed && option.value !== fixed);
    if (fixed) scope.value = fixed;
    district.disabled = scope.value === 'STATE';
    district.required = !district.disabled;
    if (district.disabled) district.value = '';
    block.disabled = scope.value !== 'BLOCK';
    block.required = !block.disabled;
    for (const option of block.options) {
      option.hidden = Boolean(option.value && option.dataset.district !== district.value);
      option.disabled = option.hidden;
    }
    if (block.disabled || block.selectedOptions[0]?.disabled) block.value = '';
  }
  for (const field of [role, scope, district]) field.addEventListener('change', update);
  update();
}
