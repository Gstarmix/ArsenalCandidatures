const btn = document.getElementById("capture");
const statusEl = document.getElementById("status");
function setStatus(msg, kind) {
  statusEl.textContent = msg;
  statusEl.className = kind || "info";
}
function extractOffre() {
  const clean = s => (s || "").replace(/\s+/g, " ").trim();
  let jobLd = null;
  for (const tag of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      let parsed = JSON.parse(tag.textContent);
      const arr = Array.isArray(parsed) ? parsed : [parsed];
      for (const node of arr) {
        const graph = node && node["@graph"] ? node["@graph"] : [node];
        for (const g of graph) {
          if (g && g["@type"] && String(g["@type"]).includes("JobPosting")) jobLd = g;
        }
      }
    } catch (e) {}
  }
  const applyLinks = [];
  for (const a of document.querySelectorAll("a[href]")) {
    const txt = clean(a.textContent).toLowerCase();
    const href = a.href || "";
    if (/postuler|candidater|apply|déposer ma candidature/.test(txt) || /apply|postuler|candidat/i.test(href)) {
      if (href && !applyLinks.includes(href)) applyLinks.push(href);
    }
  }
  const main = document.querySelector("main, article, [role=main]") || document.body;
  const fullText = clean(main.innerText).slice(0, 14000);
  let entreprise = "";
  if (jobLd && jobLd.hiringOrganization) {
    entreprise = clean(jobLd.hiringOrganization.name || jobLd.hiringOrganization);
  }
  let lieu = "";
  if (jobLd && jobLd.jobLocation) {
    const loc = Array.isArray(jobLd.jobLocation) ? jobLd.jobLocation[0] : jobLd.jobLocation;
    if (loc && loc.address) {
      lieu = clean([loc.address.addressLocality, loc.address.postalCode].filter(Boolean).join(" "));
    }
  }
  return {
    schema_version: "arsenal_candidatures/offre-1",
    capture_le: new Date().toISOString(),
    url: location.href,
    titre_page: clean(document.title),
    titre_offre: clean(jobLd && jobLd.title) || clean((document.querySelector("h1") || {}).textContent),
    entreprise: entreprise,
    lieu: lieu,
    type_contrat: clean(jobLd && jobLd.employmentType),
    date_publication: clean(jobLd && jobLd.datePosted),
    description_structuree: clean(jobLd && jobLd.description),
    liens_candidature: applyLinks.slice(0, 10),
    texte_page: fullText,
    a_du_jobposting: !!jobLd
  };
}
btn.addEventListener("click", async () => {
  btn.disabled = true;
  setStatus("Capture en cours…", "info");
  try {
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true
    });
    if (!tab || !tab.id || /^(chrome|edge|about):/.test(tab.url || "")) {
      throw new Error("Ouvre d'abord une page d'offre d'emploi dans l'onglet.");
    }
    const results = await chrome.scripting.executeScript({
      target: {
        tabId: tab.id
      },
      func: extractOffre
    });
    const offre = results && results[0] && results[0].result;
    if (!offre) throw new Error("Extraction impossible sur cette page.");
    const stamp = offre.capture_le.replace(/[:.]/g, "-").slice(0, 19);
    const json = JSON.stringify(offre, null, 2);
    const url = "data:application/json;charset=utf-8," + encodeURIComponent(json);
    await chrome.downloads.download({
      url: url,
      filename: `Arsenal_Candidatures_inbox/offre_${stamp}.json`,
      saveAs: false,
      conflictAction: "uniquify"
    });
    setStatus("Offre capturée ✔\n" + (offre.titre_offre || offre.titre_page).slice(0, 70) + "\n\nFichier dans : Téléchargements/Arsenal_Candidatures_inbox/", "ok");
  } catch (e) {
    setStatus("Erreur : " + e.message, "err");
  } finally {
    btn.disabled = false;
  }
});