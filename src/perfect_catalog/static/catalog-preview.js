"use strict";

document.querySelectorAll(".catalog-preview-sheet[data-brand-primary]").forEach((sheet) => {
  const colors = {
    "--forest": sheet.dataset.brandPrimary,
    "--secondary": sheet.dataset.brandSecondary,
    "--brand-ink": sheet.dataset.brandInk,
    "--brand-paper": sheet.dataset.brandPaper,
  };
  for (const [property, value] of Object.entries(colors)) {
    if (/^#[0-9A-F]{6}$/i.test(value || "")) sheet.style.setProperty(property, value);
  }
});
