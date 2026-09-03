/* SENDA 0.4.3 - habilita selección/copia en áreas informativas sin bloquear controles. */
(function sendaEnableMouseSelection() {
  'use strict';

  const selectors = [
    '[data-senda-selectable="true"]',
    '#informacion-senda', '.informacion-senda',
    '#expediente', '.expediente',
    '#expedientes', '.expedientes',
    '#movimientos', '.movimientos',
    '#control', '.control',
    '#folios', '.folios',
    '#fincas', '.fincas',
    '#alarmas', '.alarmas',
    '[class*="senda-info"]',
    '[class*="folio"]',
    '[class*="finca"]',
    '[class*="movimiento"]',
    '[class*="expediente"]'
  ];

  const interactiveSelector = [
    'button', 'input', 'select', 'textarea', 'option',
    '[role="button"]', '[role="checkbox"]', '[draggable="true"]'
  ].join(',');

  function markSelectable(root) {
    if (!(root instanceof Element)) return;
    root.classList.add('senda-selectable');
    root.setAttribute('data-senda-selectable', 'true');

    root.querySelectorAll(interactiveSelector).forEach((control) => {
      control.classList.add('senda-interactive');
    });
  }

  function scan(scope) {
    selectors.forEach((selector) => {
      scope.querySelectorAll(selector).forEach(markSelectable);
    });
  }

  function start() {
    scan(document);

    // La UI puede ser dinámica: marca también paneles que se agreguen después.
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (!(node instanceof Element)) continue;
          if (selectors.some((selector) => node.matches(selector))) {
            markSelectable(node);
          }
          scan(node);
        }
      }
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
