// The Google Apps Script for the Google Sheets file.

var SHEET_NAME = "Purchasing List";
var NAME_COL = 1;
var PRICE_COL = 6;
var SKU_COL = 9;
var SUPPLIER_COL = 10;
var URL_COL = 11;
var MAGIC_API_BASE = "<API base URL>";

function myOnEdit(e) {
    var range = e.range;
    var sheet = range.getSheet();

    // Ensure we only look at edits to single cells on the purchasing list.
    if (!(sheet.getName() == SHEET_NAME && e.value)) {
        return;
    }

    var row = range.getRow();
    var col = range.getColumn();
    if (col == URL_COL) {
        var url = e.value;
        _doURL(url, row, sheet);
    } else if (col == SKU_COL) {
        // Try to determine the supplier from the SKU.
        var sku = e.value;
        var supplier, url;

        if (sku.slice(0, 3) == "am-") {
            supplier = "AndyMark";
            if (sku.slice(-3) == "AUS") {
                supplier += " Australia";
            }
            url = "https://www.andymark.com/" + sku;
        } else if (sku.slice(0, 4) == "REV-") {
            supplier = "REV Robotics";
            url = "http://www.revrobotics.com/" + sku.toLowerCase() + "/";
        }

        if (supplier) {
            // sheet.getRange(row, SUPPLIER_COL, 1, 2).setValues([supplier, url]);
            _setCell(sheet, row, SUPPLIER_COL, supplier);
            _setCell(sheet, row, URL_COL, url);
            _doURL(url, row, sheet);
        }
    }
}

function _doURL(url, row, sheet) {
    var info = _getJSON(MAGIC_API_BASE + encodeURIComponent(url));
    if (!info) {
        Logger.log("unsupported URL: %s", url);
        return;
    }

    if (info.name)
        _setCell(sheet, row, NAME_COL, info.name);
    if (info.sku)
        _setCell(sheet, row, SKU_COL, info.sku);
    if (info.supplier)
        _setCell(sheet, row, SUPPLIER_COL, info.supplier);

    if (info.price) {
        if (info.currency == "AUD") {
            _setCell(sheet, row, PRICE_COL, info.price, info.has_aggregate);
        }
    }
}

function _getJSON(url) {
  var response = UrlFetchApp.fetch(url);
  return JSON.parse(response.getContentText());
}

function _setCell(sheet, row, col, newValue, noOverwrite) {
    var cell = sheet.getRange(row, col);
    var currValue = cell.getValue();
    if (currValue) {
        if (currValue == newValue || noOverwrite)
            return;
        // prompt user
    }
    return cell.setValue(newValue);
}

// vim: ft=javascript:
