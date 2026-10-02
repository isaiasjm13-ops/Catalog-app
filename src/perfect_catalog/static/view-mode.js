// Vista Simple / Completa (idea tomada de Kairo: modo avanzado que muestra u oculta lo técnico).
// Por defecto "completa" (el comportamiento de siempre). La preferencia vive solo en este navegador.
(function () {
  var KEY = 'pc_view';
  function read() {
    try { return localStorage.getItem(KEY) === 'simple' ? 'simple' : 'full'; } catch (e) { return 'full'; }
  }
  function write(v) { try { localStorage.setItem(KEY, v); } catch (e) { /* sin almacenamiento: no pasa nada */ } }
  function apply(v) {
    document.documentElement.setAttribute('data-view', v);
    var btn = document.getElementById('view-toggle');
    if (btn) {
      btn.textContent = v === 'simple' ? 'Vista: Simple' : 'Vista: Completa';
      btn.setAttribute('aria-pressed', v === 'simple' ? 'true' : 'false');
      btn.title = v === 'simple' ? 'Cambiar a la vista completa (todo el detalle)' : 'Cambiar a la vista simple (solo lo esencial)';
    }
    // En vista simple, "Inicio" lleva al paso a paso.
    var home = document.querySelectorAll('[data-home]');
    for (var i = 0; i < home.length; i++) home[i].setAttribute('href', v === 'simple' ? '/operator/guiado' : '/operator');
  }
  apply(read());
  document.addEventListener('DOMContentLoaded', function () {
    apply(read());
    var btn = document.getElementById('view-toggle');
    if (btn) btn.addEventListener('click', function () {
      var next = read() === 'simple' ? 'full' : 'simple';
      write(next);
      apply(next);
    });
  });
})();
