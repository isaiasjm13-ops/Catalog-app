(function () {
  "use strict";

  var previewFields = [
    "title", "subtitle", "group_by", "group_by_secondary", "filter_field",
    "filter_query", "selected_references", "theme", "columns", "template_profile"
  ];
  var draftFields = previewFields.concat([
    "format_html", "format_html_standalone", "format_pdf", "format_pptx",
    "format_indesign_json"
  ]);

  function openPreview(button) {
    var actions = button.closest(".js-preview-actions");
    var form = button.closest("form");
    if (!actions || !form) return;
    var formData = new FormData(form);
    var query = new URLSearchParams();
    previewFields.forEach(function (name) {
      var value = formData.get(name);
      if (value !== null && String(value).trim() !== "") query.set(name, String(value));
    });
    query.set("preview_target", button.getAttribute("data-preview-target") || "digital");
    window.location.assign(actions.getAttribute("data-preview-url") + "?" + query.toString());
  }

  function storageKey(actions) {
    return "perfect-catalog:composer:" + actions.getAttribute("data-preview-url");
  }

  function readDraft(key) {
    try { return JSON.parse(window.localStorage.getItem(key) || "null"); }
    catch (error) { return null; }
  }

  function writeDraft(key, value) {
    try { window.localStorage.setItem(key, JSON.stringify(value)); return true; }
    catch (error) { return false; }
  }

  function clearDraft(key) {
    try { window.localStorage.removeItem(key); }
    catch (error) { /* La edición sigue funcionando sin almacenamiento local. */ }
  }

  function valuesFrom(form) {
    var data = new FormData(form);
    var values = {};
    draftFields.forEach(function (name) {
      var value = data.get(name);
      if (value !== null) values[name] = String(value);
    });
    return values;
  }

  function restore(form, values) {
    if (!values || typeof values !== "object") return false;
    draftFields.forEach(function (name) {
      if (!Object.prototype.hasOwnProperty.call(values, name)) return;
      var control = form.elements.namedItem(name);
      if (!control) return;
      try { control.value = values[name]; } catch (error) { /* Campo antiguo: se ignora. */ }
    });
    return true;
  }

  function referenceCount(value) {
    return String(value || "").split(/[\n,;]+/).map(function (item) {
      return item.trim().toLocaleUpperCase("es");
    }).filter(function (item, index, all) { return item && all.indexOf(item) === index; }).length;
  }

  function selectedFormats(values) {
    var labels = {
      format_html: "HTML", format_html_standalone: "HTML autónomo",
      format_pdf: "PDF", format_pptx: "PowerPoint", format_indesign_json: "InDesign"
    };
    return Object.keys(labels).filter(function (name) { return values[name] === "yes"; })
      .map(function (name) { return labels[name]; });
  }

  function updateSummary(form, summary) {
    var values = valuesFrom(form);
    var groups = {
      category_path: "categoría", vehicle_make: "marca vehicular",
      brand: "marca de producto", internal_reference_original: "referencia"
    };
    var count = referenceCount(values.selected_references);
    var formats = selectedFormats(values);
    var items = [
      "Agrupado por " + (groups[values.group_by] || "categoría"),
      (values.columns || "2") + " columna" + (values.columns === "1" ? "" : "s"),
      count ? count + " referencias elegidas" : "Todos los productos",
      formats.length ? formats.join(" · ") : "Sin entregables"
    ];
    summary.replaceChildren.apply(summary, items.map(function (itemText) {
      var item = document.createElement("li"); item.textContent = itemText; return item;
    }));
  }

  function enhanceComposer(form, actions) {
    var key = storageKey(actions);
    var summary = document.createElement("ul");
    summary.className = "composer-live-summary";
    summary.setAttribute("aria-label", "Resumen actual de la edición");
    var tools = document.createElement("div");
    tools.className = "composer-draft-tools";
    tools.innerHTML = '<p><strong>Borrador de composición</strong><span>Los cambios se guardan únicamente en este navegador.</span></p>';
    var reset = document.createElement("button");
    reset.type = "button"; reset.className = "secondary-button"; reset.textContent = "Restablecer";
    tools.appendChild(reset);
    actions.parentNode.insertBefore(summary, actions);
    actions.parentNode.insertBefore(tools, actions);

    var restored = restore(form, readDraft(key));
    var status = tools.querySelector("span");
    if (restored) status.textContent = "Borrador recuperado de este navegador.";
    updateSummary(form, summary);

    var timer = 0;
    function save() {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        var stored = writeDraft(key, valuesFrom(form));
        status.textContent = stored ? "Guardado localmente a las " + new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}) + "." : "No fue posible guardar localmente.";
      }, 180);
      updateSummary(form, summary);
    }
    form.addEventListener("input", save);
    form.addEventListener("change", save);
    reset.addEventListener("click", function () {
      clearDraft(key); form.reset(); updateSummary(form, summary);
      status.textContent = "Se restauró la configuración inicial.";
    });
  }

  document.documentElement.classList.add("composer-js");
  document.querySelectorAll(".js-preview-actions").forEach(function (actions) {
    var form = actions.closest("form");
    if (form) enhanceComposer(form, actions);
  });
  document.querySelectorAll("[data-preview-target]").forEach(function (button) {
    button.addEventListener("click", function () { openPreview(button); });
  });
}());
