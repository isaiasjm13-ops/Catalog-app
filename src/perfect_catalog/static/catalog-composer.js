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

  function enhanceProductPicker(form, actions) {
    var textarea = form.elements.namedItem("selected_references");
    if (!textarea) return;
    var launch = document.createElement("button");
    launch.type = "button"; launch.className = "secondary-button product-picker-launch";
    launch.textContent = "Elegir productos visualmente";
    textarea.parentNode.appendChild(launch);

    var dialog = document.createElement("dialog");
    dialog.className = "product-picker";
    dialog.innerHTML = '<header><div><strong>Elegir productos</strong><small>Busca y marca referencias del release publicado.</small></div><button type="button" class="product-picker-close" aria-label="Cerrar">×</button></header><form method="dialog" class="product-picker-search"><input type="search" maxlength="120" placeholder="Referencia, producto, categoría, aplicación o motor" aria-label="Buscar productos"><button type="submit" class="secondary-button">Buscar</button></form><p class="product-picker-status" role="status" aria-live="polite"></p><div class="product-picker-grid"></div><footer><button type="button" class="secondary-button product-picker-all">Usar todos</button><div><button type="button" class="secondary-button product-picker-prev">Anterior</button><button type="button" class="secondary-button product-picker-next">Siguiente</button></div><button type="button" class="primary-button product-picker-apply">Aplicar selección</button></footer>';
    document.body.appendChild(dialog);
    var search = dialog.querySelector("input"), grid = dialog.querySelector(".product-picker-grid");
    var status = dialog.querySelector(".product-picker-status"), offset = 0, limit = 24, total = 0;
    var chosen = new Map();

    function readTextarea() {
      chosen.clear();
      String(textarea.value || "").split(/[\n,;]+/).map(function (value) { return value.trim(); })
        .filter(Boolean).forEach(function (value) { chosen.set(value.toLocaleUpperCase("es"), value); });
    }

    function productCard(product) {
      var label = document.createElement("label"); label.className = "product-picker-card";
      var checkbox = document.createElement("input"); checkbox.type = "checkbox";
      checkbox.checked = chosen.has(product.reference.toLocaleUpperCase("es"));
      checkbox.addEventListener("change", function () {
        var key = product.reference.toLocaleUpperCase("es");
        if (checkbox.checked) chosen.set(key, product.reference); else chosen.delete(key);
        status.textContent = chosen.size ? chosen.size + " productos seleccionados" : "Todos los productos se incluirán";
      });
      label.appendChild(checkbox);
      if (product.has_image) {
        var image = document.createElement("img");
        image.src = actions.getAttribute("data-preview-url") + "/images/" + product.item_number;
        image.alt = ""; image.loading = "lazy"; label.appendChild(image);
      } else {
        var placeholder = document.createElement("span"); placeholder.className = "product-picker-placeholder";
        placeholder.textContent = "Sin imagen"; label.appendChild(placeholder);
      }
      var content = document.createElement("span"); content.className = "product-picker-copy";
      var reference = document.createElement("code"); reference.textContent = product.reference;
      var name = document.createElement("strong"); name.textContent = product.name;
      var category = document.createElement("small"); category.textContent = product.category;
      content.append(reference, name, category);
      if (product.applications.length) {
        var applications = document.createElement("small"); applications.textContent = product.applications.join(" · "); content.appendChild(applications);
      }
      label.appendChild(content); return label;
    }

    function load() {
      status.textContent = "Cargando productos…"; grid.replaceChildren();
      var endpoint = actions.getAttribute("data-preview-url").replace(/\/preview$/, "/products");
      var query = new URLSearchParams({query: search.value.trim(), limit: String(limit), offset: String(offset)});
      window.fetch(endpoint + "?" + query.toString(), {headers: {Accept: "application/json"}})
        .then(function (response) { if (!response.ok) throw new Error("request"); return response.json(); })
        .then(function (payload) {
          total = payload.total; grid.replaceChildren.apply(grid, payload.products.map(productCard));
          status.textContent = total ? (offset + 1) + "–" + Math.min(offset + limit, total) + " de " + total + " · " + (chosen.size ? chosen.size + " seleccionados" : "se incluirán todos") : "No se encontraron productos";
          dialog.querySelector(".product-picker-prev").disabled = offset === 0;
          dialog.querySelector(".product-picker-next").disabled = offset + limit >= total;
        }).catch(function () { status.textContent = "No se pudieron cargar los productos. Reintenta."; });
    }

    launch.addEventListener("click", function () { readTextarea(); offset = 0; dialog.showModal(); load(); });
    dialog.querySelector(".product-picker-close").addEventListener("click", function () { dialog.close(); });
    dialog.querySelector(".product-picker-search").addEventListener("submit", function (event) { event.preventDefault(); offset = 0; load(); });
    dialog.querySelector(".product-picker-prev").addEventListener("click", function () { offset = Math.max(0, offset - limit); load(); });
    dialog.querySelector(".product-picker-next").addEventListener("click", function () { offset += limit; load(); });
    dialog.querySelector(".product-picker-all").addEventListener("click", function () { chosen.clear(); textarea.value = ""; textarea.dispatchEvent(new Event("input", {bubbles: true})); dialog.close(); });
    dialog.querySelector(".product-picker-apply").addEventListener("click", function () { textarea.value = Array.from(chosen.values()).join("\n"); textarea.dispatchEvent(new Event("input", {bubbles: true})); dialog.close(); });
    dialog.addEventListener("click", function (event) { if (event.target === dialog) dialog.close(); });
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
    enhanceProductPicker(form, actions);

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
