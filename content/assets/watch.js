// The tables on /watch/ sort when a heading is clicked, or focused and Enter pressed. tablesort is
// the library Material for MkDocs documents for this (reference/data-tables, "Sortable tables"),
// vendored under assets/vendor/tablesort/ rather than loaded from a CDN, so the site's
// Content-Security-Policy needs no new origin. document$ is Material's page-load observable: it fires
// on an ordinary load, and again after each page swap if instant navigation is ever turned on.
document$.subscribe(function () {
  document.querySelectorAll(".lockrot-watch table").forEach(function (table) {
    var sort = new Tablesort(table);
    // The rows arrive sorted (scripts/build_watch_page.py prints them in Flagged order and marks that
    // heading aria-sort). Telling tablesort so lets a click on another heading clear that arrow;
    // data-sort-default would re-sort on load instead, and reverse every tie the page printed.
    var current = table.querySelector("thead th[aria-sort]");
    if (current) {
      sort.current = current;
    }
  });
});
