// Generador público: evita doble envío y muestra que el catálogo se está generando.
(function () {
  var form = document.getElementById('generar-form');
  if (!form) return;
  var button = form.querySelector('button[type="submit"]');
  var status = document.getElementById('generar-estado');
  form.addEventListener('submit', function () {
    if (!button || button.disabled) return;
    var label = button.textContent;
    button.disabled = true;
    button.textContent = 'Generando… puede tardar unos minutos';
    if (status) status.hidden = false;
    // La descarga no recarga la página: volver a habilitar el botón después de un rato.
    setTimeout(function () {
      button.disabled = false;
      button.textContent = label;
      if (status) status.hidden = true;
    }, 90000);
  });
})();
