class CreateElement {
  static create(tag, options = {}) {
    const el = document.createElement(tag);

    if (options.className) el.className = options.className;
    if (options.text) el.textContent = options.text;
    if (options.html) el.innerHTML = options.html;
    if (options.style) el.style = options.style;

    return el;
  }
}
(function () {
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
            // el.querySelector('tr').style = `background: ${key.custom}`
          }
        }
      }
    }
    const actionBottomBar = document.querySelector('#changelist-actions');

    if (actionBottomBar) {
      // Проверяем, есть ли уже div с определённым id или классом
      let sumDiv = actionBottomBar.querySelector('#sum-info');

      if (!sumDiv) {
        // Если div ещё не существует — создаём
        sumDiv = document.createElement('div');
        sumDiv.id = 'sum-info'; // Добавим id, чтобы легко находить
        sumDiv.style.setProperty('color', '#2200ffff');
        sumDiv.style.setProperty('background-color', '#e2e2e2ff');
        sumDiv.style.setProperty('padding', '10px');
        sumDiv.style.setProperty('border-radius', '10px');
        actionBottomBar.appendChild(sumDiv);
      }

      // Обновляем текст (в любом случае)
      sumDiv.textContent = 'Сумма ' + sumNationalCurrencyValue;
    }
  }, 500);
  return 1;
}

const getData = async function (url, queryParam) {
  try {
    // Преобразуем объект queryParam в query string
    const params = new URLSearchParams(queryParam).toString();
    const fullUrl = `${url}?${params}`;

    const result = await fetch(fullUrl, {
      method: 'GET',
    });

    // Возможно, тебе нужно result.json()
    const data = await result.json();
    return data;
  } catch (error) {
    console.error(error);
  }
};

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
  // })();

  document.addEventListener('DOMContentLoaded', function () {
    console.log("JS подключен и DOM загружен!");
    // 
    if (document.querySelectorAll('.tracking-tight')[1]?.textContent?.trim() === 'Select Сделка to change'){
      const titleOrder = CreateElement.create('div', {
        text: 'Сделки',
        className: 'main-order__title'
      });
      console.log(titleOrder)
      document.querySelector('#content').prepend(titleOrder)
    }else{
      const titleOrder = document.querySelector('.main-order__title')
      titleOrder && titleOrder.remove()
    }
    // thame
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


    // in_exes where list 
    const inExes = JSON.parse(window.localStorage.getItem('in_exes'));
    const listIncomeExpense = document.querySelectorAll('table#result_list>tbody>tr');
    document.querySelector('table#result_list>thead>tr>th>div>div>label>input') &&
      document.querySelector('table#result_list>thead>tr>th>div>div>label>input').addEventListener('click', () => checkSelectItem(listIncomeExpense, inExes));
    for (let incomeExpense of listIncomeExpense) {
      // input checkbox
      const checkbox = incomeExpense.querySelector('td>input');
      checkbox.addEventListener('click', () => checkSelectItem(listIncomeExpense, inExes));
      // -----------------------
      const incomeExpenseId = incomeExpense.querySelector('[data-label="ID"]');
      for (let i = 0; i < inExes.length; i++) {
        const exes = inExes[i];

        if (+exes.id === +incomeExpenseId.textContent.trim()) {
          // icome
          const income = incomeExpense.querySelector('[data-label="Счет прихода"]');
          income.querySelector('a').addEventListener('mouseover', (e) => handleIncomExpense(income, {
            before: exes.income_before,
            after: exes.income_after,
          }, e, '--list'));
          income.querySelector('a').addEventListener('mouseout', (e) => handleIncomExpense(income, {
            before: exes.income_before,
            after: exes.income_after,
          }, e, '--list'));
          // expense
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
    // страница добавления ордера
    const rendeerNewStyleForm = function () {
      const selectorBread = document.querySelectorAll('.tracking-tight');
      if(selectorBread.length){
        // if (false && selectorBread.length > 1 
        if (selectorBread.length > 1 
          && typeof selectorBread[1].textContent === 'string' 
          && (selectorBread[1].textContent.trim() === 'Add Сделка'
              || selectorBread[1].textContent.trim() === 'Change Сделка')
        ){
            const autocomplete = window.localStorage.getItem('autocomplete');
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
  
              // Функция проверки перед сохранением
              async function checkRequiredFields() {
                const categoryText = categorySelect.options[categorySelect.selectedIndex]?.text || '';
                const incomeAmount = document.querySelector('#id_deal_data-0-income_amount');
                const expenseAmount = document.querySelector('#id_deal_data-0-expense_amount');
                const expenseAccount = document.querySelector('#id_deal_data-0-income_account');
                const nationalCurrency = document.querySelector('#id_national_currency');
                //
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
                    if(isActiveCurrency?.required_national_currency){
                      nationalCurrency.style.setProperty('border','1px solid #0091ff');
                      canSave = canSave && (nationalCurrency.value.trim() !== '' && nationalCurrency?.value.trim() !== '0.0' && nationalCurrency?.value.trim() !== '0');
                    }else{
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
  
              // Слушаем изменения категории
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
  
                    // 2. Заполняем ДДС (Cashflow)
                    selectDDS.innerHTML = `
                        <option value="" selected>Выберите значение</option>
                        ${response.cashflow.map(cf => `<option value="${cf.id}">${cf.name}</option>`).join('')}
                    `;
                //     selectContractor.innerHTML = `
                //   <option value="" selected>Выберите значение</option>
                //   <option value="${response.contractor.id}">${response.contractor.name}</option>
                // `;
                //     selectDDS.innerHTML = `
                //   <option value="" selected>Выберите значение</option>
                //   <option value="${response.cashflow.id}">${response.cashflow.name}</option>
                // `;
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
  
              // Слушаем ввод в нужные поля
              ['#id_deal_data-0-income_amount', '#id_deal_data-0-expense_amount', '#id_deal_data-0-income_account','#id_national_currency']
                .forEach(selector => {
                  const el = document.querySelector(selector);
                  if (el) {
                    el.addEventListener('input', checkRequiredFields);
                    el.addEventListener('change', checkRequiredFields);
                  }
                });
            }
              // redisaign form
              let itemContragent = null;
              let sectionMoveContragent = null;
              const moveContragentSectionGeneral = document.querySelector('#debt_operations-group');
              const incomingSectionGeneral = document.querySelector('#deal_data-group');
              if (incomingSectionGeneral){
                sectionIncoming = incomingSectionGeneral.cloneNode(true);
                incomingSectionGeneral.remove();
                const general = document.querySelector('fieldset.module[x-show="activeTab == \'general\'"]');
                // create two tabs general and contragent
                // коприруем в память вкладку Движения контрагентов
                sectionMoveContragent = moveContragentSectionGeneral.cloneNode(true);
                sectionMoveContragent.classList.add('data-form-tab__container-contractor')
                moveContragentSectionGeneral.remove();
                // коприруем в память вкладку "Курс контрагентов" и удаляем из общего списка
                if(general){
                  const listItems = general.querySelectorAll('.field-row.form-row.group\\/row');
                  listItems.forEach( item => {
                    if (item.innerText.trim().includes("Курс контрагентов")) {
                      itemContragent = item.cloneNode(true);
                      item.remove()
                    }
                  })
                  // подписываем главный аорму таб
                  const generalFormTab = general.querySelector('div');
                  generalFormTab.setAttribute('data-form-tab', 'form-tab');
                  generalFormTab.style.setProperty('overflow', 'hidden');
                  // добавим вторую форму таб и делаем невидимым
                  const contragentFormTab = document.createElement('div');
                  contragentFormTab.className = generalFormTab.className;
                  contragentFormTab.style.setProperty('overflow', 'hidden');
                  contragentFormTab.setAttribute('data-form-tab', 'form-tab');
                  generalFormTab.classList.add('active');
                  generalFormTab.appendChild(incomingSectionGeneral);
                  itemContragent && contragentFormTab.appendChild(itemContragent);
                  contragentFormTab.appendChild(sectionMoveContragent);
                  general.appendChild(contragentFormTab);
                  // добавим табы и стилизуем их
                  const titleTab = general.querySelector('h2');
  
                  if (titleTab) {
                    // 1. Создаем внешнюю обертку (контейнер)
                    const wrapContainerTabs = document.createElement('div');
                    wrapContainerTabs.className = 'customTab__container';
  
                    // 2. Создаем внутреннюю обертку для заголовка
                    const wrapTitleTabGeneral = document.createElement('div');
                    wrapTitleTabGeneral.className = 'customTab active';
                    wrapTitleTabGeneral.setAttribute('data-tab', 'general');
                    const wrapTitleTabContragent = document.createElement('div');
                    const h2TitleContragent = document.createElement('h2');
                    h2TitleContragent.className = titleTab.className;
                    h2TitleContragent.textContent = 'Контрагент';
  
                    wrapTitleTabContragent.className = 'customTab';
                    wrapTitleTabContragent.setAttribute('data-tab', 'contragent');
  
                    wrapTitleTabContragent.appendChild(h2TitleContragent);
                    // 3. Собираем структуру "в памяти"
                    // Сначала вставляем контейнер в DOM на место h2
                    titleTab.parentNode.insertBefore(wrapContainerTabs, titleTab);
  
                    // 4. Переносим элементы внутрь
                    wrapContainerTabs.appendChild(wrapTitleTabGeneral);
                    wrapContainerTabs.appendChild(wrapTitleTabContragent);
                    wrapTitleTabGeneral.appendChild(titleTab);
                    // оживим табы
                    const tabs = [wrapTitleTabGeneral, wrapTitleTabContragent];
                    const formTabs = [generalFormTab,contragentFormTab];
                    const handleClickTab = function (e) {
                      e.preventDefault();
                      formTabs.forEach( ft => ft.classList.remove('active'));
                      tabs.forEach((tab, index) => {
                        tab.classList.remove('active');
                        const dataTab = this.getAttribute('data-tab');
                        switch(dataTab){
                          case 'general':
                              generalFormTab.classList.add('active');
                            break;
                            case 'contragent':
                              contragentFormTab.classList.add('active');
                            break;
                            default:
  
                        }
                      }); // Удаляем у всех
                      this.classList.add('active'); // Добавляем той, по которой кликнули
                    }
                    tabs.forEach(tab => {
                      tab.addEventListener('click', handleClickTab)
                    })
                  }else{
                    console.warn('Изначальная вкладка не найдена')
                  }
                  const contWarmInfo1 = CreateElement.create('p', {
                    className: 'data-form-tab__date-warm'
                  });
                  const contWarmInfo2 = CreateElement.create('p', {
                    className: 'data-form-tab__date-warm'
                  });
                  function renderFirstForm(initTab) {
                    // уменьшаем отступ от хлебных крошек 
                    document.querySelector('#main > div:nth-child(2) > div').style.marginBottom = '10px'
                    const wrapContainerForm = CreateElement.create('div', {
                      className: 'data-form-tab__first-subform-container'
                    });
                    const titleGeneralForm = document.createElement('p');
                    titleGeneralForm.textContent = 'Общая информация';
                    titleGeneralForm.style = 'grid-area: title-common'
                    titleGeneralForm.classList.add('data-form-tab__title')
                    // создадим поле ввода даты
                    const contInputDate = CreateElement.create('div',{
                      className: 'data-form-tab__container-date',
                      style: 'grid-area: date'
                    })
                    const labelInputDate = CreateElement.create('p', {
                      className: 'data-form-tab__label-date',
                      text: 'Дата создания'
                    });
                    const contInputSelectDate = CreateElement.create('div', {
                      className: 'data-form-tab__date-cont'
                    });
                    const inputDate = document.querySelector('[name="date_create_0"]');
                    const inputDateCopySelector = inputDate.cloneNode(true);
                    inputDateCopySelector.type = 'date';
                    // inputDate.remove();
                    const contInputDateCopySelector = CreateElement.create('div',{
                      className:'data-form-tab__date-input-cont'
                    });
                    const contCelenderDateCopySelector = CreateElement.create('div', {
                      className: 'data-form-tab__date-celender-cont'
                    });
                    contCelenderDateCopySelector.insertAdjacentHTML("beforeend", `<svg width="17" height="17" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path fill-rule="evenodd" clip-rule="evenodd" d="M2.64018 0C2.91632 0 3.14018 0.223858 3.14018 0.5V1.61175C5.02533 1.44387 6.92169 1.44387 8.80684 1.61176V0.5C8.80684 0.223858 9.0307 0 9.30684 0C9.58299 0 9.80684 0.223858 9.80684 0.5V1.71096C10.8022 1.8517 11.5886 2.63898 11.7217 3.64322L11.7794 4.07852C12.0221 5.90941 12.0011 7.76563 11.7171 9.59057C11.5765 10.4946 10.842 11.189 9.93152 11.2788L9.13619 11.3572C7.03282 11.5646 4.91416 11.5646 2.81079 11.3572L2.01546 11.2788C1.10496 11.189 0.370525 10.4946 0.229852 9.59057C-0.0541203 7.76563 -0.0750808 5.90941 0.16761 4.07853L0.22531 3.64322C0.358428 2.63897 1.1448 1.85167 2.14018 1.71095V0.5C2.14018 0.223858 2.36403 0 2.64018 0ZM2.93695 2.6352C4.95641 2.43605 6.99057 2.43605 9.01003 2.6352L9.61366 2.69473C10.1915 2.75171 10.654 3.19903 10.7303 3.77463L10.788 4.20993C10.8082 4.362 10.8264 4.51426 10.8428 4.66667H1.10422C1.12054 4.51426 1.13878 4.362 1.15894 4.20993L1.21664 3.77463C1.29294 3.19903 1.75549 2.75171 2.33332 2.69473L2.93695 2.6352ZM1.02473 5.66667C0.959278 6.92538 1.02376 8.18881 1.21796 9.43681C1.28852 9.89026 1.65691 10.2385 2.1136 10.2836L2.90893 10.362C4.94703 10.563 6.99995 10.563 9.03805 10.362L9.83338 10.2836C10.2901 10.2385 10.6585 9.89026 10.729 9.43681C10.9232 8.18881 10.9877 6.92538 10.9223 5.66667H1.02473Z" fill="#1E1E1E" />
                    </svg>`);
                    
                    contInputDateCopySelector.appendChild(inputDateCopySelector);
                    contInputDate.appendChild(labelInputDate);
                    contInputSelectDate.appendChild(contInputDateCopySelector);
                    contInputSelectDate.appendChild(contCelenderDateCopySelector);
                    contInputDate.appendChild(contInputSelectDate);
                    contInputDate.appendChild(contWarmInfo1);
                    // создадим поле ввода времени
                    const contTimeDate = CreateElement.create('div', {
                      className: 'data-form-tab__container-date',
                      style: 'grid-area: time'
                    })
                    const labelTimeDate = CreateElement.create('p', {
                      className: 'data-form-tab__label-date',
                      text: 'Время создания'
                    });
                    const contTimeSelectDate = CreateElement.create('div', {
                      className: 'data-form-tab__date-cont'
                    });
                    const inputTime = document.querySelector('[name="date_create_1"]');
                    const inputTimeCopySelector = inputTime.cloneNode(true);
                    inputTimeCopySelector.type = 'time';
                    // inputDate.remove();
                    const contTimeDateCopySelector = CreateElement.create('div', {
                      className: 'data-form-tab__date-input-cont'
                    });
                    const contTimerDateCopySelector = CreateElement.create('div', {
                      className: 'data-form-tab__date-time-cont'
                    });
                    contTimerDateCopySelector.insertAdjacentHTML('beforeend',`<svg width="21" height="21" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M4.57637 4.58826C5.45204 3.70956 6.66213 3.16669 7.99996 3.16669C10.6693 3.16669 12.8333 5.33064 12.8333 8.00002C12.8333 10.6694 10.6693 12.8334 7.99996 12.8334C5.33058 12.8334 3.16663 10.6694 3.16663 8.00002C3.16663 7.72388 2.94277 7.50002 2.66663 7.50002C2.39048 7.50002 2.16663 7.72388 2.16663 8.00002C2.16663 11.2217 4.7783 13.8334 7.99996 13.8334C11.2216 13.8334 13.8333 11.2217 13.8333 8.00002C13.8333 4.77836 11.2216 2.16669 7.99996 2.16669C6.38563 2.16669 4.92368 2.8231 3.86805 3.88237C3.85108 3.89939 3.83559 3.91733 3.82159 3.93603L2.98321 3.09765C2.89175 3.00619 2.75565 2.9759 2.63403 3.01993C2.51242 3.06396 2.42725 3.17437 2.41554 3.30317L2.17984 5.8959C2.17089 5.99442 2.20615 6.09183 2.2761 6.16178C2.34606 6.23173 2.44346 6.267 2.54198 6.25804L5.13471 6.02234C5.26352 6.01063 5.37392 5.92547 5.41796 5.80385C5.46199 5.68224 5.43169 5.54613 5.34023 5.45467L4.52149 4.63593C4.54064 4.62159 4.55898 4.6057 4.57637 4.58826Z" fill="#1E1E1E"/>
<path d="M8.49996 4.66669C8.49996 4.39054 8.2761 4.16669 7.99996 4.16669C7.72382 4.16669 7.49996 4.39054 7.49996 4.66669V8.00002C7.49996 8.17242 7.58877 8.33265 7.73496 8.42402L9.73496 9.67402C9.96913 9.82037 10.2776 9.74919 10.424 9.51502C10.5703 9.28085 10.4991 8.97238 10.265 8.82602L8.49996 7.7229V4.66669Z" fill="#1E1E1E"/>
</svg>`)
                    contTimeDateCopySelector.appendChild(inputTimeCopySelector);
                    contTimeDate.appendChild(labelTimeDate);
                    contTimeSelectDate.appendChild(contTimeDateCopySelector);
                    contTimeSelectDate.appendChild(contTimerDateCopySelector);
                    contTimeDate.appendChild(contTimeSelectDate);
                    contTimeDate.appendChild(contWarmInfo2);
    
                    // редизайн перекллючателя
                    const switchClosed = document.querySelector('.field-closed').cloneNode(true);
                    switchClosed.style = 'grid-area: switch';
                    switchClosed.className = 'field-closed';
                    // редизайн категории
                    const fieldCategory = document.querySelector('.field-category').cloneNode(true);
                    fieldCategory.style = 'grid-area: category';
                    fieldCategory.className = 'field-category';
                    fieldCategory
                      .querySelectorAll('.related-widget-wrapper a')
                      .forEach(a => a.remove());
                    // редизайн контрагент
                    const fieldContractor = document.querySelector('.field-contractor').cloneNode(true);
                    fieldContractor.style = 'grid-area: contractor';
                    fieldContractor.className = 'field-contractor';
                    fieldContractor
                      .querySelectorAll('.related-widget-wrapper a')
                      .forEach(a => a.remove());
                    // редизайн ддс
                    const fieldDds = document.querySelector('.field-cashflow').cloneNode(true);
                    fieldDds.style = 'grid-area: dds';
                    fieldDds.className = 'field-cashflow';
                    fieldDds
                      .querySelectorAll('.related-widget-wrapper a')
                      .forEach(a => a.remove());
                    // редизайн комментарий
                    const fieldComment= document.querySelector('.field-comment').cloneNode(true);
                    fieldComment.style = 'grid-area: comment';
                    fieldComment.className = 'field-comment';
                    fieldComment
                      .querySelectorAll('.related-widget-wrapper a')
                      .forEach(a => a.remove());
                    // редизайн Курс валюты
                    const fieldCurrency = document.querySelector('.field-rate').cloneNode(true);
                    fieldCurrency.style = 'grid-area: field-rate';
                    fieldCurrency.className = 'field-rate';
                    fieldCurrency.querySelector('label').textContent = 'Курс валюты';
                    // редизайн Долг
                    const fieldDutyDeal = document.querySelector('.field-duty_deal').cloneNode(true);
                    fieldDutyDeal.style = 'grid-area: field-duty_deal';
                    fieldDutyDeal.className = 'field-duty_deal';
                    fieldDutyDeal.querySelector('label').textContent = 'Долг';
                    // редизайн Национальная валюта
                    const fieldNationalCurrency = document.querySelector('.field-national_currency').cloneNode(true);
                    fieldNationalCurrency.style = 'grid-area: field-national_currency';
                    fieldNationalCurrency.className = 'field-national_currency';
                    fieldNationalCurrency.querySelector('label').textContent = 'Национальная валюта';
                    // Заказ 1с
                    const elFieldDeal1c = document.querySelector('.field-deal_1c');
                    let fieldDeal1c = null;
                    if (elFieldDeal1c) {
                      fieldDeal1c = elFieldDeal1c.cloneNode(true);
                      const input = elFieldDeal1c.querySelector('input');
                      input.id = input.id + '_old';
                      fieldDeal1c.style = 'grid-area: field-deal_1c';
                      fieldDeal1c.className = 'field-deal_1c';
                    }

                    //  переносим счета вверх страницы
                    const customBills = document.querySelector('.custom-bills__create');
                    let copyCustomBills = null;
                    if (customBills) {
                      copyCustomBills = customBills.cloneNode(true);
                      customBills.remove();
                    }
                    // first subform
                    copyCustomBills && document.querySelector('#content').prepend(copyCustomBills);
                    initTab.prepend(wrapContainerForm);
                    wrapContainerForm.appendChild(titleGeneralForm);
                    wrapContainerForm.appendChild(contInputDate);
                    wrapContainerForm.appendChild(contTimeDate);
                    wrapContainerForm.appendChild(switchClosed);
                    wrapContainerForm.appendChild(fieldCategory);
                    wrapContainerForm.appendChild(fieldContractor);
                    wrapContainerForm.appendChild(fieldDds);
                    wrapContainerForm.appendChild(fieldComment);
                    wrapContainerForm.appendChild(fieldCurrency);
                    wrapContainerForm.appendChild(fieldDutyDeal);
                    wrapContainerForm.appendChild(fieldNationalCurrency);
                    fieldDeal1c && wrapContainerForm.appendChild(fieldDeal1c);

                  }

                  const newStylesIncomeExposeForm = function (){
                    setTimeout(()=>{
                      const titleTable = document.querySelector('#deal_data-heading');
                      if (titleTable){
                        titleTable.remove();
                      }
                      const listTables = document.querySelectorAll('#deal_data-group > div > fieldset > div > div > div > div > div > div > table > tbody');
                      for (let i = 0; i <= listTables.length -1; i++){
                        const table = listTables[i];
                        const headersTable = document.querySelectorAll('#deal_data-group > div > fieldset > div > div > div > div > div > div > table > thead > tr > th');
                        const headers = [...headersTable].map(el => el.querySelector('span')?.textContent?.trim());
                        const headerTitle = document.querySelector('#deal_data-group > div > fieldset > div > div > div > div > div > div > table > thead')
                        if (headerTitle) {
                          headerTitle.style.opacity = 0;
                          headerTitle.style.visibility = 'hidden';
                          headerTitle.style.position = 'absolute';
                        }
                        if (selectorBread[1].textContent.trim() === 'Change Сделка') {
                          const rowTable = table.querySelectorAll('tr');
                          console.log({ rowTable })
                          if(rowTable.length > 1 ){
                            headers.unshift('fake')
                            // rowTable[0]?.remove();
                            console.log('{ rowTable }')

                            rowTable[0].style.display = 'none';
                          }else{
                            rowTable[0].style.display = 'grid';
                          }
                        }
                        if(i !== listTables.length-1){
                          const titleGeneralFormSumAndOrder = document.createElement('p');
                          titleGeneralFormSumAndOrder.textContent = 'Суммы и счета';
                          titleGeneralFormSumAndOrder.style = 'grid-area: title-common-sec'
                          titleGeneralFormSumAndOrder.classList.add('data-form-tab__title');
                          table.classList.add('data-form-tab__secend-subform-container');
                          const titleTable = table.querySelector('.data-form-tab__title');
                          if (!titleTable){
                            table.prepend(titleGeneralFormSumAndOrder);
                          }
                          const listColumns = table.querySelectorAll('td');

                          for (let j = 0; j <= listColumns.length - 1; j++) {
                            const col = listColumns[j];
                            col.style.padding = 0;
                            const headerWrap = CreateElement.create('div',{});
                            headerWrap.textContent = headers[j];
                            headerWrap.classList.add('data-form-tab__title-item')
                            const elWrapContFormInput = col.querySelector('div > div');
                            if (elWrapContFormInput) {
                              elWrapContFormInput.style.width = '100%';
                            }
                            const elFormInput = col.querySelector('div > div > input');
                            if (elFormInput) {
                              elFormInput.style.width = '100%';
                              elFormInput.style.minWidth = '100%';
                              elFormInput.style.borderRadius = '12px';
                            }
                            const elFormSelect = col.querySelector('div > div > select');
                            if (elFormSelect) {
                              elFormSelect.style.width = '100%';
                              elFormSelect.style.minWidth = '100%';
                              elFormSelect.style.borderRadius = '12px';
                            }
                            const titleHeaderCol = col.dataset?.label?.trim();
                            switch (titleHeaderCol) {

                              case 'Сумма прихода':
                                col.style.gridArea = 'sum-deal';
                                break;

                              case 'Курс прихода':
                                col.style.gridArea = 'income-rate';
                                break;

                              case 'Счет прихода':
                                col.style.gridArea = 'income-account';
                                break;
                              
                              case 'Сумма расхода':
                                col.style.gridArea = 'expence-amount';
                                break;
                              case 'Курс расхода':
                                col.style.gridArea = 'expence-rate';
                                break;
                              case 'Счет расхода':
                                col.style.gridArea = 'expense-account';
                                break;
                              case 'Комиссия':
                                col.style.gridArea = 'comission';
                                break;
                              case 'Remove':
                                const aRemove = col.querySelector('a');
                                if (aRemove){
                                  col.classList.add('data-form-tab__remove')
                                  col.setAttribute('data-remove', 'remove');
                                  aRemove.textContent = 'Удалить';
                                } else {
                                  // col.remove();
                                  col.style.display = 'none';
                                }
                                break;

                              default:
                                // col.remove();
                                col.style.display = 'none';
                            }
                            if (!col?.querySelector('.data-form-tab__title-item')) {
                              col.prepend(headerWrap);
                            }
                          }
                        }else{
                          table.classList.add('custom__remove-border')
                          setTimeout(() => {
                            const elFieldAddRow = table?.querySelector('tr.add-row');
                            let fieldAddRow = null;
                            if (elFieldAddRow) {
                              fieldAddRow = elFieldAddRow;
                              fieldAddRow.classList.add('data-form-tab__add-table');
                              fieldAddRow.querySelector('a').textContent = '+ Добавить Движение по счетам';
                              fieldAddRow.onclick = () => {
                                newStylesIncomeExposeForm();
                              }

                            }
                          }, 1000);
                        }
                      }
                    },500)
                  }
                  // redisagn contractor
                  const newStylesContractorForm = async function () {
                    setTimeout(() => {
                      const titleTable = document.querySelector('#debt_operations-heading');
                      if (titleTable) {
                        titleTable.remove();
                      }
                      const listTables = document.querySelectorAll('#debt_operations-group > div > fieldset > div > div > div > div > div > div > table > tbody');
                      for (let i = 0; i <= listTables.length - 1; i++) {
                        const table = listTables[i];
                        const headersTable = document.querySelectorAll('#debt_operations-group > div > fieldset > div > div > div > div > div > div > table > thead > tr > th');
                        const headers = [...headersTable].map(el => el.querySelector('span')?.textContent?.trim());
                        const headerTitle = document.querySelector('#debt_operations-group > div > fieldset > div > div > div > div > div > div > table > thead')
                        if (headerTitle) {
                          headerTitle.style.opacity = 0;
                          headerTitle.style.visibility = 'hidden';
                          headerTitle.style.position = 'absolute';
                        }
                        if(selectorBread[1].textContent.trim() === 'Change Сделка'){
                          const rowTable = table.querySelectorAll('tr');
                          if (rowTable.length > 1) {
                            headers.unshift('fake')
                            // rowTable[0]?.remove();
                            rowTable[0].style.display = 'none';
                          } else {
                            rowTable[0].style.display = 'grid';
                          }
                        }
                        if (i !== listTables.length - 1) {
                          const titleGeneralFormSumAndOrder = document.createElement('p');
                          titleGeneralFormSumAndOrder.textContent = 'Движения контрагентов';
                          titleGeneralFormSumAndOrder.style = 'grid-area: title-contragent'
                          titleGeneralFormSumAndOrder.classList.add('data-form-tab__title');
                          table.classList.add('data-form-tab__secend-contractor-subform-container');
                          const titleTable = table.querySelector('.data-form-tab__title');
                          if (!titleTable) {
                            table.prepend(titleGeneralFormSumAndOrder);
                          }
                          const listColumns = table.querySelectorAll('td');

                          for (let j = 0; j <= listColumns.length - 1; j++) {
                            const col = listColumns[j];
                            col.style.padding = 0;
                            const headerWrap = CreateElement.create('div', {});
                            headerWrap.textContent = headers[j];
                            headerWrap.classList.add('data-form-tab__title-item')
                            const elWrapContFormInput = col.querySelector('div > div');
                            if (elWrapContFormInput) {
                              elWrapContFormInput.style.width = '100%';
                            }
                            const elFormInput = col.querySelector('div > div > input');
                            if (elFormInput) {
                              elFormInput.style.width = '100%';
                              elFormInput.style.minWidth = '100%';
                              elFormInput.style.borderRadius = '12px';
                            }
                            const elFormSelect = col.querySelector('div > div > select');
                            if (elFormSelect) {
                              elFormSelect.style.width = '100%';
                              elFormSelect.style.minWidth = '100%';
                              elFormSelect.style.borderRadius = '12px';
                            }
                            const balanceContractor = CreateElement.create('div',{
                              className: 'data-form-tab__contractor-cont-balance',
                            }) 
                            const balanceContractorTitle = CreateElement.create('div',{
                              className: 'data-form-tab__contractor-cont-balance-title',
                              text: 'Счет Контрагента'
                            }) 
                            const balanceContractorAmount = CreateElement.create('div',{
                              className: 'data-form-tab__contractor-cont-balance-amount',
                              text: ''
                            }) 

                            balanceContractor.appendChild(balanceContractorTitle);
                            balanceContractor.appendChild(balanceContractorAmount);
                            balanceContractor.style = 'grid-area: contractor-balance';
                            const titleHeaderCol = col.dataset?.label?.trim();
                            const getBalance = async function (value){
                              try {
                                const responseBalance = await getData('https://exsum-test.ru/api/v1/operation/get_cashflow_balance/', { contractor_id: value })
                                const balance = responseBalance?.cashflow_bill;
                                return balance;
                              } catch (error) {
                                const err = new Error('Ошибка получения данных');
                                console.error(error.message + '\n' + err)
                              } 
                            }
                            if (!col?.querySelector('.data-form-tab__title-item')) {
                              if (col.className !== 'original') {
                                col.prepend(headerWrap);
                              }
                            }
                            switch (titleHeaderCol) {
                              // https://exsum-test.ru/api/v1/operation/get_cashflow_balance/?contractor_id=2
                              // https://exsum-test.ru/api/v1/operation/get_cashflow_balance/?contractor_id=1
                              case 'Контрагент':
                                col.style.gridArea = 'contractor';
                                col.classList.add('data-form-tab__contractor-cont')
                                col.after(balanceContractor);
                                const select = col.querySelector('select');
                                if (selectorBread[1].textContent.trim() === 'Change Сделка'){
                                  const idConrtactor = select.value;
                                  if(idConrtactor){
                                    const setBalance = async function (){
                                      const balance = await getBalance(idConrtactor);
                                      const el = balanceContractor.querySelector('.data-form-tab__contractor-cont-balance-amount')
                                      el.textContent = balance;
                                    }
                                    setBalance();
                                  }
                                }
                                select.addEventListener('change', async (e) => {
                                  const value = e.target.value;
                                  const setBalance = async function () {
                                    const balance = await getBalance(value);
                                    const el = balanceContractor.querySelector('.data-form-tab__contractor-cont-balance-amount')
                                    el.textContent = balance;
                                  }
                                  setBalance();
                                });
                                break;

                              case 'Сумма операции':
                                col.style.gridArea = 'dept-operation';
                                break;

                              case 'Тип операции':
                                col.style.gridArea = 'type-operation';
                                break;

                              case 'Процент':
                                col.style.gridArea = 'procent-operation';
                                break;

                              case 'Валюта':
                                col.style.gridArea = 'currency-operation';
                                break;
                              case 'Комментарий':
                                col.style.gridArea = 'comment-operation';
                                break;
                              
                              case 'Remove':
                                const aRemove = col.querySelector('a');
                                if (aRemove) {
                                  col.classList.add('data-form-tab__remove')
                                  col.setAttribute('data-remove', 'remove');
                                  aRemove.textContent = 'Удалить';
                                }else{
                                  // col.remove();
                                  col.style.display = 'none';
                                }
                                break;
                                
                              default:
                                  // col.remove();
                                col.style.display = 'none';
                            }
                            
                          }
                        } else {
                          table.classList.add('custom__remove-border')
                          setTimeout(() => {
                            const elFieldAddRow = table?.querySelector('tr.add-row');
                            let fieldAddRow = null;
                            if (elFieldAddRow) {
                              fieldAddRow = elFieldAddRow;
                              fieldAddRow.classList.add('data-form-tab__add-table');
                              fieldAddRow.querySelector('a').textContent = '+ Добавить Движение балансов';
                              fieldAddRow.onclick = () => {
                                newStylesContractorForm();
                              }

                            }
                          }, 1000);
                        }
                      }
                    }, 500)
                  }
                  
                  renderFirstForm(generalFormTab);
                  newStylesIncomeExposeForm();
                  newStylesContractorForm();
                  

                  const getWarmText = setInterval(() => {
                    const warningEl = document.querySelector('.help.timezonewarning');
                    
                    if (warningEl) {
                      const warningText = warningEl.textContent;
                      if (warningText) {
                        contWarmInfo1.textContent = warningText;
                        contWarmInfo2.textContent = warningText;
                        listItems.forEach(el=>el.remove())
                        document.querySelector('.data-form-tab__date-celender-cont').addEventListener('click', () => {
                          document.getElementById('id_date_create_0').showPicker();
                          document.getElementById('id_date_create_0').focus();
                        });
                        document.querySelector('.data-form-tab__date-time-cont').addEventListener('click', () => {
                          document.getElementById('id_date_create_1').showPicker();
                          document.getElementById('id_date_create_1').focus();
                        });
                        clearInterval(getWarmText);
                      }
                    }
                  }, 1000);
                  
                }
              }
        }
      }
    }

//
  //hz
    rendeerNewStyleForm();
  })
})();
