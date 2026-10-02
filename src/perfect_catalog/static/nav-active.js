// Marca la sección activa en el menú y en la barra de pasos (accesible: aria-current).
(function () {
  var p = location.pathname.replace(/\/+$/, '') || '/';
  var map = [
    ['/operator/simple', 'cargar'], ['/operator/intake', 'cargar'],
    ['/operator/review', 'revisar'], ['/operator/plans', 'revisar'],
    ['/operator/import-plans', 'revisar'], ['/operator/images', 'revisar'],
    ['/operator/catalogs', 'entregar'],
    ['/operator/admin', 'admin'], ['/operator/brands', 'admin'],
    ['/operator/company', 'admin'], ['/operator/public-links', 'admin']
  ];
  var section = (p === '/operator' || p === '/operator/guiado') ? 'inicio' : null;
  for (var i = 0; i < map.length && !section; i++) {
    if (p === map[i][0] || p.indexOf(map[i][0] + '/') === 0) section = map[i][1];
  }
  if (!section) return;
  var links = document.querySelectorAll('[data-section="' + section + '"]');
  for (var j = 0; j < links.length; j++) links[j].setAttribute('aria-current', 'page');
})();
