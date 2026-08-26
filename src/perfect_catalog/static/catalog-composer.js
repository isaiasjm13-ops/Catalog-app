(function () {
  "use strict";

  var previewFields = [
    "title", "subtitle", "group_by", "group_by_secondary", "filter_field",
    "filter_query", "selected_references", "theme", "columns", "template_profile"
  ];

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

  document.documentElement.classList.add("composer-js");
  document.querySelectorAll("[data-preview-target]").forEach(function (button) {
    button.addEventListener("click", function () { openPreview(button); });
  });
}());
