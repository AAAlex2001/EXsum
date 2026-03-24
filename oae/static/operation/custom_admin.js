(function () {
  const originalSetItem = localStorage.setItem;
  const originalRemoveItem = localStorage.removeItem;
  localStorage.setItem = function (key, value) {
    const event = new CustomEvent('localstorage-change', {
      detail: { key, value }
    });
    window.dispatchEvent(event);
    return originalSetItem.apply(this, arguments);
  };
  localStorage.removeItem = function (key) {
    const event = new CustomEvent('localstorage-change', {
      detail: { key, value: null }
    });
    window.dispatchEvent(event);
    return originalRemoveItem.apply(this, arguments);
  };
  document.addEventListener('DOMContentLoaded', function () {
    window.addEventListener('localstorage-change', (e) => {
      const { key, value } = e.detail;
      if (key && value === '"dark"') {
        document.documentElement.style.setProperty('--color-table', 'rgb(var(--color-font-default-dark)/var(--tw-text-opacity,1))')
      } else {
        document.documentElement.style.setProperty('--color-table', '#101827')
      }
    });
    const adminTheme = window.localStorage.getItem('adminTheme');
    if (adminTheme && adminTheme === '"dark"') {
      document.documentElement.style.setProperty('--color-table', 'rgb(var(--color-font-default-dark)/var(--tw-text-opacity,1))')
    } else {
      document.documentElement.style.setProperty('--color-table', '#101827')
    }
    // in_exes one
    const inExesOne = JSON.parse(window.localStorage.getItem('in_exes'));
    const listIncomeExpenseOne = document.querySelectorAll('tbody.has_original');
    for (let i = 0; i < inExesOne.length; i++) {
      const exes = inExesOne[i];
      for (let incomeExpense of listIncomeExpenseOne) {
        const incomeExpenseId = incomeExpense.querySelector('tr>td>p>span');
        if (+exes.id === +incomeExpenseId.textContent.trim()) {
          // icome
          const income = incomeExpense.querySelector('tr>[data-label="Счет прихода"]>div>div>div>div>select');
          income.addEventListener('mouseover', (e) => handleIncomExpense(income, {
            before: exes.income_before,
            after: exes.income_after,
          }, e));
          income.addEventListener('mouseout', (e) => handleIncomExpense(income, {
            before: exes.income_before,
            after: exes.income_after,
          }, e));
          // expense
          const expense = incomeExpense.querySelector('tr>[data-label="Счет расхода"]>div>div>div>div>select');
          expense.addEventListener('mouseover', (e) => handleIncomExpense(expense, {
            before: exes.expense_before,
            after: exes.expense_after,
          }, e));
          expense.addEventListener('mouseout', (e) => handleIncomExpense(expense, {
            before: exes.expense_before,
            after: exes.expense_after,
          }, e));
        }
      }

    }

    const inExes = JSON.parse(window.localStorage.getItem('in_exes'));
    const listIncomeExpense = document.querySelectorAll('table#result_list>tbody>tr');
    document.querySelector('table#result_list>thead>tr>th>div>div>label>input') &&
      document.querySelector('table#result_list>thead>tr>th>div>div>label>input').addEventListener('click', () => checkSelectItem(listIncomeExpense, inExes));
    for (let incomeExpense of listIncomeExpense) {
      const checkbox = incomeExpense.querySelector('td>input');
      checkbox.addEventListener('click', () => checkSelectItem(listIncomeExpense, inExes));
      const incomeExpenseId = incomeExpense.querySelector('[data-label="ID"]');
      for (let i = 0; i < inExes.length; i++) {
        const exes = inExes[i];
        if (+exes.id === +incomeExpenseId.textContent.trim()) {
          const income = incomeExpense.querySelector('[data-label="Счет прихода"]');
          income.querySelector('a').addEventListener('mouseover', (e) => handleIncomExpense(income, {
            before: exes.income_before,
            after: exes.income_after,
          }, e, '--list'));
          income.querySelector('a').addEventListener('mouseout', (e) => handleIncomExpense(income, {
            before: exes.income_before,
            after: exes.income_after,
          }, e, '--list'));
          const expense = incomeExpense.querySelector('[data-label="Счет расхода"]');
          expense.querySelector('a').addEventListener('mouseover', (e) => handleIncomExpense(expense, {
            before: exes.expense_before,
            after: exes.expense_after,
          }, e, '--list'));
          expense.querySelector('a').addEventListener('mouseout', (e) => handleIncomExpense(expense, {
            before: exes.expense_before,
            after: exes.expense_after,
          }, e, '--list'));
        }
      }
    }
    // ------------------------------------------------------autocomplete---------------------------
    const autocomplete = window.localStorage.getItem('autocomplete');
    // hidden button add another field
    setTimeout(() => {
      document.querySelector('.template>.add-row').style.setProperty('display', 'none');
    }, 1000);
    // if (true) {
    if (autocomplete === '"True"') {
      // let isCurrencyUSD = true;
      const categorySelect = document.getElementById('id_category');
      const saveButton = document.querySelector('[name="_save"]');
      const saveButton2 = document.querySelector('[name="_continue"]');
      const saveButton3 = document.querySelector('[name="_addanother"]');
      let oldDataSelectIncome = {};
      let oldDataSelectExpense = {};
      let oldDataSelectContractor = {};
      let oldDataSelectDDS = {};
      async function checkRequiredFields() {
        const categoryText = categorySelect.options[categorySelect.selectedIndex]?.text || '';
        const incomeAmount = document.querySelector('#id_deal_data-0-income_amount');
        const expenseAmount = document.querySelector('#id_deal_data-0-expense_amount');
        const expenseAccount = document.querySelector('#id_deal_data-0-income_account');
        const nationalCurrency = document.querySelector('#id_national_currency');
        //
        const currency = document.querySelector('#id_rate');

        let canSave = true;

        if (categoryText === 'Сделка с клиентом') {
          nationalCurrency.style.setProperty('border-color', 'grb(var(--color-base-700)/var(--tw-border-opacity,1))');
          incomeAmount.style.setProperty('border-color', 'rgb(var(--color-base-700)/var(--tw-border-opacity,1))');
          expenseAccount.style.setProperty('border-color', 'rgb(var(--color-base-700)/var(--tw-border-opacity,1))');
          incomeAmount.style.setProperty('border', '1px solid #0091ff');
          expenseAmount.style.setProperty('border', '1px solid #0091ff');

          canSave = (incomeAmount?.value.trim() !== '' && incomeAmount?.value.trim() !== '0.0' && incomeAmount?.value.trim() !== '0') && expenseAmount?.value.trim() !== '0.0';
        } else if (categoryText === 'Сделка с КК') {
          expenseAmount.style.setProperty('border-color', 'rgb(var(--color-base-700)/var(--tw-border-opacity,1))');
          incomeAmount.style.setProperty('border', '1px solid #0091ff');
          expenseAccount.style.setProperty('border', '1px solid #0091ff');

          canSave = (incomeAmount?.value.trim() !== '' && incomeAmount?.value.trim() !== '0.0' && incomeAmount?.value.trim() !== '0') && expenseAccount?.value.trim() !== '';
          if (expenseAccount?.value) {
            const isActiveCurrency = await getData(`https://exsum.ru/api/v1/operation/check_national_currency/`,
              {
                bill_id: expenseAccount.value
              }
            );
            if (isActiveCurrency?.required_national_currency) {
              nationalCurrency.style.setProperty('border', '1px solid #0091ff');
              canSave = canSave && (nationalCurrency.value.trim() !== '' && nationalCurrency?.value.trim() !== '0.0' && nationalCurrency?.value.trim() !== '0');
            } else {
              nationalCurrency.style.setProperty('border-color', 'rgb(var(--color-base-700)/var(--tw-border-opacity,1))');
            }

          }
        }
        if (canSave) {
          saveButton.removeAttribute('disabled');
          saveButton2.removeAttribute('disabled');
          saveButton3.removeAttribute('disabled');
        } else {
          saveButton.setAttribute('disabled', 'disabled');
          saveButton2.setAttribute('disabled', 'disabled');
          saveButton3.setAttribute('disabled', 'disabled');
        }
      }
      categorySelect.addEventListener('change', async function () {
        const selectedValue = categorySelect.value;
        const selectedText = categorySelect.options[categorySelect.selectedIndex].text;
        const response = await getData('https://exsum.ru/api/v1/operation/check_autocomplete/', {
          category: selectedText
        });
        const tables = document.querySelectorAll('[aria-labelledby="deal_data-heading"]>div>div>div>div>div>div>table>tbody.template');
        for (let numberTable = 0; numberTable < tables.length - 1; numberTable++) {
          const selectIncome = document.querySelector(`#id_deal_data-${numberTable}-income_account`);
          const selectExpense = document.querySelector(`#id_deal_data-${numberTable}-expense_account`);
          const selectContractor = document.querySelector(`#id_contractor`);
          const selectDDS = document.querySelector(`#id_cashflow`);
          if (selectedText === 'Сделка с клиентом') {
            oldDataSelectIncome[numberTable] = selectIncome.innerHTML;
            oldDataSelectExpense[numberTable] = selectExpense.innerHTML;
            if (!!oldDataSelectContractor[numberTable]) funcRestoreData(selectContractor, oldDataSelectContractor[numberTable]);
            if (!!oldDataSelectDDS[numberTable]) funcRestoreData(selectDDS, oldDataSelectDDS[numberTable]);
            let textContentExposeAccount = '<option value="" selected>Выберите значение</option>';
            for (const d of response.expense_accounts) {
              textContentExposeAccount += `<option value="${d.id}">${d.name}</option>`;
            }
            selectExpense.innerHTML = textContentExposeAccount;
            let textContentIncomeAccount = '<option value="" selected>Выберите значение</option>';
            for (const d of response.income_accounts) {
              textContentIncomeAccount += `<option value="${d.id}">${d.name}</option>`;
            }
            selectIncome.innerHTML = textContentIncomeAccount;
            saveButton.setAttribute('disabled', 'disabled');
            saveButton2.setAttribute('disabled', 'disabled');
            saveButton3.setAttribute('disabled', 'disabled');
          } else if (selectedText === 'Сделка с КК') {
            if (!!oldDataSelectIncome[numberTable]) funcRestoreData(selectIncome, oldDataSelectIncome[numberTable]);
            if (!!oldDataSelectExpense[numberTable]) funcRestoreData(selectExpense, oldDataSelectExpense[numberTable]);
            oldDataSelectContractor[numberTable] = selectContractor.innerHTML;
            oldDataSelectDDS[numberTable] = selectDDS.innerHTML;
            // 1. Заполняем Контрагентов
            selectContractor.innerHTML = `
                <option value="" selected>Выберите значение</option>
                ${response.contractor.map(c => `<option value="${c.id}">${c.name}</option>`).join('')}
            `;
            selectDDS.innerHTML = `
                <option value="" selected>Выберите значение</option>
                ${response.cashflow.map(cf => `<option value="${cf.id}">${cf.name}</option>`).join('')}
            `;
            saveButton.setAttribute('disabled', 'disabled');
            saveButton2.setAttribute('disabled', 'disabled');
            saveButton3.setAttribute('disabled', 'disabled');
          } else {
            if (!!oldDataSelectIncome[numberTable]) funcRestoreData(selectIncome, oldDataSelectIncome[numberTable]);
            if (!!oldDataSelectExpense[numberTable]) funcRestoreData(selectExpense, oldDataSelectExpense[numberTable]);
            if (!!oldDataSelectContractor[numberTable]) funcRestoreData(selectContractor, oldDataSelectContractor[numberTable]);
            if (!!oldDataSelectDDS[numberTable]) funcRestoreData(selectDDS, oldDataSelectDDS[numberTable]);
            saveButton.removeAttribute('disabled');
            saveButton2.removeAttribute('disabled');
            saveButton3.removeAttribute('disabled');
          }
        }

        checkRequiredFields();
      });

      ['#id_deal_data-0-income_amount', '#id_deal_data-0-expense_amount', '#id_deal_data-0-income_account', '#id_national_currency']
        .forEach(selector => {
          const el = document.querySelector(selector);
          if (el) {
            el.addEventListener('input', checkRequiredFields);
            el.addEventListener('change', checkRequiredFields);
          }
        });
    }

  })
})();

const funcRestoreData = function (el, data) {
  el.innerHTML = data;
}
const handleIncomExpense = function (element, objData, event, addStyle = '') {
  const divIncome = event.target;
  const modalView = document.createElement('div');
  // divIncome.querySelector('div').style.setProperty('pointer-events', 'none')
  modalView.classList = 'modal__container' + addStyle
  modalView.innerHTML = `
  <p>До    ${objData.before} </p>
  <p>После ${objData.after} </p>
  `
  divIncome.parentNode.style.setProperty('position', 'relative');
  divIncome.parentNode.style.setProperty('overflow', 'unset');
  if (event.type === 'mouseout') {
    element.removeEventListener('mouseover', (e) => handleIncomExpense(element, objData, e));
    const customStyle = '.modal__container' + addStyle;
    document.querySelectorAll(customStyle).forEach(m => m.remove());
    divIncome.parentNode.style.setProperty('overflow', 'hidden');

  } else if (event.type === 'mouseover') {
    divIncome.parentNode.appendChild(modalView)
    element.removeEventListener('mouseout', (e) => handleIncomExpense(element, objData, e));
  }
}

const checkSelectItem = function (listEl, data) {
  setTimeout(() => {
    let sumNationalCurrencyValue = 0;
    for (const item of listEl) {
      if (item.classList.contains('selected')) {
        const idSelectItem = item.querySelector('th>a').textContent;
        for (const d of data) {
          if (+d.id === +idSelectItem) {
            sumNationalCurrencyValue += d.national_currency_value;
          }
        }
      }
    }
    const actionBottomBar = document.querySelector('#changelist-actions');
    if (actionBottomBar) {
      let sumDiv = actionBottomBar.querySelector('#sum-info');
      if (!sumDiv) {
        sumDiv = document.createElement('div');
        sumDiv.id = 'sum-info';
        sumDiv.style.setProperty('color', '#2200ffff');
        sumDiv.style.setProperty('background-color', '#e2e2e2ff');
        sumDiv.style.setProperty('padding', '10px');
        sumDiv.style.setProperty('border-radius', '10px');
        actionBottomBar.appendChild(sumDiv);
      }
      sumDiv.textContent = 'Сумма ' + sumNationalCurrencyValue;
    }
  }, 500);
  return 1;
}

const getData = async function (url, queryParam) {
  try {
    const params = new URLSearchParams(queryParam).toString();
    const fullUrl = `${url}?${params}`;
    const result = await fetch(fullUrl, {
      method: 'GET',
    });
    const data = await result.json();
    return data;
  } catch (error) {
    console.error(error);
  }
};
