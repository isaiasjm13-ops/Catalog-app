(function () {
  "use strict";

  function channel(value) {
    value /= 255;
    return value <= 0.03928 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
  }

  function luminance(hex) {
    var value = String(hex || "").replace("#", "");
    return 0.2126 * channel(parseInt(value.slice(0, 2), 16))
      + 0.7152 * channel(parseInt(value.slice(2, 4), 16))
      + 0.0722 * channel(parseInt(value.slice(4, 6), 16));
  }

  function contrast(first, second) {
    var light = Math.max(luminance(first), luminance(second));
    var dark = Math.min(luminance(first), luminance(second));
    return (light + 0.05) / (dark + 0.05);
  }

  function currentLogo(form) {
    var container = form.closest(".brand-profile-card, .brand-profile-builder");
    var image = container ? container.querySelector(".identity-logo-preview") : null;
    return image ? image.src : "";
  }

  function enhance(form) {
    var primary = form.querySelector('input[name="primary_color"][type="color"]');
    if (!primary) return;
    var secondary = form.elements.namedItem("secondary_color");
    var ink = form.elements.namedItem("ink_color");
    var paper = form.elements.namedItem("paper_color");
    var name = form.elements.namedItem("display_name");
    var code = form.elements.namedItem("code");
    var tagline = form.elements.namedItem("tagline");
    var logoInput = form.elements.namedItem("logo");
    var preview = document.createElement("section");
    preview.className = "brand-live-preview";
    preview.setAttribute("aria-label", "Vista previa de identidad visual");
    preview.innerHTML = '<div class="brand-live-cover"><img class="brand-live-logo" alt="Vista previa del logo" hidden><span class="brand-live-initials"></span><small>Catálogo de productos</small><strong></strong></div><article class="brand-live-card"><code>REF-0001</code><strong>Nombre del producto</strong><span>APLICACIONES · Toyota Corolla 2014</span><span>MOTOR · 1.8 L</span></article><img class="brand-live-watermark" alt="" hidden><p class="brand-contrast-status" role="status"></p>';
    var anchor = form.querySelector(".brand-color-row");
    anchor.parentNode.insertBefore(preview, anchor.nextSibling);
    var logo = preview.querySelector(".brand-live-logo");
    var watermark = preview.querySelector(".brand-live-watermark");
    var initials = preview.querySelector(".brand-live-initials");
    var heading = preview.querySelector(".brand-live-cover strong");
    var status = preview.querySelector(".brand-contrast-status");
    var objectUrl = "";

    function label() {
      return String((name && name.value) || (code && code.value) || "Nueva marca").trim() || "Nueva marca";
    }

    function setLogo(source) {
      logo.hidden = !source; watermark.hidden = !source; initials.hidden = Boolean(source);
      if (source) { logo.src = source; watermark.src = source; }
    }

    function render() {
      preview.style.setProperty("--preview-primary", primary.value);
      preview.style.setProperty("--preview-secondary", secondary.value);
      preview.style.setProperty("--preview-ink", ink.value);
      preview.style.setProperty("--preview-paper", paper.value);
      var display = label(); initials.textContent = display.slice(0, 3).toLocaleUpperCase("es");
      heading.textContent = tagline && tagline.value.trim() ? tagline.value.trim() : display;
      var textRatio = contrast(ink.value, paper.value);
      var brandRatio = contrast(primary.value, paper.value);
      var valid = textRatio >= 4.5 && brandRatio >= 4.5;
      status.classList.toggle("has-warning", !valid);
      status.textContent = valid
        ? "Contraste legible · texto " + textRatio.toFixed(1) + ":1 · principal " + brandRatio.toFixed(1) + ":1"
        : "Ajusta los colores: texto/fondo y principal/fondo deben alcanzar 4.5:1.";
    }

    setLogo(currentLogo(form)); render();
    form.addEventListener("input", render);
    form.addEventListener("change", render);
    if (logoInput) logoInput.addEventListener("change", function () {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = logoInput.files && logoInput.files[0] ? URL.createObjectURL(logoInput.files[0]) : "";
      setLogo(objectUrl || currentLogo(form));
    });
  }

  document.querySelectorAll('form[action="/operator/brands"], form[action="/operator/brands/identity"]').forEach(enhance);
}());
