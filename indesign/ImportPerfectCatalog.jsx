#target "InDesign"

(function () {
    var SCHEMA = "perfect-catalog.indesign-snapshot.v1";

    function fail(message) {
        alert("Perfect Catalog\n\n" + message);
        throw new Error(message);
    }

    function readJson(file) {
        file.encoding = "UTF-8";
        if (!file.open("r")) fail("No se pudo abrir el snapshot.");
        var text = file.read();
        file.close();
        if (text.charCodeAt(0) === 65279) text = text.substring(1);
        if (typeof JSON === "undefined" || !JSON.parse) {
            fail("Esta versión de InDesign no ofrece JSON.parse.");
        }
        return JSON.parse(text);
    }

    function value(product, key, fallback) {
        var current = product[key];
        if (current === null || current === undefined || current === "") return fallback;
        if (current instanceof Array) return current.join("; ");
        return String(current);
    }

    function frame(page, bounds, contents, pointSize, bold) {
        var box = page.textFrames.add({geometricBounds: bounds, contents: contents});
        box.textFramePreferences.insetSpacing = [8, 8, 8, 8];
        box.texts[0].pointSize = pointSize;
        if (bold) {
            try { box.texts[0].fontStyle = "Bold"; } catch (ignored) {}
        }
        return box;
    }

    function render(snapshot) {
        if (!snapshot || snapshot.schema !== SCHEMA) fail("El esquema del snapshot no es compatible.");
        if (!snapshot.release || snapshot.release.status !== "published") fail("El release no está publicado.");
        if (!(snapshot.products instanceof Array) || snapshot.products.length < 1) fail("El snapshot no contiene productos.");

        var document = app.documents.add();
        document.insertLabel("perfect_catalog_schema", snapshot.schema);
        document.insertLabel("perfect_catalog_release_id", snapshot.release.release_id);
        document.insertLabel("perfect_catalog_snapshot_sha256", snapshot.release.snapshot_sha256);

        var title = (snapshot.layout && snapshot.layout.title) || "Catálogo de productos";
        var subtitle = (snapshot.layout && snapshot.layout.subtitle) || snapshot.release.version;
        frame(document.pages[0], [160, 55, 245, 540], title, 30, true);
        frame(document.pages[0], [260, 55, 315, 540], subtitle, 16, false);

        var cardsPerPage = 6;
        var overflow = 0;
        for (var index = 0; index < snapshot.products.length; index++) {
            var slot = index % cardsPerPage;
            if (slot === 0) document.pages.add();
            var page = document.pages[document.pages.length - 1];
            var column = slot % 2;
            var row = Math.floor(slot / 2);
            var top = 45 + row * 235;
            var left = 35 + column * 285;
            var product = snapshot.products[index];
            var contents = value(product, "internal_reference_original", "Sin referencia") + "\r" +
                value(product, "name_original", "Sin nombre") + "\r" +
                value(product, "category_path", "Sin categoría") + "\r" +
                "Aplicaciones: " + value(product, "applications", "No indicadas");
            var card = frame(page, [top, left, top + 205, left + 255], contents, 10, false);
            try { card.paragraphs[0].fontStyle = "Bold"; } catch (ignored) {}
            card.paragraphs[0].pointSize = 14;
            card.insertLabel("perfect_catalog_product_index", String(index));
            if (card.overflows) overflow++;
        }

        var destination = File.saveDialog("Guardar catálogo InDesign", "InDesign document:*.indd");
        if (!destination) {
            document.close(SaveOptions.NO);
            return;
        }
        if (!/\.indd$/i.test(destination.name)) destination = new File(destination.fsName + ".indd");
        document.save(destination);
        alert("Catálogo creado: " + snapshot.products.length + " productos.\n" +
            "Textos desbordados detectados: " + overflow + ".\n\n" + destination.fsName);
    }

    try {
        var source = File.openDialog("Seleccionar snapshot Perfect Catalog", "Perfect Catalog JSON:*.json");
        if (source) render(readJson(source));
    } catch (error) {
        alert("Perfect Catalog\n\nError: " + error.message);
    }
}());
