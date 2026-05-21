/**
 * Ferme l’offcanvas sidebar sur mobile après clic sur un lien (navigation pleine page).
 */
(function () {
  var sidebar = document.getElementById("drpSidebar");
  if (!sidebar || !window.bootstrap || !bootstrap.Offcanvas) return;
  sidebar.querySelectorAll("a[href]").forEach(function (a) {
    a.addEventListener("click", function () {
      if (!window.matchMedia("(max-width: 991.98px)").matches) return;
      var oc = bootstrap.Offcanvas.getInstance(sidebar);
      if (oc) oc.hide();
    });
  });
})();
