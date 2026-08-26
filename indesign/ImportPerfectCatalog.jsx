#target "InDesign"

(function () {
    var SCHEMA = "perfect-catalog.indesign-snapshot.v1";
    function fail(message) { alert("Perfect Catalog\n\n" + message); throw new Error(message); }
    function readJson(file) {
        file.encoding = "UTF-8"; if (!file.open("r")) fail("No se pudo abrir el snapshot.");
        var text = file.read(); file.close();
        if (text.charCodeAt(0) === 65279) text = text.substring(1);
        if (typeof JSON === "undefined" || !JSON.parse) fail("Esta versión de InDesign no ofrece JSON.parse.");
        return JSON.parse(text);
    }
    function writeJson(file, payload) {
        file.encoding = "UTF-8"; if (!file.open("w")) fail("No se pudo escribir el reporte de preflight.");
        file.write(JSON.stringify(payload, null, 2)); file.close();
    }
    function value(product, key, fallback) {
        var current = product[key];
        if (current === null || current === undefined || current === "") return fallback;
        if (current instanceof Array) return current.join("; ");
        return String(current);
    }
    function frame(page, bounds, contents, pointSize, bold) {
        var box = page.textFrames.add({geometricBounds: bounds, contents: contents});
        box.textFramePreferences.insetSpacing = [8, 8, 8, 8]; box.texts[0].pointSize = pointSize;
        if (bold) { try { box.texts[0].fontStyle = "Bold"; } catch (ignored) {} }
        return box;
    }
    function imageFile(baseFolder, imagePath) {
        if (!imagePath) return null;
        var clean = String(imagePath).replace(/\\/g, "/");
        if (clean.indexOf("..") >= 0 || clean.charAt(0) === "/" || /^[A-Za-z]:/.test(clean)) return null;
        var candidate = new File(baseFolder.fsName + "/" + clean);
        return candidate.exists ? candidate : null;
    }
    function separatorPage(document, label) {
        var page = document.pages.add();
        frame(page, [260, 55, 335, 540], String(label), 30, true);
        frame(page, [350, 55, 390, 540], "Separador de sección · Perfect Trading", 11, false);
    }
    function profileDefinition(profile) {
        if (profile === "T1") return {perPage: 1, columns: 1, rows: 1, imageHeight: 300};
        if (profile === "T2") return {perPage: 2, columns: 1, rows: 2, imageHeight: 150};
        if (profile === "TABLE") return {perPage: 16, columns: 1, rows: 16, imageHeight: 0};
        return {perPage: 4, columns: 2, rows: 2, imageHeight: 125};
    }
    function productBounds(definition, slot) {
        if (definition.perPage === 16) {
            var rowTop = 50 + slot * 43; return [rowTop, 35, rowTop + 37, 560];
        }
        var column = slot % definition.columns, row = Math.floor(slot / definition.columns);
        var width = 525 / definition.columns, height = 690 / definition.rows;
        return [55 + row * height, 35 + column * width, 55 + (row + 1) * height - 12, 35 + (column + 1) * width - 12];
    }
    function productFrame(page, bounds, product, index, definition, baseFolder, report) {
        var reference = value(product, "internal_reference_original", "Sin referencia");
        if (definition.perPage === 16) {
            var tableRow = frame(page, bounds, reference + "\t" + value(product, "name_original", "Sin nombre") + "\t" + value(product, "applications", "No indicadas"), 8, false);
            tableRow.insertLabel("perfect_catalog_product_index", String(index));
            if (tableRow.overflows) report.overflow_product_indexes.push(index); return;
        }
        var top = bounds[0], left = bounds[1], bottom = bounds[2], right = bounds[3];
        var image = imageFile(baseFolder, product.image_path);
        if (image) {
            try {
                var imageBox = page.rectangles.add({geometricBounds: [top + 8, left + 8, top + definition.imageHeight, right - 8]});
                imageBox.place(image); imageBox.fit(FitOptions.PROPORTIONALLY); imageBox.fit(FitOptions.CENTER_CONTENT);
                report.linked_image_count++;
            } catch (imageError) { report.missing_images.push({product_index: index, reference: reference, reason: imageError.message}); }
        } else { report.missing_images.push({product_index: index, reference: reference, reason: "Ruta ausente o no segura"}); }
        var contents = reference + "\r" + value(product, "name_original", "Sin nombre") + "\r" +
            value(product, "category_path", "Sin categoría") + "\r" + "Aplicaciones: " + value(product, "applications", "No indicadas");
        var card = frame(page, [top + definition.imageHeight + 6, left, bottom, right], contents, 9, false);
        try { card.paragraphs[0].fontStyle = "Bold"; } catch (ignored) {}
        card.paragraphs[0].pointSize = 13; card.insertLabel("perfect_catalog_product_index", String(index));
        if (card.overflows) report.overflow_product_indexes.push(index);
    }
    function render(snapshot, baseFolder) {
        if (!snapshot || snapshot.schema !== SCHEMA) fail("El esquema del snapshot no es compatible.");
        if (!snapshot.release || snapshot.release.status !== "published") fail("El release no está publicado.");
        if (!(snapshot.products instanceof Array) || snapshot.products.length < 1) fail("El snapshot no contiene productos.");
        var profile = (snapshot.layout && snapshot.layout.template_profile) || "T4";
        if (!/^(T4|T2|T1|TABLE)$/.test(profile)) fail("El perfil de plantilla no es compatible.");
        var document = app.documents.add();
        document.insertLabel("perfect_catalog_schema", snapshot.schema);
        document.insertLabel("perfect_catalog_release_id", snapshot.release.release_id);
        document.insertLabel("perfect_catalog_snapshot_sha256", snapshot.release.snapshot_sha256);
        document.insertLabel("perfect_catalog_template_profile", profile);
        var report = {schema: "perfect-catalog.indesign-preflight.v1", release_id: snapshot.release.release_id,
            snapshot_sha256: snapshot.release.snapshot_sha256, template_profile: profile,
            product_count: snapshot.products.length, linked_image_count: 0, missing_images: [],
            overflow_product_indexes: [], unavailable_fonts: []};
        var title = (snapshot.layout && snapshot.layout.title) || "Catálogo de productos";
        var subtitle = (snapshot.layout && snapshot.layout.subtitle) || snapshot.release.version;
        frame(document.pages[0], [160, 55, 245, 540], title, 30, true);
        frame(document.pages[0], [260, 55, 315, 540], subtitle, 16, false);
        var definition = profileDefinition(profile), groupBy = (snapshot.layout && snapshot.layout.group_by) || "category_path";
        var currentGroup = null, slot = definition.perPage, page = null;
        for (var index = 0; index < snapshot.products.length; index++) {
            var product = snapshot.products[index], group = value(product, groupBy, "Sin categoría");
            if (group !== currentGroup) { separatorPage(document, group); currentGroup = group; slot = definition.perPage; }
            if (slot >= definition.perPage) { page = document.pages.add(); slot = 0; }
            productFrame(page, productBounds(definition, slot), product, index, definition, baseFolder, report); slot++;
        }
        var destination = File.saveDialog("Guardar catálogo InDesign", "InDesign document:*.indd");
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
        alert("Catálogo creado: " + snapshot.products.length + " productos.\nImágenes faltantes: " + report.missing_images.length +
            ".\nTextos desbordados: " + report.overflow_product_indexes.length + ".\n\n" + destination.fsName);
    }
    try {
        var source = File.openDialog("Seleccionar snapshot Perfect Catalog", "Perfect Catalog JSON:*.json");
        if (source) render(readJson(source), source.parent);
    } catch (error) { alert("Perfect Catalog\n\nError: " + error.message); }
}());
