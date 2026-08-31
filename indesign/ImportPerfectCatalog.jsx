#target "InDesign"

(function () {
    var SCHEMA = "perfect-catalog.indesign-snapshot.v1";
    var SCRIPT_VERSION = "1.36.0";
    var ACTIVE_TITLE_FONT = null, ACTIVE_BODY_FONT = null;
    function fail(message) { alert("Perfect Catalog\n\n" + message); throw new Error(message); }
    function parseJson(text) {
        if (typeof JSON !== "undefined" && JSON.parse) return JSON.parse(text);
        var sanitized = String(text);
        if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(sanitized)) fail("El snapshot JSON contiene caracteres de control no permitidos.");
        var safe = /^[\],:{}\s]*$/.test(sanitized
            .replace(/\\(?:["\\\/bfnrt]|u[0-9a-fA-F]{4})/g, "@")
            .replace(/"[^"\\\n\r]*"|true|false|null|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?/g, "]")
            .replace(/(?:^|:|,)(?:\s*\[)+/g, ""));
        if (!safe) fail("El snapshot JSON contiene sintaxis no permitida.");
        try { return eval("(" + sanitized + ")"); }
        catch (error) { fail("El snapshot JSON no se pudo interpretar."); }
    }
    function quoteJson(value) {
        return '"' + String(value).replace(/[\\"\u0000-\u001f]/g, function (character) {
            var escapes = {"\\": "\\\\", '"': '\\"', "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"};
            if (escapes[character]) return escapes[character];
            var code = character.charCodeAt(0).toString(16); return "\\u" + ("0000" + code).slice(-4);
        }) + '"';
    }
    function stringifyJson(value) {
        if (typeof JSON !== "undefined" && JSON.stringify) return JSON.stringify(value, null, 2);
        if (value === null) return "null";
        if (typeof value === "string") return quoteJson(value);
        if (typeof value === "number") return isFinite(value) ? String(value) : "null";
        if (typeof value === "boolean") return value ? "true" : "false";
        var index, parts = [];
        if (value instanceof Array) {
            for (index = 0; index < value.length; index++) parts.push(stringifyJson(value[index]));
            return "[" + parts.join(",") + "]";
        }
        if (typeof value === "object") {
            for (var key in value) if (value.hasOwnProperty(key) && typeof value[key] !== "undefined") parts.push(quoteJson(key) + ":" + stringifyJson(value[key]));
            return "{" + parts.join(",") + "}";
        }
        return "null";
    }
    function readJson(file) {
        file.encoding = "UTF-8"; if (!file.open("r")) fail("No se pudo abrir el snapshot.");
        var text = file.read(); file.close();
        if (text.charCodeAt(0) === 65279) text = text.substring(1);
        return parseJson(text);
    }
    function writeJson(file, payload) {
        file.encoding = "UTF-8"; if (!file.open("w")) fail("No se pudo escribir el reporte de preflight.");
        file.write(stringifyJson(payload)); file.close();
    }
    function repairText(input) {
        var text = String(input);
        var replacements = {
            "\u00c2\u00b7": "\u00b7", "\u00c2\u00a0": " ",
            "\u00c3\u00a1": "\u00e1", "\u00c3\u00a9": "\u00e9", "\u00c3\u00ad": "\u00ed", "\u00c3\u00b3": "\u00f3", "\u00c3\u00ba": "\u00fa",
            "\u00c3\u0081": "\u00c1", "\u00c3\u0089": "\u00c9", "\u00c3\u008d": "\u00cd", "\u00c3\u0093": "\u00d3", "\u00c3\u009a": "\u00da",
            "\u00c3\u00b1": "\u00f1", "\u00c3\u0091": "\u00d1", "\u00c3\u00bc": "\u00fc", "\u00c3\u009c": "\u00dc"
        };
        for (var damaged in replacements) if (replacements.hasOwnProperty(damaged)) text = text.split(damaged).join(replacements[damaged]);
        return text;
    }
    function value(product, key, fallback) {
        var current = product[key];
        if (current === null || current === undefined || current === "") return repairText(fallback);
        if (current instanceof Array) return repairText(current.join("; "));
        return repairText(current);
    }
    function optionalValue(product, key) {
        var current = product[key];
        if (current === null || current === undefined || current === "") return "";
        if (current instanceof Array) return repairText(current.join("; "));
        return repairText(current);
    }
    function frame(page, bounds, contents, pointSize, bold, style) {
        var box = page.textFrames.add({geometricBounds: bounds, contents: contents});
        box.textFramePreferences.insetSpacing = [8, 8, 8, 8]; box.texts[0].pointSize = Math.max(12, pointSize);
        box.texts[0].leading = box.texts[0].pointSize * (style && style.leading ? style.leading : 1.8);
        var selectedFont = bold ? ACTIVE_TITLE_FONT : ACTIVE_BODY_FONT;
        if (selectedFont && selectedFont.isValid) box.texts[0].appliedFont = selectedFont;
        if (bold) { try { box.texts[0].fontStyle = "Bold"; } catch (ignored) {} }
        if (style) {
            if (style.fill) box.fillColor = style.fill;
            if (style.stroke) { box.strokeColor = style.stroke; box.strokeWeight = style.strokeWeight || 0.75; }
            if (style.text) box.texts[0].fillColor = style.text;
        }
        return box;
    }
    function fitFrame(box, preferredSize, minimumSize, leadingRatio) {
        var size = preferredSize;
        while (box.overflows && size > minimumSize) {
            size -= 1;
            box.texts[0].pointSize = size;
            box.texts[0].leading = size * leadingRatio;
        }
        return box;
    }
    function fontByName(family, style) {
        var font = app.fonts.itemByName(String(family) + "\t" + String(style));
        return font && font.isValid ? font : null;
    }
    function documentColor(document, name, values) {
        var color = document.colors.itemByName(name);
        if (!color.isValid) color = document.colors.add({name: name, model: ColorModel.PROCESS, space: ColorSpace.RGB, colorValue: values});
        return color;
    }
    function hexRgb(value, fallback) {
        var match = /^#([0-9a-f]{6})$/i.exec(String(value || ""));
        if (!match) return fallback;
        return [parseInt(match[1].substr(0,2),16), parseInt(match[1].substr(2,2),16), parseInt(match[1].substr(4,2),16)];
    }
    function themeDefinition(document, name, visual) {
        var palettes = {
            forest: {primary: [8, 102, 80], secondary: [199, 223, 84], ink: [23, 35, 31], paper: [244, 241, 232], card: [255, 255, 255]},
            industrial: {primary: [195, 74, 33], secondary: [32, 35, 39], ink: [34, 39, 43], paper: [236, 235, 231], card: [255, 255, 255]},
            midnight: {primary: [46, 99, 199], secondary: [122, 162, 247], ink: [17, 24, 39], paper: [233, 238, 247], card: [255, 255, 255]},
            classic: {primary: [138, 106, 47], secondary: [201, 169, 106], ink: [33, 29, 23], paper: [245, 240, 229], card: [255, 253, 248]}
        };
        if (!palettes[name]) fail("El tema editorial no es compatible.");
        var palette = palettes[name], prefix = "Perfect Catalog " + name + " ";
        if (visual) palette = {primary: hexRgb(visual.primary_color, palette.primary), secondary: hexRgb(visual.secondary_color, palette.secondary), ink: hexRgb(visual.ink_color, palette.ink), paper: hexRgb(visual.paper_color, palette.paper), card: [255,255,255]};
        return {name: name,
            primary: documentColor(document, prefix + "Primary", palette.primary),
            secondary: documentColor(document, prefix + "Secondary", palette.secondary),
            ink: documentColor(document, prefix + "Ink", palette.ink),
            paper: documentColor(document, prefix + "Paper", palette.paper),
            card: documentColor(document, prefix + "Card", palette.card)};
    }
    function imageFile(baseFolder, imagePath) {
        if (!imagePath) return null;
        var clean = String(imagePath).replace(/\\/g, "/");
        if (clean.indexOf("..") >= 0 || clean.charAt(0) === "/" || /^[A-Za-z]:/.test(clean)) return null;
        var candidate = new File(baseFolder.fsName + "/" + clean);
        return candidate.exists ? candidate : null;
    }
    function brandMark(page, baseFolder, visual, watermark, company) {
        if (!visual) return;
        var source = company ? (visual.company || {}) : visual;
        var logo = imageFile(baseFolder, source.packaged_logo_path);
        if (!logo && !company && visual.logo_asset_key) logo = new File(baseFolder.fsName + "/brand/logo.svg");
        if (!logo || !logo.exists) return;
        var bounds = watermark ? [720, 300, 760, 550] : [18, 420, 48, 560];
        var box = page.rectangles.add({geometricBounds: bounds, strokeWeight: 0});
        try { box.place(logo); box.fit(FitOptions.PROPORTIONALLY); box.fit(FitOptions.CENTER_CONTENT); if (watermark) box.transparencySettings.blendingSettings.opacity = Number(visual.watermark_opacity || .05) * 100; } catch (ignored) {}
    }
    function separatorPage(document, label, theme) {
        var page = document.pages.add();
        var background = page.rectangles.add({geometricBounds: page.bounds, fillColor: theme.paper, strokeWeight: 0});
        background.sendToBack();
        page.rectangles.add({geometricBounds: [190, 55, 205, 305], fillColor: theme.secondary, strokeWeight: 0});
        var heading = frame(page, [225, 55, 385, 540], repairText(label), 30, true, {text: theme.primary, leading: 1.15});
        fitFrame(heading, 30, 18, 1.15);
        frame(page, [405, 55, 455, 540], "Separador de secci\u00f3n \u00b7 Perfect Trading", 12, false, {text: theme.ink, leading: 1.4});
        return page;
    }
    function createContentsPages(document, count, theme) {
        var pages = [], total = Math.max(1, Math.ceil(count / 15));
        for (var index = 0; index < total; index++) {
            var page = document.pages.add();
            page.rectangles.add({geometricBounds: page.bounds, fillColor: theme.paper, strokeWeight: 0}).sendToBack();
            frame(page, [45, 45, 115, 550], index ? "\u00cdndice (continuaci\u00f3n)" : "\u00cdndice", 28, true, {text: theme.primary, leading: 1.15});
            pages.push(page);
        }
        return pages;
    }
    function fillContentsPages(pages, entries, theme) {
        for (var index = 0; index < entries.length; index++) {
            var local = index % 15, page = pages[Math.floor(index / 15)], top = 125 + local * 42;
            frame(page, [top, 50, top + 40, 500], entries[index].label, 12, false, {text: theme.ink, leading: 1.15});
            frame(page, [top, 505, top + 40, 550], String(entries[index].page), 12, true, {text: theme.primary, leading: 1.15});
        }
    }
    function companyAccent(document, visual) {
        var company = (visual && visual.company) || {};
        return documentColor(document, "Perfect Catalog Company Primary",
            hexRgb(company.primary_color, [8, 102, 80]));
    }
    function addPageNumbers(document, firstContentPage, theme, visual) {
        var corporate = companyAccent(document, visual);
        var companyName = (visual && visual.company && visual.company.display_name) || "Perfect Trading International";
        for (var index = firstContentPage; index < document.pages.length; index++) {
            frame(document.pages[index], [790, 270, 825, 325], String(index + 1), 12, true, {text: theme.primary, leading: 1.1});
            document.pages[index].rectangles.add({geometricBounds: [782, 45, 784, 550], fillColor: corporate, strokeWeight: 0});
            frame(document.pages[index], [790, 45, 825, 260], companyName, 12, false, {text: corporate, leading: 1.1});
        }
    }
    function vehicleMakeMark(page, baseFolder, visual, makeName) {
        var source = visual && visual.vehicle_makes && visual.vehicle_makes[String(makeName)];
        var logo = source ? imageFile(baseFolder, source.packaged_logo_path) : null;
        if (!logo) return;
        var box = page.rectangles.add({geometricBounds: [268, 445, 322, 540], strokeWeight: 0});
        try { box.place(logo); box.fit(FitOptions.PROPORTIONALLY); box.fit(FitOptions.CENTER_CONTENT); } catch (ignored) {}
    }
    function profileDefinition(profile) {
        if (profile === "T1") return {perPage: 1, columns: 1, rows: 1, imageHeight: 300};
        if (profile === "T2") return {perPage: 2, columns: 1, rows: 2, imageHeight: 150};
        if (profile === "TABLE") return {perPage: 10, columns: 1, rows: 10, imageHeight: 0};
        return {perPage: 4, columns: 2, rows: 2, imageHeight: 125};
    }
    function adaptiveProfile(requested, product) {
        if (requested === "TABLE" || requested === "T1") return requested;
        var score = value(product, "name_original", "").length
            + value(product, "applications", "").length
            + value(product, "oem_references", "").length
            + value(product, "engine_types", "").length
            + value(product, "category_path", "").length;
        if (score > 280) return "T1";
        if (requested === "T4" && score > 120) return "T2";
        return requested;
    }
    function configureDocument(document) {
        document.viewPreferences.horizontalMeasurementUnits = MeasurementUnits.POINTS;
        document.viewPreferences.verticalMeasurementUnits = MeasurementUnits.POINTS;
        document.viewPreferences.rulerOrigin = RulerOrigin.PAGE_ORIGIN;
        document.documentPreferences.facingPages = false;
        document.documentPreferences.pageWidth = "210mm";
        document.documentPreferences.pageHeight = "297mm";
        document.documentPreferences.documentBleedUniformSize = true;
        document.documentPreferences.documentBleedTopOffset = "3mm";
        document.insertLabel("perfect_catalog_page_format", "A4-portrait");
        document.insertLabel("perfect_catalog_bleed_mm", "3");
    }
    function productBounds(definition, slot) {
        if (definition.perPage === 10) {
            var rowTop = 50 + slot * 67; return [rowTop, 35, rowTop + 59, 560];
        }
        var column = slot % definition.columns, row = Math.floor(slot / definition.columns);
        var width = 525 / definition.columns, height = 690 / definition.rows;
        return [55 + row * height, 35 + column * width, 55 + (row + 1) * height - 12, 35 + (column + 1) * width - 12];
    }
    function productFrame(page, bounds, product, index, definition, baseFolder, report, theme) {
        var reference = value(product, "internal_reference_original", "Sin referencia");
        if (definition.perPage === 10) {
            var tableRow = frame(page, bounds, reference + "\t" + value(product, "name_original", "Sin nombre") + "\t" + value(product, "applications", "No indicadas"), 12, false,
                {fill: index % 2 ? theme.card : theme.paper, stroke: theme.primary, text: theme.ink, strokeWeight: 0.35});
            tableRow.insertLabel("perfect_catalog_product_index", String(index));
            if (tableRow.overflows) report.overflow_product_indexes.push(index); return;
        }
        var top = bounds[0], left = bounds[1], bottom = bounds[2], right = bounds[3];
        var image = imageFile(baseFolder, product.image_path);
        var imageHeight = image ? definition.imageHeight : 0;
        if (image) {
            try {
                var imageBox = page.rectangles.add({geometricBounds: [top + 8, left + 8, top + imageHeight, right - 8]});
                imageBox.strokeColor = theme.primary; imageBox.strokeWeight = 0.75;
                imageBox.place(image); imageBox.fit(FitOptions.PROPORTIONALLY); imageBox.fit(FitOptions.CENTER_CONTENT);
                report.linked_image_count++;
            } catch (imageError) { report.missing_images.push({product_index: index, reference: reference, reason: imageError.message}); }
        } else { report.missing_images.push({product_index: index, reference: reference, reason: "Ruta ausente o no segura"}); }
        var lines = [reference, value(product, "name_original", "Sin nombre")];
        var category = optionalValue(product, "piece_type") || optionalValue(product, "category_path"), brand = optionalValue(product, "brand");
        if (category || brand) lines.push(category + (category && brand ? " \u00b7 " : "") + brand);
        var oem = optionalValue(product, "oem_references"), applications = optionalValue(product, "applications"), engines = optionalValue(product, "engine_types");
        if (oem) lines.push("OEM: " + oem);
        if (applications) lines.push("Aplicaciones: " + applications);
        if (engines) lines.push("Motor: " + engines);
        var contents = lines.join("\r");
        var cardTop = image ? top + imageHeight + 6 : top;
        var card = frame(page, [cardTop, left, bottom, right], contents, 12, false,
            {fill: theme.card, stroke: theme.primary, text: theme.ink, strokeWeight: 0.75});
        try { card.paragraphs[0].fontStyle = "Bold"; } catch (ignored) {}
        card.paragraphs[0].pointSize = 13; card.insertLabel("perfect_catalog_product_index", String(index));
        if (card.paragraphs.length > 1) {
            try { card.paragraphs[1].fontStyle = "Bold"; } catch (ignoredName) {}
            card.paragraphs[1].pointSize = 14; card.paragraphs[1].fillColor = theme.primary;
        }
        if (card.overflows) report.overflow_product_indexes.push(index);
    }
    function render(snapshot, baseFolder) {
        if (!snapshot || snapshot.schema !== SCHEMA) fail("El esquema del snapshot no es compatible.");
        if (!snapshot.release || snapshot.release.status !== "published") fail("El release no est\u00e1 publicado.");
        if (!(snapshot.products instanceof Array) || snapshot.products.length < 1) fail("El snapshot no contiene productos.");
        var profile = (snapshot.layout && snapshot.layout.template_profile) || "T4";
        if (!/^(T4|T2|T1|TABLE)$/.test(profile)) fail("El perfil de plantilla no es compatible.");
        var themeName = (snapshot.layout && snapshot.layout.theme) || "forest";
        if (!/^(forest|industrial|midnight|classic)$/.test(themeName)) fail("El tema editorial no es compatible.");
        var document = app.documents.add();
        configureDocument(document);
        var visual = (snapshot.layout && snapshot.layout.visual_profile) || null;
        var theme = themeDefinition(document, themeName, visual);
        document.insertLabel("perfect_catalog_schema", snapshot.schema);
        document.insertLabel("perfect_catalog_release_id", snapshot.release.release_id);
        document.insertLabel("perfect_catalog_snapshot_sha256", snapshot.release.snapshot_sha256);
        document.insertLabel("perfect_catalog_template_profile", profile);
        document.insertLabel("perfect_catalog_theme", themeName);
        document.insertLabel("perfect_catalog_importer_version", SCRIPT_VERSION);
        var report = {schema: "perfect-catalog.indesign-preflight.v1", release_id: snapshot.release.release_id,
            snapshot_sha256: snapshot.release.snapshot_sha256, template_profile: profile, theme: themeName,
            product_count: snapshot.products.length, linked_image_count: 0, missing_images: [],
            overflow_product_indexes: [], unavailable_fonts: [], group_count: 0, page_count: 0};
        var titleFamily = (visual && visual.title_font_family) || "Barlow Condensed";
        var bodyFamily = (visual && visual.body_font_family) || "DM Sans";
        ACTIVE_TITLE_FONT = fontByName(titleFamily, "Bold");
        ACTIVE_BODY_FONT = fontByName(bodyFamily, "Regular");
        if (!ACTIVE_TITLE_FONT) report.unavailable_fonts.push(titleFamily + " Bold");
        if (!ACTIVE_BODY_FONT) report.unavailable_fonts.push(bodyFamily + " Regular");
        var title = repairText((snapshot.layout && snapshot.layout.title) || "Cat\u00e1logo de productos");
        var subtitle = repairText((snapshot.layout && snapshot.layout.subtitle) || snapshot.release.version);
        var coverBackground = document.pages[0].rectangles.add({geometricBounds: document.pages[0].bounds, fillColor: theme.paper, strokeWeight: 0});
        coverBackground.sendToBack();
        frame(document.pages[0], [160, 55, 245, 540], title, 30, true, {text: theme.primary});
        frame(document.pages[0], [260, 55, 315, 540], subtitle, 16, false, {text: theme.ink});
        brandMark(document.pages[0], baseFolder, visual, false, true);
        if (!visual || visual.watermark_enabled !== false) brandMark(document.pages[0], baseFolder, visual, true, false);
        var definition = profileDefinition(profile), groupBy = (snapshot.layout && snapshot.layout.group_by) || "category_path";
        var secondaryGroupBy = (snapshot.layout && snapshot.layout.group_by_secondary) || "";
        var groupKeys = {}, expectedGroups = 0;
        for (var groupIndex = 0; groupIndex < snapshot.products.length; groupIndex++) {
            var groupProduct = snapshot.products[groupIndex], groupKey = value(groupProduct, groupBy, "Sin categor\u00eda");
            if (secondaryGroupBy) groupKey += " \u00b7 " + value(groupProduct, secondaryGroupBy, "Sin subgrupo");
            if (!groupKeys[groupKey]) { groupKeys[groupKey] = true; expectedGroups++; }
        }
        var contentsPages = createContentsPages(document, expectedGroups, theme), contentsEntries = [];
        var currentGroup = null, activeProfile = null, slot = definition.perPage, page = null, promotedCount = 0;
        for (var index = 0; index < snapshot.products.length; index++) {
            var product = snapshot.products[index], primaryGroup = value(product, groupBy, "Sin categor\u00eda"), group = primaryGroup, groupLabel = primaryGroup;
            if (secondaryGroupBy) {
                var secondaryGroup = value(product, secondaryGroupBy, "Sin subgrupo");
                group += " \u00b7 " + secondaryGroup;
                groupLabel += "\r" + secondaryGroup;
            }
            if (group !== currentGroup) { var separator = separatorPage(document, groupLabel, theme); brandMark(separator, baseFolder, visual, false, false); if (groupBy === "vehicle_make") vehicleMakeMark(separator, baseFolder, visual, primaryGroup); contentsEntries.push({label: groupLabel.replace(/\r/g, " / "), page: separator.documentOffset + 1}); currentGroup = group; slot = definition.perPage; activeProfile = null; report.group_count++; }
            var effectiveProfile = adaptiveProfile(profile, product), effectiveDefinition = profileDefinition(effectiveProfile);
            if (effectiveProfile !== profile) promotedCount++;
            if (activeProfile !== effectiveProfile || slot >= effectiveDefinition.perPage) { page = document.pages.add(); brandMark(page, baseFolder, visual, false, false); slot = 0; activeProfile = effectiveProfile; }
            productFrame(page, productBounds(effectiveDefinition, slot), product, index, effectiveDefinition, baseFolder, report, theme); slot++;
        }
        fillContentsPages(contentsPages, contentsEntries, theme);
        addPageNumbers(document, contentsPages.length + 1, theme, visual);
        report.page_count = document.pages.length;
        var destination = File.saveDialog("Guardar cat\u00e1logo InDesign", "InDesign document:*.indd");
        if (!destination) { document.close(SaveOptions.NO); return; }
        if (!/\.indd$/i.test(destination.name)) destination = new File(destination.fsName + ".indd");
        document.save(destination);
        try {
            var fonts = document.fonts.everyItem().getElements();
            for (var fontIndex = 0; fontIndex < fonts.length; fontIndex++) {
                if (fonts[fontIndex].status !== FontStatus.INSTALLED) report.unavailable_fonts.push(fonts[fontIndex].fullName);
            }
        } catch (fontError) { report.unavailable_fonts.push("No se pudo consultar: " + fontError.message); }
        var reportFile = new File(destination.fsName.replace(/\.indd$/i, "") + ".preflight.json");
        writeJson(reportFile, report);
        alert("Perfect Catalog Importer v" + SCRIPT_VERSION + "\n\nCat\u00e1logo creado: " + snapshot.products.length + " productos.\nIm\u00e1genes faltantes: " + report.missing_images.length +
            ".\nFichas ampliadas automaticamente: " + promotedCount + ".\nTextos desbordados: " + report.overflow_product_indexes.length +
            ".\nFuentes no disponibles: " + report.unavailable_fonts.length + ".\nPaginas generadas: " + report.page_count + ".\n\n" + destination.fsName);
    }
    try {
        var scriptFile = new File($.fileName);
        var adjacent = new File(scriptFile.parent.fsName + "/catalog.indesign.json");
        var source = adjacent.exists ? adjacent : File.openDialog("Seleccionar snapshot Perfect Catalog", "Perfect Catalog JSON:*.json");
        if (source) render(readJson(source), source.parent);
    } catch (error) { alert("Perfect Catalog\n\nError: " + error.message); }
}());
