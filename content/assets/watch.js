// The tables on /watch/ sort when a heading is clicked, or focused and Enter pressed. tablesort is
// the library Material for MkDocs documents for this (reference/data-tables, "Sortable tables"),
// vendored under assets/vendor/tablesort/ rather than loaded from a CDN, so the site's
// Content-Security-Policy needs no new origin. document$ is Material's page-load observable: it fires
// on an ordinary load, and again after each page swap if instant navigation is ever turned on.
document$.subscribe(function () {
  document.querySelectorAll(".lockrot-watch table").forEach(function (table) {
    new Tablesort(table);
  });
});
