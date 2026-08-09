mergeInto(LibraryManager.library, {
  TevGate6AReport: function (passed) {
    var value = passed ? "PASS" : "FAIL";
    var root = document.documentElement;
    root.setAttribute("data-tev-gate6a", value);

    var node = document.getElementById("tev-gate6a-result");
    if (!node) {
      node = document.createElement("pre");
      node.id = "tev-gate6a-result";
      document.body.appendChild(node);
    }

    node.textContent = "TEV_SCRIPT_UNITY_WEB_GATE_6A=" + value;
    document.title = "TEV_GATE6A_" + value;
  }
});
