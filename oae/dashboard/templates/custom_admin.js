(function() {
  const originalSetItem = localStorage.setItem;
  const originalRemoveItem = localStorage.removeItem;

  localStorage.setItem = function(key, value) {
    const event = new CustomEvent('localstorage-change', {
      detail: { key, value }
    });
    window.dispatchEvent(event);
    return originalSetItem.apply(this, arguments);
  };

  localStorage.removeItem = function(key) {
    const event = new CustomEvent('localstorage-change', {
      detail: { key, value: null }
    });
    window.dispatchEvent(event);
    return originalRemoveItem.apply(this, arguments);
  };
})();

document.addEventListener('DOMContentLoaded', function () {
  console.log("JS подключен и DOM загружен!");
  window.addEventListener('localstorage-change', (e) => {
    const { key, value } = e.detail;
    console.log('Изменено в localStorage:', key, value);
    if(key && value === '"dark"'){
      console.log('dark')
      document.documentElement.style.setProperty('--color-table', 'rgb(var(--color-font-default-dark)/var(--tw-text-opacity,1))')
    }else{
      document.documentElement.style.setProperty('--color-table', '#101827')  
    }
  });
  const adminTheme = window.localStorage.getItem('adminTheme');
  console.log({adminTheme})
  if(adminTheme && adminTheme === '"dark"'){
    console.log('dark')
    document.documentElement.style.setProperty('--color-table', 'rgb(var(--color-font-default-dark)/var(--tw-text-opacity,1))')
  }else{
    document.documentElement.style.setProperty('--color-table', '#101827')  
  }

  // const customData = JSON.parse('{{ color_data|escapejs }}');

  //   // Пример: повесить скрытые div с данными
  //   for (const item of customData) {
  //     const el = document.createElement('div');
  //     el.dataset.id = item.id;
  //     el.dataset.custom = JSON.stringify(item.custom);
  //     el.style.display = 'none';
  //     document.body.appendChild(el);
  //   }

  //   console.log('Custom data per object:', customData);
});


(function($) {
  $(function() {
    $('.js-click-toggle').on('click', function() {
      const $el = $(this);
      // проверяем, какой сейчас текст, и меняем
      const isOriginal = $el.text() === $el.data('original');
      $el.text(isOriginal ? $el.data('alt') : $el.data('original'));
    });
  });
})(django.jQuery);